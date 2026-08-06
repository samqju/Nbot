"""Append-only candidate observation storage."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from strategy.features import CANDIDATE_FEATURE_SCHEMA_VERSION
from strategy.experiment_contract import (
    copy_experiment_context,
    experiment_projection,
)


class CandidateObservationWriter:
    def __init__(
        self,
        path: str,
        system_log=None,
        *,
        environment: str | None = None,
        execution_mode: str | None = None,
    ):
        self.path = Path(path)
        self.system_log = system_log
        self.environment = (
            str(environment).strip().upper() if environment else None
        )
        self.execution_mode = (
            str(execution_mode).strip().upper() if execution_mode else None
        )
        self._lock = threading.Lock()

    def append(self, candidate, *, rank: int, selected: bool) -> None:
        experiment_context = copy_experiment_context(
            getattr(candidate, "experiment_context", None)
        )
        projection = experiment_projection(experiment_context)
        if selected:
            selection_status = "SELECTED_FOR_EXECUTION"
            rejection_reason = None
        elif not bool(
            getattr(candidate, "execution_eligible", True)
        ):
            selection_status = "OBSERVATION_ONLY"
            rejection_reason = "SYMBOL_NOT_IN_EXECUTION_UNIVERSE"
        else:
            selection_status = "NOT_SELECTED"
            rejection_reason = "LOWER_RULE_RANK"

        row = {
            "schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            **projection,
            "observation_type": "STRATEGY_CANDIDATE",
            "observed_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "candidate_observation_id": candidate.observation_id,
            "symbol": candidate.symbol,
            "direction": candidate.direction,
            "pattern": candidate.pattern,
            "bucket": candidate.bucket,
            "rule_score": (candidate.score_breakdown.rule_score if candidate.score_breakdown is not None else candidate.score),
            "final_score": candidate.score,
            "score_breakdown": (candidate.score_breakdown.as_dict() if candidate.score_breakdown is not None else None),
            "reference_price": candidate.reference_price,
            "risk_plan": (candidate.risk_plan.as_dict() if candidate.risk_plan is not None else None),
            "rank": int(rank),
            "selected": bool(selected),
            "execution_eligible": bool(
                getattr(candidate, "execution_eligible", True)
            ),
            "selection_status": selection_status,
            "rejection_reason": rejection_reason,
            "eligible_for_training": True,
            "features": candidate.features.as_dict(),
            "structure_fingerprint": candidate.structure_fingerprint,
            "market_context": (
                experiment_context.get("market_context")
                if experiment_context else None
            ),
            "cost_model": (
                experiment_context.get("cost_model")
                if experiment_context else None
            ),
            "virtual_policy": (
                experiment_context.get("virtual_policy")
                if experiment_context else None
            ),
            "paper_policy": (
                experiment_context.get("paper_policy")
                if experiment_context else None
            ),
            "experiment_context": experiment_context,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str)

        with self._lock:
            fd = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(fd, (line + "\n").encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)

        if self.system_log:
            getattr(self.system_log, "debug", lambda *_args, **_kwargs: None)(
                "CANDIDATE_OBSERVATION_WRITTEN | "
                f"id={candidate.observation_id} | "
                f"symbol={candidate.symbol} | rank={rank} | "
                f"selected={str(selected).lower()} | "
                f"schema={CANDIDATE_FEATURE_SCHEMA_VERSION}"
            )
