#!/usr/bin/env python3
"""Passive Binance aggTrade replay service for NBOT decision counterfactuals.

No credentials, no order authority, no recommendation authority. The service
subscribes only symbols with OPEN hypotheses. REST is used only to backfill the
small chronology window between decision creation/reconnect and live WSS.
"""
from __future__ import annotations

import os
import signal
import threading
import time
from pathlib import Path

from nbot.config.profiles import get_profile
from nbot.exchange.binance_stream import (
    AggTrade, BinanceLiveStreamConfig, BinanceLiveWebSocketMarketData,
)
from nbot.exchange.binance_public import BinanceLivePublicMarketConfig, BinanceLivePublicMarketData
from nbot.observation.binance_public import BinanceUsdMPublicClient
from nbot.observation.config import observation_config_for_profile
from nbot.observation.decision_ledger import DecisionOutcomeLedger


def _positive_float(key: str, default: float) -> float:
    value = float(os.environ.get(key, default))
    if value <= 0:
        raise ValueError(f"{key}_INVALID")
    return value


def _positive_int(key: str, default: int) -> int:
    value = int(os.environ.get(key, default))
    if value <= 0:
        raise ValueError(f"{key}_INVALID")
    return value


def main() -> int:
    root = Path(__file__).resolve().parent
    ledger = DecisionOutcomeLedger(root / "data/observation/live/decision_outcomes.db")
    profile = get_profile("live-paper")
    rest = BinanceLivePublicMarketData(BinanceLivePublicMarketConfig(
        request_timeout_seconds=_positive_float("LIVE_PUBLIC_REST_TIMEOUT_SECONDS", 3.0),
        max_clock_skew_ms=_positive_int("LIVE_PUBLIC_MAX_CLOCK_SKEW_MS", 5_000),
    ))
    stream = BinanceLiveWebSocketMarketData(
        BinanceLiveStreamConfig(
            first_event_timeout_seconds=_positive_float(
                "LIVE_PUBLIC_WS_FIRST_EVENT_TIMEOUT_SECONDS", 4.0
            ),
            max_quote_age_ms=_positive_int("LIVE_PUBLIC_WS_MAX_QUOTE_AGE_MS", 2_000),
            max_symbols=_positive_int("LIVE_PUBLIC_WS_MAX_SYMBOLS", 200),
            enable_book_ticker=False,
            enable_agg_trade=True,
        ),
        rest_recovery=rest,
    )
    history = BinanceUsdMPublicClient(observation_config_for_profile(profile))
    stop = threading.Event()
    lock = threading.RLock()
    ready: set[str] = set()
    buffering: set[str] = set()
    buffers: dict[str, list[AggTrade]] = {}
    generation = 0
    next_funding_sync = 0.0

    def on_trade(trade: AggTrade) -> None:
        with lock:
            if trade.symbol in buffering:
                buf = buffers.setdefault(trade.symbol, [])
                if len(buf) >= 20_000:
                    # Losing chronology is preferable to pretending the path is complete.
                    ledger.mark_stream_gap(at_ms=trade.trade_time_ms)
                    del buf[:10_000]
                buf.append(trade)
                return
        ledger.on_agg_trade(trade, source="WSS")

    def on_status(state: str, at_ms: int) -> None:
        nonlocal generation
        if state == "DISCONNECTED":
            ledger.mark_stream_gap(at_ms=at_ms)
            with lock:
                ready.clear()
        elif state == "CONNECTED":
            generation += 1

    def catch_up(symbol: str) -> None:
        start = ledger.catchup_start_ms(symbol)
        if start is None:
            return
        with lock:
            buffering.add(symbol)
            buffers.setdefault(symbol, [])
        stream.subscribe(symbol)
        cutoff = int(time.time() * 1000)
        # Endpoint requires <1 hour per start/end range and returns max 1000.
        # The client paginates within each slice and the 4h hypothesis horizon
        # is comfortably inside Binance's documented 48h REST retention.
        for trade in history.aggregate_trades(symbol, start, cutoff):
            ledger.on_agg_trade(trade, source="REST_BACKFILL")
        with lock:
            queued = sorted(
                buffers.pop(symbol, []),
                key=lambda t: (t.trade_time_ms, t.aggregate_trade_id),
            )
            buffering.discard(symbol)
            ready.add(symbol)
        for trade in queued:
            ledger.on_agg_trade(trade, source="WSS")
        ledger.resolve_stream_gap(symbol)

    stream.add_trade_listener(on_trade)
    stream.add_status_listener(on_status)

    def request_stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    stream.connect()
    try:
        while not stop.wait(1.0):
            ledger.expire()
            now_mono = time.monotonic()
            if now_mono >= next_funding_sync:
                # Query a complete 5h window: every 4h hypothesis plus margin
                # for scheduler jitter. Funding completion is required before a
                # counterfactual can become an ML training target.
                now_ms = int(time.time() * 1000)
                ledger.finalize_funding(history.funding_history(now_ms - 5*60*60*1000, now_ms))
                next_funding_sync = now_mono + 60.0
            pending = set(ledger.pending_symbols())
            with lock:
                needs = sorted(pending.difference(ready).difference(buffering))
            for symbol in needs:
                if stop.is_set():
                    break
                try:
                    catch_up(symbol)
                except Exception:
                    # Preserve the unresolved-gap marker. A later loop retries.
                    with lock:
                        buffering.discard(symbol)
                        buffers.pop(symbol, None)
                        ready.discard(symbol)
                    time.sleep(1.0)
        return 0
    finally:
        stream.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
