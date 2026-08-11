"""Continuous champion-challenger virtual decision testing for Phase 5.9."""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

from utils.jsonl_history import iter_jsonl_lines, logical_jsonl_exists
from typing import Any

from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.model_registry import ModelRegistry
from strategy.candidate import rank_candidates


SHADOW_DECISION_SCHEMA_VERSION = 1
SHADOW_DECISION_REPORT_SCHEMA_VERSION = 2


class ShadowDecisionTestingError(RuntimeError):
    pass


class ChampionChallengerShadowTester:
    """Create one authority-free decision snapshot per completed cycle."""

    def __init__(
        self,
        *,
        enabled: bool,
        environment: str,
        registry_path: str,
        default_champion_model_id: str,
        decisions_path: str,
        top_k: int = 3,
        system_log=None,
    ):
        self.enabled = bool(enabled)
        self.environment = str(environment or "").strip().upper()
        self.default_champion_model_id = str(
            default_champion_model_id or ""
        ).strip()
        self.decisions_path = Path(decisions_path)
        self.top_k = int(top_k)
        self.system_log = system_log
        if not self.environment:
            raise ValueError("SHADOW_DECISION_ENVIRONMENT_REQUIRED")
        if not self.default_champion_model_id:
            raise ValueError("SHADOW_DECISION_CHAMPION_REQUIRED")
        if not (1 <= self.top_k <= 10):
            raise ValueError("SHADOW_DECISION_TOP_K_INVALID")
        self.registry = ModelRegistry(
            path=registry_path,
            environment=self.environment,
            default_champion_model_id=self.default_champion_model_id,
        )
        self._scorers: dict[tuple[str, str, str], RegisteredModelArtifactScorer] = {}
        self._write_lock = threading.Lock()

    def record_cycle(
        self,
        *,
        candidates,
        decision_batch_id: str,
        market_event_id: str,
        candle_bucket: int,
        cycle_coverage: dict | None = None,
    ) -> dict | None:
        if not self.enabled:
            return None
        batch_id = str(decision_batch_id or "").strip()
        event_id = str(market_event_id or "").strip()
        if not batch_id or not event_id:
            raise ShadowDecisionTestingError(
                "SHADOW_DECISION_IDENTITY_INVALID"
            )

        self.registry.initialize()
        challenger = self.registry.activate_next_shadow_challenger()
        registry_document = self.registry.load()
        champion_model_id = str(
            registry_document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        challenger_model_id = (
            str(challenger.get("model_id")) if challenger else None
        )

        rule_ranked = rank_candidates(list(candidates))
        systems: dict[str, dict] = {
            "RULES": self._rule_system(rule_ranked),
        }
        systems["CHAMPION"] = self._model_or_rules_system(
            role="CHAMPION",
            model_id=champion_model_id,
            registry_document=registry_document,
            candidates=rule_ranked,
        )
        systems["CHALLENGER"] = self._challenger_system(
            challenger=challenger,
            candidates=rule_ranked,
        )

        document = {
            "schema_version": SHADOW_DECISION_SCHEMA_VERSION,
            "observation_type": "CHAMPION_CHALLENGER_DECISION",
            "observed_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "decision_batch_id": batch_id,
            "market_event_id": event_id,
            "candle_bucket": int(candle_bucket),
            "candidate_count": len(rule_ranked),
            "top_k": self.top_k,
            "cycle_coverage": dict(cycle_coverage or {}),
            "current_champion_model_id": champion_model_id,
            "current_challenger_model_id": challenger_model_id,
            "systems": systems,
            "comparisons": self._comparison_snapshot(systems),
            "runtime_effect": "NONE",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
        }
        self._append(document)
        if self.system_log:
            challenger_top = self._top_symbol(systems["CHALLENGER"])
            champion_top = self._top_symbol(systems["CHAMPION"])
            rules_top = self._top_symbol(systems["RULES"])
            self.system_log.info(
                "CHAMPION_CHALLENGER_DECISION_RECORDED | "
                f"batch={batch_id} | candidates={len(rule_ranked)} | "
                f"rules={rules_top} | champion={champion_top} | "
                f"challenger={challenger_top} | runtime_effect=NONE"
            )
        return document

    def _rule_system(self, candidates) -> dict:
        ranked = [
            self._selection(candidate, score=float(candidate.score))
            for candidate in candidates
        ]
        return self._system_document(
            model_id=self.default_champion_model_id,
            kind="RULES",
            status="AVAILABLE",
            ranked=ranked,
        )

    def _model_or_rules_system(
        self,
        *,
        role: str,
        model_id: str,
        registry_document: dict,
        candidates,
    ) -> dict:
        if model_id == self.default_champion_model_id:
            system = self._rule_system(candidates)
            system["role"] = role
            system["kind"] = "RULES"
            return system
        record = registry_document.get("models", {}).get(model_id)
        if not isinstance(record, dict):
            return self._unavailable_system(
                model_id=model_id,
                reason="CHAMPION_REGISTRY_RECORD_MISSING",
                role=role,
            )
        return self._score_model(
            role=role,
            record=record,
            candidates=candidates,
        )

    def _challenger_system(self, *, challenger, candidates) -> dict:
        if challenger is None:
            return self._unavailable_system(
                model_id=None,
                reason="NO_OFFLINE_VALIDATED_CHALLENGER",
                role="CHALLENGER",
            )
        return self._score_model(
            role="CHALLENGER",
            record=challenger,
            candidates=candidates,
        )

    def _score_model(self, *, role: str, record: dict, candidates) -> dict:
        model_id = str(record.get("model_id") or "").strip()
        artifact_path = str(record.get("artifact_path") or "").strip()
        checksum = str(
            record.get("artifact_checksum_sha256") or ""
        ).strip().lower()
        if not model_id or not artifact_path:
            return self._unavailable_system(
                model_id=model_id or None,
                reason="MODEL_ARTIFACT_REFERENCE_MISSING",
                role=role,
            )
        cache_key = (model_id, artifact_path, checksum)
        try:
            scorer = self._scorers.get(cache_key)
            if scorer is None:
                scorer = RegisteredModelArtifactScorer(
                    model_id=model_id,
                    artifact_path=artifact_path,
                    expected_checksum_sha256=checksum or None,
                )
                self._scorers[cache_key] = scorer
            probabilities = scorer.score_candidates(candidates)
            ranked_candidates = sorted(
                candidates,
                key=lambda candidate: (
                    -float(probabilities[candidate.observation_id]),
                    candidate.symbol,
                    candidate.direction,
                    candidate.observation_id,
                ),
            )
            ranked = [
                self._selection(
                    candidate,
                    score=float(probabilities[candidate.observation_id]),
                )
                for candidate in ranked_candidates
            ]
            return self._system_document(
                model_id=model_id,
                kind="MODEL",
                status="AVAILABLE",
                ranked=ranked,
                role=role,
            )
        except (RegisteredModelScoringError, KeyError, ValueError) as exc:
            if self.system_log:
                self.system_log.error(
                    "CHAMPION_CHALLENGER_MODEL_SCORING_FAILED | "
                    f"role={role} | model_id={model_id} | error={exc} | "
                    "runtime_effect=NONE"
                )
            return self._unavailable_system(
                model_id=model_id,
                reason=f"{type(exc).__name__}:{exc}",
                role=role,
            )

    def _system_document(
        self,
        *,
        model_id: str,
        kind: str,
        status: str,
        ranked: list[dict],
        role: str | None = None,
    ) -> dict:
        top_one = ranked[:1]
        top_k = ranked[: self.top_k]
        return {
            "role": role or kind,
            "model_id": model_id,
            "kind": kind,
            "status": status,
            "ranked_candidate_count": len(ranked),
            "top_one": top_one,
            "top_k": top_k,
            "runtime_effect": "NONE",
        }

    @staticmethod
    def _selection(candidate, *, score: float) -> dict:
        context = candidate.experiment_context or {}
        market_context = context.get("market_context") or {}
        return {
            "candidate_observation_id": candidate.observation_id,
            "symbol": candidate.symbol,
            "direction": candidate.direction,
            "pattern": candidate.pattern,
            "score": float(score),
            "rule_score": float(candidate.score),
            "decision_batch_id": candidate.decision_batch_id,
            "market_event_id": candidate.market_event_id,
            "market_context": market_context,
        }

    @staticmethod
    def _unavailable_system(
        *, model_id: str | None, reason: str, role: str
    ) -> dict:
        return {
            "role": role,
            "model_id": model_id,
            "kind": "MODEL" if model_id else "NONE",
            "status": "UNAVAILABLE",
            "reason": reason,
            "ranked_candidate_count": 0,
            "top_one": [],
            "top_k": [],
            "runtime_effect": "NONE",
        }

    @staticmethod
    def _selection_ids(system: dict, key: str) -> tuple[str, ...]:
        return tuple(
            str(row.get("candidate_observation_id"))
            for row in system.get(key, [])
        )

    def _comparison_snapshot(self, systems: dict) -> dict:
        comparisons = {}
        for left, right in (
            ("CHALLENGER", "CHAMPION"),
            ("CHALLENGER", "RULES"),
            ("CHAMPION", "RULES"),
        ):
            left_system = systems[left]
            right_system = systems[right]
            available = (
                left_system.get("status") == "AVAILABLE"
                and right_system.get("status") == "AVAILABLE"
            )
            name = f"{left}_VS_{right}"
            if not available:
                comparisons[name] = {
                    "available": False,
                    "top_one_agreement": None,
                    "top_k_exact_agreement": None,
                    "top_k_overlap_count": None,
                }
                continue
            left_one = self._selection_ids(left_system, "top_one")
            right_one = self._selection_ids(right_system, "top_one")
            left_k = self._selection_ids(left_system, "top_k")
            right_k = self._selection_ids(right_system, "top_k")
            comparisons[name] = {
                "available": True,
                "top_one_agreement": left_one == right_one,
                "top_k_exact_agreement": left_k == right_k,
                "top_k_overlap_count": len(set(left_k) & set(right_k)),
            }
        return comparisons

    def _append(self, document: dict) -> None:
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(document, sort_keys=True, default=str)
        with self._write_lock:
            descriptor = os.open(
                self.decisions_path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(descriptor, (line + "\n").encode("utf-8"))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    @staticmethod
    def _top_symbol(system: dict) -> str:
        rows = system.get("top_one") or []
        if not rows:
            return "NONE"
        return f"{rows[0]['symbol']}:{rows[0]['direction']}"


class ShadowDecisionEvaluator:
    """Join virtual outcomes to decision snapshots and summarize evidence."""

    def __init__(
        self,
        *,
        decisions_path: str,
        outcomes_path: str,
        report_path: str,
        outcome_type: str = "VIRTUAL_TRADE",
        challenger_model_id: str | None = None,
        champion_model_id: str | None = None,
        recent_event_window: int = 30,
    ):
        self.decisions_path = Path(decisions_path)
        self.outcomes_path = Path(outcomes_path)
        self.report_path = Path(report_path)
        self.outcome_type = str(outcome_type).strip().upper()
        self.challenger_model_id = (
            str(challenger_model_id).strip()
            if challenger_model_id
            else None
        )
        self.champion_model_id = (
            str(champion_model_id).strip()
            if champion_model_id
            else None
        )
        self.recent_event_window = int(recent_event_window)
        if not (1 <= self.recent_event_window <= 10000):
            raise ValueError("SHADOW_DECISION_RECENT_WINDOW_INVALID")

    def evaluate(self) -> dict:
        issues = Counter()
        decisions = self._read_jsonl(
            self.decisions_path, issues, "decision"
        )
        outcomes = self._index_outcomes(
            self._read_jsonl(self.outcomes_path, issues, "outcome"),
            issues,
        )
        valid_decisions = self._validate_decisions(decisions, issues)
        policies = {}
        for system_name in ("RULES", "CHAMPION", "CHALLENGER"):
            policies[system_name] = {}
            for policy_name, key in (("TOP_ONE", "top_one"), ("TOP_K", "top_k")):
                records = self._completed_policy_records(
                    valid_decisions,
                    outcomes,
                    system_name=system_name,
                    selection_key=key,
                )
                policies[system_name][policy_name] = {
                    "summary": self._summary(records),
                    "regimes": self._regime_breakdown(records),
                }

        pairwise = {}
        for left, right in (
            ("CHALLENGER", "CHAMPION"),
            ("CHALLENGER", "RULES"),
            ("CHAMPION", "RULES"),
        ):
            pairwise[f"{left}_VS_{right}"] = {}
            for policy_name, key in (("TOP_ONE", "top_one"), ("TOP_K", "top_k")):
                pairwise[f"{left}_VS_{right}"][policy_name] = (
                    self._pairwise(
                        valid_decisions,
                        outcomes,
                        left=left,
                        right=right,
                        selection_key=key,
                    )
                )

        completed_challenger = policies["CHALLENGER"]["TOP_ONE"][
            "summary"
        ]["completed_raw_batches"]
        status = (
            "EMPTY"
            if not valid_decisions
            else "COLLECTING"
            if completed_challenger == 0
            else "EVALUATED"
        )
        report = {
            "schema_version": SHADOW_DECISION_REPORT_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "phase": "5.9",
            "status": status,
            "outcome_type": self.outcome_type,
            "filters": {
                "challenger_model_id": self.challenger_model_id,
                "champion_model_id": self.champion_model_id,
            },
            "recent_event_window": self.recent_event_window,
            "decision_rows_read": len(decisions),
            "valid_decision_cycles": len(valid_decisions),
            "outcome_rows_indexed": len(outcomes),
            "policies": policies,
            "pairwise": pairwise,
            "evidence_policy": {
                "promotion_basis": "INDEPENDENT_MARKET_EVENTS",
                "top_one_and_top_k_separate": True,
                "top_k_portfolio_weighting": "EQUAL_WEIGHT",
                "incomplete_portfolios_excluded": True,
                "return_basis": "NET_AFTER_ESTIMATED_COSTS",
            },
            "runtime_effect": "NONE",
            "paper_authority": "UNCHANGED",
            "promotion_authority": "NONE",
            "real_order_authority": "NONE",
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }
        self._write_json_atomic(report)
        return report

    def _completed_policy_records(
        self,
        decisions: list[dict],
        outcomes: dict[str, dict],
        *,
        system_name: str,
        selection_key: str,
    ) -> list[dict]:
        records = []
        for decision in decisions:
            system = decision["systems"].get(system_name, {})
            if system.get("status") != "AVAILABLE":
                continue
            selections = system.get(selection_key) or []
            if not selections:
                continue
            candidate_outcomes = []
            for selection in selections:
                outcome = outcomes.get(
                    str(selection.get("candidate_observation_id") or "")
                )
                if outcome is None:
                    candidate_outcomes = []
                    break
                candidate_outcomes.append(outcome)
            if not candidate_outcomes:
                continue
            count = len(candidate_outcomes)
            records.append(
                {
                    "decision_batch_id": decision["decision_batch_id"],
                    "market_event_id": decision["market_event_id"],
                    "observed_at_ms": decision["observed_at_ms"],
                    "selection_ids": tuple(
                        row["candidate_observation_id"]
                        for row in selections
                    ),
                    "net_r": sum(row["net_r"] for row in candidate_outcomes) / count,
                    "gross_r": sum(row["gross_r"] for row in candidate_outcomes) / count,
                    "cost_r": sum(row["cost_r"] for row in candidate_outcomes) / count,
                    "profitable": (
                        sum(row["net_r"] for row in candidate_outcomes) / count
                    ) > 0,
                    "regime": self._selection_regime(selections),
                }
            )
        return sorted(
            records,
            key=lambda row: (
                int(row["observed_at_ms"]),
                row["decision_batch_id"],
            ),
        )

    def _pairwise(
        self,
        decisions: list[dict],
        outcomes: dict[str, dict],
        *,
        left: str,
        right: str,
        selection_key: str,
    ) -> dict:
        left_records = {
            row["decision_batch_id"]: row
            for row in self._completed_policy_records(
                decisions,
                outcomes,
                system_name=left,
                selection_key=selection_key,
            )
        }
        right_records = {
            row["decision_batch_id"]: row
            for row in self._completed_policy_records(
                decisions,
                outcomes,
                system_name=right,
                selection_key=selection_key,
            )
        }
        paired = []
        for batch_id in sorted(set(left_records) & set(right_records)):
            left_row = left_records[batch_id]
            right_row = right_records[batch_id]
            paired.append(
                {
                    "batch_id": batch_id,
                    "market_event_id": left_row["market_event_id"],
                    "observed_at_ms": left_row["observed_at_ms"],
                    "left_r": left_row["net_r"],
                    "right_r": right_row["net_r"],
                    "agreement": (
                        left_row["selection_ids"]
                        == right_row["selection_ids"]
                    ),
                }
            )
        independent = self._group_pairwise_by_event(paired)
        disagreements = [row for row in independent if not row["agreement"]]
        basis = disagreements if disagreements else independent
        left_average = self._average([row["left_r"] for row in basis])
        right_average = self._average([row["right_r"] for row in basis])
        left_win_rate = (
            sum(row["left_r"] > 0 for row in basis) / len(basis)
            if basis else None
        )
        right_win_rate = (
            sum(row["right_r"] > 0 for row in basis) / len(basis)
            if basis else None
        )
        return {
            "raw_completed_pairs": len(paired),
            "independent_market_event_pairs": len(independent),
            "agreement_events": sum(row["agreement"] for row in independent),
            "disagreement_events": len(disagreements),
            "comparison_basis": (
                "DISAGREEMENTS" if disagreements else "ALL_PAIRED_EVENTS"
            ),
            "left_average_net_r": left_average,
            "right_average_net_r": right_average,
            "left_minus_right_average_net_r": (
                None
                if left_average is None or right_average is None
                else left_average - right_average
            ),
            "left_win_rate": left_win_rate,
            "right_win_rate": right_win_rate,
            "left_minus_right_win_rate": (
                None
                if left_win_rate is None or right_win_rate is None
                else left_win_rate - right_win_rate
            ),
            "left_better_events": sum(
                row["left_r"] > row["right_r"] for row in basis
            ),
            "right_better_events": sum(
                row["right_r"] > row["left_r"] for row in basis
            ),
            "tie_events": sum(
                row["right_r"] == row["left_r"] for row in basis
            ),
            "promotion_basis": "INDEPENDENT_MARKET_EVENTS",
        }

    def _summary(self, records: list[dict]) -> dict:
        independent = self._group_records_by_event(records)
        returns = [row["net_r"] for row in independent]
        gross = [row["gross_r"] for row in independent]
        costs = [row["cost_r"] for row in independent]
        recent = independent[-self.recent_event_window :]
        recent_returns = [row["net_r"] for row in recent]
        return {
            "completed_raw_batches": len(records),
            "independent_market_events": len(independent),
            "average_net_r": self._average(returns),
            "total_net_r": sum(returns) if returns else None,
            "average_gross_r": self._average(gross),
            "average_estimated_cost_r": self._average(costs),
            "win_rate": (
                sum(value > 0 for value in returns) / len(returns)
                if returns else None
            ),
            "recent_event_window": self.recent_event_window,
            "recent_event_count": len(recent),
            "recent_average_net_r": self._average(recent_returns),
            "recent_win_rate": (
                sum(value > 0 for value in recent_returns)
                / len(recent_returns)
                if recent_returns else None
            ),
            "maximum_drawdown_r": self._max_drawdown(returns),
            "maximum_losing_streak": self._max_losing_streak(returns),
            "evidence_basis": "INDEPENDENT_MARKET_EVENTS",
        }

    @staticmethod
    def _group_records_by_event(records: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in records:
            grouped[row["market_event_id"]].append(row)
        result = []
        for event_id, rows in grouped.items():
            rows = sorted(rows, key=lambda row: row["observed_at_ms"])
            result.append(
                {
                    "market_event_id": event_id,
                    "observed_at_ms": rows[0]["observed_at_ms"],
                    "net_r": sum(row["net_r"] for row in rows) / len(rows),
                    "gross_r": sum(row["gross_r"] for row in rows) / len(rows),
                    "cost_r": sum(row["cost_r"] for row in rows) / len(rows),
                }
            )
        return sorted(result, key=lambda row: (row["observed_at_ms"], row["market_event_id"]))

    @staticmethod
    def _group_pairwise_by_event(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["market_event_id"]].append(row)
        result = []
        for event_id, event_rows in grouped.items():
            result.append(
                {
                    "market_event_id": event_id,
                    "observed_at_ms": min(
                        int(row["observed_at_ms"]) for row in event_rows
                    ),
                    "left_r": sum(row["left_r"] for row in event_rows) / len(event_rows),
                    "right_r": sum(row["right_r"] for row in event_rows) / len(event_rows),
                    "agreement": all(row["agreement"] for row in event_rows),
                }
            )
        return sorted(
            result,
            key=lambda row: (row["observed_at_ms"], row["market_event_id"]),
        )

    def _regime_breakdown(self, records: list[dict]) -> dict:
        dimensions = defaultdict(lambda: defaultdict(list))
        for row in records:
            for dimension, value in row["regime"].items():
                dimensions[dimension][value].append(row)
        result = {}
        for dimension, groups in sorted(dimensions.items()):
            result[dimension] = {
                value: self._summary(rows)
                for value, rows in sorted(groups.items())
            }
        return result

    @staticmethod
    def _selection_regime(selections: list[dict]) -> dict:
        def combined(values):
            normalized = {str(value or "NOT_AVAILABLE").upper() for value in values}
            return next(iter(normalized)) if len(normalized) == 1 else "MIXED"

        contexts = [row.get("market_context") or {} for row in selections]
        return {
            "market_regime": combined(
                context.get("market_regime") for context in contexts
            ),
            "trend_regime": combined(
                context.get("trend_regime") for context in contexts
            ),
            "volatility_regime": combined(
                context.get("volatility_regime") for context in contexts
            ),
            "direction": combined(row.get("direction") for row in selections),
            "pattern": combined(row.get("pattern") for row in selections),
        }

    def _index_outcomes(self, rows: list[dict], issues: Counter) -> dict[str, dict]:
        indexed = {}
        duplicate = set()
        for row in rows:
            if row.get("observation_type") != "CANDIDATE_OUTCOME":
                continue
            if str(row.get("outcome_type") or "").upper() != self.outcome_type:
                continue
            candidate_id = str(row.get("candidate_observation_id") or "").strip()
            payload = row.get("payload")
            if not candidate_id or not isinstance(payload, dict):
                issues["outcome_identity_or_payload_invalid"] += 1
                continue
            net_r = self._number(
                payload.get("net_exit_r", payload.get("exit_r"))
            )
            if net_r is None:
                issues["outcome_net_r_missing"] += 1
                continue
            gross_r = self._number(payload.get("gross_exit_r"))
            cost_r = self._number(payload.get("estimated_cost_r"))
            if gross_r is None:
                gross_r = net_r + (cost_r or 0.0)
            if cost_r is None:
                cost_r = gross_r - net_r
            if candidate_id in indexed:
                duplicate.add(candidate_id)
                issues["duplicate_candidate_outcome"] += 1
                continue
            indexed[candidate_id] = {
                "net_r": net_r,
                "gross_r": gross_r,
                "cost_r": cost_r,
            }
        for candidate_id in duplicate:
            indexed.pop(candidate_id, None)
        return indexed

    def _validate_decisions(self, rows: list[dict], issues: Counter) -> list[dict]:
        valid = []
        seen = set()
        for row in rows:
            if row.get("observation_type") != "CHAMPION_CHALLENGER_DECISION":
                continue
            if row.get("runtime_effect") != "NONE":
                issues["decision_runtime_effect_invalid"] += 1
                continue
            batch_id = str(row.get("decision_batch_id") or "").strip()
            event_id = str(row.get("market_event_id") or "").strip()
            if not batch_id or not event_id or batch_id in seen:
                issues["decision_identity_invalid_or_duplicate"] += 1
                continue
            if not isinstance(row.get("systems"), dict):
                issues["decision_systems_invalid"] += 1
                continue
            systems = row["systems"]
            if self.challenger_model_id is not None:
                challenger_id = str(
                    (systems.get("CHALLENGER") or {}).get("model_id")
                    or row.get("current_challenger_model_id")
                    or ""
                ).strip()
                if challenger_id != self.challenger_model_id:
                    issues["decision_filtered_other_challenger"] += 1
                    continue
            if self.champion_model_id is not None:
                champion_id = str(
                    (systems.get("CHAMPION") or {}).get("model_id")
                    or row.get("current_champion_model_id")
                    or ""
                ).strip()
                if champion_id != self.champion_model_id:
                    issues["decision_filtered_other_champion"] += 1
                    continue
            try:
                row["observed_at_ms"] = int(row["observed_at_ms"])
            except (KeyError, TypeError, ValueError):
                issues["decision_timestamp_invalid"] += 1
                continue
            seen.add(batch_id)
            valid.append(row)
        return sorted(valid, key=lambda row: (row["observed_at_ms"], row["decision_batch_id"]))

    @staticmethod
    def _read_jsonl(path: Path, issues: Counter, prefix: str) -> list[dict]:
        if not logical_jsonl_exists(path):
            issues[f"{prefix}_file_missing"] += 1
            return []
        rows = []
        for line in iter_jsonl_lines(path):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                issues[f"{prefix}_malformed_json"] += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                issues[f"{prefix}_row_not_object"] += 1
        return rows

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _average(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _max_drawdown(returns: list[float]) -> float | None:
        if not returns:
            return None
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for value in returns:
            equity += float(value)
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    @staticmethod
    def _max_losing_streak(returns: list[float]) -> int:
        maximum = 0
        current = 0
        for value in returns:
            if value <= 0:
                current += 1
                maximum = max(maximum, current)
            else:
                current = 0
        return maximum

    def _write_json_atomic(self, document: dict) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.report_path.name}.",
            suffix=".tmp",
            dir=str(self.report_path.parent),
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.report_path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
