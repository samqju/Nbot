"""Explicit public-only WSS transport for the V5 research evidence bridge.

No service registration, collector imports, private routes, credentials or
execution methods. The default application does not import/start this module.
"""
from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from ..common.binance_limits import RequestBudget

from .v5_live_evidence import LiveEvidenceBridge, MAX_BUFFER, symbol_name

REST_BASE = "https://fapi.binance.com"
WSS_BASE = "wss://fstream.binance.com"
PUBLIC_PATHS = {"/fapi/v1/aggTrades", "/fapi/v1/depth", "/fapi/v1/fundingRate"}
ORDER_AUTHORITY = "NONE"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError("V5_PUBLIC_REDIRECT_FORBIDDEN")


class PublicRest:
    """Allowlisted GET only, bounded bytes/time; errors never imply coverage."""
    def __init__(self, *, budget=None, funding_budget=None):
        # Callers can inject one reserved budget across V5 shards. No V4 budget
        # database is opened by default. Cross-host/IP coordination is a gate.
        self.budget = budget if budget is not None else RequestBudget(ceiling=600)
        self.funding_budget = funding_budget if funding_budget is not None else RequestBudget(ceiling=80)

    def __call__(self, path, params):
        if path not in PUBLIC_PATHS:
            raise ValueError("V5_PUBLIC_ENDPOINT_FORBIDDEN")
        allowed = {
            "/fapi/v1/aggTrades": {"symbol", "fromId", "limit"},
            "/fapi/v1/depth": {"symbol", "limit"},
            "/fapi/v1/fundingRate": {"symbol", "startTime", "endTime", "limit"},
        }[path]
        if set(params) - allowed or "symbol" not in params:
            raise ValueError("V5_PUBLIC_PARAMETERS_FORBIDDEN")
        symbol_name(params["symbol"])
        self.budget.acquire(20)  # conservative maximum of these public requests
        if path == '/fapi/v1/fundingRate':
            self.funding_budget.acquire(1)
        request = Request(REST_BASE + path + "?" + urlencode(params), method="GET",
                          headers={"User-Agent": "NBOT-V5-Research-Evidence"})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=10) as response:
                self.budget.observe(response.headers, response.status)
                raw = response.read(2 * 1024 * 1024 + 1)
        except HTTPError as exc:
            self.budget.observe(exc.headers, exc.code)
            raise
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("V5_PUBLIC_RESPONSE_OVERFLOW")
        return json.loads(raw)


def stream_urls(symbols):
    symbols = tuple(symbol_name(s).lower() for s in symbols)
    if not 0 < len(symbols) <= 20:
        raise ValueError("V5_WSS_SHARD_LIMIT")
    return (
        WSS_BASE + "/market/stream?streams=" + "/".join(s + "@aggTrade" for s in symbols),
        WSS_BASE + "/public/stream?streams=" + "/".join(
            stream for s in symbols for stream in (s + "@bookTicker", s + "@depth@100ms")),
    )


MAX_QUEUE_BYTES = 2 * 1024 * 1024
MAX_MESSAGE_BYTES = 64 * 1024
MAX_QUEUE_ITEMS = 256
SYNC_TIMEOUT = 15.0
MAX_PROCESSING_DELAY_MS = 2000
ROTATION_SECONDS = 23 * 60 * 60


async def run_session(bridge, *, rest=None, connect=None, clock=None):
    """Owned tasks, bounded raw bytes, off-loop durable writes, explicit faults."""
    if not isinstance(bridge, LiveEvidenceBridge) or not bridge.ready or bridge.integrity_fault:
        raise ValueError("V5_INITIALIZED_BRIDGE_REQUIRED")
    if connect is None:
        from websockets.asyncio.client import connect
    rest = rest or PublicRest()
    clock = clock or (lambda: time.time_ns() // 1_000_000)
    queue = asyncio.Queue(maxsize=min(MAX_BUFFER, MAX_QUEUE_ITEMS))
    queue_bytes = 0
    opened = 0
    ready = asyncio.Event()
    snapshots = set()
    tasks = set()
    failure = asyncio.get_running_loop().create_future()
    started = time.monotonic()
    unsynced_since = {s: started for s in bridge.symbols}

    def own(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)
        def completed(t):
            # Every exception is retrieved, even tasks created during a wait.
            if not t.cancelled():
                error = t.exception()
                if error is None:
                    error = RuntimeError("V5_REQUIRED_TASK_ENDED")
                if not failure.done():
                    failure.set_result(error)
            tasks.discard(t)
        task.add_done_callback(completed)
        return task

    def enqueue(typ, payload, receipt):
        nonlocal queue_bytes
        raw = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        size = len(raw.encode() if isinstance(raw, str) else raw)
        limit = MAX_QUEUE_BYTES if typ == 'snapshot' else MAX_MESSAGE_BYTES
        if size > limit or queue_bytes + size > MAX_QUEUE_BYTES:
            raise RuntimeError("V5_WSS_BYTE_BUFFER_OVERFLOW")
        try:
            queue.put_nowait((typ, raw, receipt, size, time.monotonic()))
        except asyncio.QueueFull as exc:
            raise RuntimeError("V5_WSS_BUFFER_OVERFLOW") from exc
        queue_bytes += size

    async def mutate(fn, *args, **kwargs):
        # Cancellation must not race a still-running SQLite mutation/cleanup.
        work = asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            try:
                await work
            except BaseException:
                pass  # outer cancellation/failure remains the primary error
            raise

    async def reader(url, channel):
        nonlocal opened
        async with connect(url, max_queue=8, max_size=MAX_MESSAGE_BYTES,
                           ping_interval=30, ping_timeout=30, open_timeout=10,
                           close_timeout=2) as ws:
            opened += 1
            if opened == 2:
                ready.set()
            async for message in ws:
                enqueue(channel, message, clock())
                await asyncio.sleep(0)
        raise RuntimeError("V5_WSS_CLOSED")

    async def snapshot(symbol):
        data = await asyncio.wait_for(asyncio.to_thread(
            rest, "/fapi/v1/depth", {"symbol": symbol, "limit": 1000}), SYNC_TIMEOUT)
        enqueue("snapshot", {"symbol": symbol, "data": data}, clock())
        # Successful finite tasks must not be treated as required-feed closure.
        await asyncio.Event().wait()

    async def watchdog():
        await asyncio.wait_for(ready.wait(), SYNC_TIMEOUT)
        while True:
            await asyncio.sleep(.1)
            now = time.monotonic()
            if now - started >= ROTATION_SECONDS:
                raise RuntimeError("V5_FORCED_ROTATION")
            for symbol in bridge.symbols:
                if bridge.feeds[symbol]["synced"]:
                    unsynced_since[symbol] = None
                else:
                    if unsynced_since[symbol] is None:
                        unsynced_since[symbol] = now
                    if now - unsynced_since[symbol] >= SYNC_TIMEOUT:
                        raise TimeoutError("V5_BOOK_SYNC_DEADLINE")
            # Independent of FIFO traffic; bridge lock serializes with writes.
            await mutate(bridge.check_source_coverage, clock())

    async def consume():
        nonlocal queue_bytes
        await asyncio.wait_for(ready.wait(), SYNC_TIMEOUT)
        for symbol in bridge.symbols:
            await mutate(bridge.connected, symbol)
        while True:
            typ, raw, receipt, size, queued = await asyncio.wait_for(queue.get(), timeout=30)
            queue_bytes -= size
            if (time.monotonic() - queued) * 1000 > MAX_PROCESSING_DELAY_MS:
                raise RuntimeError("V5_CONSUMER_BACKLOG_STALE")
            message = json.loads(raw)
            if typ == "snapshot":
                symbol = message["symbol"]
                await mutate(bridge.snapshot, symbol, message["data"], receipt)
                snapshots.remove(symbol)
                # Stop the completed snapshot owner without hiding any error.
                snapshot_tasks.pop(symbol).cancel()
                continue
            row = message.get("data", message)
            if not isinstance(row, dict):
                raise ValueError("V5_WSS_EVENT_INVALID")
            kind = row.get("e")
            if ((typ == "market") != (kind == "aggTrade") or
                    typ == "public" and kind not in ("bookTicker", "depthUpdate")):
                raise ValueError("V5_WSS_SOURCE_ROUTING_INVALID")
            symbol = row.get("s")
            if symbol not in bridge.symbols:
                raise ValueError("V5_WSS_SHARD_SYMBOL_MISMATCH")
            if kind == "aggTrade":
                old = bridge.feeds[symbol]["agg"]
                if old is not None and row["a"] > old + 1:
                    await mutate(bridge.disconnect, symbol, "WSS_GAP")
                    recovered = await mutate(bridge.recover_trades, symbol, row["a"] - 1, rest)
                    if not recovered:
                        raise RuntimeError("V5_TRADE_RECOVERY_UNAVAILABLE")
                    await mutate(bridge.connected, symbol)
            await mutate(bridge.ingest, message, receipt)
            if kind == "depthUpdate" and bridge.feeds[symbol]["depth_id"] is None and symbol not in snapshots:
                snapshots.add(symbol)
                snapshot_tasks[symbol] = own(snapshot(symbol))

    snapshot_tasks = {}
    market_url, public_url = stream_urls(bridge.symbols)
    own(reader(market_url, "market"))
    own(reader(public_url, "public"))
    own(watchdog())
    own(consume())
    primary = None
    try:
        error = await failure
        raise error
    except BaseException as exc:
        primary = exc
        raise
    finally:
        owned = tuple(tasks)
        for task in owned:
            task.cancel()
        await asyncio.gather(*owned, return_exceptions=True)
        for symbol in bridge.symbols:
            try:
                await mutate(bridge.disconnect, symbol)
            except BaseException:
                # The integrity latch remains set if cleanup cannot commit.
                if primary is None:
                    raise


async def run_research_capture(bridge, *, enabled=False):
    """Explicit opt-in, bounded shard, capped exponential reconnect delay."""
    if enabled is not True:
        raise RuntimeError("V5_RESEARCH_CAPTURE_OPT_IN_REQUIRED")
    from websockets.exceptions import WebSocketException
    delay = 1
    rest = PublicRest()  # retain request budgets and cooldowns across reconnects
    while True:
        try:
            await run_session(bridge, rest=rest)
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError, RuntimeError, TimeoutError, WebSocketException) as exc:
            if bridge.integrity_fault is not None:
                raise RuntimeError("V5_CAPTURE_REQUIRES_EXPLICIT_INTEGRITY_RECOVERY") from exc
            # Visible diagnostic, no success/coverage claims on failure.
            print(f"V5 research evidence interrupted: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
