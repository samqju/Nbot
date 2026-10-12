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
        request = Request(REST_BASE + path + "?" + urlencode(params), method="GET",
                          headers={"User-Agent": "NBOT-V5-Research-Evidence"})
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
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


async def run_session(bridge, *, rest=None, connect=None, clock=None):
    """One session; any disconnect/overflow/silence invalidates the whole shard.

    Snapshot fetching runs concurrently with capture; depth events buffer until
    the snapshot bridges U/u. Every bridge mutation runs on the consumer thread.
    The caller retries with backoff, preserving committed state.
    """
    if not isinstance(bridge, LiveEvidenceBridge) or not bridge.ready:
        raise ValueError("V5_INITIALIZED_BRIDGE_REQUIRED")
    if connect is None:
        from websockets.asyncio.client import connect
    rest = rest or PublicRest()
    clock = clock or (lambda: time.time_ns() // 1_000_000)
    queue = asyncio.Queue(maxsize=MAX_BUFFER)
    opened = 0
    ready = asyncio.Event()
    snapshots = set()
    tasks = []

    def enqueue(item):
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull as exc:
            raise RuntimeError("V5_WSS_BUFFER_OVERFLOW") from exc

    async def reader(url, channel):
        nonlocal opened
        async with connect(url, max_queue=64, max_size=256 * 1024,
                           ping_interval=30, ping_timeout=30, open_timeout=10) as ws:
            opened += 1
            if opened == 2:
                ready.set()
            async for message in ws:
                # Overflow is an explicit integrity fault; never silently drop.
                # Retain the source socket identity; shared-queue activity
                # must not conceal loss of a required individual stream.
                enqueue(("wss", (channel, json.loads(message)), clock()))
        raise RuntimeError("V5_WSS_CLOSED")

    async def snapshot(s):
        payload = await asyncio.to_thread(rest, "/fapi/v1/depth", {"symbol": s, "limit": 1000})
        enqueue(("snapshot", (s, payload), clock()))

    async def watchdog():
        await ready.wait()
        while True:
            # A dedicated wall-clock check continues despite heavy traffic
            # in the shared consumer queue. No SQLite write on healthy checks.
            await asyncio.sleep(0.5)
            enqueue(("watchdog", None, clock()))

    async def consume():
        await ready.wait()
        for s in bridge.symbols:
            bridge.connected(s)
        while True:
            typ, payload, receipt = await asyncio.wait_for(queue.get(), timeout=30)
            if typ == "watchdog":
                bridge.check_source_coverage(receipt)
                continue
            if typ == "snapshot":
                s, data = payload
                bridge.snapshot(s, data, receipt)
                snapshots.remove(s)
                continue
            channel, message = payload
            row = message.get("data", message)
            if not isinstance(row, dict):
                raise ValueError("V5_WSS_EVENT_INVALID")
            kind = row.get("e")
            if channel not in ("market", "public") or (
                    (channel == "market") != (kind == "aggTrade")) or (
                    channel == "public" and kind not in ("bookTicker", "depthUpdate")):
                raise ValueError("V5_WSS_SOURCE_ROUTING_INVALID")
            s = row.get("s")
            if s not in bridge.symbols:
                raise ValueError("V5_WSS_SHARD_SYMBOL_MISMATCH")
            if row.get("e") == "aggTrade":
                old = bridge.feeds[s]["agg"]
                if old is not None and row["a"] > old + 1:
                    bridge.disconnect(s, "WSS_GAP")
                    recovered = await asyncio.to_thread(
                        bridge.recover_trades, s, row["a"] - 1, rest)
                    if not recovered:
                        raise RuntimeError("V5_TRADE_RECOVERY_UNAVAILABLE")
                    bridge.connected(s)
            bridge.ingest(message, receipt)
            if (row.get("e") == "depthUpdate" and
                    bridge.feeds[s]["depth_id"] is None and s not in snapshots):
                snapshots.add(s)
                tasks.append(asyncio.create_task(snapshot(s)))

    market_url, public_url = stream_urls(bridge.symbols)
    tasks.extend((asyncio.create_task(reader(market_url, "market")),
                  asyncio.create_task(reader(public_url, "public")),
                  asyncio.create_task(watchdog())))
    tasks.append(asyncio.create_task(consume()))
    try:
        # Include snapshot exceptions as they are created without swallowing them.
        while True:
            done, _ = await asyncio.wait(tasks, timeout=0.1, return_when=asyncio.FIRST_EXCEPTION)
            for task in done:
                if task.cancelled() or task.exception() is not None:
                    await task
            tasks[:] = [t for t in tasks if not t.done()]
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for s in bridge.symbols:
            bridge.disconnect(s)


async def run_research_capture(bridge, *, enabled=False):
    """Explicit opt-in, bounded shard, capped exponential reconnect delay."""
    if enabled is not True:
        raise RuntimeError("V5_RESEARCH_CAPTURE_OPT_IN_REQUIRED")
    from websockets.exceptions import WebSocketException
    delay = 1
    while True:
        try:
            await run_session(bridge)
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError, RuntimeError, TimeoutError, WebSocketException) as exc:
            # Visible diagnostic, no success/coverage claims on failure.
            print(f"V5 research evidence interrupted: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
