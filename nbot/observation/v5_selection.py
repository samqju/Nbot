"""V5 prospective, deterministic, research-only directional entry selection.

No exchange, model, file IO, order authority or history-dependent optimization.
All thresholds below are unproven, frozen experiments to test on future data.
100 is a *maximum*, not a fill target. An absence of setups means abstention.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import statistics
from typing import Iterable

from .v5_accounting import ENTRY_FEE_RATE, EXIT_FEE_RATE, ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE

VERSION = "NBOT_V5_DIRECTIONAL_SELECTOR_V2"
ORDER_AUTHORITY = "NONE"
FIVE_MINUTES_MS = 300_000
LOOKBACK = 49
CAPACITY = 100
EXPLORATION_CAP = 4


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _valid(number: float, *, positive: bool = False) -> bool:
    try:
        value = float(number)
    except (ValueError, TypeError):
        return False
    return math.isfinite(value) and (not positive or value > 0)


@dataclass(frozen=True)
class Bar:
    open_ms: int
    open: float
    high: float
    low: float
    close: float
    quote_volume: float


@dataclass(frozen=True)
class Instrument:
    symbol: str
    tick_size: float
    quantity_step: float
    min_notional: float
    trading: bool
    captured_at_ms: int
    min_qty: float = 0.0
    max_qty: float | None = None
    source_digest: str = ""


@dataclass(frozen=True)
class DepthSnapshot:
    symbol: str
    started_at_ms: int
    captured_at_ms: int
    update_id: int
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]
    source_digest: str


@dataclass(frozen=True)
class Observation:
    symbol: str
    event_open_ms: int
    event_close_ms: int
    captured_at_ms: int
    bid: float
    ask: float
    quote_volume_24h_usd: float
    funding_rate: float | None
    selection_rank: int
    bars: tuple[Bar, ...]
    provenance_ok: bool
    instrument: Instrument | None = None
    depth: DepthSnapshot | None = None


@dataclass(frozen=True)
class SelectionPolicy:
    version: str = VERSION
    min_24h_quote_volume_usd: float = 3_000_000.0
    max_relative_spread: float = 0.0015
    max_modeled_entry_cost_r: float = 0.30
    max_abs_snapshot_funding_rate: float = 0.002
    max_snapshot_age_ms: int = 120_000
    max_instrument_age_ms: int = 86_400_000
    max_depth_lag_ms: int = 10_000
    max_depth_age_ms: int = 10_000
    max_depth_impact_bps: float = 10.0
    probe_notional_usd: float = 100.0
    min_stop_ticks: int = 3
    max_positions: int = CAPACITY
    max_exploratory_positions: int = EXPLORATION_CAP
    max_positions_per_side: int = 60

    def __post_init__(self) -> None:
        if self.version != VERSION or self.max_positions != CAPACITY:
            raise ValueError("V5_SELECTION_POLICY_VERSION_OR_CAPACITY_INVALID")
        if not (0 <= self.max_exploratory_positions <= EXPLORATION_CAP):
            raise ValueError("V5_EXPLORATION_CAP_INVALID")
        if not 1 <= self.max_positions_per_side <= CAPACITY:
            raise ValueError("V5_SIDE_CAP_INVALID")
        for k in ("min_24h_quote_volume_usd", "max_relative_spread",
                  "max_modeled_entry_cost_r", "max_abs_snapshot_funding_rate"):
            if not _valid(getattr(self, k)) or float(getattr(self, k)) < 0:
                raise ValueError("V5_SELECTION_THRESHOLD_INVALID")
        if (not _valid(self.max_depth_impact_bps) or self.max_depth_impact_bps < 0
                or not _valid(self.probe_notional_usd, positive=True)):
            raise ValueError("V5_SELECTION_THRESHOLD_INVALID")
        if min(self.max_snapshot_age_ms, self.max_instrument_age_ms,
               self.max_depth_lag_ms, self.max_depth_age_ms,
               self.min_stop_ticks) <= 0:
            raise ValueError("V5_SELECTION_THRESHOLD_INVALID")


@dataclass(frozen=True)
class Candidate:
    decision_id: str
    symbol: str
    side: str
    event_open_ms: int
    status: str
    reason: str
    setup: str | None
    regime: str
    feature_digest: str
    cost_r_estimate: float | None
    initial_stop_price: float | None
    sampling_probability: float
    qualified: bool
    exploration_eligible: bool
    universe_rank: int


@dataclass(frozen=True)
class SelectionPlan:
    event_open_ms: int
    policy: str
    records: tuple[Candidate, ...]
    selected: tuple[Candidate, ...]
    exploratory: tuple[Candidate, ...]
    abstained: bool
    order_authority: str = ORDER_AUTHORITY


def _ema(values: list[float], period: int) -> float:
    weight = 2.0 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = weight * value + (1.0 - weight) * result
    return result


def _atr(bars: tuple[Bar, ...]) -> float:
    ranges = []
    for a, b in zip(bars[-15:-1], bars[-14:]):
        ranges.append(max(b.high - b.low, abs(b.high - a.close),
                          abs(b.low - a.close)))
    return statistics.fmean(ranges)


def _regime(bars: tuple[Bar, ...], atr: float) -> str:
    closes = [b.close for b in bars[-35:]]
    gap = _ema(closes, 8) - _ema(closes, 21)
    if abs(gap) >= 0.35 * atr:
        return "UPTREND" if gap > 0 else "DOWNTREND"
    return "RANGE" if abs(gap) <= 0.20 * atr else "UNKNOWN"


def _setup(bars: tuple[Bar, ...], side: str, atr: float, regime: str) -> tuple[str | None, bool]:
    """Directional setups use only fully closed bars in the supplied event."""
    direction = 1 if side == "LONG" else -1
    last, prev = bars[-1], bars[-2]
    close = [b.close for b in bars[-35:]]
    fast, slow = _ema(close, 8), _ema(close, 21)
    prior20 = bars[-21:-1]  # strictly before last completed candle
    high20 = max(b.high for b in prior20)
    low20 = min(b.low for b in prior20)
    width = last.high - last.low
    trend_ok = regime == ("UPTREND" if side == "LONG" else "DOWNTREND")
    strong_body = width > 0 and direction * (last.close - last.open) >= 0.45 * width
    volume_base = statistics.median(b.quote_volume for b in prior20)
    volume_confirmed = last.quote_volume >= 1.4 * volume_base > 0

    # A genuine completed close through a prior 20-bar level + volume/body.
    broke = last.close > high20 if side == "LONG" else last.close < low20
    if trend_ok and broke and strong_body and volume_confirmed:
        return "LEVEL_BREAKOUT_V1", False

    # Trend-aligned pullback/touch and directional recovery, no lookahead.
    touched = last.low <= fast + 0.20 * atr if side == "LONG" else last.high >= fast - 0.20 * atr
    recovered = last.close > fast and last.close > prev.close if side == "LONG" else (
        last.close < fast and last.close < prev.close
    )
    if trend_ok and touched and recovered and strong_body:
        return "TREND_PULLBACK_V1", False

    # Boundary sweep and close inside the prior range; directional rejection.
    swept = last.low < low20 and last.close > low20 if side == "LONG" else (
        last.high > high20 and last.close < high20
    )
    if regime == "RANGE" and swept and strong_body:
        return "RANGE_REJECTION_V1", False

    # Deliberate, side-specific near-miss for bounded exploration. Not qualified.
    near = (trend_ok and direction * (last.close - prev.close) > 0
            and strong_body) or (
                regime == "RANGE" and strong_body and (
                    last.close <= low20 + 0.20 * (high20 - low20)
                    if side == "LONG"
                    else last.close >= high20 - 0.20 * (high20 - low20)
                )
            )
    return None, bool(near)


def _depth_problems(
    market: Observation, *, now_ms: int, policy: SelectionPolicy
) -> list[str]:
    """Check independent bid+ask depth for a small hypothetical notional probe.

    This is a quality *gate*, not an actual fill or a guarantee of execution.
    """
    inst, book = market.instrument, market.depth
    if book is None or inst is None:
        return ["DEPTH_MISSING"]
    if book.symbol != market.symbol or not book.source_digest or len(book.source_digest) != 64:
        return ["DEPTH_PROVENANCE_INVALID"]
    if (type(book.started_at_ms) is not int or type(book.captured_at_ms) is not int
            or type(book.update_id) is not int or book.update_id <= 0
            or book.started_at_ms < market.event_close_ms
            or book.started_at_ms < market.captured_at_ms
            or book.captured_at_ms < book.started_at_ms
            or book.captured_at_ms > now_ms
            or now_ms - book.captured_at_ms > policy.max_depth_age_ms
            or book.captured_at_ms - market.captured_at_ms > policy.max_depth_lag_ms):
        return ["DEPTH_STALE_OR_FUTURE"]
    if not book.bids or not book.asks or len(book.bids) > 100 or len(book.asks) > 100:
        return ["DEPTH_LEVELS_INVALID"]
    for levels, is_bid in ((book.bids, True), (book.asks, False)):
        if any(not (_valid(price, positive=True) and _valid(qty, positive=True))
               for price, qty in levels):
            return ["DEPTH_LEVELS_INVALID"]
        prices = [float(p) for p, _ in levels]
        if any((prices[i] <= prices[i + 1] if is_bid
                else prices[i] >= prices[i + 1])
               for i in range(len(prices) - 1)):
            return ["DEPTH_LEVELS_INVALID"]
    if book.bids[0][0] >= book.asks[0][0]:
        return ["DEPTH_CROSSED"]
    if not (_valid(market.bid, positive=True) and _valid(market.ask, positive=True)):
        return ["DEPTH_MARKET_QUOTE_MISMATCH"]
    if (abs(book.bids[0][0] - market.bid) > inst.tick_size * 1.01
            or abs(book.asks[0][0] - market.ask) > inst.tick_size * 1.01):
        return ["DEPTH_MARKET_QUOTE_MISMATCH"]
    # Probe $100 in underlying quantity, rounded up to legal lot step.
    # Reject if even the minimum permitted order is above our probe, so
    # the result is not misleadingly advertised as $100 market-depth proof.
    import math
    qty = math.ceil((policy.probe_notional_usd /
                     ((market.bid + market.ask) / 2)) / inst.quantity_step) * inst.quantity_step
    if (qty < inst.min_qty or
            (inst.max_qty is not None and qty > inst.max_qty) or
            qty * market.ask < inst.min_notional):
        return ["DEPTH_PROBE_LOT_OR_NOTIONAL_INVALID"]
    for levels, buy in ((book.asks, True), (book.bids, False)):
        top = float(levels[0][0])
        left, paid = qty, 0.0
        for price, available in levels:
            used = min(left, available)
            paid += used * price
            left -= used
            if left <= max(1e-12, qty * 1e-10):
                break
        if left > max(1e-12, qty * 1e-10):
            return ["DEPTH_NOTIONAL_INSUFFICIENT"]
        vwap = paid / qty
        adverse_bps = (vwap / top - 1 if buy else 1 - vwap / top) * 10_000
        if adverse_bps > policy.max_depth_impact_bps:
            return ["DEPTH_IMPACT_TOO_HIGH"]
    return []


def evaluate(observation: Observation, side: str, *, now_ms: int,
             policy: SelectionPolicy = SelectionPolicy()) -> Candidate:
    """One symbol+side has exactly one auditable evaluation, even when rejected."""
    if side not in ("LONG", "SHORT") or now_ms < 0:
        raise ValueError("V5_SELECTION_ARGUMENT_INVALID")
    failures: list[str] = []
    m = observation
    safe_symbol = bool(m.symbol) and m.symbol == m.symbol.upper()
    if not safe_symbol or m.event_open_ms < 0 or m.event_open_ms % FIVE_MINUTES_MS:
        raise ValueError("V5_EVENT_OR_SYMBOL_INVALID")
    if m.event_close_ms != m.event_open_ms + FIVE_MINUTES_MS - 1:
        failures.append("EVENT_CLOCK_INVALID")
    if not m.provenance_ok:
        failures.append("PROVENANCE_NOT_LIVE_POINT_IN_TIME")
    if m.captured_at_ms < m.event_close_ms or m.captured_at_ms > now_ms or (
        now_ms - m.captured_at_ms > policy.max_snapshot_age_ms
    ):
        failures.append("SNAPSHOT_STALE_OR_FUTURE")
    if not (_valid(m.bid, positive=True) and _valid(m.ask, positive=True)) or (
        _valid(m.bid, positive=True) and _valid(m.ask, positive=True)
        and m.ask <= m.bid
    ):
        failures.append("INVALID_BID_ASK")
    if not _valid(m.quote_volume_24h_usd) or (
        m.quote_volume_24h_usd < policy.min_24h_quote_volume_usd
    ):
        failures.append("INSUFFICIENT_24H_LIQUIDITY")
    if m.funding_rate is None or not _valid(m.funding_rate) or (
        abs(m.funding_rate) > policy.max_abs_snapshot_funding_rate
    ):
        failures.append("FUNDING_SNAPSHOT_MISSING_OR_EXTREME")
    inst = m.instrument
    if inst is None or inst.symbol != m.symbol or not inst.trading or (
        not _valid(inst.tick_size, positive=True)
        or not _valid(inst.quantity_step, positive=True)
        or not _valid(inst.min_notional)
        or inst.min_notional < 0 or not _valid(inst.min_qty)
        or inst.min_qty < 0 or (inst.max_qty is not None and (
            not _valid(inst.max_qty, positive=True) or inst.max_qty < inst.min_qty))
        or len(inst.source_digest) != 64
    ):
        failures.append("INSTRUMENT_RULES_MISSING_OR_INVALID")
    elif inst.captured_at_ms > now_ms or inst.captured_at_ms < 0 or (
        now_ms - inst.captured_at_ms > policy.max_instrument_age_ms
    ):
        failures.append("INSTRUMENT_RULES_STALE_OR_FUTURE")

    if "INSTRUMENT_RULES_MISSING_OR_INVALID" not in failures:
        failures.extend(_depth_problems(m, now_ms=now_ms, policy=policy))

    bars = m.bars
    if len(bars) != LOOKBACK or any(
        b.open_ms != m.event_open_ms - (LOOKBACK - 1 - i) * FIVE_MINUTES_MS
        or not all(_valid(x, positive=True) for x in (b.open, b.high, b.low, b.close))
        or not _valid(b.quote_volume)
        or b.quote_volume < 0
        or b.low > min(b.open, b.close) or b.high < max(b.open, b.close)
        or b.high < b.low
        for i, b in enumerate(bars)
    ):
        failures.append("INCOMPLETE_OR_INVALID_4H_HISTORY")
    payload = {
        "symbol": m.symbol, "event": m.event_open_ms, "close": m.event_close_ms,
        "snapshot_time": m.captured_at_ms, "bid": m.bid, "ask": m.ask,
        "volume_24h": m.quote_volume_24h_usd, "funding": m.funding_rate,
        "universe_rank": m.selection_rank, "provenance": m.provenance_ok,
        "instrument": None if inst is None else vars(inst),
        "depth": None if m.depth is None else vars(m.depth),
        "bars": [vars(bar) for bar in bars], "side": side, "v": VERSION,
    }
    # Invalid numerical evidence must not create an opaque/colliding feature ID.
    try:
        feature_digest = _hash(payload)
    except (ValueError, TypeError):
        feature_digest = _hash([VERSION, m.symbol, side, m.event_open_ms,
                                "INVALID_NONFINITE_FEATURES"])
    decision_id = _hash([VERSION, m.event_open_ms, m.symbol, side])[:32]

    cost_r = None
    stop = None
    regime = "UNKNOWN"
    setup = None
    near = False
    if not failures:
        atr = _atr(bars)
        if not _valid(atr, positive=True):
            failures.append("ATR_INVALID")
        else:
            regime = _regime(bars, atr)
            entry = m.ask if side == "LONG" else m.bid
            distance = atr
            stop = entry - distance if side == "LONG" else entry + distance
            if not (stop > 0 and distance >= policy.min_stop_ticks * inst.tick_size):
                failures.append("STOP_TOO_CLOSE_TO_TICK")
            else:
                mid = (m.bid + m.ask) / 2.0
                spread = (m.ask - m.bid) / mid
                if spread > policy.max_relative_spread:
                    failures.append("SPREAD_TOO_WIDE")
                # Spread here is a prospective entry-quality budget, not an
                # extra fee in the later fill-based outcome accounting.
                cost_r = ((m.ask - m.bid) + mid * (
                    ENTRY_FEE_RATE + EXIT_FEE_RATE
                    + ENTRY_SLIPPAGE_RATE + EXIT_SLIPPAGE_RATE)) / distance
                if cost_r > policy.max_modeled_entry_cost_r:
                    failures.append("ECONOMIC_COST_TOO_HIGH")
                if not failures:
                    setup, near = _setup(bars, side, atr, regime)
                    if setup is None:
                        failures.append("NO_CONFIRMED_DIRECTIONAL_SETUP")

    qualified = not failures
    return Candidate(
        decision_id=decision_id, symbol=m.symbol, side=side,
        event_open_ms=m.event_open_ms, status="QUALIFIED" if qualified else "REJECTED",
        reason="CONFIRMED_" + setup if qualified else "|".join(failures),
        setup=setup, regime=regime, feature_digest=feature_digest,
        cost_r_estimate=cost_r, initial_stop_price=stop,
        sampling_probability=0.0, qualified=qualified,
        exploration_eligible=(not qualified and near and failures ==
                              ["NO_CONFIRMED_DIRECTIONAL_SETUP"]),
        universe_rank=m.selection_rank,
    )


def plan_event(
    observations: Iterable[Observation], *, event_open_ms: int, now_ms: int,
    active_pairs: Iterable[tuple[str, str]] = (), active_count: int = 0,
    policy: SelectionPolicy = SelectionPolicy(),
) -> SelectionPlan:
    """Never force 100 entries. Qualified precedes bounded exploration."""
    if event_open_ms < 0 or event_open_ms % FIVE_MINUTES_MS or now_ms < 0:
        raise ValueError("V5_PLAN_EVENT_INVALID")
    if not 0 <= active_count <= CAPACITY:
        raise ValueError("V5_ACTIVE_CAPACITY_INVALID")
    active = set(active_pairs)
    if len(active) > active_count or any(s not in ("LONG", "SHORT") for _, s in active):
        raise ValueError("V5_ACTIVE_PAIRS_INVALID")
    obs = tuple(observations)
    if len(obs) > 500 or len({x.symbol for x in obs}) != len(obs):
        raise ValueError("V5_UNIVERSE_DUPLICATE_OR_TOO_LARGE")
    if any(x.event_open_ms != event_open_ms for x in obs):
        raise ValueError("V5_EVENT_MIXED")
    candidates = [evaluate(x, side, now_ms=now_ms, policy=policy)
                  for x in obs for side in ("LONG", "SHORT")]
    records = { (c.symbol, c.side): c for c in candidates }
    vacancies = min(policy.max_positions - active_count, CAPACITY - active_count)
    side_counts = {side: sum(s == side for _, s in active) for side in ("LONG", "SHORT")}
    def priority(c: Candidate):
        return (c.cost_r_estimate if c.cost_r_estimate is not None else float("inf"),
                c.universe_rank, c.symbol, c.side)
    selected: list[Candidate] = []
    for c in sorted((c for c in candidates if c.qualified), key=priority):
        pair = (c.symbol, c.side)
        if pair in active or side_counts[c.side] >= policy.max_positions_per_side:
            continue
        if len(selected) >= vacancies:
            continue
        picked = replace(c, status="SELECTED", reason=c.reason,
                         sampling_probability=1.0)
        records[pair] = picked
        selected.append(picked)
        active.add(pair)
        side_counts[c.side] += 1

    exploration_candidates = [
        c for c in candidates if c.exploration_eligible
        and (c.symbol, c.side) not in active
    ]
    remaining = max(0, vacancies - len(selected))
    pools = {side: [c for c in exploration_candidates if c.side == side]
             for side in ("LONG", "SHORT")}
    allowance = {side: min(len(pools[side]), max(0, policy.max_positions_per_side
                                             - side_counts[side]))
                 for side in pools}
    total_available = sum(allowance.values())
    sample_size = min(policy.max_exploratory_positions, remaining, total_available)
    # Allocate capacity between LONG and SHORT *before* sampling.
    # Within each side, min-hash chooses k of n uniformly; logged probability
    # k/n is therefore exact for the frozen side-stratified eligible population.
    take = {side: 0 for side in pools}
    for _ in range(sample_size):
        options = [side for side in pools if take[side] < allowance[side]]
        if not options:
            break
        # Fractional-fair share relative to the available population.
        winner = max(options, key=lambda side: (
            allowance[side] / (take[side] + 1),
            1 if side == "LONG" else 0,
        ))
        take[winner] += 1
    exploratory: list[Candidate] = []
    for side in ("LONG", "SHORT"):
        pool = pools[side]
        p = take[side] / len(pool) if pool else 0.0
        ordered = sorted(pool, key=lambda x: _hash(
            [VERSION, "EXPLORATION", event_open_ms, x.symbol, x.side]))
        for c in ordered[:take[side]]:
            picked = replace(c, status="EXPLORATORY",
                             reason="EXPLORATORY_NEAR_MISS",
                             sampling_probability=p)
            records[(c.symbol, c.side)] = picked
            exploratory.append(picked)
    return SelectionPlan(
        event_open_ms, VERSION,
        tuple(records[k] for k in sorted(records)), tuple(selected),
        tuple(exploratory), not selected and not exploratory,
    )


def submit_order(*_args, **_kwargs):
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
