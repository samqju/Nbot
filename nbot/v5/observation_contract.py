"""V5 clean-restart, synthetic-first market observation records.

This module only validates and stores complete two-sided candidate *observations*.
It never requests market data, sends a recommendation, runs a model, or places
paper/live orders. Pattern classifications are inputs; detectors come later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import sqlite3
from typing import Mapping, Sequence

SCHEMA_VERSION = "NBOT_V5_CANDIDATE_OBSERVATION_V1"
INTERVAL_MS = 300_000
MAX_SYMBOLS = 50
SIDES = ("LONG", "SHORT")
PATTERN_IDS = (
    "TREND_CONTINUATION_V1",
    "TREND_PULLBACK_V1",
    "STRETCHED_REVERSAL_V1",
    "VOLATILITY_EXPANSION_V1",
    "RELATIVE_STRENGTH_V1",
    "DONCHIAN_BREAKOUT_V1",
    "BREAKOUT_RETEST_V1",
    "FAILED_BREAKOUT_V1",
    "RANGE_EDGE_REJECTION_V1",
    "BOLLINGER_REENTRY_V1",
    "RSI_RECLAIM_V1",
    "EMA_CROSS_V1",
    "EMA_PULLBACK_V1",
    "MACD_CROSS_V1",
    "SQUEEZE_BREAKOUT_V1",
    "VOLUME_BREAKOUT_V1",
    "VWAP_RECLAIM_V1",
    "INSIDE_BAR_BREAKOUT_V1",
    "OUTSIDE_BAR_REVERSAL_V1",
    "ENGULFING_REVERSAL_V1",
    "PIN_BAR_REJECTION_V1",
    "MULTITIMEFRAME_TREND_V1",
    "CONFIRMED_SWING_CONTINUATION_V1",
    "BTC_RELATIVE_MOMENTUM_V1",
)
PATTERN_STATES = frozenset({"MATCH", "NO_MATCH", "UNAVAILABLE"})
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}")


@dataclass(frozen=True)
class Evidence:
    """Only a completed current candle and past-only sources can be valid."""

    last_closed_bar_open_ms: int
    source_max_bar_open_ms: int
    observed_at_ms: int
    patterns_by_side: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _evidence_reasons(
    evidence: Evidence | None, event_open_ms: int, decision_at_ms: int, prefix: str
) -> list[str]:
    if evidence is None:
        return [f"{prefix}_MISSING"]
    if any(type(v) is not int or v < 0 for v in (
        evidence.last_closed_bar_open_ms,
        evidence.source_max_bar_open_ms,
        evidence.observed_at_ms,
    )):
        return [f"{prefix}_INVALID_TIMESTAMPS"]
    reasons = []
    if evidence.last_closed_bar_open_ms != event_open_ms:
        reasons.append(f"{prefix}_CANDLE_MISSING_OR_STALE")
    if evidence.source_max_bar_open_ms != event_open_ms:
        reasons.append(f"{prefix}_SOURCE_NOT_ASOF_EVENT")
    if not (event_open_ms + INTERVAL_MS <= evidence.observed_at_ms <= decision_at_ms):
        reasons.append(f"{prefix}_OBSERVATION_TIME_INVALID")
    return reasons


def build_candidate_records(
    *,
    event_open_ms: int,
    decision_at_ms: int,
    eligible_symbols: Sequence[str],
    btc_context: Evidence | None,
    observations: Mapping[str, Evidence],
) -> tuple[dict, ...]:
    """One immutable-intent record for every eligible symbol and both directions.

    Missing sources remain visible as UNSCORABLE records. No research outcomes
    or trades are created and no patterns are invented.
    """
    if (
        type(event_open_ms) is not int
        or event_open_ms < 0
        or event_open_ms % INTERVAL_MS
        or type(decision_at_ms) is not int
        or decision_at_ms < event_open_ms + INTERVAL_MS
    ):
        raise ValueError("V5_EVENT_NOT_CLOSED_OR_INVALID")
    if not 1 <= len(eligible_symbols) <= MAX_SYMBOLS:
        raise ValueError("V5_UNIVERSE_SIZE_INVALID")
    if any(not isinstance(s, str) or not _SYMBOL.fullmatch(s) for s in eligible_symbols):
        raise ValueError("V5_SYMBOL_INVALID")
    if len(set(eligible_symbols)) != len(eligible_symbols):
        raise ValueError("V5_UNIVERSE_DUPLICATE")
    if set(observations) - set(eligible_symbols):
        raise ValueError("V5_UNIVERSE_UNEXPECTED_EVIDENCE")

    universe = tuple(sorted(eligible_symbols))
    universe_digest = _digest({"eligible_symbols": universe, "event_open_ms": event_open_ms})
    btc_errors = _evidence_reasons(btc_context, event_open_ms, decision_at_ms, "BTC")
    result = []
    for symbol in universe:
        evidence = observations.get(symbol)
        symbol_errors = _evidence_reasons(evidence, event_open_ms, decision_at_ms, "SYMBOL")
        for side in SIDES:
            supplied = evidence.patterns_by_side.get(side, {}) if evidence else {}
            if any(p not in PATTERN_IDS for p in supplied):
                raise ValueError("V5_PATTERN_UNKNOWN")
            if any(state not in PATTERN_STATES for state in supplied.values()):
                raise ValueError("V5_PATTERN_STATE_INVALID")
            if evidence and set(evidence.patterns_by_side) - set(SIDES):
                raise ValueError("V5_PATTERN_SIDE_INVALID")
            states = {p: supplied.get(p, "UNAVAILABLE") for p in PATTERN_IDS}
            reasons = [*btc_errors, *symbol_errors]
            if "UNAVAILABLE" in states.values():
                reasons.append("PATTERN_EVIDENCE_UNAVAILABLE")
            reasons = sorted(set(reasons))
            decision_id = _digest({
                "schema": SCHEMA_VERSION, "event_open_ms": event_open_ms,
                "symbol": symbol, "side": side,
            })
            result.append({
                "schema_version": SCHEMA_VERSION,
                "decision_id": decision_id,
                "event_open_ms": event_open_ms,
                "decision_at_ms": decision_at_ms,
                "universe_digest": universe_digest,
                "symbol": symbol,
                "side": side,
                "btc_context_valid": not btc_errors,
                "patterns": states,
                "status": "UNSCORABLE" if reasons else "OBSERVED",
                "reason_codes": reasons,
                "action": "OBSERVE_ONLY",
                "order_authority": "NONE",
            })
    return tuple(result)


def initialize_candidate_ledger(connection: sqlite3.Connection) -> None:
    """Initialize a fresh *separate* V5 database, never a historical V4 file."""
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS v5_candidate_observations (
            decision_id TEXT PRIMARY KEY,
            event_open_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')),
            payload_sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE(event_open_ms, symbol, side)
        );
        CREATE TRIGGER IF NOT EXISTS v5_candidate_no_update
        BEFORE UPDATE ON v5_candidate_observations
        BEGIN SELECT RAISE(ABORT, 'V5_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS v5_candidate_no_delete
        BEFORE DELETE ON v5_candidate_observations
        BEGIN SELECT RAISE(ABORT, 'V5_IMMUTABLE'); END;
    """)


def append_candidate_records(
    connection: sqlite3.Connection, records: Sequence[dict]
) -> int:
    """Atomic append, unchanged replay accepted, altered ID rejected."""
    if not records:
        raise ValueError("V5_EMPTY_BATCH")
    ids = [r["decision_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("V5_BATCH_DUPLICATE")
    for record in records:
        if record.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("V5_SCHEMA_MISMATCH")
        if record.get("order_authority") != "NONE" or record.get("action") != "OBSERVE_ONLY":
            raise ValueError("V5_ORDER_AUTHORITY_FORBIDDEN")
        expected = _digest({
            "schema": SCHEMA_VERSION, "event_open_ms": record["event_open_ms"],
            "symbol": record["symbol"], "side": record["side"],
        })
        if record["decision_id"] != expected:
            raise ValueError("V5_DECISION_ID_MISMATCH")
    inserted = 0
    with connection:
        for record in records:
            payload = _canonical(record)
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            row = connection.execute(
                "SELECT payload_sha256, payload_json FROM v5_candidate_observations "
                "WHERE decision_id=?", (record["decision_id"],)
            ).fetchone()
            if row:
                if row != (digest, payload):
                    raise ValueError("V5_CHANGED_DECISION_REJECTED")
                continue
            connection.execute(
                "INSERT INTO v5_candidate_observations "
                "(decision_id,event_open_ms,symbol,side,payload_sha256,payload_json) "
                "VALUES (?,?,?,?,?,?)",
                (record["decision_id"], record["event_open_ms"],
                 record["symbol"], record["side"], digest, payload),
            )
            inserted += 1
    return inserted
