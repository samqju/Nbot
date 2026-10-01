"""Explain stored evidence; never invent explanations for unavailable history."""
from __future__ import annotations

from .challengers import CHALLENGER_PREFIX, EVALUATION_PREFIX, MODEL_PREFIX
from .context_learning import explain_gates


def learning_report(memory):
    challengers = memory.list_artifacts(prefix=CHALLENGER_PREFIX)
    evaluations = memory.list_artifacts(prefix=EVALUATION_PREFIX)
    lines = ["# Learning progress", "", "This is research and experimental Testnet learning, not proof of profitability.", "",
             "Training outcomes use a four-hour simulation and ATR-based risk units; these are not actual execution P&L forecasts.", "",
             f"Models trained in this learner version: {len(challengers)}",
             f"Completed evaluations: {len(evaluations)}", ""]
    if not challengers:
        lines += ["No model yet. Keep the LIVE collector and research timer running.",
                  "A fresh installation needs roughly 16 hours of usable evidence plus processing."]
    else:
        latest = challengers[-1]["payload"]
        model = memory.artifact(MODEL_PREFIX + latest["model_version"])
        if model is None:
            raise ValueError("LEARNING_REPORT_MODEL_MISSING")
        calibration = model["payload"]["model"]["context_calibration"]
        lines += ["## Latest model", "", f"Model: {latest['model_version']}",
                  f"Training events (overlapping market observations): {model['payload']['training_event_count']}",
                  f"Recent independent setup samples: {calibration['independent_events']}",
                  "Setup results below are training descriptions, not unseen-test results.", "",
                  "| Setup / condition | Independent events | Mean simulated R |", "|---|---:|---:|"]
        for key, value in sorted(calibration["groups"].items()):
            lines.append(f"| {key} | {value['events']} | {value['mean_net_r']:.3f} |")
        lines += ["", "R means outcome divided by the initial simulated risk.",
                  "Fewer than 8 independent samples: retain the price model; do not claim setup knowledge.",
                  "Evaluation uses 20 validation and 20 test events, each spaced at least 4 hours 5 minutes apart.",
                  "That takes roughly seven days of future data plus outcome maturity, not 40 five-minute candles."]
    for record in evaluations[-10:]:
        evaluation = record["payload"]
        lines += ["", "## " + str(evaluation["challenger_version"]), "", str(evaluation["status"])]
        metrics = evaluation.get("final_test", {})
        for key in ("candidate", "benchmark"):
            data = metrics.get(key, {})
            lines.append(f"{key}: mean R={data.get('mean_net_r', 'unavailable')}; lower confidence bound={data.get('mean_ci_low', 'unavailable')}")
        lines += [f"Trades taken: {metrics.get('trade_utilization', {}).get('trade_events', 'unavailable')} (minimum required: 5)",
                  f"Lower confidence bound of improvement over benchmark: {metrics.get('paired_lift', {}).get('mean_lift_ci_low', 'unavailable')} (must exceed 0)",
                  f"Mean R with doubled base costs: {metrics.get('cost_and_capture', {}).get('cost_stress', {}).get('2.0x', {}).get('mean_net_r', 'unavailable')} (must exceed 0)"]
        gates = evaluation.get("promotion_gates")
        if gates is None:
            lines.append("Detailed rejection evidence is missing; the reason cannot be reconstructed.")
        else:
            failures = explain_gates(gates)
            lines.extend(f"- {item['check']}: {item['explanation']}" for item in failures)
            if not failures:
                lines.append("All checks for this research window passed. This does not promote a live trading model.")
    return "\n".join(lines) + "\n"
