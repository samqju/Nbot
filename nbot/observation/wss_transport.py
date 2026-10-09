"""Async Binance combined-stream transport with reconnect and bounded backpressure.

The default connector imports the optional `websockets` package lazily. Tests can
inject a connector without adding network dependencies to the existing V2 path.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .wss_market import WssMarketState, reconnect_delay_seconds

AUTHORITY = "RESEARCH_MARKET_DATA_ONLY_NO_EXECUTION"


class TransportError(RuntimeError):
    pass


def decode_combined_message(raw: str | bytes) -> dict[str, Any]:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        body = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise TransportError("WSS_MESSAGE_JSON_INVALID") from exc
    if not isinstance(body, dict):
        raise TransportError("WSS_MESSAGE_INVALID")
    data = body.get("data", body)
    if not isinstance(data, dict):
        raise TransportError("WSS_MESSAGE_DATA_INVALID")
    return data


async def default_connect(url: str):
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise TransportError("WSS_DEPENDENCY_MISSING:websockets") from exc
    return connect(url, ping_interval=20, ping_timeout=20, close_timeout=5, max_queue=1024)


class CombinedStreamRunner:
    def __init__(self, *, url: str, state: WssMarketState, symbols: tuple[str, ...],
                 connect_factory: Callable[[str], Awaitable[Any]] | None = None,
                 queue_size: int = 4096, rotate_seconds: int = 23 * 60 * 60) -> None:
        if queue_size <= 0 or not 60 <= rotate_seconds < 24 * 60 * 60:
            raise ValueError("WSS_RUNNER_CONFIG_INVALID")
        self.url = url
        self.state = state
        self.symbols = symbols
        self.connect_factory = connect_factory or default_connect
        self.queue: asyncio.Queue[tuple[int, dict[str, Any]]] = asyncio.Queue(maxsize=queue_size)
        self.rotate_seconds = rotate_seconds
        self.dropped = 0
        self._stop = False

    async def stop(self) -> None:
        self._stop = True

    async def _consume(self) -> None:
        while not self._stop:
            receipt, payload = await self.queue.get()
            try:
                event = payload.get("e")
                if event == "bookTicker":
                    self.state.ingest_book_ticker(payload, receipt_time_ms=receipt)
                elif event == "aggTrade":
                    self.state.ingest_agg_trade(payload, receipt_time_ms=receipt)
            finally:
                self.queue.task_done()

    async def run(self) -> None:
        consumer = asyncio.create_task(self._consume())
        attempt = 0
        try:
            while not self._stop:
                self.state.mark_disconnected(self.symbols)
                try:
                    cm = await self.connect_factory(self.url)
                    async with cm as ws:
                        self.state.mark_connected(self.symbols)
                        attempt = 0
                        started = time.monotonic()
                        while not self._stop and time.monotonic() - started < self.rotate_seconds:
                            raw = await ws.recv()
                            payload = decode_combined_message(raw)
                            item = (int(time.time() * 1000), payload)
                            try:
                                self.queue.put_nowait(item)
                            except asyncio.QueueFull:
                                self.dropped += 1
                                self.state.mark_disconnected(self.symbols)
                                raise TransportError("WSS_BACKPRESSURE_OVERFLOW")
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.state.mark_disconnected(self.symbols)
                    await asyncio.sleep(reconnect_delay_seconds(attempt, jitter=0))
                    attempt = min(attempt + 1, 16)
        finally:
            consumer.cancel()
            try:
                await consumer
            except asyncio.CancelledError:
                pass
            self.state.mark_disconnected(self.symbols)
