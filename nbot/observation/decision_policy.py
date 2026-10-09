"""Causal calibration of Selective-ML PASS/REJECT gates.

Research-only: thresholds are selected on an earlier chronological window and
can qualify only when they beat the current policy on a later holdout. One
capital position is modelled by skipping events until a hypothetical accepted
position exits.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any

from .decision_ledger import DecisionOutcomeLedger

VERSION = "DECISION_GATE_CALIBRATION_V1"
CURRENT_CONFIDENCE_R = 0.08
CURRENT_EDGE_R = 0.05


@dataclass(frozen=True)
class GateCalibrationConfig:
    min_events: int = 120
    train_fraction: float = 0.70
    min_train_accepted: int = 15
    min_validation_accepted: int = 8
    min_validation_gain_r_per_event: float = 0.01
    confidence_grid: tuple[float, ...] = (-0.10,-0.05,0.00,0.02,0.04,0.06,0.08,0.10,0.12,0.15,0.20)
    edge_grid: tuple[float, ...] = (0.00,0.02,0.03,0.05,0.07,0.10)

    def validate(self) -> None:
        if self.min_events < 50:
            raise ValueError("GATE_CALIBRATION_MIN_EVENTS_INVALID")
        if not 0.5 <= self.train_fraction <= 0.85:
            raise ValueError("GATE_CALIBRATION_SPLIT_INVALID")
        if self.min_train_accepted <= 0 or self.min_validation_accepted <= 0:
            raise ValueError("GATE_CALIBRATION_ACCEPTED_MIN_INVALID")
        if self.min_validation_gain_r_per_event < 0:
            raise ValueError("GATE_CALIBRATION_GAIN_INVALID")
        if CURRENT_CONFIDENCE_R not in self.confidence_grid or CURRENT_EDGE_R not in self.edge_grid:
            raise ValueError("GATE_CALIBRATION_CURRENT_POLICY_MISSING")


class GatePolicyCalibrator:
    def __init__(self, ledger: DecisionOutcomeLedger, config: GateCalibrationConfig | None = None):
        self.ledger = ledger
        self.config = config or GateCalibrationConfig()
        self.config.validate()

    @staticmethod
    def _top_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output, seen = [], set()
        for row in sorted(rows, key=lambda r: (int(r["event_ms"]), int(r["rank"]), r["symbol"], r["side"])):
            if int(row["rank"]) != 1 or int(row["event_ms"]) in seen:
                continue
            scores = row.get("scores") or {}
            confidence, edge = scores.get("conservative_score_r"), scores.get("raw_edge_gap_r")
            if confidence is None or edge is None:
                continue
            try:
                confidence, edge = float(confidence), float(edge)
                target, exit_ms = float(row["target_net_r"]), int(row["exit_time_ms"])
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(v) for v in (confidence, edge, target)) or exit_ms <= int(row["event_ms"]):
                continue
            seen.add(int(row["event_ms"]))
            output.append({**row, "confidence_r": confidence, "edge_r": edge,
                           "target_net_r": target, "exit_time_ms": exit_ms})
        return output

    @staticmethod
    def _evaluate(rows: list[dict[str, Any]], confidence: float, edge: float) -> dict[str, Any]:
        total_r, accepted, wins, losses, skipped, busy_until = 0.0, 0, 0, 0, 0, -1
        for row in rows:
            event = int(row["event_ms"])
            if event < busy_until:
                skipped += 1
                continue
            if float(row["confidence_r"]) + 1e-12 < confidence or float(row["edge_r"]) + 1e-12 < edge:
                continue
            value = float(row["target_net_r"])
            accepted += 1
            wins += int(value > 0)
            losses += int(value < 0)
            total_r += value
            busy_until = max(event + 1, int(row["exit_time_ms"]))
        n = len(rows)
        return {"confidence_r": confidence, "edge_r": edge, "events": n,
                "accepted": accepted, "wins": wins, "losses": losses,
                "skipped_capacity": skipped, "total_net_r": total_r,
                "net_r_per_event": total_r / n if n else 0.0,
                "mean_accepted_net_r": total_r / accepted if accepted else 0.0}

    def calibrate(self) -> dict[str, Any]:
        rows = self._top_rows(self.ledger.decision_policy_rows())
        current = {"min_confidence_r": CURRENT_CONFIDENCE_R, "min_edge_gap_r": CURRENT_EDGE_R}
        if len(rows) < self.config.min_events:
            return {"version": VERSION, "qualified": False, "reason": "INSUFFICIENT_RESOLVED_EVENTS",
                    "events": len(rows), "required_events": self.config.min_events,
                    "active_gate": current, "recommended_gate": current}
        split = max(1, min(len(rows)-1, int(len(rows) * self.config.train_fraction)))
        train, valid = rows[:split], rows[split:]
        current_train = self._evaluate(train, CURRENT_CONFIDENCE_R, CURRENT_EDGE_R)
        current_valid = self._evaluate(valid, CURRENT_CONFIDENCE_R, CURRENT_EDGE_R)
        candidates = []
        for confidence in self.config.confidence_grid:
            for edge in self.config.edge_grid:
                result = self._evaluate(train, confidence, edge)
                if result["accepted"] >= self.config.min_train_accepted:
                    candidates.append(result)
        if not candidates:
            return {"version": VERSION, "qualified": False, "reason": "INSUFFICIENT_TRAIN_ACCEPTANCES",
                    "events": len(rows), "active_gate": current, "recommended_gate": current,
                    "current_train": current_train, "current_validation": current_valid}
        winner = sorted(candidates, key=lambda r: (-r["net_r_per_event"], -r["accepted"],
                                                   -r["confidence_r"], -r["edge_r"]))[0]
        winner_valid = self._evaluate(valid, winner["confidence_r"], winner["edge_r"])
        gain = winner_valid["net_r_per_event"] - current_valid["net_r_per_event"]
        different = (abs(winner["confidence_r"]-CURRENT_CONFIDENCE_R) > 1e-12 or
                     abs(winner["edge_r"]-CURRENT_EDGE_R) > 1e-12)
        qualified = bool(different and
                         winner_valid["accepted"] >= self.config.min_validation_accepted and
                         gain >= self.config.min_validation_gain_r_per_event and
                         winner_valid["total_net_r"] > 0)
        recommended = ({"min_confidence_r": winner["confidence_r"],
                        "min_edge_gap_r": winner["edge_r"]} if qualified else current)
        return {"version": VERSION, "qualified": qualified,
                "reason": "OOS_IMPROVEMENT_QUALIFIED" if qualified else "KEEP_CURRENT_GATE",
                "events": len(rows), "train_events": len(train), "validation_events": len(valid),
                "active_gate": current, "recommended_gate": recommended,
                "train_winner": winner, "winner_validation": winner_valid,
                "current_train": current_train, "current_validation": current_valid,
                "validation_gain_r_per_event": gain,
                "capacity_model": "ONE_POSITION_UNTIL_COUNTERFACTUAL_EXIT",
                "target_source": "AGGTRADE_RESOLVED_COUNTERFACTUAL_ONLY"}
