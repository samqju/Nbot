"""Observation-only G1d WSS-to-durable-final-candle integration.

Public Binance WSS market/public separation, bounded latest-quote state and
append-only 5-minute final events. No models, orders, execution imports,
paper portfolios or service autostart. Source-health guards are conservative.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, Mapping, Sequence

from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import HISTORY, public_get
from nbot.v5.stream_buffer import BoundedObservationBuffer
from nbot.v5.ws_contract import UnsafeStream, decode_frame, stream_urls


class ObservationContinuity:
    """In-memory WSS transport plus a separately persistent candle ledger.

    Socket lifecycle invalidates quote/trade/cohort readiness; reopening a
    SQLite database never falsely repairs them. Every source window remains
    timestamp-anchored to an actually completed Binance REST event.
    """

    def __init__(self, symbols: Sequence[str], path: str | Path, *,
                 quote_mode: str = "depth5@500ms"):
        stream_urls(symbols, quote_mode=quote_mode)
        self.symbols = tuple(sorted(set(symbols) | {"BTCUSDT"}))
        self.store = BoundedObservationBuffer(symbols, quote_mode=quote_mode)
        self.ledger = CandleEvidenceLedger(path)
        self.stats = Counter()
        self.final_opens: dict[str, list[int]] = {s: [] for s in self.symbols}

    def close(self) -> None:
        self.ledger.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def connect(self, route: str) -> None:
        self.store.connect(route)

    def disconnect(self, route: str) -> None:
        self.store.disconnect(route)

    def restore_rest(self, symbol: str, payload: Sequence[list], *,
                     event_open_ms: int, observed_ms: int) -> tuple[str, int]:
        if symbol not in self.symbols:
            raise EvidenceHold("V5_G1D_SYMBOL_NOT_IN_COHORT")
        # SQLite first. Never validate memory as sound if disk-source proof fails.
        label, inserted = self.ledger.synchronize_asof_rest(
            symbol, payload, event_open_ms=event_open_ms,
            observed_ms=observed_ms,
        )
        # Existing in-memory gap flags require a new source generation. The
        # persisted ledger is the authority; discard only in-memory transport
        # continuity, NEVER delete evidence/trade-gap flags on disk.
        coin = self.store.coins[symbol]
        if coin.candle_gap or coin.candle_conflict:
            self.store.health.cohort_valid = False
            self.store.coins[symbol].closed_candles.clear()
            self.store.coins[symbol].candle_gap = False
            self.store.coins[symbol].candle_conflict = False
        self.store.seed_closed_candles(
            symbol, payload, event_open_ms=event_open_ms,
        )
        self.stats["rest_" + label.lower()] += 1
        return label, inserted

    def retrieve_rest(self, symbol: str, *, event_open_ms: int,
                      observed_ms: int, getter: Callable = public_get):
        """REST is for audited CLOSED candles only; never fake quotes/trades."""
        if symbol not in self.symbols:
            raise EvidenceHold("V5_G1D_SYMBOL_NOT_IN_COHORT")
        if observed_ms < event_open_ms + INTERVAL_MS:
            raise EvidenceHold("V5_G1D_REST_EVENT_NOT_CLOSED")
        payload = getter("/fapi/v1/klines", {
            "symbol": symbol, "interval": "5m",
            "startTime": str(event_open_ms - (HISTORY - 1) * INTERVAL_MS),
            "endTime": str(event_open_ms + INTERVAL_MS - 1),
            "limit": str(HISTORY),
        })
        return self.restore_rest(
            symbol, payload, event_open_ms=event_open_ms,
            observed_ms=observed_ms,
        )

    def consume(self, route: str, payload: str | bytes, *,
                received_ms: int) -> str:
        parsed = decode_frame(
            route, payload, received_ms=received_ms,
            subscribed_symbols=self.symbols,
        )
        symbol, kind = parsed["symbol"], parsed["kind"]
        if kind == "kline_5m" and parsed["closed"]:
            if not self.store.health.market_connected:
                raise EvidenceHold("V5_G1D_MARKET_DISCONNECTED")
            # Persist first: a WSS gap/conflict is never swallowed by the
            # in-memory ring. Database refuses out-of-order and mismatches.
            outcome = self.ledger.append_wss_final(parsed)
            if outcome == "APPENDED_WSS_FINAL":
                self.final_opens[symbol].append(parsed["candle"][0])
                self.stats["wss_final_appended"] += 1
            elif outcome == "UNCHANGED_REPLAY":
                self.stats["wss_final_replayed"] += 1
            else:
                self.stats["wss_final_held"] += 1
            # Buffer cursor is downstream of immutable source; a WSS gap may
            # require a new generation seeded only from audited REST.
            buffer_outcome = self.store.consume(
                route, payload, received_ms=received_ms,
            )
            if buffer_outcome == "CANDLE_GAP_HOLD":
                self.stats["buffer_gap_held"] += 1
            return outcome
        classification = self.store.consume(
            route, payload, received_ms=received_ms,
        )
        if kind == "aggTrade":
            self.stats["trade_updates"] += 1
        elif kind in ("bookTicker", "depth5@500ms"):
            self.stats["sampled_quote_updates"] += 1
        return classification

    def gate(self, symbol: str, *, event_open_ms: int,
             now_ms: int) -> tuple[bool, tuple[str, ...]]:
        """BTC and per-coin independent source health; never trade/research.

        An observation may be complete and still not be usable for training.
        The unrecoverable/reconnect-unverified cohort always remains HOLD.
        """
        if symbol not in self.symbols:
            raise EvidenceHold("V5_G1D_UNKNOWN_SYMBOL")
        reasons = []
        for current in sorted({symbol, "BTCUSDT"}):
            source_ready, source_reasons = self.store.health.gate(
                symbol=current, now_ms=now_ms,
            )
            if not source_ready:
                reasons.extend(current + "_" + x for x in source_reasons)
            ledger = self.ledger.inspect(current)
            if ledger["last_event_open_ms"] != event_open_ms:
                reasons.append(current + "_CANDLE_EVENT_MISSING")
            reasons.extend(current + "_" + x
                           for x in ledger["open_candle_gates"])
            memory_ok, memory_reasons = self.store.candle_readiness(
                symbol=current, event_open_ms=event_open_ms,
                now_ms=now_ms,
            )
            if not memory_ok:
                reasons.extend(current + "_" + x for x in memory_reasons)
        # Formal G1/F0 certification remains a later owner-approved gate.
        reasons.append("RESEARCH_COHORT_NOT_CERTIFIED")
        return False, tuple(sorted(set(reasons)))

    def snapshot(self, *, event_open_ms: int, now_ms: int) -> dict:
        state = {}
        for symbol in self.symbols:
            ok, reasons = self.gate(
                symbol, event_open_ms=event_open_ms, now_ms=now_ms,
            )
            state[symbol] = {
                "research_ready": ok,
                "health_holds": reasons,
                "persisted": self.ledger.inspect(symbol)["closed_bar_count"],
                "wss_final_events": list(self.final_opens[symbol]),
            }
        return {
            "result": "OBSERVATION_ONLY",
            "symbols": state,
            "totals": dict(self.stats),
            "ring": self.store.describe(),
            "research_ready": False,
            "training_labels_created": 0,
            "order_authority": "NONE",
            "paper_trades": 0,
        }
