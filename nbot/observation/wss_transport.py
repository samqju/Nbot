"""Async Binance combined-stream transport with reconnect and bounded backpressure."""
from __future__ import annotations

import asyncio
import json
import logging
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
                 queue_size: int = 4096, rotate_seconds: int = 23 * 60 * 60,
                 event_sink: Callable[[str, Any], None] | None = None) -> None:
        if queue_size <= 0 or not 60 <= rotate_seconds < 24 * 60 * 60:
            raise ValueError("WSS_RUNNER_CONFIG_INVALID")
        self.url = url
        self.state = state
        self.symbols = symbols
        self.connect_factory = connect_factory or default_connect
        self.queue: asyncio.Queue[tuple[int, dict[str, Any]]] = asyncio.Queue(maxsize=queue_size)
        self.rotate_seconds = rotate_seconds
        self.event_sink = event_sink
        self.dropped = 0
        self._stop = False
        self._ws = None

    async def stop(self) -> None:
        self._stop = True
        ws = self._ws
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _consume(self) -> None:
        while not self._stop:
            receipt, payload = await self.queue.get()
            try:
                event = payload.get("e")
                if event == "bookTicker":
                    parsed = self.state.ingest_book_ticker(payload, receipt_time_ms=receipt)
                    if self.event_sink is not None:
                        self.event_sink("bookTicker", parsed)
                elif event == "aggTrade":
                    parsed = self.state.ingest_agg_trade(payload, receipt_time_ms=receipt)
                    if self.event_sink is not None:
                        self.event_sink("aggTrade", parsed)
            except Exception:
                logging.getLogger(__name__).exception("WSS_CONSUMER_PAYLOAD_FAILED")
                self.state.mark_disconnected(self.symbols)
                if self.event_sink is not None:
                    self.event_sink("disconnected", self.symbols)
                if self._ws is not None:
                    await self._ws.close()
            finally:
                self.queue.task_done()

    async def run(self) -> None:
        consumer = asyncio.create_task(self._consume())
        attempt = 0
        try:
            while not self._stop:
                self.state.mark_disconnected(self.symbols)
                if self.event_sink is not None:
                    self.event_sink("disconnected", self.symbols)
                try:
                    cm = await self.connect_factory(self.url)
                    async with cm as ws:
                        self._ws = ws
                        self.state.mark_connected(self.symbols)
                        attempt = 0
                        started = time.monotonic()
                        while not self._stop and time.monotonic() - started < self.rotate_seconds:
                            remaining = self.rotate_seconds - (time.monotonic() - started)
                            raw = await asyncio.wait_for(ws.recv(), timeout=max(.1, remaining))
                            payload = decode_combined_message(raw)
                            item = (int(time.time() * 1000), payload)
                            try:
                                self.queue.put_nowait(item)
                            except asyncio.QueueFull:
                                self.dropped += 1
                                self.state.mark_disconnected(self.symbols)
                                raise TransportError("WSS_BACKPRESSURE_OVERFLOW")
                        self._ws = None
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._ws = None
                    self.state.mark_disconnected(self.symbols)
                    if self.event_sink is not None:
                        self.event_sink("disconnected", self.symbols)
                    if not self._stop:
                        await asyncio.sleep(reconnect_delay_seconds(attempt, jitter=0))
                        attempt = min(attempt + 1, 16)
        finally:
            consumer.cancel()
            try:
                await consumer
            except asyncio.CancelledError:
                pass
            self._ws = None
            self.state.mark_disconnected(self.symbols)
            if self.event_sink is not None:
                self.event_sink("disconnected", self.symbols)
