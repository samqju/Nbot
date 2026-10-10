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
import sqlite3
import time
from contextlib import closing
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


def _activity_summary(database_path: Path, profile: str, release_sha: str) -> dict:
    """Read a consistent snapshot, including older releases without pooling scores."""
    if not database_path.exists():
        return {"status": "No shadow database yet"}
    deadline = time.monotonic() + 2.0
    with closing(sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro",
                               uri=True, timeout=2)) as conn:
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.execute("BEGIN")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_results'").fetchone():
            return {"status": "No shadow history yet"}
        active = conn.execute("SELECT state_json FROM shadow_positions WHERE profile=?", (profile,)).fetchall()
        states = [json.loads(row[0]) for row in active]
        counts = conn.execute("""SELECT COUNT(*),COALESCE(SUM(eligible),0),MAX(closed_ms)
                                FROM shadow_results WHERE profile=?""", (profile,)).fetchone()
        current = conn.execute("""SELECT COUNT(*),COALESCE(SUM(eligible),0),
            COALESCE(SUM(CASE WHEN eligible=1 THEN json_extract(result_json,'$.net_usd') ELSE 0 END),0)
            FROM shadow_results WHERE profile=? AND release_sha=?""", (profile,release_sha)).fetchone()
        latest = conn.execute("SELECT MAX(event_ms) FROM shadow_batches WHERE profile=?", (profile,)).fetchone()[0]
        reasons = dict(conn.execute("""SELECT json_extract(result_json,'$.reason'),COUNT(*)
            FROM shadow_results WHERE profile=? AND eligible=0 GROUP BY 1""",(profile,)))
        drift = conn.execute("""SELECT AVG(json_extract(result_json,'$.entry_drift_pct')),
            AVG(json_extract(result_json,'$.entry_wait_ms'))/1000.0 FROM shadow_results
            WHERE profile=? AND eligible=0 AND json_extract(result_json,'$.reason')='ENTRY_DRIFT_REJECTED'""",
            (profile,)).fetchone()
        feedback={}
        if profile=="live-paper" and conn.execute("SELECT 1 FROM sqlite_master WHERE name='paper_feedback_checks'").fetchone():
            row=conn.execute("SELECT decision_ms,detail_json FROM paper_feedback_checks ORDER BY decision_ms DESC LIMIT 1").fetchone()
            if row:
                feedback=dict(json.loads(row[1]), decision_ms=row[0])
        return {"status": "Recorded", "feedback": feedback, "cancellation_reasons": reasons,
                "mean_cancelled_drift_pct": round(drift[0],3) if drift[0] is not None else None,
                "mean_cancelled_wait_seconds": round(drift[1],1) if drift[1] is not None else None, "open": sum(p.get("status")=="OPEN" for p in states),
                "pending": sum(p.get("status")=="PENDING" for p in states),
                "completed": counts[1], "excluded": counts[0]-counts[1],
                "latest_result_ms": counts[2], "latest_opportunity_ms": latest,
                "current_completed": current[1], "current_excluded": current[0]-current[1],
                "current_net_usd": round(current[2], 4)}


def _activity_text(data: Mapping[str, Any]) -> str:
    activity = data.get("shadow_activity", {})
    readiness = data.get("recommendation", {})
    reason = str(readiness.get("reason") or "none")
    waiting = {
        "LEARNED_LIVE_EVENT_STALE_OR_FUTURE": "Waiting for the next fresh 5-minute market update.",
        "LEARNING_WAIT_FOR_COMPATIBLE_MODEL": "Waiting for a compatible trained model.",
        "LEARNED_NO_POSITIVE_OPPORTUNITY": "No qualifying setup in the latest market update.",
    }.get(reason, reason.replace("_", " ").lower())
    def when(value):
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(value/1000)) if value else "none yet"
    return (
        f"Trade suggestions: {_e(readiness.get('status', 'unknown'))}\n"
        f"Waiting reason: {_e(waiting)}\n"
        f"Compatible model available: {_e(data.get('compatible_model_available', 'unknown'))}\n"
        f"Shadow simulations: {_e(activity.get('status', 'unavailable'))}\n"
        f"Open: {_e(activity.get('open'))} | Pending entry: {_e(activity.get('pending'))}\n"
        f"Completed, all releases: {_e(activity.get('completed'))}\n"
        f"Cancelled/unscorable, all releases: {_e(activity.get('excluded'))}\n"
        f"This release: {_e(activity.get('current_completed'))} completed; "
        f"net {_e(activity.get('current_net_usd'))} simulated USD\n"
        f"Last shadow opportunity: {_e(when(activity.get('latest_opportunity_ms')))}\n"
        f"Last shadow result: {_e(when(activity.get('latest_result_ms')))}\n"
        f"Next-bar drift research cancellations: {_e(activity.get('cancellation_reasons',{}).get('ENTRY_DRIFT_REJECTED',0))}\n"
        f"Measured next-bar drift: {_e(activity.get('mean_cancelled_drift_pct'))}% / "
        f"wait {_e(activity.get('mean_cancelled_wait_seconds'))} seconds\n"
        "Valid shadow trade outcomes affect paper outcome calibration at 25% weight per time block.\n"
        "Next-bar drift is research-only and does not gate or penalize immediate entries.\n\n"
        + _feedback_text(activity.get("feedback", {}))
    )


def _feedback_text(data: Mapping[str, Any]) -> str:
    if not data:
        return "Learning effect: waiting for the next assessed market event.\n\n"
    selected=data.get("selected",{})
    before=data.get("baseline",{})
    raw_ml=data.get("raw_ml_winner") if isinstance(data.get("raw_ml_winner"), Mapping) else {}
    now=int(time.time()*1000)
    pauses=[key for key,value in data.get("active_cooldowns",{}).items() if value.get("until_ms",0)>now]

    def r(value):
        return "N/A" if value is None else f"{float(value):.4f} R"

    def pct(value):
        return "N/A" if value is None else f"{100*float(value):.1f}%"

    def gate(value):
        return "PASS" if value is True else "FAIL" if value is False else "N/A"

    if raw_ml:
        primary = raw_ml.get("gate_reason") or selected.get("reason")
        decay = selected.get("next_bar_signal_decay")
        decay = decay if isinstance(decay, Mapping) else {}
        decay_text = (
            f"{_e(decay.get('filled'))}/{_e(decay.get('attempts'))} survived old next-bar drift test"
            if decay else "no candidate-specific sample"
        )
        return (
            f"Last learning decision: {_e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(data.get('decision_ms',0)/1000)))}\n"
            f"Feedback used: {_e(data.get('main_samples'))} main / {_e(data.get('shadow_samples'))} shadow outcomes\n"
            f"Ridge winner: {_e(before.get('symbol'))} {_e(before.get('side'))} / {_e(before.get('candidate'))} | {_e(r(before.get('score')))}\n"
            f"Raw ML winner: {_e(raw_ml.get('symbol'))} {_e(raw_ml.get('side'))} | conservative {_e(r(raw_ml.get('conservative_score_r')))} "
            f"(need >= {_e(r(raw_ml.get('min_confidence_r')))}) | confidence {_e(gate(raw_ml.get('confidence_pass')))}\n"
            f"ML components: ridge {_e(r(raw_ml.get('ridge_score_r')))} | mean {_e(r(raw_ml.get('ml_mean_r')))} | "
            f"lower {_e(r(raw_ml.get('ml_lower_r')))} | ensemble {_e(r(raw_ml.get('ensemble_mean_r')))}\n"
            f"ML runner-up: {_e(raw_ml.get('runner_up_symbol'))} {_e(raw_ml.get('runner_up_side'))} | "
            f"{_e(r(raw_ml.get('runner_up_conservative_score_r')))} | gap {_e(r(raw_ml.get('edge_gap_r')))} "
            f"(need >= {_e(r(raw_ml.get('min_edge_gap_r')))}) | edge {_e(gate(raw_ml.get('edge_pass')))}\n"
            f"Post-feedback candidate: {_e(selected.get('symbol'))} {_e(selected.get('side'))} / {_e(selected.get('candidate'))} | "
            f"score {_e(r(selected.get('post_feedback_score_r')))} | outcome factor {_e(selected.get('outcome_factor'))}\n"
            "Entry gate: REALTIME AT EXECUTION (fresh quote, spread, reference drift, fill/slippage safety).\n"
            f"Next-bar drift research only: {decay_text}; it does not affect selection or entry.\n"
            f"Final score: {_e(r(selected.get('score')))} | Decision: {_e('NO TRADE' if data.get('no_trade') else 'TRADE ALLOWED')}\n"
            f"Primary blocker: {_e(primary or 'NONE')} | feedback status: {_e(selected.get('reason') or 'NONE')}\n"
            f"Choices blocked by loss pause: {_e(data.get('cooldown_choices_blocked'))} | "
            f"Active loss pauses: {_e(', '.join(pauses) or 'none')}\n\n"
        )

    return (
        f"Last learning decision: {_e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(data.get('decision_ms',0)/1000)))}\n"
        f"Feedback used: {_e(data.get('main_samples'))} main / {_e(data.get('shadow_samples'))} shadow outcomes\n"
        f"Choice changed by feedback: {_e(data.get('choice_changed'))}\n"
        f"Before: {_e(before.get('symbol'))} {_e(before.get('side'))} / {_e(before.get('candidate'))}\n"
        f"After: {_e(selected.get('symbol'))} {_e(selected.get('side'))} / {_e(selected.get('candidate'))}"
        f" (score factor {_e(selected.get('factor'))})\n"
        f"Decision: {_e('NO TRADE' if data.get('no_trade') else selected.get('reason'))}\n"
        f"Choices adjusted: outcomes {_e(data.get('outcome_choices_adjusted'))}, "
        f"entry practicality {_e(data.get('entry_choices_adjusted'))}\n"
        f"Choices blocked by loss pause: {_e(data.get('cooldown_choices_blocked'))}\n"
        f"Active loss pauses: {_e(', '.join(pauses) or 'none')}\n\n"
    )


def _format_learning(data: Mapping[str, Any]) -> str:
    challengers = data.get("challengers") if isinstance(data.get("challengers"), Mapping) else {}
    active = challengers.get("active_challenger") if isinstance(challengers.get("active_challenger"), Mapping) else {}
    future = challengers.get("active_future_evidence") if isinstance(challengers.get("active_future_evidence"), Mapping) else {}
    governance = data.get("governance") if isinstance(data.get("governance"), Mapping) else {}
    eligibility = governance.get("research_champion_eligibility") if isinstance(governance.get("research_champion_eligibility"), Mapping) else {}
    research = data.get("research_champion_promotion") if isinstance(data.get("research_champion_promotion"), Mapping) else {}
    two_tier = data.get("two_tier_research") if isinstance(data.get("two_tier_research"), Mapping) else {}
    ledger = two_tier.get("ledger_counts") if isinstance(two_tier.get("ledger_counts"), Mapping) else {}
    detailed = data.get("counterfactual_learning") or {}
    detailed = detailed if isinstance(detailed, Mapping) else {}
    review = detailed.get("review") or {}
    states = governance.get("challenger_states") or []
    finalized = [row for row in states if isinstance(row, Mapping)
                 and row.get("state") != "ACTIVE_WAITING_FUTURE_EVIDENCE"]
    latest = finalized[-1] if finalized else {}
    return _activity_text(data) + (
        f"Learning state: {_e(str(data.get('status') or 'unknown').replace('_', ' ').lower())}\n"
        f"New model being tested: {_e(active.get('model_version') or 'none currently')}\n"
        f"Later market samples collected: {_e(future.get('available_future_events'))}"
        f" / {_e(future.get('required_future_events'))} needed\n"
        f"Tests passed: {_e(challengers.get('passed_windows'))}\n"
        f"Tests rejected: {_e(challengers.get('rejected_windows'))}\n"
        f"Latest completed test: {_e(str(latest.get('state') or 'none yet').replace('_', ' ').lower())}\n"
        f"Research model selected: {_e(research.get('current_research_champion') or 'none yet')}\n"
        f"Review progress: {_e(str(eligibility.get('decision') or 'unknown').replace('_', ' ').lower())}\n\n"
        f"100/20 research: {_e(str(two_tier.get('state') or 'not running').replace('_', ' ').lower())}\n"
        f"Broad scan target: {_e(two_tier.get('broad_target'))}\n"
        f"High-resolution symbols: {_e(len(two_tier.get('active_symbols') or []))}"
        f" / {_e(two_tier.get('high_res_cap'))}\n"
        f"Active high-resolution hypotheses: {_e(two_tier.get('active_hypotheses'))}\n"
        f"Research outcomes matured: {_e(ledger.get('matured_research'))}\n"
        f"Detailed outcomes usable for training: {_e(detailed.get('eligible_rows'))}\n"
        f"Usable rejected opportunities: {_e(detailed.get('rejected_opportunities'))}\n"
        f"Detailed model later test events: {_e(detailed.get('future_events_collected'))}"
        f" / {_e(detailed.get('future_events_required'))}\n"
        f"Detailed paper model active: {_e('yes' if detailed.get('active_model') else 'no; using fallback')}\n"
        f"Detailed model review: {_e(review.get('status') or 'waiting for enough later evidence')}\n"
        f"Research decisions rejected/not admitted: {_e(ledger.get('rejected'))}"
        f" / unresolved {_e(ledger.get('unresolved'))}\n\n"
        "The learner tests predictions against later market outcomes.\n"
        "Waiting means more evidence is needed. Rejected means a test did not pass.\n"
        "These counts alone do not prove improving trading profits.\n"
        "Use /recent and /pnl for your actual paper-trade results.\n"
        "This report does not approve real-money trading."
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
        if view == "learning":
            data = self._admin_json(READ_ONLY_ADMIN_VIEWS["learning"])
            data["recommendation"] = self.target.health_snapshot()
            try:
                data["shadow_activity"] = _activity_summary(
                    self.target.database.path, self.target.profile.name, self.target.release_sha)
            except Exception:
                data["shadow_activity"] = {"status": "Activity report unavailable"}
            try:
                source = self.target.recommendations.learned_source
                data["compatible_model_available"] = (
                    source._model(int(time.time()*1000)) is not None if source else False)
            except Exception:
                data["compatible_model_available"] = "unavailable"
            return data
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
