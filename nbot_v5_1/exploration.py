"""G3 read-only causal 24-detector Exploration, complete coin-side denominator.

Uses exactly the original V4 5-context/19-technical pure formulas, but NEW
V5.1 source admission, full up-to-100 x LONG/SHORT accounting, masking and
capacity checks. A detector MATCH is a research question, NOT a signal, order,
positive economic label or permission to enter any position.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import statistics

from .core import FiveMinuteEvent, ObservationAuthority, ObservationDisposition, canonical_digest
from .observation import ObservationBook, ClosedBar
from . import detector_rules as legacy

G3_SCHEMA = "NBOT_V5_1_EXPLORATION_V1"
SIDES = ("LONG", "SHORT")
PATTERN_IDS = tuple(x.id for x in legacy.REGISTRY)
TECH_IDS = PATTERN_IDS[5:]
CATALOG_SHA = legacy.CATALOG_DIGEST
DETECTOR_VERSION = "NBOT_V5_1_G3_ADAPTER_V1:" + CATALOG_SHA
MAX_UNIVERSE_AGE_MS = 90 * 60_000  # absent a new cohort, fail closed
if len(PATTERN_IDS) != 24 or len(set(PATTERN_IDS)) != 24 or len(TECH_IDS) != 19:
    raise RuntimeError("G3_DETECTOR_CATALOG_DRIFT")
MASKS = frozenset(("MATCH", "NO_MATCH", "UNAVAILABLE",
                   "NOT_EVALUATED_CAPACITY", "NOT_EVALUATED_SOURCE"))


@dataclass(frozen=True)
class ExplorationRow:
    symbol: str
    side: str
    event_open_ms: int
    status: str
    source_reason: str | None
    detector_states: tuple[tuple[str, str], ...]
    btc_regime: str
    market_regime: str
    coin_regime: str
    structure: str
    structure_maturity: str
    source_hash: str | None
    history_count: int
    selection_groups: tuple[str, ...]
    liquidity_state: str
    cost_state: str
    source_epoch: int | None
    source_route: str | None
    source_grade: str
    inclusion_probability: float
    decision_id: str
    disposition: ObservationDisposition = ObservationDisposition.NO_TRADE
    authority: ObservationAuthority = ObservationAuthority.NONE

    def states(self) -> dict[str, str]:
        return dict(self.detector_states)

    def as_record(self) -> dict:
        return {"symbol": self.symbol, "side": self.side,
                "event_open_ms": self.event_open_ms, "status": self.status,
                "source_reason": self.source_reason,
                "patterns": dict(self.detector_states),
                "btc_regime": self.btc_regime,
                "market_regime": self.market_regime,
                "coin_regime": self.coin_regime,
                "structure": self.structure,
                "maturity": self.structure_maturity,
                "source_hash": self.source_hash,
                "history_count": self.history_count,
                "selection_groups": list(self.selection_groups),
                "liquidity_state": self.liquidity_state,
                "cost_state": self.cost_state,
                "source_epoch": self.source_epoch,
                "source_route": self.source_route,
                "source_grade": self.source_grade,
                "inclusion_probability": self.inclusion_probability,
                "decision_id": self.decision_id,
                "disposition": self.disposition.value,
                "authority": self.authority.value,
                "detector_version": DETECTOR_VERSION}


@dataclass(frozen=True)
class ExplorationBatch:
    event_open_ms: int
    decision_at_ms: int
    universe_sha: str
    detector_version: str
    policy: str
    capacity_slots: int
    evaluation_limit: int
    eligible_pairs: int
    evaluated_pairs: int
    source_skipped_pairs: int
    capacity_skipped_pairs: int
    rows: tuple[ExplorationRow, ...]
    batch_id: str

    def as_record(self) -> dict:
        return {"schema": G3_SCHEMA, "event_open_ms": self.event_open_ms,
                "decision_at_ms": self.decision_at_ms,
                "universe_sha": self.universe_sha,
                "detector_version": self.detector_version,
                "policy": self.policy,
                "capacity_slots": self.capacity_slots,
                "evaluation_limit": self.evaluation_limit,
                "eligible_pairs": self.eligible_pairs,
                "evaluated_pairs": self.evaluated_pairs,
                "source_skipped_pairs": self.source_skipped_pairs,
                "capacity_skipped_pairs": self.capacity_skipped_pairs,
                "rows": [r.as_record() for r in self.rows], "id": self.batch_id}


def _atr_fraction(bars: tuple[ClosedBar, ...]) -> float:
    tr = [max(float(b.high)-float(b.low),
              abs(float(b.high)-float(a.closing)),
              abs(float(b.low)-float(a.closing)))
          for a, b in zip(bars[-15:-1], bars[-14:])]
    return statistics.fmean(tr) / float(bars[-1].closing)


def _percentile(values: dict[str, float], symbol: str) -> float:
    order = sorted(values.values())
    if len(order) == 1:
        return .5
    value = values[symbol]
    less = sum(v < value for v in order)
    equal = sum(v == value for v in order)
    return (less + (equal-1)/2)/(len(order)-1)


def _input_history(bars: tuple[ClosedBar, ...]) -> tuple[tuple, ...]:
    # Adapter conversion happens only after G2's source/known-at checks pass.
    return tuple((b.open_ms, float(b.opening), float(b.high), float(b.low),
                  float(b.closing), float(b.volume)) for b in bars)


def _classification(bars: tuple[ClosedBar, ...], side: str) -> tuple[str, str, str]:
    last, prev = bars[-1], bars[-2]
    c, o, hi, lo = [float(v) for v in
                     (last.closing, last.opening, last.high, last.low)]
    pct4h = c / float(bars[-49].closing) - 1
    atr = _atr_fraction(bars)
    coin = "UPTREND" if pct4h > max(2*atr, .001) else (
           "DOWNTREND" if pct4h < -max(2*atr,.001) else "RANGE")
    high20 = max(float(b.high) for b in bars[-21:-1])
    low20 = min(float(b.low) for b in bars[-21:-1])
    if c > high20:
        structure, maturity = "RANGE_BREAK_UP", "CONFIRMED"
    elif c < low20:
        structure, maturity = "RANGE_BREAK_DOWN", "CONFIRMED"
    elif hi > high20 and c <= high20:
        structure, maturity = "FAILED_UP_BREAK", "FAILED"
    elif lo < low20 and c >= low20:
        structure, maturity = "FAILED_DOWN_BREAK", "FAILED"
    elif c > float(prev.closing) and side == "LONG":
        structure, maturity = "UP_MOVE", "FORMING"
    elif c < float(prev.closing) and side == "SHORT":
        structure, maturity = "DOWN_MOVE", "FORMING"
    else:
        structure, maturity = "RANGE_OR_NONE", "UNCONFIRMED"
    return coin, structure, maturity


def explore_event(
    book: ObservationBook, event: FiveMinuteEvent, *,
    capacity_slots: int = 0, evaluation_limit: int = 200,
) -> ExplorationBatch:
    """Observe every coin-side, evaluate only source-ready capacity-admitted pairs.

    A positive capacity_slots only means *the caller reports* vacant research
    capacity. No order/admission/slot state is actually created by G3.
    The optional <200 evaluation_limit is a declared deterministic hash-order
    sampling policy; inclusion_probability is design K/N, not a measurement
    of post-hoc profitable candidate selection.
    """
    if type(book) is not ObservationBook or type(event) is not FiveMinuteEvent:
        raise ValueError("G3_INPUT_TYPE_INVALID")
    if type(capacity_slots) is not int or not 0 <= capacity_slots <= 40:
        raise ValueError("G3_CAPACITY_INVALID")
    if type(evaluation_limit) is not int or not 0 <= evaluation_limit <= 200:
        raise ValueError("G3_EVALUATION_LIMIT_INVALID")
    snapshot = book.snapshot(event)  # independently enforces event as-of/candle.
    source_rows = {r.symbol: r for r in snapshot.rows}
    cohort = book.manifest.symbols
    if len(cohort) != len(snapshot.rows) or len(cohort) > 100 or len(cohort) < 1:
        raise ValueError("G3_DENOMINATOR_INVALID")
    histories = {s: book.history_asof(s, event) for s in cohort}
    universe_stale = event.decision_at_ms-book.manifest.selected_at_ms>MAX_UNIVERSE_AGE_MS
    complete = {s: bars for s, bars in histories.items()
                if len(bars) >= legacy.MIN_BARS and not universe_stale
                and source_rows[s].state == "METADATA_CLOSED"}
    btc_history = complete.get("BTCUSDT")
    required = max(10, math.ceil(.8*len(cohort)))
    # No manufacturing cross-sectional ranks from thin surviving samples.
    cross_healthy = len(complete) >= required
    raw_1h = {s: float(b[-1].closing)/float(b[-13].closing)-1 for s,b in complete.items()}
    volatility = {s: _atr_fraction(b) for s,b in complete.items()}
    usable = {s for s,b in complete.items() if volatility[s] > 0 and
              math.isfinite(volatility[s])}
    pairs = [(s,side) for s in cohort for side in SIDES]
    source_eligible = [(s,side) for s,side in pairs if s in usable]
    if capacity_slots == 0:
        evaluated: set[tuple[str,str]] = set()
    else:
        # Hash rotation prevents a stable alphabetical priority bias.
        keys = lambda p: (canonical_digest("intent",
                 {"schema": G3_SCHEMA, "event": event.event_open_ms,
                  "symbol": p[0], "side": p[1]}),p)
        evaluated = set(sorted(source_eligible, key=keys)[:evaluation_limit])
    probability = (len(evaluated) / len(source_eligible)) if source_eligible else 0.0
    btc_regime = "UNAVAILABLE"
    if btc_history:
        r = float(btc_history[-1].closing)/float(btc_history[-13].closing)-1
        btc_regime = "UP" if r > .002 else "DOWN" if r < -.002 else "FLAT"
    market_regime = "UNAVAILABLE"
    if cross_healthy:
        breadth = sum(1 if r>0 else -1 if r<0 else 0 for r in raw_1h.values())/len(raw_1h)
        market_regime = "UP" if breadth > .3 else "DOWN" if breadth < -.3 else "MIXED"
    rows: list[ExplorationRow] = []
    for sym,side in pairs:
        srow = source_rows[sym]
        own = histories[sym]
        if sym not in usable:
            state = "NOT_EVALUATED_SOURCE"
            cause = ("UNIVERSE_STALE" if universe_stale else
                     "SOURCE_" + ("HOLD" if srow.state=="HOLD" else "INVALID_ATR"))
        elif (sym,side) not in evaluated:
            state = "NOT_EVALUATED_CAPACITY"
            cause = None
        else:
            state = "OBSERVED"
            cause = None
        detector = dict.fromkeys(PATTERN_IDS, state if state != "OBSERVED"
                                  else "NO_MATCH")
        coin_regime = structure = maturity = "UNAVAILABLE"
        if sym in usable:
            coin_regime,structure,maturity = _classification(own,side)
        if state == "OBSERVED":
            sign = 1 if side=="LONG" else -1
            close = [float(b.closing) for b in own]
            now = close[-1]
            vectors = {
              "ret_5m_side": sign*(now/close[-2]-1),
              "ret_15m_side": sign*(now/close[-4]-1),
              "ret_1h_side": sign*raw_1h[sym],
              "ret_4h_side": sign*(now/close[-49]-1),
              "range_frac": (float(own[-1].high)-float(own[-1].low))/now,
              "atr14_frac": volatility[sym],
              "candidate_btc_available": 1 if btc_history else 0,
              "btc_ret_1h_side": (sign*(float(btc_history[-1].closing)/
                      float(btc_history[-13].closing)-1)) if btc_history else 0.0,
            }
            if cross_healthy:
                side_r = {s:sign*r for s,r in raw_1h.items()}
                vectors.update({
                  "ret_1h_percentile_side": _percentile(side_r,sym),
                  "volatility_percentile": _percentile(volatility,sym),
                  "breadth_1h_side": sum(1 if r>0 else -1 if r<0 else 0
                                         for r in side_r.values())/len(side_r),
                })
                context = legacy.describe(vectors)["setup"]+"_V1"
                if context in PATTERN_IDS[:5]:
                    detector[context] = "MATCH"
            else:
                for ident in PATTERN_IDS[:5]:
                    detector[ident]="UNAVAILABLE"
            original = legacy.technical_conditions(_input_history(own),side,vectors)
            if set(original) != set(TECH_IDS) or any(type(x) is not bool for x in original.values()):
                raise ValueError("G3_LEGACY_DETECTOR_OUTPUT_INVALID")
            for ident,val in original.items():
                detector[ident] = "MATCH" if val else "NO_MATCH"
            if not btc_history:
                # The historical V4 rule defaults a missing BTC return to
                # zero; V5.1 MUST never count that as a valid NO_MATCH.
                detector["BTC_RELATIVE_MOMENTUM_V1"] = "UNAVAILABLE"
        if set(detector) != set(PATTERN_IDS) or not set(detector.values()) <= MASKS:
            raise ValueError("G3_DETECTOR_STATES_INCOMPLETE")
        fingerprint = srow.bar_hash if sym in usable else None
        identity = canonical_digest("intent", {"schema": G3_SCHEMA, "event":event.event_open_ms,
                 "manifest": snapshot.universe_sha, "symbol":sym, "side":side,
                 "detectors": DETECTOR_VERSION})
        rows.append(ExplorationRow(sym,side,event.event_open_ms,state,cause,
                    tuple((name,detector[name]) for name in PATTERN_IDS),
                    btc_regime,market_regime,coin_regime,structure,maturity,
                    fingerprint,len(own),
                    next(e.groups for e in book.manifest.entries if e.symbol==sym),
                    "UNIVERSE_LIQUIDITY_METADATA_ONLY" if not universe_stale else "UNIVERSE_STALE",
                    "QUOTE_SLIPPAGE_FEE_FUNDING_UNVERIFIED",
                    srow.source_epoch, srow.route,
                    "CLOSED_PUBLIC_CANDLE_METADATA_NOT_ORIGINAL",
                    probability if (sym,side) in source_eligible and capacity_slots>0 else 0.0,
                    identity))
    if len(rows) != 2*len(cohort) or len({r.decision_id for r in rows})!=len(rows):
        raise ValueError("G3_DIRECTION_DENOMINATOR_INVALID")
    counts = {name:sum(r.status == name for r in rows) for name in
              ("OBSERVED","NOT_EVALUATED_SOURCE","NOT_EVALUATED_CAPACITY")}
    if sum(counts.values()) != len(rows):
        raise ValueError("G3_DENOMINATOR_ACCOUNTING_INVALID")
    policy = "NONE_FULL_CAPACITY" if capacity_slots==0 else (
             "HASH_ROTATING_LIMIT_V1")
    batch_id = canonical_digest("event", {"schema":G3_SCHEMA,"event":event.event_open_ms,
           "manifest":snapshot.universe_sha,"clock":event.decision_at_ms,
           "detectors":DETECTOR_VERSION,"limit":evaluation_limit,
           "vacancies":capacity_slots,
           "rows":[[r.decision_id,r.status,[[n,s] for n,s in r.detector_states]]
                   for r in rows]})
    return ExplorationBatch(event.event_open_ms,event.decision_at_ms,
           snapshot.universe_sha,DETECTOR_VERSION,policy,capacity_slots,
           evaluation_limit,len(source_eligible),counts["OBSERVED"],
           counts["NOT_EVALUATED_SOURCE"],counts["NOT_EVALUATED_CAPACITY"],
           tuple(rows),batch_id)
