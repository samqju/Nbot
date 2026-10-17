#!/usr/bin/env python3
"""Compact, reproducible M2 Sep 2026 25-pair evaluation evidence.

Reads existing official Freqtrade historical ZIP backtests, previously generated
data/funding/fee audits and raw training LOG. Never downloads market data,
trains models, places orders or changes the strategy.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from m2_funding_reconcile import archive_strategy


def summary(r: dict) -> dict:
    scenarios = r["realized_by_scenario_extra_roundtrip_bps"]
    plain = scenarios["0"]
    return {
        "trades": plain["trades"],
        "winners": plain["winners"],
        "losers": plain["losers"],
        "win_rate_pct": plain["win_rate_pct"],
        "net_usdt": plain["pnl_usdt"],
        "engine_fee_open_close_rates": plain["engine_fee_open_close_rates"],
        "long_trades": plain["long_trades"],
        "short_trades": plain["short_trades"],
        "per_side": plain["per_side"],
        "per_coin": plain["per_pair"],
        "extra_fixed_roundtrip_cost_scenarios_usdt": {
            bps: row["pnl_usdt"] for bps, row in scenarios.items()
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cost", required=True, type=Path)
    p.add_argument("--data-audit", required=True, type=Path)
    p.add_argument("--exposure", required=True, type=Path)
    p.add_argument("--funding", required=True, type=Path)
    p.add_argument("--ai-highfee", required=True, type=Path)
    p.add_argument("--nonml-highfee", required=True, type=Path)
    p.add_argument("--training-log", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    study = json.loads(args.cost.read_text())
    data = json.loads(args.data_audit.read_text())
    exposure = json.loads(args.exposure.read_text())
    funding = json.loads(args.funding.read_text())
    if data["passed_pairs"] != 25 or data["failed_pairs"]:
        raise ValueError("Historical candle audit is not 25/25")
    if study["pair_count"] != 25 or study["max_open_trades"] != 1:
        raise ValueError("Wrong pair count or slots")
    if exposure["duration_hours"] != 720:
        raise ValueError("Expected precisely 30 days")
    ai = summary(study["benchmarks"]["AI_V6"])
    baseline = summary(study["benchmarks"]["NO_ML"])
    ai_fee = archive_strategy(args.ai_highfee, "NbotV6")
    no_fee = archive_strategy(args.nonml_highfee, "NbotV6NoML")
    train_log = args.training_log.read_text(errors="replace")
    model_fits = train_log.count("Done training")
    error_lines = sum(" - ERROR -" in line for line in train_log.splitlines())
    if model_fits != 125 or error_lines:
        raise ValueError(f"Expected 125 completed 30-day rolling fits and zero errors; got {model_fits} fits and {error_lines} errors")
    if ai["trades"] != 137 or baseline["trades"] != 163:
        raise ValueError("Unexpected exported trade counts for Sep 2026")
    if abs(ai["net_usdt"] + 444.98) > .03 or abs(baseline["net_usdt"] + 242.894) > .03:
        raise ValueError("Unexpected original Sep PnL")
    high_fee = {
        "AI_V6": {"trades": len(ai_fee["trades"]),
                  "net_usdt": round(float(ai_fee["profit_total_abs"]), 3)},
        "NO_ML": {"trades": len(no_fee["trades"]),
                  "net_usdt": round(float(no_fee["profit_total_abs"]), 3)}
    }
    report = {
        "title": "NBOT V6 M2: September 2026 complete-month, 25-pair non-ML/AI vs NO TRADE comparison",
        "window_utc": ["2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"],
        "days": 30, "futures_pairs": 25,
        "initial_dry_wallet_usdt": 100000,
        "stake_amount_usdt": 1000,
        "max_global_open_positions": 1,
        "leverage": 1,
        "source": "Official Freqtrade 2026.9 / FreqAI LightGBMRegressor historical Docker backtests",
        "data_audit": {
            "passed_pairs": data["passed_pairs"],
            "failed_pairs": data["failed_pairs"],
            "required_warmup_start_utc": data["required_warmup_start_utc"]
        },
        "rolling_freqai_train_days": 30,
        "rolling_freqai_test_days": 7,
        "expected_models": 125,
        "actual_fitted_models": model_fits,
        "error_lines": error_lines,
        "baseline_fee_per_side": 0.0005,
        "first_week_october_reference": {
            "AI_V6_net_usdt": -135.640,
            "NO_ML_net_usdt": 169.849,
            "note": "Oct 1-8 was trained on September. This fresh September test trains from earlier history instead."
        },
        "september_base_fee": {
            "AI_V6": ai,
            "NO_ML": baseline,
            "NO_TRADE": {"trades": 0, "net_usdt": 0.0}
        },
        "september_doubled_fee_per_side": 0.001,
        "september_doubled_fee_official_replays": high_fee,
        "position_exposure": exposure["results"],
        "funding_reconciliation": {
            name: {k: row[k] for k in (
                "trades", "total_external_estimate_usdt",
                "total_engine_funding_field_usdt",
                "absolute_delta_sum_usdt",
                "max_trade_abs_delta_usdt",
                "trades_disagreeing_by_over_0_05_usdt",
                "settlement_events_in_trade_windows"
            )}
            for name,row in funding["results"].items()
        },
        "comparison": {
            "NO_ML_minus_AI_net_usdt": round(baseline["net_usdt"]-ai["net_usdt"], 3),
            "NO_TRADE_minus_AI_net_usdt": round(-ai["net_usdt"], 3),
            "NO_TRADE_minus_NO_ML_net_usdt": round(-baseline["net_usdt"], 3)
        },
        "limits": [
            "One pre-chosen month plus one earlier October week is NOT sufficient evidence of permanent profitability or market-regime robustness.",
            "Static 25-pair universe; owner-planned eight-hour dynamic selector and 20-position paper mode NOT used.",
            "Broker fill prices, historical best bid/ask spreads, real slippage, stop gaps and queue positions are NOT independently verified.",
            "Extra basis-point stresses are hypothetical cost deductions on unchanged fills, not market orders.",
            "The previously flagged FreqAI lookahead indicator-difference warning remains unresolved; M2 release approval is NOT granted.",
            "Using August/prior history for sequential training avoids simple in-sample September reuse, but is not a blanket certification against leakage."
        ],
        "decision": "Research study complete; M2 release remains NO-GO, no M3/paper/live authorization."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("METRICS", json.dumps({
        "AI": ai["net_usdt"], "NO_ML": baseline["net_usdt"],
        "doubled_fees": high_fee,
        "fitted_models": model_fits,
        "funding_flagged": {
            k:v["trades_disagreeing_by_over_0_05_usdt"]
            for k,v in report["funding_reconciliation"].items()
        }
    }))
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
