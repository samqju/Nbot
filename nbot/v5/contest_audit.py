"""E3 synthetic contest audit. Diagnostics only; never promotes a model.

No network, orders, training, deployment or side effects. Always HOLD.
"""
from __future__ import annotations

import json
from decimal import Decimal

from .execution_engine import PORTFOLIOS, number
from .execution_replay import SyntheticReplay


def audit_synthetic_contest(replay: SyntheticReplay, cutoff_ms: int) -> dict:
    base = replay.common_window_report(cutoff_ms)
    if base["status"] == "HOLD_NO_SHARED_EVENTS":
        return {**base, "promotion_recommendation": "NONE"}
    c = replay.engine.db
    start = replay.rules.contest_start_ms
    end = base["common_endpoint_ms"]
    rows = c.execute("""SELECT receipt_json FROM replay_frames WHERE at_ms BETWEEN ? AND ?
                        ORDER BY at_ms, rowid""", (start, end)).fetchall()
    opportunity_counts = {
        book: {"accepted": 0, "abstained": 0, "rejected": 0, "not_emitted": 0}
        for book in PORTFOLIOS
    }
    linked_decision_ids = {book: set() for book in PORTFOLIOS}
    for record in rows:
        receipt = json.loads(record["receipt_json"])
        for book in PORTFOLIOS:
            decision = receipt["decisions"].get(book)
            if decision is None:
                opportunity_counts[book]["not_emitted"] += 1
                continue
            status = decision["status"].lower()
            if status in opportunity_counts[book]:
                opportunity_counts[book][status] += 1
            else:
                raise ValueError("UNRECOGNIZED_SYNTHETIC_DECISION")
            if "decision_id" in decision:
                linked_decision_ids[book].add(decision["decision_id"])
    starting = replay.engine.policy.starting_equity
    book_audits = {}
    reasons = list(base["reasons"])
    for book in PORTFOLIOS:
        marks = c.execute("""SELECT m.equity,m.wallet,m.reason
                             FROM replay_marks m JOIN replay_frames f
                               ON f.frame_id=m.frame_id
                             WHERE m.portfolio=? AND f.at_ms BETWEEN ? AND ?
                             ORDER BY f.at_ms,f.rowid""", (book, start, end)).fetchall()
        valid = [number(m["equity"]) for m in marks if m["equity"] is not None]
        missing = len(marks)-len(valid)
        high = starting
        worst = Decimal(0)
        for equity in valid:
            high = max(high, equity)
            if high > 0:
                worst = max(worst, (high - equity) / high)
        ledger_fees = c.execute("""SELECT COALESCE(SUM(CAST(fee AS REAL)),0) FROM fills
                                   WHERE portfolio=? AND at_ms BETWEEN ? AND ?""",
                                (book, start, end)).fetchone()[0]
        # Only settled funding is posted to wallet. Unrealized accrued funding
        # is conservatively reflected in each qualified mark, never as a true exchange payment.
        settled = c.execute("""SELECT funding FROM settled WHERE portfolio=?
                               AND closed_ms BETWEEN ? AND ?""",
                            (book, start, end)).fetchall()
        funding = sum((number(s["funding"]) for s in settled), Decimal(0))
        all_decisions = c.execute("""SELECT id FROM decisions WHERE portfolio=?
                                     AND as_of_ms BETWEEN ? AND ?""",
                                  (book, start-replay.engine.policy.max_recommendation_age_ms,
                                   end)).fetchall()
        unlinked = len(set(d["id"] for d in all_decisions) - linked_decision_ids[book])
        if unlinked:
            reasons.append("UNLINKED_DIRECT_ENGINE_DECISIONS")
        equity_at_end = base["portfolios"][book]["equity"]
        realized = number(base["portfolios"][book]["wallet"])
        book_audits[book] = {
            "model_id": base["portfolios"][book]["model_id"],
            "model_sha": base["portfolios"][book]["model_sha"],
            "settled_count": base["portfolios"][book]["settled_count"],
            "decisions": opportunity_counts[book],
            "unlinked_decision_count": unlinked,
            "realized_wallet": str(realized),
            "realized_return_on_same_initial_capital": str(realized / starting - 1),
            "common_endpoint_equity": equity_at_end,
            "equity_return_on_same_initial_capital": (
                str(number(equity_at_end) / starting - 1)
                if equity_at_end is not None else None),
            "qualified_equity_samples": len(valid),
            "missing_or_stale_equity_samples": missing,
            "max_observed_sampled_equity_drawdown_fraction": (
                str(worst) if not missing else None),
            "sampled_drawdown_is_not_intrabar_drawdown": True,
            "fee_total_approx_float_diagnostic_only": ledger_fees,
            "settled_adverse_funding_assumption": str(funding),
        }
        if missing:
            reasons.append("UNVERIFIABLE_EQUITY_PATH")
    first, second = (book_audits[book] for book in PORTFOLIOS)
    if (first["common_endpoint_equity"] is not None
            and second["common_endpoint_equity"] is not None):
        equity_spread = str(number(second["equity_return_on_same_initial_capital"]) -
                            number(first["equity_return_on_same_initial_capital"]))
    else:
        equity_spread = None
    if all((number(v["realized_return_on_same_initial_capital"]) < 0 for v in book_audits.values())):
        reasons.append("BOTH_UNDER_ZERO_RETURN_NO_TRADE_BENCHMARK")
    return {
        "status": "HOLD_REVIEW_REQUIRED",
        "comparison_grade": "SYNTHETIC_ONLY_NOT_VALIDATION",
        "contest_window_start_ms": start,
        "actual_first_observation_ms": base.get("first_observed_ms"),
        "common_endpoint_ms": end,
        "frozen_end_ms": replay.rules.contest_end_ms,
        "common_event_count": base["shared_frames"],
        "unique_event_ids_not_statistically_independent": base.get("unique_event_ids_not_independent"),
        "same_initial_equity_per_book": str(starting),
        "no_trade_baseline_return": "0",
        "challenger_minus_champion_equity_return": equity_spread,
        "books": book_audits,
        "hold_reasons": sorted(set(reasons)),
        "independent_event_blocked_uncertainty": "NOT_AVAILABLE",
        "btc_regime_coverage": "UNVERIFIED",
        "unresolved_exit_policy": "HOLD_MISSING_PRICE_PATH",
        "may_train_on_contest_period": False,
        "promotion_recommendation": "NONE",
        "paper_promotion_authority": "NONE",
        "live_order_authority": "NONE",
    }
