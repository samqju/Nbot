"""Approved Phase 5.6 virtual strategy laboratory.

The laboratory is research-only. It creates deterministic virtual exit-policy
variants for already-valid strategy candidates. It cannot rank candidates,
change paper-trade selection, alter risk limits, or submit exchange orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from strategy.experiment_contract import (
    copy_experiment_context,
    validate_experiment_context,
)


STRATEGY_LAB_SCHEMA_VERSION = 1

_BREAKOUT_PATTERNS = frozenset({
    "PULLBACK_CONTINUATION",
    "TRIANGLE_BREAKOUT",
    "RANGE_BREAKOUT",
})
_REVERSION_PATTERNS = frozenset({
    "MEAN_REVERSION",
    "FAKE_BREAKOUT",
    "LIQUIDITY_SWEEP",
    "SUPPORT_BOUNCE",
    "RESISTANCE_REJECTION",
    "MOMENTUM_EXHAUSTION",
    "TREND_REVERSAL",
})


@dataclass(frozen=True)
class VirtualStrategyVariant:
    variant_id: str
    family: str
    stop_multiplier: float
    target_r: float
    max_candles: int
    patterns: frozenset[str] | None = None
    baseline: bool = False

    def __post_init__(self) -> None:
        variant_id = str(self.variant_id or "").strip().upper()
        family = str(self.family or "").strip().upper()
        if not variant_id:
            raise ValueError("STRATEGY_LAB_VARIANT_ID_INVALID")
        if not family:
            raise ValueError("STRATEGY_LAB_FAMILY_INVALID")
        if not (0.25 <= float(self.stop_multiplier) <= 3.0):
            raise ValueError("STRATEGY_LAB_STOP_MULTIPLIER_INVALID")
        if not (0.25 <= float(self.target_r) <= 10.0):
            raise ValueError("STRATEGY_LAB_TARGET_R_INVALID")
        if not (3 <= int(self.max_candles) <= 500):
            raise ValueError("STRATEGY_LAB_MAX_CANDLES_INVALID")
        patterns = self.patterns
        if patterns is not None:
            patterns = frozenset(
                str(pattern).strip().upper()
                for pattern in patterns
                if str(pattern).strip()
            )
            if not patterns:
                raise ValueError("STRATEGY_LAB_PATTERNS_INVALID")
        object.__setattr__(self, "variant_id", variant_id)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "stop_multiplier", float(self.stop_multiplier))
        object.__setattr__(self, "target_r", float(self.target_r))
        object.__setattr__(self, "max_candles", int(self.max_candles))
        object.__setattr__(self, "patterns", patterns)
        object.__setattr__(self, "baseline", bool(self.baseline))

    def applies_to(self, pattern: str) -> bool:
        normalized = str(pattern or "").strip().upper()
        return self.patterns is None or normalized in self.patterns

    def as_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "family": self.family,
            "stop_multiplier": self.stop_multiplier,
            "target_r": self.target_r,
            "max_candles": self.max_candles,
            "patterns": (
                sorted(self.patterns) if self.patterns is not None else "ALL"
            ),
            "baseline": self.baseline,
        }


def build_approved_variant_catalog(
    *,
    baseline_variant_id: str,
    baseline_target_r: float,
    baseline_max_candles: int,
) -> tuple[VirtualStrategyVariant, ...]:
    """Return the small, fixed Phase 5.6 experiment catalog."""
    catalog = (
        VirtualStrategyVariant(
            variant_id=baseline_variant_id,
            family="BASELINE",
            stop_multiplier=1.0,
            target_r=baseline_target_r,
            max_candles=baseline_max_candles,
            patterns=None,
            baseline=True,
        ),
        VirtualStrategyVariant(
            variant_id="VIRTUAL_FAST_TIGHT_1_5R_12C_V1",
            family="FAST_TIGHT",
            stop_multiplier=0.75,
            target_r=1.5,
            max_candles=12,
            patterns=None,
        ),
        VirtualStrategyVariant(
            variant_id="VIRTUAL_BREAKOUT_WIDE_2_5R_36C_V1",
            family="BREAKOUT_WIDE",
            stop_multiplier=1.25,
            target_r=2.5,
            max_candles=36,
            patterns=_BREAKOUT_PATTERNS,
        ),
        VirtualStrategyVariant(
            variant_id="VIRTUAL_REVERSION_FAST_1_25R_8C_V1",
            family="REVERSION_FAST",
            stop_multiplier=0.75,
            target_r=1.25,
            max_candles=8,
            patterns=_REVERSION_PATTERNS,
        ),
    )
    validate_variant_catalog(catalog)
    return catalog


def validate_variant_catalog(
    variants: Iterable[VirtualStrategyVariant],
) -> tuple[VirtualStrategyVariant, ...]:
    rows = tuple(variants)
    if not rows:
        raise ValueError("STRATEGY_LAB_CATALOG_EMPTY")
    ids = [row.variant_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("STRATEGY_LAB_VARIANT_ID_DUPLICATE")
    if sum(1 for row in rows if row.baseline) != 1:
        raise ValueError("STRATEGY_LAB_BASELINE_COUNT_INVALID")
    return rows


def variants_for_pattern(
    catalog: Iterable[VirtualStrategyVariant],
    pattern: str,
) -> tuple[VirtualStrategyVariant, ...]:
    rows = tuple(row for row in catalog if row.applies_to(pattern))
    if not any(row.baseline for row in rows):
        raise RuntimeError("STRATEGY_LAB_BASELINE_NOT_APPLICABLE")
    return rows


def build_variant_experiment_context(
    *,
    base_context: dict | None,
    variant: VirtualStrategyVariant,
    catalog_version: str,
) -> dict | None:
    """Create a detached context describing the exact virtual variant."""
    context = copy_experiment_context(base_context)
    if context is None:
        return None
    context["virtual_policy"] = {
        "schema_version": 2,
        "variant_id": variant.variant_id,
        "family": variant.family,
        "base_stop_multiplier": variant.stop_multiplier,
        "stop_r": 1.0,
        "target_r": variant.target_r,
        "max_candles": variant.max_candles,
        "ambiguous_touch_policy": "STOP_FIRST",
        "label_basis": "NET_AFTER_ESTIMATED_COSTS",
    }
    cost_model = dict(context.get("cost_model") or {})
    cost_model.update({
        "fees_included_in_virtual_outcome": True,
        "entry_slippage_included_in_virtual_outcome": True,
        "exit_slippage_included_in_virtual_outcome": True,
        "spread_included_in_virtual_outcome": True,
        "funding_included": True,
        "spread_evidence_source": (
            "MEASURED_ENTRY_AND_EXIT_BOOK_TICKER"
        ),
        "funding_evidence_source": "BINANCE_FUNDING_RATE_HISTORY",
        "complete_cost_evidence_required_for_training": True,
    })
    context["cost_model"] = cost_model
    context["strategy_lab"] = {
        "schema_version": STRATEGY_LAB_SCHEMA_VERSION,
        "catalog_version": str(catalog_version).strip().upper(),
        "research_only": True,
        "paper_authority": "UNCHANGED",
        "variant": variant.as_dict(),
    }
    validate_experiment_context(context)
    return context


def estimate_round_trip_cost_r(
    *,
    entry_price: float,
    exit_price: float,
    risk_distance: float,
    taker_fee_rate: float,
    entry_slippage_pct: float,
    exit_slippage_pct: float,
    entry_spread_pct: float | None = None,
    exit_spread_pct: float | None = None,
    direction: str | None = None,
    funding_events: list[dict] | None = None,
    funding_history_complete: bool = False,
) -> dict:
    """Estimate round-trip costs per unit in R multiples.

    Fees and configured slippage are deterministic policy inputs. Spread uses
    measured book-ticker observations at entry and exit, charging half of each
    observed spread at the corresponding market fill. Funding uses actual
    Binance funding-history rows that occurred while the virtual position was
    open. Positive funding is a cost to LONG and a credit to SHORT.
    """
    entry = float(entry_price)
    exit_value = float(exit_price)
    risk = float(risk_distance)
    fee_rate = float(taker_fee_rate)
    entry_slippage_rate = float(entry_slippage_pct) / 100.0
    exit_slippage_rate = float(exit_slippage_pct) / 100.0
    if min(entry, exit_value, risk) <= 0:
        raise ValueError("STRATEGY_LAB_COST_PRICE_INVALID")
    if min(fee_rate, entry_slippage_rate, exit_slippage_rate) < 0:
        raise ValueError("STRATEGY_LAB_COST_RATE_INVALID")

    entry_fee_r = (entry * fee_rate) / risk
    exit_fee_r = (exit_value * fee_rate) / risk
    entry_slippage_r = (entry * entry_slippage_rate) / risk
    exit_slippage_r = (exit_value * exit_slippage_rate) / risk

    entry_spread_r = None
    exit_spread_r = None
    spread_r = None
    try:
        entry_spread_value = float(entry_spread_pct)
        exit_spread_value = float(exit_spread_pct)
    except (TypeError, ValueError):
        entry_spread_value = None
        exit_spread_value = None
    if (
        entry_spread_value is not None
        and exit_spread_value is not None
        and entry_spread_value >= 0
        and exit_spread_value >= 0
    ):
        entry_spread_r = (
            entry * (entry_spread_value / 100.0) * 0.5
        ) / risk
        exit_spread_r = (
            exit_value * (exit_spread_value / 100.0) * 0.5
        ) / risk
        spread_r = entry_spread_r + exit_spread_r

    side = str(direction or "").strip().upper()
    funding_r = None
    normalized_funding_events = []
    if funding_history_complete and side in {"LONG", "SHORT"}:
        funding_r = 0.0
        side_sign = 1.0 if side == "LONG" else -1.0
        for event in funding_events or []:
            if not isinstance(event, dict):
                continue
            try:
                funding_rate = float(event["funding_rate"])
                mark_price = float(event["mark_price"])
                funding_time = int(event["funding_time"])
            except (KeyError, TypeError, ValueError):
                continue
            if mark_price <= 0 or funding_time <= 0:
                continue
            event_cost_r = side_sign * (
                mark_price * funding_rate
            ) / risk
            funding_r += event_cost_r
            normalized_funding_events.append({
                "funding_time": funding_time,
                "funding_rate": funding_rate,
                "mark_price": mark_price,
                "rate_type": str(event.get("rate_type") or "Regular"),
                "cost_r": event_cost_r,
            })

    known_total = (
        entry_fee_r
        + exit_fee_r
        + entry_slippage_r
        + exit_slippage_r
        + (spread_r if spread_r is not None else 0.0)
        + (funding_r if funding_r is not None else 0.0)
    )
    if spread_r is not None and funding_r is not None:
        completeness = (
            "FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3"
        )
    elif spread_r is not None:
        completeness = "FEES_SLIPPAGE_SPREAD_ONLY"
    elif funding_r is not None:
        completeness = "FEES_SLIPPAGE_FUNDING_ONLY"
    else:
        completeness = "FEES_AND_CONFIGURED_SLIPPAGE_ONLY"

    return {
        "entry_fee_r": entry_fee_r,
        "exit_fee_r": exit_fee_r,
        "entry_slippage_r": entry_slippage_r,
        "exit_slippage_r": exit_slippage_r,
        "entry_spread_pct": entry_spread_value,
        "exit_spread_pct": exit_spread_value,
        "entry_spread_r": entry_spread_r,
        "exit_spread_r": exit_spread_r,
        "spread_r": spread_r,
        "funding_r": funding_r,
        "funding_event_count": len(normalized_funding_events),
        "funding_events": normalized_funding_events,
        "total_cost_r": known_total,
        "cost_completeness": completeness,
    }
