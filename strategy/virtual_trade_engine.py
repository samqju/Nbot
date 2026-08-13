"""Parallel virtual-trade engine and Phase 5.6 strategy laboratory."""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from config import (
    VIRTUAL_LAB_CATALOG_VERSION,
    VIRTUAL_LAB_MAX_ACTIVE,
    VIRTUAL_STRATEGY_VARIANT_ID,
    VIRTUAL_TRADES_PATH,
    LEARNING_RAW_SEGMENT_MAX_MB,
    LEARNING_RAW_RETAIN_SEGMENTS,
    VIRTUAL_TRADE_MAX_ACTIVE,
    VIRTUAL_TRADE_MAX_CANDLES,
    VIRTUAL_TRADE_TARGET_R,
)
from utils.jsonl_history import append_jsonl_line_bounded

from strategy.experiment_contract import (
    copy_experiment_context,
    validate_experiment_context,
)
from strategy.strategy_lab import (
    VirtualStrategyVariant,
    build_approved_variant_catalog,
    build_variant_experiment_context,
    estimate_round_trip_cost_r,
    validate_variant_catalog,
    variants_for_pattern,
)


class VirtualTradeEngine:
    def __init__(
        self,
        *,
        system_log=None,
        outcome_writer=None,
        runtime_store=None,
        environment: str | None = None,
        execution_mode: str | None = None,
        lab_enabled: bool = False,
        variant_catalog=None,
        catalog_version: str | None = None,
        max_active: int | None = None,
    ):
        self.system_log = system_log
        self.environment = (
            str(environment).strip().upper() if environment else None
        )
        self.execution_mode = (
            str(execution_mode).strip().upper() if execution_mode else None
        )
        self.outcome_writer = outcome_writer
        self.runtime_store = runtime_store
        self.path = Path(VIRTUAL_TRADES_PATH)
        self.lab_enabled = bool(lab_enabled)
        self.catalog_version = str(
            catalog_version or VIRTUAL_LAB_CATALOG_VERSION
        ).strip().upper()
        self.variant_catalog = validate_variant_catalog(
            variant_catalog
            or build_approved_variant_catalog(
                baseline_variant_id=VIRTUAL_STRATEGY_VARIANT_ID,
                baseline_target_r=VIRTUAL_TRADE_TARGET_R,
                baseline_max_candles=VIRTUAL_TRADE_MAX_CANDLES,
            )
        )
        self._baseline_variant = next(
            variant for variant in self.variant_catalog if variant.baseline
        )
        default_capacity = (
            VIRTUAL_LAB_MAX_ACTIVE
            if self.lab_enabled
            else VIRTUAL_TRADE_MAX_ACTIVE
        )
        self.max_active = int(
            default_capacity if max_active is None else max_active
        )
        if self.max_active <= 0:
            raise ValueError("VIRTUAL_TRADE_MAX_ACTIVE_INVALID")
        self.max_candles = VIRTUAL_TRADE_MAX_CANDLES
        self.target_r = VIRTUAL_TRADE_TARGET_R
        self._active: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._active_state_dirty = False
        self._runtime_enrollment_attempts = 0
        self._runtime_enrollments = 0
        self._runtime_capacity_rejections = 0
        self._runtime_closures = 0
        self._peak_active_experiments = 0
        self._cost_evidence_snapshot: dict | None = None
        self._restore_active_trades()
        self._peak_active_experiments = len(self._active)

    @staticmethod
    def _active_key(observation_id: str, variant_id: str) -> str:
        return f"{str(observation_id).strip()}::{str(variant_id).strip().upper()}"

    def enroll(self, candidate) -> bool:
        """Backward-compatible baseline-only enrollment."""
        before = int(
            getattr(self, "_runtime_capacity_rejections", 0)
        )
        created = self._enroll_variant(candidate, self._baseline_variant)
        rejected = (
            int(getattr(self, "_runtime_capacity_rejections", 0))
            - before
        )
        system_log = getattr(self, "system_log", None)
        if rejected and system_log:
            system_log.warning(
                "VIRTUAL_TRADE_CAPACITY_REACHED | "
                f"rejected={rejected} | active={self.active_count()} | "
                f"max_active={self.max_active}"
            )
        return created

    def enroll_all(self, candidates, *, persist: bool = True) -> int:
        """Enroll approved variants and persist the batch at most once."""
        created = 0
        capacity_rejections_before = int(
            getattr(self, "_runtime_capacity_rejections", 0)
        )
        for candidate in candidates:
            variants = (
                variants_for_pattern(
                    self.variant_catalog,
                    candidate.pattern,
                )
                if self.lab_enabled
                else (self._baseline_variant,)
            )
            for variant in variants:
                created += int(
                    self._enroll_variant(
                        candidate,
                        variant,
                        persist=False,
                    )
                )
        if created and persist:
            self.flush_active_state()
        rejected = (
            int(getattr(self, "_runtime_capacity_rejections", 0))
            - capacity_rejections_before
        )
        system_log = getattr(self, "system_log", None)
        if rejected and system_log:
            system_log.warning(
                "VIRTUAL_TRADE_CAPACITY_REACHED | "
                f"rejected={rejected} | active={self.active_count()} | "
                f"max_active={self.max_active}"
            )
        if self.system_log and created:
            self.system_log.info(
                "STRATEGY_LAB_ENROLLED | "
                f"experiments={created} | active={self.active_count()} | "
                f"catalog={self.catalog_version} | "
                f"enabled={str(self.lab_enabled).lower()} | "
                "paper_authority=UNCHANGED"
            )
        return created

    def _enroll_variant(
        self,
        candidate,
        variant: VirtualStrategyVariant,
        *,
        persist: bool = True,
    ) -> bool:
        if candidate.risk_plan is None:
            raise ValueError("VIRTUAL_TRADE_RISK_PLAN_MISSING")
        observation_id = candidate.observation_id
        active_key = self._active_key(
            observation_id,
            variant.variant_id,
        )
        with self._lock:
            self._runtime_enrollment_attempts = int(
                getattr(self, "_runtime_enrollment_attempts", 0)
            ) + 1
            if active_key in self._active:
                return False
            if len(self._active) >= self.max_active:
                self._runtime_capacity_rejections = int(
                    getattr(self, "_runtime_capacity_rejections", 0)
                ) + 1
                return False

            plan = candidate.risk_plan
            entry = float(plan.reference_price)
            base_risk = float(plan.stop_distance_price)
            risk = base_risk * variant.stop_multiplier
            if entry <= 0 or base_risk <= 0 or risk <= 0:
                raise ValueError("VIRTUAL_TRADE_RISK_PLAN_INVALID")

            if candidate.direction == "LONG":
                stop_price = entry - risk
                target_price = entry + variant.target_r * risk
            else:
                stop_price = entry + risk
                target_price = entry - variant.target_r * risk

            variant_context = build_variant_experiment_context(
                base_context=candidate.experiment_context,
                variant=variant,
                catalog_version=self.catalog_version,
            )
            self._active[active_key] = {
                "virtual_trade_id": active_key,
                "candidate_observation_id": observation_id,
                "symbol": candidate.symbol,
                "direction": candidate.direction,
                "pattern": candidate.pattern,
                "entry_price": entry,
                "stop_price": float(stop_price),
                "base_risk_distance": base_risk,
                "risk_distance": risk,
                "stop_multiplier": variant.stop_multiplier,
                "target_r": variant.target_r,
                "target_price": float(target_price),
                "max_candles": variant.max_candles,
                "candles_seen": 0,
                "mae_r": 0.0,
                "mfe_r": 0.0,
                "opened_at_ms": int(time.time() * 1000),
                "environment": self.environment,
                "execution_mode": self.execution_mode,
                "decision_batch_id": candidate.decision_batch_id,
                "market_event_id": candidate.market_event_id,
                "strategy_version": candidate.strategy_version,
                "strategy_variant_id": candidate.strategy_variant_id,
                "model_version": candidate.model_version,
                "outcome_variant_id": variant.variant_id,
                "outcome_type": (
                    "VIRTUAL_TRADE"
                    if variant.baseline
                    else "VIRTUAL_STRATEGY_VARIANT"
                ),
                "strategy_lab_catalog_version": self.catalog_version,
                "strategy_lab_family": variant.family,
                "strategy_lab_baseline": variant.baseline,
                "experiment_context": variant_context,
            }
            self._runtime_enrollments = int(
                getattr(self, "_runtime_enrollments", 0)
            ) + 1
            self._peak_active_experiments = max(
                int(getattr(self, "_peak_active_experiments", 0)),
                len(self._active),
            )
            self._active_state_dirty = True
            if persist:
                self._persist_active_locked()
        return True

    def on_candle(
        self,
        symbol: str,
        candle: tuple,
        *,
        persist: bool = True,
        closed_at_ms: int | None = None,
    ) -> list[dict]:
        _, high, low, close = candle
        effective_closed_at_ms = int(
            closed_at_ms if closed_at_ms is not None else time.time() * 1000
        )
        finished = []
        changed = False
        with self._lock:
            for key, trade in list(self._active.items()):
                if trade["symbol"] != symbol:
                    continue
                changed = True
                risk = float(trade["risk_distance"])
                entry = float(trade["entry_price"])
                if trade["direction"] == "LONG":
                    adverse = max(0.0, (entry - low) / risk)
                    favorable = max(0.0, (high - entry) / risk)
                    stop_hit = low <= trade["stop_price"]
                    target_hit = high >= trade["target_price"]
                else:
                    adverse = max(0.0, (high - entry) / risk)
                    favorable = max(0.0, (entry - low) / risk)
                    stop_hit = high >= trade["stop_price"]
                    target_hit = low <= trade["target_price"]

                trade["mae_r"] = max(float(trade["mae_r"]), adverse)
                trade["mfe_r"] = max(float(trade["mfe_r"]), favorable)
                trade["candles_seen"] = int(trade["candles_seen"]) + 1

                reason = None
                gross_exit_r = None
                exit_price = None
                if stop_hit and target_hit:
                    reason = "AMBIGUOUS_STOP_FIRST"
                    gross_exit_r = -1.0
                    exit_price = float(trade["stop_price"])
                elif stop_hit:
                    reason = "STOP_LOSS"
                    gross_exit_r = -1.0
                    exit_price = float(trade["stop_price"])
                elif target_hit:
                    reason = "TARGET"
                    gross_exit_r = float(trade["target_r"])
                    exit_price = float(trade["target_price"])
                elif trade["candles_seen"] >= int(trade["max_candles"]):
                    reason = "TIMEOUT"
                    exit_price = float(close)
                    gross_exit_r = (
                        (exit_price - entry) / risk
                        if trade["direction"] == "LONG"
                        else (entry - exit_price) / risk
                    )

                if reason is not None:
                    cost = self._estimate_cost(
                        trade=trade,
                        exit_price=exit_price,
                        closed_at_ms=effective_closed_at_ms,
                    )
                    net_exit_r = float(gross_exit_r) - float(
                        cost["total_cost_r"]
                    )
                    result = dict(trade)
                    result.update({
                        "closed_at_ms": effective_closed_at_ms,
                        "exit_reason": reason,
                        "exit_price": float(exit_price),
                        # Kept for the legacy virtual-trades file contract.
                        "exit_r": float(gross_exit_r),
                        "gross_exit_r": float(gross_exit_r),
                        "net_exit_r": float(net_exit_r),
                        "estimated_cost_r": float(
                            cost["total_cost_r"]
                        ),
                        "cost_breakdown": cost,
                        "gross_profitable": bool(gross_exit_r > 0),
                        "profitable": bool(net_exit_r > 0),
                        "label_basis": "NET_AFTER_ESTIMATED_COSTS",
                    })
                    finished.append(result)
                    del self._active[key]

            if finished:
                self._runtime_closures += len(finished)
            if changed:
                self._active_state_dirty = True
                if persist:
                    self._persist_active_locked()

        for result in finished:
            self._append(result)
            if self.outcome_writer:
                self.outcome_writer.append(
                    observation_id=result["candidate_observation_id"],
                    outcome_type=result["outcome_type"],
                    symbol=result["symbol"],
                    direction=result["direction"],
                    payload={
                        "pattern": result["pattern"],
                        "exit_reason": result["exit_reason"],
                        # Learning labels are after estimated costs.
                        "exit_r": result["net_exit_r"],
                        "gross_exit_r": result["gross_exit_r"],
                        "net_exit_r": result["net_exit_r"],
                        "estimated_cost_r": result[
                            "estimated_cost_r"
                        ],
                        "cost_breakdown": result["cost_breakdown"],
                        "label_basis": result["label_basis"],
                        "mae_r": result["mae_r"],
                        "mfe_r": result["mfe_r"],
                        "candles_seen": result["candles_seen"],
                        "profitable": result["profitable"],
                        "gross_profitable": result[
                            "gross_profitable"
                        ],
                        "outcome_variant_id": result.get(
                            "outcome_variant_id"
                        ),
                        "strategy_lab_catalog_version": result.get(
                            "strategy_lab_catalog_version"
                        ),
                        "strategy_lab_family": result.get(
                            "strategy_lab_family"
                        ),
                        "stop_multiplier": result.get(
                            "stop_multiplier"
                        ),
                        "target_r": result.get("target_r"),
                        "max_candles": result.get("max_candles"),
                    },
                    experiment_context=result.get(
                        "experiment_context"
                    ),
                    outcome_variant_id=result.get(
                        "outcome_variant_id"
                    ),
                )
        return finished

    def set_cost_evidence_snapshot(self, snapshot: dict | None) -> None:
        with self._lock:
            self._cost_evidence_snapshot = (
                copy.deepcopy(snapshot) if isinstance(snapshot, dict) else None
            )

    def oldest_active_opened_at_ms(self) -> int | None:
        with self._lock:
            values = [
                int(row.get("opened_at_ms", 0) or 0)
                for row in self._active.values()
                if int(row.get("opened_at_ms", 0) or 0) > 0
            ]
        return min(values) if values else None

    def _estimate_cost(
        self,
        *,
        trade: dict,
        exit_price: float,
        closed_at_ms: int,
    ) -> dict:
        context = trade.get("experiment_context") or {}
        cost_model = context.get("cost_model") or {}
        market_context = context.get("market_context") or {}
        liquidity = market_context.get("liquidity") or {}
        entry_spread_pct = liquidity.get("spread_pct")

        # on_candle already holds the engine lock while estimating costs, so
        # the snapshot setter cannot mutate/replace this reference concurrently.
        # Avoid deep-copying the full 200-symbol evidence snapshot per closure.
        evidence = self._cost_evidence_snapshot
        evidence = evidence if isinstance(evidence, dict) else {}
        spread_by_symbol = evidence.get("spread_by_symbol") or {}
        symbol = str(trade.get("symbol") or "").strip().upper()
        exit_spread_pct = (
            spread_by_symbol.get(symbol)
            if isinstance(spread_by_symbol, dict)
            else None
        )

        opened_at_ms = int(trade.get("opened_at_ms", 0) or 0)
        funding_complete = False
        funding_events = []
        try:
            coverage_start = int(
                evidence.get("funding_coverage_start_ms", -1)
            )
            coverage_end = int(
                evidence.get("funding_coverage_end_ms", -1)
            )
        except (TypeError, ValueError):
            coverage_start = -1
            coverage_end = -1
        if (
            evidence.get("funding_history_complete") is True
            and opened_at_ms > 0
            and coverage_start <= opened_at_ms
            and coverage_end >= int(closed_at_ms)
        ):
            funding_complete = True
            by_symbol = evidence.get("funding_events_by_symbol") or {}
            rows = by_symbol.get(symbol, []) if isinstance(by_symbol, dict) else []
            if isinstance(rows, list):
                funding_events = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and opened_at_ms < int(row.get("funding_time", 0) or 0)
                    <= int(closed_at_ms)
                ]

        return estimate_round_trip_cost_r(
            entry_price=float(trade["entry_price"]),
            exit_price=float(exit_price),
            risk_distance=float(trade["risk_distance"]),
            taker_fee_rate=float(
                cost_model.get("paper_taker_fee_rate", 0.0) or 0.0
            ),
            entry_slippage_pct=float(
                cost_model.get("paper_entry_slippage_pct", 0.0) or 0.0
            ),
            exit_slippage_pct=float(
                cost_model.get("paper_exit_slippage_pct", 0.0) or 0.0
            ),
            entry_spread_pct=entry_spread_pct,
            exit_spread_pct=exit_spread_pct,
            direction=trade.get("direction"),
            funding_events=funding_events,
            funding_history_complete=funding_complete,
        )

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def active_candidate_count(self) -> int:
        with self._lock:
            return len({
                row["candidate_observation_id"]
                for row in self._active.values()
            })

    def active_symbols(self) -> set[str]:
        """Return symbols that still require candle updates."""
        with self._lock:
            return {
                trade["symbol"]
                for trade in self._active.values()
                if trade.get("symbol")
            }

    def has_dirty_state(self) -> bool:
        with self._lock:
            return bool(self._active_state_dirty)

    def runtime_state_snapshot(self) -> list[dict]:
        """Copy active state for a combined learning-runtime checkpoint."""
        with self._lock:
            return [dict(trade) for trade in self._active.values()]

    def mark_runtime_state_persisted(self) -> None:
        with self._lock:
            self._active_state_dirty = False

    def flush_active_state(self) -> bool:
        """Persist deferred active-trade progress immediately."""
        with self._lock:
            if not self._active_state_dirty:
                return False
            self._persist_active_locked()
            return True

    def metrics_snapshot(self) -> dict:
        """Return in-memory virtual-trade telemetry."""
        with self._lock:
            active = len(self._active)
            return {
                "active_experiments": active,
                "active_candidates": len({
                    row["candidate_observation_id"]
                    for row in self._active.values()
                }),
                "max_active_experiments": int(self.max_active),
                "capacity_remaining": max(0, self.max_active - active),
                "capacity_utilization": (
                    active / self.max_active if self.max_active else 0.0
                ),
                "peak_active_experiments": int(
                    getattr(self, "_peak_active_experiments", active)
                ),
                "runtime_enrollment_attempts": int(
                    getattr(self, "_runtime_enrollment_attempts", 0)
                ),
                "runtime_enrollments": int(
                    getattr(self, "_runtime_enrollments", 0)
                ),
                "runtime_capacity_rejections": int(
                    getattr(self, "_runtime_capacity_rejections", 0)
                ),
                "runtime_closures": int(
                    getattr(self, "_runtime_closures", 0)
                ),
            }

    def _restore_active_trades(self) -> None:
        if self.runtime_store is None:
            return

        rows = self.runtime_store.get_section(
            "active_virtual_trades"
        )
        restored = {}
        for raw_trade in rows:
            trade = self._normalize_recovered_trade(raw_trade)
            self._validate_recovered_trade(trade)
            key = self._active_key(
                trade["candidate_observation_id"],
                trade["outcome_variant_id"],
            )
            if key in restored:
                raise RuntimeError(
                    "VIRTUAL_TRADE_RECOVERY_DUPLICATE_ID"
                )
            trade["virtual_trade_id"] = key
            restored[key] = trade

        if len(restored) > self.max_active:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_CAPACITY_EXCEEDED"
            )

        self._active = restored
        if self.system_log:
            self.system_log.info(
                "VIRTUAL_TRADES_RECOVERED | "
                f"experiments={len(restored)} | "
                f"candidates={self.active_candidate_count()}"
            )

    def _normalize_recovered_trade(self, raw_trade: dict) -> dict:
        if not isinstance(raw_trade, dict):
            raise RuntimeError("VIRTUAL_TRADE_RECOVERY_SCHEMA_INVALID")
        trade = dict(raw_trade)
        variant_id = str(
            trade.get("outcome_variant_id")
            or VIRTUAL_STRATEGY_VARIANT_ID
        ).strip().upper()
        trade.setdefault("outcome_variant_id", variant_id)
        trade.setdefault(
            "outcome_type",
            "VIRTUAL_TRADE"
            if variant_id == self._baseline_variant.variant_id
            else "VIRTUAL_STRATEGY_VARIANT",
        )
        trade.setdefault("base_risk_distance", trade.get("risk_distance"))
        trade.setdefault("stop_multiplier", 1.0)
        trade.setdefault("target_r", self.target_r)
        trade.setdefault("max_candles", self.max_candles)
        trade.setdefault(
            "strategy_lab_catalog_version",
            "LEGACY_PRE_PHASE5_6",
        )
        trade.setdefault("strategy_lab_family", "LEGACY_BASELINE")
        trade.setdefault(
            "strategy_lab_baseline",
            variant_id == self._baseline_variant.variant_id,
        )
        return trade

    @staticmethod
    def _validate_recovered_trade(trade: dict) -> None:
        required = {
            "candidate_observation_id",
            "symbol",
            "direction",
            "pattern",
            "entry_price",
            "stop_price",
            "risk_distance",
            "target_price",
            "target_r",
            "max_candles",
            "outcome_variant_id",
            "candles_seen",
            "mae_r",
            "mfe_r",
            "opened_at_ms",
        }
        if not isinstance(trade, dict) or not required.issubset(trade):
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_SCHEMA_INVALID"
            )
        if trade["direction"] not in {"LONG", "SHORT"}:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_DIRECTION_INVALID"
            )
        if float(trade["entry_price"]) <= 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_ENTRY_INVALID"
            )
        if float(trade["risk_distance"]) <= 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_RISK_INVALID"
            )
        if int(trade["candles_seen"]) < 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_CANDLES_INVALID"
            )
        if int(trade["max_candles"]) < 3:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_MAX_CANDLES_INVALID"
            )
        if not str(trade["outcome_variant_id"]).strip():
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_VARIANT_INVALID"
            )
        context = trade.get("experiment_context")
        if context is not None:
            try:
                validate_experiment_context(context)
            except ValueError as exc:
                raise RuntimeError(
                    "VIRTUAL_TRADE_RECOVERY_EXPERIMENT_INVALID"
                ) from exc

    def _persist_active_locked(self) -> None:
        if self.runtime_store is None:
            self._active_state_dirty = False
            return
        self.runtime_store.replace_section(
            "active_virtual_trades",
            [dict(trade) for trade in self._active.values()],
        )
        self._active_state_dirty = False

    def _append(self, row):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str)
        append_jsonl_line_bounded(
            self.path,
            line,
            max_bytes=int(LEARNING_RAW_SEGMENT_MAX_MB * 1024 * 1024),
            retain_segments=LEARNING_RAW_RETAIN_SEGMENTS,
            segment_tag="virtual-trades",
        )
