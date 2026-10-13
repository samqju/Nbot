"""Offline-only V5 adapter for the 24 previously tested V4 pattern hypotheses.

V4 pattern *definitions* may be reused, but no V4 selection, research ledger,
model, training, paper or execution service is imported. No exchange or network.
Input candles are point-in-time, fully closed five-minute tuples
(open_ms, open, high, low, close, base_volume).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Mapping, Sequence

from nbot.observation import candidate_setups as rules
from nbot.observation.context_learning import describe
from nbot.v5.observation_contract import (
    Evidence, INTERVAL_MS, MAX_SYMBOLS, PATTERN_IDS, SIDES,
    build_candidate_records,
)

DETECTOR_VERSION = "NBOT_V5_24_PATTERN_ADAPTER_V1"
MIN_HISTORY = 49
MAX_HISTORY = 96
MIN_CROSS_SECTION = 10

# Refuse silent drift between the original 24 rules and the new record schema.
if tuple(item.id for item in rules.REGISTRY) != PATTERN_IDS:
    raise RuntimeError("V5_PATTERN_CATALOG_DRIFT")
if rules.INTERVAL_MS != INTERVAL_MS or rules.MIN_BARS != MIN_HISTORY:
    raise RuntimeError("V5_PATTERN_TIME_CONTRACT_DRIFT")


@dataclass(frozen=True)
class _Audit:
    bars: tuple[tuple, ...] | None
    last_ms: int
    max_ms: int
    issue: str | None
    digest: str | None = None


def _audit_candles(candles: Sequence[tuple] | None, event_open_ms: int) -> _Audit:
    """Validate the *entire* supplied source before any indicator sees it."""
    if candles is None or not candles:
        return _Audit(None, -1, -1, "MISSING_HISTORY")
    if len(candles) > MAX_HISTORY:
        return _Audit(None, -1, -1, "HISTORY_OVER_LIMIT")
    out = []
    for candle in candles:
        if len(candle) != 6:
            return _Audit(None, -1, -1, "CANDLE_SHAPE_INVALID")
        t, *numbers = candle
        if type(t) is not int or t < 0 or t % INTERVAL_MS:
            return _Audit(None, -1, -1, "CANDLE_TIME_INVALID")
        if any(
            isinstance(v, bool) or not isinstance(v, (float, int))
            for v in numbers
        ):
            return _Audit(None, t, t, "CANDLE_VALUES_INVALID")
        try:
            values = tuple(float(v) for v in numbers)
        except (OverflowError, ValueError):
            return _Audit(None, t, t, "CANDLE_VALUES_INVALID")
        o, h, l, c, volume = values
        if (
            not all(math.isfinite(v) for v in values)
            or min(o, h, l, c) <= 0
            or volume < 0
            or h < max(o, c)
            or l > min(o, c)
            or l > h
        ):
            return _Audit(None, t, t, "CANDLE_OHLCV_INVALID")
        out.append((t, *values))
    times = [row[0] for row in out]
    last = times[-1]
    latest = max(times)
    if latest > event_open_ms:
        return _Audit(None, last, latest, "FUTURE_BAR_PRESENT")
    if len(out) < MIN_HISTORY:
        return _Audit(None, last, latest, "INSUFFICIENT_HISTORY")
    if last != event_open_ms:
        return _Audit(None, last, latest, "LATEST_CANDLE_NOT_EVENT")
    if any(b - a != INTERVAL_MS for a, b in zip(times, times[1:])):
        return _Audit(None, last, latest, "CANDLE_GAP_OR_REORDER")
    closes = [row[4] for row in out]
    # Zero volatility means the legacy detector returns an empty dictionary.
    # Do not misinterpret "unable to evaluate" as "no pattern matched".
    atr = _atr_fraction(out)
    if not math.isfinite(atr) or atr <= 0:
        return _Audit(None, last, latest, "ZERO_OR_INVALID_ATR")
    return _Audit(tuple(out), last, latest, None, rules.history_digest(out))


def _atr_fraction(bars: Sequence[tuple]) -> float:
    true_ranges = [
        max(b[2] - b[3], abs(b[2] - a[4]), abs(b[3] - a[4]))
        for a, b in zip(bars[-15:-1], bars[-14:])
    ]
    return statistics.fmean(true_ranges) / bars[-1][4]


def _percentile(values: Mapping[str, float], symbol: str) -> float:
    ordered = sorted(values.values())
    value = values[symbol]
    if len(ordered) == 1:
        return .5
    less = sum(v < value for v in ordered)
    equal = sum(v == value for v in ordered)
    return (less + (equal - 1) / 2) / (len(ordered) - 1)


def _proxies(
    symbol: str, bars: Sequence[tuple], btc_bars: Sequence[tuple] | None,
    side: str, raw_1h: Mapping[str, float], vol: Mapping[str, float]
) -> dict:
    sign = 1 if side == "LONG" else -1
    closes = [b[4] for b in bars]
    now = closes[-1]
    # Use completed bars only. All horizons use data at or before event_open_ms.
    ret_1h = raw_1h[symbol]
    side_returns = {s: sign * r for s, r in raw_1h.items()}
    return {
        "ret_5m_side": sign * (now / closes[-2] - 1),
        "ret_15m_side": sign * (now / closes[-4] - 1),
        "ret_1h_side": sign * ret_1h,
        "ret_4h_side": sign * (now / closes[-49] - 1),
        "range_frac": (bars[-1][2] - bars[-1][3]) / now,
        "atr14_frac": _atr_fraction(bars),
        "ret_1h_percentile_side": _percentile(side_returns, symbol),
        "breadth_1h_side": sum(1 if r > 0 else -1 if r < 0 else 0
                              for r in side_returns.values()) / len(side_returns),
        "volatility_percentile": _percentile(vol, symbol),
        "candidate_btc_available": 1 if btc_bars is not None else 0,
        "btc_ret_1h_side": (
            sign * (btc_bars[-1][4] / btc_bars[-13][4] - 1)
            if btc_bars is not None else 0
        ),
    }


def _classification(bars: Sequence[tuple], side: str, vector: dict,
                    *, btc_valid: bool) -> dict[str, str]:
    """Five exclusive proxy labels + 19 genuine technical detectors."""
    selected = describe(vector)["setup"] + "_V1"
    conditions = rules.technical_conditions(bars, side, vector)
    expected_technical = set(PATTERN_IDS[5:])
    if set(conditions) != expected_technical:
        raise ValueError("V5_TECHNICAL_DETECTOR_INCOMPLETE")
    states = {name: "NO_MATCH" for name in PATTERN_IDS}
    if selected in PATTERN_IDS[:5]:
        states[selected] = "MATCH"
    for name, passed in conditions.items():
        if type(passed) is not bool:
            raise ValueError("V5_TECHNICAL_DETECTOR_NONBOOLEAN")
        states[name] = "MATCH" if passed else "NO_MATCH"
    if not btc_valid:
        states["BTC_RELATIVE_MOMENTUM_V1"] = "UNAVAILABLE"
    return states


def build_observations_from_closed_candles(
    *,
    event_open_ms: int,
    decision_at_ms: int,
    observed_at_ms: int,
    eligible_symbols: Sequence[str],
    candles_by_symbol: Mapping[str, Sequence[tuple]],
) -> tuple[dict, ...]:
    """Create all eligible LONG/SHORT records; never select or trade.

    BTCUSDT must be supplied as context even when not among eligible symbols.
    A missing, gapped, stale, future, or otherwise invalid source is recorded as
    UNSCORABLE rather than silently removed or replaced with zero returns.
    """
    if (
        type(event_open_ms) is not int or event_open_ms < 0
        or event_open_ms % INTERVAL_MS
        or type(decision_at_ms) is not int
        or decision_at_ms < event_open_ms + INTERVAL_MS
        or type(observed_at_ms) is not int
    ):
        raise ValueError("V5_EVENT_OR_OBSERVATION_TIME_INVALID")
    if (
        not 1 <= len(eligible_symbols) <= MAX_SYMBOLS
        or len(set(eligible_symbols)) != len(eligible_symbols)
        or any(not isinstance(s, str) or not s.isalnum() or s != s.upper()
               for s in eligible_symbols)
    ):
        raise ValueError("V5_UNIVERSE_INVALID")
    unexpected = set(candles_by_symbol) - (set(eligible_symbols) | {"BTCUSDT"})
    if unexpected:
        raise ValueError("V5_UNEXPECTED_CANDLE_SOURCE")
    universe = tuple(sorted(eligible_symbols))
    audits = {
        symbol: _audit_candles(candles_by_symbol.get(symbol), event_open_ms)
        for symbol in (set(universe) | {"BTCUSDT"})
    }
    btc = audits["BTCUSDT"]
    btc_good = btc.issue is None and (
        event_open_ms + INTERVAL_MS <= observed_at_ms <= decision_at_ms
    )
    valid = {symbol: audit.bars for symbol in universe
             if (audit := audits[symbol]).bars is not None}
    # Require broad contemporaneous coverage before assigning ranks/proxy tags.
    required = max(MIN_CROSS_SECTION, math.ceil(.8 * len(universe)))
    cross_good = len(valid) >= required
    raw_1h = {symbol: bars[-1][4] / bars[-13][4] - 1
              for symbol, bars in valid.items()}
    vol = {symbol: _atr_fraction(bars) for symbol, bars in valid.items()}

    def evidence(audit: _Audit, patterns: dict, issues: tuple[str, ...]) -> Evidence:
        return Evidence(
            last_closed_bar_open_ms=audit.last_ms,
            source_max_bar_open_ms=audit.max_ms,
            observed_at_ms=observed_at_ms,
            patterns_by_side=patterns,
            quality_issues=issues,
            source_digest=audit.digest,
            detector_version=DETECTOR_VERSION,
        )

    btc_evidence = (
        evidence(btc, {}, (btc.issue,) if btc.issue else ())
        if "BTCUSDT" in candles_by_symbol else None
    )
    evidence_by_symbol: dict[str, Evidence] = {}
    for symbol in universe:
        if symbol not in candles_by_symbol:
            continue
        audit = audits[symbol]
        issues = tuple([audit.issue] if audit.issue else [])
        by_side: dict[str, dict] = {}
        if audit.bars is not None and not cross_good:
            issues += ("CROSS_SECTION_INCOMPLETE",)
        if audit.bars is not None and cross_good:
            for side in SIDES:
                vector = _proxies(symbol, audit.bars, btc.bars if btc_good else None,
                                  side, raw_1h, vol)
                try:
                    by_side[side] = _classification(
                        audit.bars, side, vector, btc_valid=btc_good
                    )
                except (ArithmeticError, ValueError, TypeError):
                    issues += ("DETECTOR_FAILURE",)
                    by_side = {}
                    break
        evidence_by_symbol[symbol] = evidence(audit, by_side, tuple(sorted(set(issues))))

    return build_candidate_records(
        event_open_ms=event_open_ms,
        decision_at_ms=decision_at_ms,
        eligible_symbols=universe,
        btc_context=btc_evidence,
        observations=evidence_by_symbol,
    )
