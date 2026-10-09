"""Policy-explicit chronological counterfactual replay for V3 research."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable

from .chronological_replay import TradeEvent


class EvidenceQuality(str, Enum):
    AGGTRADE_RESOLVED = "AGGTRADE_RESOLVED"
    ONE_MINUTE_RESOLVED = "1M_RESOLVED"
    FIVE_MINUTE_UNAMBIGUOUS = "5M_UNAMBIGUOUS"
    FIVE_MINUTE_AMBIGUOUS = "5M_AMBIGUOUS"
    GAP_UNRESOLVED = "GAP_UNRESOLVED"


class TrailPolicy(str, Enum):
    TICK_INTEGER_R = "TICK_INTEGER_R_V1"
    BAR_CLOSE_INTEGER_R = "BAR_CLOSE_INTEGER_R_V1"


@dataclass(frozen=True)
class ReplayCosts:
    taker_fee_rate: float = 0.0005
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0
    funding_r: float = 0.0

    def __post_init__(self) -> None:
        if not 0 <= self.taker_fee_rate < 0.1 or min(self.entry_slippage_bps, self.exit_slippage_bps) < 0:
            raise ValueError("COUNTERFACTUAL_COST_INVALID")
        if not all(math.isfinite(x) for x in (self.entry_slippage_bps, self.exit_slippage_bps, self.funding_r)):
            raise ValueError("COUNTERFACTUAL_COST_INVALID")


@dataclass(frozen=True)
class PolicyOutcome:
    policy_id: str
    quality: EvidenceQuality
    exit_reason: str
    exit_time_ms: int | None
    exit_price: float | None
    gross_r: float | None
    net_r: float | None
    mfe_r: float
    mae_r: float
    final_stop_r: int
    events_seen: int
    ambiguous: bool
    source_digest: str


def _source_digest(events: list[TradeEvent]) -> str:
    body = [(e.symbol, e.trade_id, e.trade_time_ms, e.price) for e in events]
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def replay_policy(events: Iterable[TradeEvent], *, symbol: str, side: str, entry_price: float, one_r_price: float,
                  entry_time_ms: int, policy: TrailPolicy, costs: ReplayCosts = ReplayCosts(),
                  horizon_ms: int = 4 * 60 * 60 * 1000, bar_ms: int = 5 * 60 * 1000,
                  require_contiguous_ids: bool = True) -> PolicyOutcome:
    if side not in {"LONG", "SHORT"} or entry_price <= 0 or one_r_price <= 0 or horizon_ms <= 0:
        raise ValueError("COUNTERFACTUAL_CONFIG_INVALID")
    direction = 1 if side == "LONG" else -1
    rows = list(events)
    digest = _source_digest(rows)
    stop_r = -1
    peak = 0.0
    trough = 0.0
    seen = 0
    last_id = None
    last_time = None
    exit_time = None
    exit_price = None
    exit_reason = "HORIZON"
    ambiguous = False
    current_bar = None
    bar_peak = 0.0
    for e in rows:
        if e.symbol != symbol:
            raise ValueError("COUNTERFACTUAL_SYMBOL_MISMATCH")
        if last_time is not None and (e.trade_time_ms < last_time or e.trade_id <= last_id):
            return PolicyOutcome(policy.value, EvidenceQuality.GAP_UNRESOLVED, "GAP_UNRESOLVED", None, None,
                                 None, None, peak, trough, stop_r, seen, False, digest)
        if last_id is not None and require_contiguous_ids and e.trade_id != last_id + 1:
            return PolicyOutcome(policy.value, EvidenceQuality.GAP_UNRESOLVED, "GAP_UNRESOLVED", None, None,
                                 None, None, peak, trough, stop_r, seen, False, digest)
        last_id, last_time = e.trade_id, e.trade_time_ms
        if e.trade_time_ms < entry_time_ms:
            continue
        if e.trade_time_ms > entry_time_ms + horizon_ms:
            break
        seen += 1
        r = direction * (e.price - entry_price) / one_r_price
        peak, trough = max(peak, r), min(trough, r)
        if r <= stop_r:
            exit_time, exit_price, exit_reason = e.trade_time_ms, e.price, "STOP"
            break
        if policy is TrailPolicy.TICK_INTEGER_R:
            if peak >= 1:
                stop_r = max(stop_r, math.floor(peak) - 1)
        else:
            bucket = (e.trade_time_ms // bar_ms) * bar_ms
            if current_bar is None:
                current_bar = bucket
            if bucket != current_bar:
                if bar_peak >= 1:
                    stop_r = max(stop_r, math.floor(bar_peak) - 1)
                current_bar = bucket
                bar_peak = r
            else:
                bar_peak = max(bar_peak, r)
    gross_r = None if exit_price is None else direction * (exit_price - entry_price) / one_r_price
    if gross_r is None:
        net_r = None
    else:
        fee_r = 2.0 * costs.taker_fee_rate * entry_price / one_r_price
        slip_r = (costs.entry_slippage_bps + costs.exit_slippage_bps) / 10000.0 * entry_price / one_r_price
        net_r = gross_r - fee_r - slip_r - costs.funding_r
    return PolicyOutcome(policy.value, EvidenceQuality.AGGTRADE_RESOLVED, exit_reason, exit_time, exit_price,
                         gross_r, net_r, peak, trough, stop_r, seen, ambiguous, digest)


def classify_rejected_outcome(*, approved: bool, net_r: float | None, quality: EvidenceQuality) -> str:
    if quality is EvidenceQuality.GAP_UNRESOLVED or net_r is None:
        return "UNRESOLVED"
    if approved:
        return "APPROVED_POLICY_OUTCOME"
    if net_r < 0:
        return "AVOIDED_LOSS"
    if net_r > 0:
        return "MISSED_PROFITABLE_POLICY_OUTCOME"
    return "NEUTRAL"
