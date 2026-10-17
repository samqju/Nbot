"""Chronological, NO-TRADE-first NBOT V6 offline regime strategy selector.

Read native Freqtrade-validated candidate scorecards from independent blocks,
never use later test results at earlier 8-hour decision timestamps. Works with
any research caller; does not place orders, train, backtest or promote models.
A caller MUST construct records from verified native trades and as-of market
regime labels; a declaration alone is not independent proof of profitability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Mapping, Sequence

VALID_FAMILIES = frozenset((
    "ema_cross", "donchian_breakout", "bollinger_reversion",
    "rsi_reversion", "macd_momentum", "stochastic_reversal",
    "atr_breakout", "volume_trend",
))
VALID_REGIMES = frozenset(("trend_up", "trend_down", "range", "high_volatility"))
TREND = frozenset(("ema_cross", "donchian_breakout", "macd_momentum", "atr_breakout", "volume_trend"))
RANGE = frozenset(("bollinger_reversion", "rsi_reversion", "stochastic_reversal"))
HEX256 = re.compile(r"^[0-9a-f]{64}$")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("REQUIRED_UTC_ISO_STRING")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("TIMESTAMPS_MUST_BE_UTC")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class CandidateBlock:
    """Audited, strictly out-of-sample native trade PnL for one regime."""
    family: str
    regime: str
    evaluated_from: str
    evaluated_until: str
    model_trained_until: str
    native_zip_sha256: str
    market_history_sha256: str
    trade_count: int
    pnl_net_usdt: float
    stressed_net_usdt: float
    max_drawdown_fraction: float
    native_audit_passed: bool
    decision_boundary_passed: bool

    def validate(self) -> None:
        if self.family not in VALID_FAMILIES or self.regime not in VALID_REGIMES:
            raise ValueError("UNRECOGNIZED_FAMILY_OR_REGIME")
        start, end, trained = map(parse_utc, (
            self.evaluated_from, self.evaluated_until, self.model_trained_until))
        if not trained < start < end:
            raise ValueError("TRAINING_AND_EVALUATION_MUST_NOT_OVERLAP")
        if not all(HEX256.fullmatch(x or "") for x in
                   (self.native_zip_sha256, self.market_history_sha256)):
            raise ValueError("REQUIRE_VERIFIABLE_SOURCE_HASHES")
        if not (self.native_audit_passed and self.decision_boundary_passed):
            raise ValueError("FAILED_NATIVE_OR_LOOKAHEAD_GATE")
        if type(self.trade_count) is not int or self.trade_count < 1:
            raise ValueError("INVALID_NATIVE_TRADE_COUNT")
        vals=(self.pnl_net_usdt, self.stressed_net_usdt, self.max_drawdown_fraction)
        if not all(type(x) in (float, int) and math.isfinite(x) for x in vals):
            raise ValueError("INVALID_ECONOMIC_METRIC")
        if not 0 <= self.max_drawdown_fraction <= 1:
            raise ValueError("INVALID_DRAWDOWN")
        if self.stressed_net_usdt > self.pnl_net_usdt + 1e-6:
            raise ValueError("COST_STRESS_CANNOT_IMPROVE_PNL")


@dataclass(frozen=True)
class SelectorDecision:
    action: str
    family: str | None
    regime: str
    estimated_conservative_stressed_profit_per_trade: float | None
    reason: str

    @property
    def is_no_trade(self) -> bool:
        return self.action == "NO_TRADE"


def choose_validated_strategy(
    blocks: Sequence[CandidateBlock], *, decision_at: str, regime: str,
    minimum_trades_per_block: int = 20,
    max_drawdown_fraction: float = 0.05,
    minimum_blocks: int = 2,
    evidence_delay_hours: int = 8,
) -> SelectorDecision:
    """Select a historically OOS-profitable candidate or abstain.

    A family is eligible only when ALL its accepted historical blocks are
    nonoverlapping, sufficiently traded, native-audited, causal and profitable
    even under hypothetical execution cost stress. Uses the *worst block*
    mean stressed profit/trade to rank candidates. NO TRADE when uncertain.
    """
    if regime not in VALID_REGIMES:
        raise ValueError("UNKNOWN_CAUSAL_MARKET_REGIME")
    now = parse_utc(decision_at)
    if now.minute or now.second or now.microsecond or now.hour % 8:
        raise ValueError("SELECTOR_REQUIRES_EXACT_8H_UTC_BOUNDARY")
    if minimum_blocks < 2 or minimum_trades_per_block < 1:
        raise ValueError("INDEPENDENT_BLOCKS_REQUIRED")
    if not 0 < max_drawdown_fraction <= .20 or evidence_delay_hours < 1:
        raise ValueError("RISK_GUARD_INVALID")
    if regime == "high_volatility":
        return SelectorDecision("NO_TRADE", None, regime, None, "High volatility blocks new entries")
    admissible = TREND if regime in ("trend_up","trend_down") else RANGE
    cutoff = now - timedelta(hours=evidence_delay_hours)
    grouped: dict[str, list[CandidateBlock]] = {}
    for block in blocks:
        block.validate()
        if block.regime != regime or block.family not in admissible:
            continue
        if parse_utc(block.evaluated_until) > cutoff:
            continue  # MUST NOT look at future/out-of-sample results
        grouped.setdefault(block.family, []).append(block)

    winners: list[tuple[float, str]] = []
    for family, records in grouped.items():
        ordered = sorted(records, key=lambda b: b.evaluated_from)
        if len(ordered) < minimum_blocks:
            continue
        if any(parse_utc(a.evaluated_until) > parse_utc(b.evaluated_from)
               for a,b in zip(ordered, ordered[1:])):
            continue  # overlapping blocks are not independent
        # Insist on enough fresh evidence rather than extrapolate a strategy
        # that might have worked years ago into the present regime.
        if now - parse_utc(ordered[-1].evaluated_until) > timedelta(days=60):
            continue
        if any(b.trade_count < minimum_trades_per_block
               or b.stressed_net_usdt <= 0
               or b.pnl_net_usdt <= 0
               or b.max_drawdown_fraction > max_drawdown_fraction
               for b in ordered):
            continue
        score = min(b.stressed_net_usdt / b.trade_count for b in ordered)
        if score > 0:
            winners.append((score, family))

    if not winners:
        return SelectorDecision("NO_TRADE", None, regime, None,
                                "No independently validated family passes all after-cost / drawdown gates")
    # Deterministic tie-break, with no risk appetite added by tie order.
    score, family = sorted(winners, key=lambda item: (-item[0], item[1]))[0]
    return SelectorDecision("SELECT", family, regime, round(score, 8),
                            "Two or more non-overlapping native historical blocks qualify (research only)")


def parse_blocks(raw: Sequence[Mapping]) -> list[CandidateBlock]:
    if not isinstance(raw, list) or len(raw) > 10000:
        raise ValueError("INVALID_SCORECARD_LIST")
    fields=set(CandidateBlock.__dataclass_fields__)
    blocks=[]
    for item in raw:
        if not isinstance(item, dict) or set(item)!=fields:
            raise ValueError("SCORECARD_SCHEMA_MISMATCH")
        result=CandidateBlock(**item)
        result.validate()
        blocks.append(result)
    return blocks
