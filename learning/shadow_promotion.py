"""Phase 4.7 shadow-outcome evaluation and advisory promotion gate."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss


class ShadowPromotionError(RuntimeError):
    pass


class ShadowPromotionEvaluator:
    """Compare completed rule and shadow selections without activation."""

    def __init__(
        self,
        *,
        predictions_path,
        outcomes_path,
        model_evaluation_report_path,
        report_path,
        outcome_type="VIRTUAL_TRADE",
        min_matched_candidates=200,
        min_paired_batches=50,
        min_avg_r_lift=0.10,
        max_win_rate_drop=0.02,
        max_brier_score=0.25,
        max_calibration_gap=0.10,
        max_feature_psi=0.25,
    ):
        self.predictions_path = Path(predictions_path)
        self.outcomes_path = Path(outcomes_path)
        self.model_evaluation_report_path = Path(
            model_evaluation_report_path
        )
        self.report_path = Path(report_path)
        self.outcome_type = str(outcome_type).strip().upper()
        self.min_matched_candidates = int(min_matched_candidates)
        self.min_paired_batches = int(min_paired_batches)
        self.min_avg_r_lift = float(min_avg_r_lift)
        self.max_win_rate_drop = float(max_win_rate_drop)
        self.max_brier_score = float(max_brier_score)
        self.max_calibration_gap = float(max_calibration_gap)
        self.max_feature_psi = float(max_feature_psi)

    def evaluate(self) -> dict:
        issues = Counter()
        prediction_rows = self._read_jsonl(
            self.predictions_path,
            source="predictions",
            issues=issues,
        )
        outcome_rows = self._read_jsonl(
            self.outcomes_path,
            source="outcomes",
            issues=issues,
        )

        outcomes = self._index_outcomes(outcome_rows, issues)
        predictions = self._validate_predictions(
            prediction_rows,
            issues,
        )

        matched = []
        unmatched_predictions = 0
        for prediction in predictions:
            outcome = outcomes.get(
                prediction["candidate_observation_id"]
            )
            if outcome is None:
                unmatched_predictions += 1
                continue
            matched.append({
                **prediction,
                "exit_r": outcome["exit_r"],
                "profitable": outcome["profitable"],
                "outcome_recorded_at_ms": outcome[
                    "recorded_at_ms"
                ],
            })

        calibration = self._calibration(matched)
        batches = self._build_batches(matched, issues)
        comparison = self._compare_selections(batches)
        drift = self._load_drift(issues)

        checks = self._gate_checks(
            matched_count=len(matched),
            comparison=comparison,
            calibration=calibration,
            drift=drift,
        )
        decision, reasons = self._decision(checks, comparison)

        report = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": "EVALUATED",
            "decision": decision,
            "runtime_activation": "DISABLED",
            "advisory_only": True,
            "inputs": {
                "predictions_path": str(self.predictions_path),
                "outcomes_path": str(self.outcomes_path),
                "model_evaluation_report_path": str(
                    self.model_evaluation_report_path
                ),
                "outcome_type": self.outcome_type,
                "prediction_rows_read": len(prediction_rows),
                "outcome_rows_read": len(outcome_rows),
            },
            "coverage": {
                "valid_predictions": len(predictions),
                "matched_candidates": len(matched),
                "unmatched_predictions": unmatched_predictions,
                "completed_batches": comparison[
                    "completed_batches"
                ],
                "paired_disagreement_batches": comparison[
                    "paired_disagreement_batches"
                ],
                "agreement_batches": comparison[
                    "agreement_batches"
                ],
            },
            "candidate_calibration": calibration,
            "selection_comparison": comparison,
            "drift": drift,
            "gate_configuration": {
                "min_matched_candidates": (
                    self.min_matched_candidates
                ),
                "min_paired_batches": self.min_paired_batches,
                "min_avg_r_lift": self.min_avg_r_lift,
                "max_win_rate_drop": self.max_win_rate_drop,
                "max_brier_score": self.max_brier_score,
                "max_calibration_gap": (
                    self.max_calibration_gap
                ),
                "max_feature_psi": self.max_feature_psi,
            },
            "gate_checks": checks,
            "reasons": reasons,
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }
        self._write_json_atomic(self.report_path, report)
        return report

    def _index_outcomes(self, rows, issues):
        indexed = {}
        duplicates = set()
        for row in rows:
            if row.get("observation_type") != "CANDIDATE_OUTCOME":
                issues["outcome_record_type_invalid"] += 1
                continue
            if (
                str(row.get("outcome_type") or "").upper()
                != self.outcome_type
            ):
                continue
            candidate_id = str(
                row.get("candidate_observation_id") or ""
            ).strip()
            if not candidate_id:
                issues["outcome_candidate_id_invalid"] += 1
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict):
                issues["outcome_payload_invalid"] += 1
                continue
            exit_r = self._extract_r(payload)
            if exit_r is None:
                issues["outcome_r_missing"] += 1
                continue
            profitable = payload.get("profitable")
            if not isinstance(profitable, bool):
                profitable = exit_r > 0
            try:
                recorded_at_ms = int(row["recorded_at_ms"])
            except (KeyError, TypeError, ValueError):
                issues["outcome_timestamp_invalid"] += 1
                continue
            if candidate_id in indexed:
                duplicates.add(candidate_id)
                issues["duplicate_candidate_outcome"] += 1
                continue
            indexed[candidate_id] = {
                "exit_r": exit_r,
                "profitable": profitable,
                "recorded_at_ms": recorded_at_ms,
            }

        for candidate_id in duplicates:
            indexed.pop(candidate_id, None)
        return indexed

    def _validate_predictions(self, rows, issues):
        valid = []
        seen = set()
        for row in rows:
            if (
                row.get("observation_type")
                != "SHADOW_MODEL_PREDICTION"
            ):
                issues["prediction_record_type_invalid"] += 1
                continue
            if row.get("runtime_effect") != "NONE":
                issues["prediction_runtime_effect_invalid"] += 1
                continue
            candidate_id = str(
                row.get("candidate_observation_id") or ""
            ).strip()
            if not candidate_id:
                issues["prediction_candidate_id_invalid"] += 1
                continue
            try:
                observed_at_ms = int(row["observed_at_ms"])
                probability = float(row["shadow_probability"])
                rule_rank = int(row["rule_rank"])
                shadow_rank = int(row["shadow_rank"])
            except (KeyError, TypeError, ValueError):
                issues["prediction_value_invalid"] += 1
                continue
            if (
                observed_at_ms < 0
                or not math.isfinite(probability)
                or not (0 <= probability <= 1)
                or rule_rank < 1
                or shadow_rank < 1
            ):
                issues["prediction_value_invalid"] += 1
                continue

            decision_batch_id = str(
                row.get("decision_batch_id") or ""
            ).strip()
            batch_id = decision_batch_id or observed_at_ms
            key = (batch_id, candidate_id)
            if key in seen:
                issues["duplicate_prediction"] += 1
                continue
            seen.add(key)
            valid.append({
                "batch_id": batch_id,
                "decision_batch_id": decision_batch_id or None,
                "market_event_id": row.get("market_event_id"),
                "shadow_model_version": row.get(
                    "shadow_model_version"
                ),
                "candidate_observation_id": candidate_id,
                "symbol": str(row.get("symbol") or "").upper(),
                "direction": str(
                    row.get("direction") or ""
                ).upper(),
                "pattern": str(row.get("pattern") or "").upper(),
                "shadow_probability": probability,
                "rule_rank": rule_rank,
                "shadow_rank": shadow_rank,
                "rule_selected": bool(
                    row.get("rule_selected", False)
                ),
                "shadow_selected": bool(
                    row.get("shadow_selected", False)
                ),
            })
        return valid

    def _build_batches(self, matched, issues):
        grouped = defaultdict(list)
        for row in matched:
            grouped[row["batch_id"]].append(row)

        completed = []
        for batch_id, rows in sorted(grouped.items()):
            rule_rows = [
                row for row in rows if row["rule_selected"]
            ]
            shadow_rows = [
                row for row in rows if row["shadow_selected"]
            ]
            if len(rule_rows) != 1 or len(shadow_rows) != 1:
                issues["batch_selection_incomplete"] += 1
                continue
            completed.append({
                "batch_id": batch_id,
                "rule": rule_rows[0],
                "shadow": shadow_rows[0],
                "same_candidate": (
                    rule_rows[0]["candidate_observation_id"]
                    == shadow_rows[0][
                        "candidate_observation_id"
                    ]
                ),
            })
        return completed

    @staticmethod
    def _compare_selections(batches):
        disagreements = [
            batch for batch in batches
            if not batch["same_candidate"]
        ]
        agreements = [
            batch for batch in batches
            if batch["same_candidate"]
        ]

        rule_r = np.asarray([
            batch["rule"]["exit_r"]
            for batch in disagreements
        ], dtype=float)
        shadow_r = np.asarray([
            batch["shadow"]["exit_r"]
            for batch in disagreements
        ], dtype=float)
        rule_wins = np.asarray([
            int(batch["rule"]["profitable"])
            for batch in disagreements
        ], dtype=int)
        shadow_wins = np.asarray([
            int(batch["shadow"]["profitable"])
            for batch in disagreements
        ], dtype=int)

        if disagreements:
            avg_r_lift = float(
                np.mean(shadow_r) - np.mean(rule_r)
            )
            win_rate_lift = float(
                np.mean(shadow_wins) - np.mean(rule_wins)
            )
            shadow_better = int(np.sum(shadow_r > rule_r))
            rule_better = int(np.sum(rule_r > shadow_r))
            ties = int(np.sum(shadow_r == rule_r))
            rule_summary = {
                "average_r": float(np.mean(rule_r)),
                "win_rate": float(np.mean(rule_wins)),
                "total_r": float(np.sum(rule_r)),
            }
            shadow_summary = {
                "average_r": float(np.mean(shadow_r)),
                "win_rate": float(np.mean(shadow_wins)),
                "total_r": float(np.sum(shadow_r)),
            }
        else:
            avg_r_lift = None
            win_rate_lift = None
            shadow_better = 0
            rule_better = 0
            ties = 0
            rule_summary = {
                "average_r": None,
                "win_rate": None,
                "total_r": None,
            }
            shadow_summary = dict(rule_summary)

        return {
            "completed_batches": len(batches),
            "agreement_batches": len(agreements),
            "paired_disagreement_batches": len(disagreements),
            "rule_selected": rule_summary,
            "shadow_selected": shadow_summary,
            "average_r_lift": avg_r_lift,
            "win_rate_lift": win_rate_lift,
            "shadow_better_batches": shadow_better,
            "rule_better_batches": rule_better,
            "tie_batches": ties,
        }

    @staticmethod
    def _calibration(matched):
        if not matched:
            return {
                "rows": 0,
                "brier_score": None,
                "mean_probability": None,
                "observed_win_rate": None,
                "absolute_calibration_gap": None,
            }
        probabilities = np.asarray([
            row["shadow_probability"]
            for row in matched
        ], dtype=float)
        labels = np.asarray([
            int(row["profitable"])
            for row in matched
        ], dtype=int)
        mean_probability = float(np.mean(probabilities))
        observed_rate = float(np.mean(labels))
        return {
            "rows": len(matched),
            "brier_score": float(
                brier_score_loss(labels, probabilities)
            ),
            "mean_probability": mean_probability,
            "observed_win_rate": observed_rate,
            "absolute_calibration_gap": abs(
                mean_probability - observed_rate
            ),
        }

    def _load_drift(self, issues):
        if not self.model_evaluation_report_path.exists():
            issues["model_evaluation_report_missing"] += 1
            return {
                "available": False,
                "max_feature_psi": None,
                "high_drift_features": [],
            }
        try:
            document = json.loads(
                self.model_evaluation_report_path.read_text()
            )
        except (OSError, json.JSONDecodeError):
            issues["model_evaluation_report_invalid"] += 1
            return {
                "available": False,
                "max_feature_psi": None,
                "high_drift_features": [],
            }

        drift = document.get("drift")
        if not isinstance(drift, dict) or not drift:
            issues["model_evaluation_drift_missing"] += 1
            return {
                "available": False,
                "max_feature_psi": None,
                "high_drift_features": [],
            }

        values = []
        high = []
        for name, row in drift.items():
            try:
                psi = float(row["psi"])
            except (KeyError, TypeError, ValueError):
                issues["model_evaluation_psi_invalid"] += 1
                continue
            if not math.isfinite(psi):
                issues["model_evaluation_psi_invalid"] += 1
                continue
            values.append(psi)
            if psi > self.max_feature_psi:
                high.append(name)

        return {
            "available": bool(values),
            "max_feature_psi": max(values) if values else None,
            "high_drift_features": sorted(high),
        }

    def _gate_checks(
        self,
        *,
        matched_count,
        comparison,
        calibration,
        drift,
    ):
        average_r_lift = comparison["average_r_lift"]
        win_rate_lift = comparison["win_rate_lift"]
        return {
            "matched_candidate_sample": (
                matched_count >= self.min_matched_candidates
            ),
            "paired_batch_sample": (
                comparison["paired_disagreement_batches"]
                >= self.min_paired_batches
            ),
            "average_r_lift": (
                average_r_lift is not None
                and average_r_lift >= self.min_avg_r_lift
            ),
            "win_rate_non_inferior": (
                win_rate_lift is not None
                and win_rate_lift >= -self.max_win_rate_drop
            ),
            "brier_score": (
                calibration["brier_score"] is not None
                and calibration["brier_score"]
                <= self.max_brier_score
            ),
            "calibration_gap": (
                calibration["absolute_calibration_gap"] is not None
                and calibration["absolute_calibration_gap"]
                <= self.max_calibration_gap
            ),
            "feature_drift": (
                drift["available"]
                and drift["max_feature_psi"]
                <= self.max_feature_psi
            ),
        }

    @staticmethod
    def _decision(checks, comparison):
        sample_checks = (
            checks["matched_candidate_sample"],
            checks["paired_batch_sample"],
        )
        if not all(sample_checks):
            return "HOLD", [
                name
                for name in (
                    "matched_candidate_sample",
                    "paired_batch_sample",
                )
                if not checks[name]
            ]

        hard_failure_names = (
            "average_r_lift",
            "win_rate_non_inferior",
            "brier_score",
            "calibration_gap",
            "feature_drift",
        )
        failures = [
            name
            for name in hard_failure_names
            if not checks[name]
        ]
        if failures:
            materially_worse = (
                comparison["average_r_lift"] is not None
                and comparison["average_r_lift"] < 0
            ) or (
                comparison["win_rate_lift"] is not None
                and comparison["win_rate_lift"] < -0.02
            )
            return (
                "REJECT" if materially_worse else "HOLD",
                failures,
            )

        return "PROMOTE", [
            "all_advisory_promotion_checks_passed"
        ]

    @staticmethod
    def _extract_r(payload):
        for key in ("exit_r", "r_multiple", "target_r"):
            value = payload.get(key)
            try:
                result = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(result):
                return result
        return None

    @staticmethod
    def _read_jsonl(path, *, source, issues):
        path = Path(path)
        if not path.exists():
            issues[f"{source}_file_missing"] += 1
            return []
        rows = []
        try:
            with path.open("r") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        issues[f"{source}_malformed_json"] += 1
                        continue
                    if not isinstance(row, dict):
                        issues[f"{source}_row_not_object"] += 1
                        continue
                    rows.append(row)
        except OSError as exc:
            raise ShadowPromotionError(
                f"SHADOW_PROMOTION_READ_FAILED | "
                f"source={source} | error={exc}"
            ) from exc
        return rows

    @staticmethod
    def _write_json_atomic(path, document):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    document,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
