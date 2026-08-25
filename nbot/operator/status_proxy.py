"""Read-only Observation status documents for local/remote operator surfaces.

This module owns no trading, training, promotion or rollback authority.  It
reads existing Observation state through fixed read-only admin commands and
formats bounded Telegram text.  Execution may display the returned document
through the authenticated control link without importing Observation research
modules.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


READ_ONLY_ADMIN_VIEWS: dict[str, tuple[str, ...]] = {
    "memory": ("research-memory-status",),
    "epoch": ("research-epoch-status",),
    "champion": ("champion-status",),
    "learning": ("learning-status",),
    "governance": ("governance-status",),
    "research": ("research-champion-review",),
    "paper": ("paper-champion-status",),
    "market-regimes": ("market-regime-status",),
    "operational-regimes": ("operational-regime-status",),
}

PUBLIC_VIEWS = frozenset(
    {
        "observation",
        "recommendation",
        "db",
        "challenger",
        *READ_ONLY_ADMIN_VIEWS,
    }
)


def _e(value: object) -> str:
    if value is None:
        return "N/A"
    return html.escape(str(value))


def _failed_gates(gates: object) -> str:
    if not isinstance(gates, Mapping):
        return "N/A"
    failed = [str(key) for key, value in gates.items() if value is False]
    return "NONE" if not failed else ", ".join(failed[:8])


def _format_observation(data: Mapping[str, Any]) -> str:
    return (
        f"Status: {_e(data.get('status'))}\n"
        f"Reason: {_e(data.get('reason') or 'NONE')}\n"
        f"Profile: {_e(data.get('profile'))}\n"
        f"Market: {_e(data.get('market_environment'))}\n"
        f"Recommendation authority: {_e(data.get('recommendation_authority'))}\n"
        f"Release: {_e(data.get('release_sha'))}\n"
        "Order authority: NONE"
    )


def _format_memory(data: Mapping[str, Any]) -> str:
    ridge = data.get("ridge_state") if isinstance(data.get("ridge_state"), Mapping) else {}
    return (
        f"Memory version: {_e(data.get('memory_version'))}\n"
        f"Epochs: {_e(data.get('epochs'))}\n"
        f"Events: {_e(data.get('events'))}\n"
        f"Latest event: {_e(data.get('latest_event_open_ms'))}\n"
        f"Training events: {_e(ridge.get('training_event_count'))}\n"
        f"Training rows: {_e(ridge.get('training_row_count'))}\n"
        f"Through event: {_e(ridge.get('through_event_ms'))}\n"
        f"Authority: {_e(data.get('authority'))}"
    )


def _format_epoch(data: Mapping[str, Any]) -> str:
    plan = data.get("plan") if isinstance(data.get("plan"), Mapping) else {}
    return (
        f"Status: {_e(plan.get('status'))}\n"
        f"Target start: {_e(plan.get('target_start_ms'))}\n"
        f"Target end: {_e(plan.get('target_end_ms'))}\n"
        f"Memory latest: {_e(plan.get('memory_latest_event_ms'))}\n"
        f"Raw latest: {_e(plan.get('latest_raw_event_ms'))}\n"
        f"Authority: {_e(data.get('authority'))}"
    )


def _format_champion(data: Mapping[str, Any]) -> str:
    champion = data.get("champion")
    if champion is None:
        champion = data.get("current_research_champion")
    return (
        f"Decision: {_e(data.get('decision') or data.get('status'))}\n"
        f"Research Champion: {_e(champion or 'NONE')}\n"
        f"Evaluations: {_e(data.get('research_champion_evaluations'))}\n"
        f"Authority: {_e(data.get('authority'))}\n"
        "Execution authority: NONE"
    )


def _format_challenger(data: Mapping[str, Any]) -> str:
    challenger = data.get("challenger") if isinstance(data.get("challenger"), Mapping) else data
    governance = data.get("governance") if isinstance(data.get("governance"), Mapping) else {}
    active = challenger.get("active_challenger") if isinstance(challenger.get("active_challenger"), Mapping) else {}
    future = challenger.get("active_future_evidence") if isinstance(challenger.get("active_future_evidence"), Mapping) else {}
    states = governance.get("challenger_states") if isinstance(governance.get("challenger_states"), list) else []
    finalized = [row for row in states if isinstance(row, Mapping) and row.get("state") != "ACTIVE_WAITING_FUTURE_EVIDENCE"]
    latest = finalized[-1] if finalized else {}
    required = future.get("required_future_events")
    available = future.get("available_future_events")
    return (
        f"Active: {_e(active.get('challenger_version') or 'NONE')}\n"
        f"Model: {_e(active.get('model_version') or 'NONE')}\n"
        f"Future evidence: {_e(available)}/{_e(required)}\n"
        f"Validation ready: {_e(future.get('available_validation_events'))}/20\n"
        f"Test ready: {_e(future.get('available_test_events'))}/20\n"
        f"Latest finalized: {_e(latest.get('challenger_version') or 'NONE')}\n"
        f"Latest result: {_e(latest.get('state') or 'NONE')}\n"
        f"PASS windows: {_e(challenger.get('passed_windows'))}\n"
        f"REJECT windows: {_e(challenger.get('rejected_windows'))}\n"
        "Automatic promotion: false"
    )


def _format_governance(data: Mapping[str, Any]) -> str:
    eligibility = data.get("research_champion_eligibility") if isinstance(data.get("research_champion_eligibility"), Mapping) else {}
    pointer = data.get("champion_pointer") if isinstance(data.get("champion_pointer"), Mapping) else {}
    basis = eligibility.get("window_basis") if isinstance(eligibility.get("window_basis"), list) else []
    return (
        f"Eligibility: {_e(eligibility.get('decision'))}\n"
        f"Eligible for review: {_e(eligibility.get('eligible_for_research_champion_review'))}\n"
        f"Eligible windows: {len(basis)}/3\n"
        f"Test events: {_e(eligibility.get('total_test_events'))}\n"
        f"Trade events: {_e(eligibility.get('total_trade_events'))}\n"
        f"Distinct UTC dates: {_e(eligibility.get('distinct_test_utc_dates'))}\n"
        f"Elapsed test hours: {_e(eligibility.get('elapsed_test_hours'))}\n"
        f"Drift transitions: {_e(eligibility.get('drift_transitions_monitored'))}\n"
        f"Weighted mean R: {_e(eligibility.get('weighted_after_cost_mean_r'))}\n"
        f"Weighted lift R: {_e(eligibility.get('weighted_paired_lift_mean_r'))}\n"
        f"Failed gates: {_e(_failed_gates(eligibility.get('gates')))}\n"
        f"Research Champion: {_e(pointer.get('current_research_champion') or 'NONE')}"
    )


def _format_research(data: Mapping[str, Any]) -> str:
    eligibility = data.get("eligibility") if isinstance(data.get("eligibility"), Mapping) else {}
    return (
        f"Review decision: {_e(data.get('decision'))}\n"
        f"Candidate: {_e(data.get('candidate') or 'NONE')}\n"
        f"Current Research Champion: {_e(data.get('current_research_champion') or 'NONE')}\n"
        f"Eligibility: {_e(eligibility.get('decision'))}\n"
        f"Eligible for review: {_e(eligibility.get('eligible_for_research_champion_review'))}\n"
        f"Execution authority: {_e(data.get('execution_authority'))}\n"
        f"Paper authority: {_e(data.get('paper_champion_authority'))}\n"
        "Automatic promotion: false"
    )


def _format_paper(data: Mapping[str, Any]) -> str:
    thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), Mapping) else {}
    return (
        f"Decision: {_e(data.get('decision'))}\n"
        f"Research Champion: {_e(data.get('research_champion') or 'NONE')}\n"
        f"Paper evidence: {_e(data.get('paper_evidence_counted'))}/{_e(thresholds.get('min_completed_paper_trades'))} trades\n"
        f"Independent events required: {_e(thresholds.get('min_independent_market_events'))}\n"
        f"Elapsed days required: {_e(thresholds.get('min_elapsed_days'))}\n"
        f"Distinct dates required: {_e(thresholds.get('min_distinct_utc_dates'))}\n"
        f"Collection: {_e(data.get('paper_evidence_collection'))}\n"
        f"Paper authority: {_e(data.get('paper_champion_authority'))}\n"
        f"Execution authority: {_e(data.get('execution_authority'))}"
    )


def _format_market_regimes(data: Mapping[str, Any]) -> str:
    coverage = data.get("coverage") if isinstance(data.get("coverage"), Mapping) else {}
    dimensions = coverage.get("dimensions") if isinstance(coverage.get("dimensions"), Mapping) else {}
    pieces = []
    for name in ("trend", "volatility", "breadth", "funding", "liquidity"):
        row = dimensions.get(name) if isinstance(dimensions.get(name), Mapping) else {}
        pieces.append(f"{name}: {'COMPLETE' if row.get('complete') else 'ACCUMULATING'}")
    return (
        f"Eligibility windows: {_e(coverage.get('eligibility_counting_final_windows'))}\n"
        f"Eligibility test events: {_e(coverage.get('eligibility_counting_test_events'))}\n"
        + "\n".join(pieces)
        + f"\nAll required observed: {_e(coverage.get('all_required_market_regimes_observed'))}"
    )


def _format_operational_regimes(data: Mapping[str, Any]) -> str:
    return (
        f"Required regimes: {_e(data.get('requirement_count'))}\n"
        f"Accepted evidence: {_e(data.get('accepted_evidence_count'))}\n"
        f"Deterministic equivalents: {_e(data.get('deterministic_equivalent_count'))}\n"
        f"Authority deferred: {_e(data.get('deferred_authority_count'))}\n"
        f"Deferred: {_e(', '.join(map(str, data.get('deferred_regimes') or [])) or 'NONE')}\n"
        f"All proven: {_e(data.get('all_required_operational_regimes_proven'))}"
    )


def _format_learning(data: Mapping[str, Any]) -> str:
    challengers = data.get("challengers") if isinstance(data.get("challengers"), Mapping) else {}
    active = challengers.get("active_challenger") if isinstance(challengers.get("active_challenger"), Mapping) else {}
    future = challengers.get("active_future_evidence") if isinstance(challengers.get("active_future_evidence"), Mapping) else {}
    governance = data.get("governance") if isinstance(data.get("governance"), Mapping) else {}
    eligibility = governance.get("research_champion_eligibility") if isinstance(governance.get("research_champion_eligibility"), Mapping) else {}
    research = data.get("research_champion_promotion") if isinstance(data.get("research_champion_promotion"), Mapping) else {}
    paper = data.get("paper_champion") if isinstance(data.get("paper_champion"), Mapping) else {}
    return (
        f"Learning: {_e(data.get('status'))}\n"
        f"Active challenger: {_e(active.get('challenger_version') or 'NONE')}\n"
        f"Future evidence: {_e(future.get('available_future_events'))}/{_e(future.get('required_future_events'))}\n"
        f"PASS / REJECT windows: {_e(challengers.get('passed_windows'))} / {_e(challengers.get('rejected_windows'))}\n"
        f"Research eligibility: {_e(eligibility.get('decision'))}\n"
        f"Research review: {_e(research.get('decision'))}\n"
        f"Research Champion: {_e(research.get('current_research_champion') or 'NONE')}\n"
        f"Paper gate: {_e(paper.get('decision'))}\n"
        f"Paper evidence counted: {_e(paper.get('paper_evidence_counted'))}\n"
        "Execution authority: NONE"
    )


def _format_db(data: Mapping[str, Any]) -> str:
    rows = []
    for key in ("quick_check", "foreign_key_errors", "integrity", "database_size_bytes", "market_events"):
        if key in data:
            rows.append(f"{key}: {_e(data.get(key))}")
    if rows:
        return "\n".join(rows)
    return html.escape(json.dumps(dict(data), sort_keys=True, indent=2)[:3000])


class ObservationReadOnlyStatusProvider:
    """Build bounded operator documents without creating authority or writes."""

    def __init__(self, *, repo_root: Path, target: Any) -> None:
        self.repo_root = Path(repo_root)
        self.target = target

    def _admin_json(self, command: tuple[str, ...]) -> dict[str, Any]:
        proc = subprocess.run(
            [
                str(self.repo_root / ".venv/bin/python"),
                str(self.repo_root / "nbot_admin.py"),
                *command,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"NBOT_ADMIN_READ_ONLY_FAILED:{' '.join(command)}:{proc.returncode}")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("NBOT_ADMIN_READ_ONLY_JSON_INVALID") from exc
        if not isinstance(data, dict):
            raise RuntimeError("NBOT_ADMIN_READ_ONLY_RESPONSE_INVALID")
        return data

    def _document(self, view: str) -> dict[str, Any]:
        if view in {"observation", "recommendation"}:
            data = self.target.health_snapshot()
            if not isinstance(data, dict):
                raise RuntimeError("OBSERVATION_HEALTH_RESPONSE_INVALID")
            return dict(data)
        if view == "db":
            data = self.target.database.integrity_check()
            if not isinstance(data, dict):
                raise RuntimeError("OBSERVATION_DATABASE_STATUS_INVALID")
            return dict(data)
        if view == "challenger":
            return {
                "challenger": self._admin_json(("challenger-status",)),
                "governance": self._admin_json(("governance-status",)),
            }
        command = READ_ONLY_ADMIN_VIEWS.get(view)
        if command is None:
            raise ValueError("OBSERVATION_OPERATOR_VIEW_INVALID")
        return self._admin_json(command)

    def status(self, view: str) -> dict[str, Any]:
        normalized = str(view or "").strip().lower()
        if normalized not in PUBLIC_VIEWS:
            raise ValueError("OBSERVATION_OPERATOR_VIEW_INVALID")
        document = self._document(normalized)
        if normalized in {"observation", "recommendation"}:
            body = _format_observation(document)
        elif normalized == "memory":
            body = _format_memory(document)
        elif normalized == "epoch":
            body = _format_epoch(document)
        elif normalized == "champion":
            body = _format_champion(document)
        elif normalized == "challenger":
            body = _format_challenger(document)
        elif normalized == "governance":
            body = _format_governance(document)
        elif normalized == "research":
            body = _format_research(document)
        elif normalized == "paper":
            body = _format_paper(document)
        elif normalized == "market-regimes":
            body = _format_market_regimes(document)
        elif normalized == "operational-regimes":
            body = _format_operational_regimes(document)
        elif normalized == "learning":
            body = _format_learning(document)
        elif normalized == "db":
            body = _format_db(document)
        else:  # pragma: no cover - PUBLIC_VIEWS is exhaustive above.
            raise ValueError("OBSERVATION_OPERATOR_VIEW_INVALID")
        return {
            "status": "OK",
            "view": normalized,
            "order_authority": "NONE",
            "telegram_body": body[:3500],
            "document": document,
        }
