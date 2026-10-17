#!/usr/bin/env python3
"""M2 trade-level, baseline/AI/no-trade and additive execution-cost stress report.

Read **official Freqtrade exported backtest ZIP files** only. Freqtrade's
profit_abs already includes its simulated entry/exit fees and any funding
modelled by the engine. Additional basis-point stresses are *hypothetical
incremental roundtrip execution costs*, NOT measured spread/slippage/funding.
We do not re-simulate fills or trade-selection feedback.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from zipfile import ZipFile

BPS = (0, 10, 25, 50, 100)


def load_zip(path: Path, strategy_name: str) -> dict:
    with ZipFile(path) as archive:
        names = [name for name in archive.namelist() if
                 name.endswith(".json") and not name.endswith("_config.json")
                 and not name.endswith(".meta.json")]
        if len(names) != 1:
            raise ValueError("Expected exactly one official Freqtrade result JSON")
        raw = json.loads(archive.read(names[0]))
    if strategy_name not in raw.get("strategy", {}):
        raise ValueError(f"Missing {strategy_name} in official strategy archive")
    return raw["strategy"][strategy_name]


def money(x: float) -> float:
    return round(float(x), 3)


def aggregate(trades: list[dict], *, extra_bps: int = 0) -> dict:
    if extra_bps < 0:
        raise ValueError("Negative execution stress is not allowed")
    total = 0.0
    fees = set()
    funding = 0.0
    notional = 0.0
    long_count = 0
    daily = defaultdict(float)
    per_pair = defaultdict(lambda: {"trades": 0, "adjusted_usdt": 0.0, "wins": 0})
    per_side = defaultdict(lambda: {"trades": 0, "adjusted_usdt": 0.0, "wins": 0})
    durations = []
    costs = 0.0
    winners = losers = zero = 0
    for t in trades:
        stake = float(t["stake_amount"])
        leverage = float(t.get("leverage", 1))
        if stake <= 0 or leverage <= 0:
            raise ValueError("Nonpositive stake/leverage in official trade")
        fees.add((round(float(t["fee_open"]), 8), round(float(t["fee_close"]), 8)))
        # 1x in V6, but the stress remains notional-consistent for other inputs.
        cost = stake * leverage * extra_bps / 10000.0
        pnl = float(t["profit_abs"]) - cost
        total += pnl
        costs += cost
        funding += float(t.get("funding_fees") or 0)
        notional += stake * leverage
        durations.append(float(t.get("trade_duration", 0)))
        side = "short" if t.get("is_short", False) else "long"
        long_count += int(side == "long")
        per_pair[t["pair"]]["trades"] += 1
        per_pair[t["pair"]]["adjusted_usdt"] += pnl
        per_pair[t["pair"]]["wins"] += int(pnl > 0)
        per_side[side]["trades"] += 1
        per_side[side]["adjusted_usdt"] += pnl
        per_side[side]["wins"] += int(pnl > 0)
        daily[t["close_date"][:10]] += pnl
        winners += int(pnl > 0)
        losers += int(pnl < 0)
        zero += int(pnl == 0)
    return {
        "trades": len(trades),
        "winners": winners,
        "losers": losers,
        "breakeven": zero,
        "win_rate_pct": money(100 * winners / len(trades)) if trades else None,
        "pnl_usdt": money(total),
        "incremental_execution_cost_usdt": money(costs),
        "total_oneway_trade_notional_usdt": money(notional),
        "sum_engine_reported_funding_fee_field": money(funding),
        "engine_fee_open_close_rates": sorted([list(x) for x in fees]),
        "short_trades": len(trades) - long_count,
        "long_trades": long_count,
        "avg_duration_minutes": money(statistics.mean(durations)) if durations else None,
        "total_duration_minutes": money(sum(durations)),
        "per_pair": {name: {**data, "adjusted_usdt": money(data["adjusted_usdt"])}
                     for name, data in sorted(per_pair.items())},
        "per_side": {name: {**data, "adjusted_usdt": money(data["adjusted_usdt"])}
                     for name, data in sorted(per_side.items())},
        "daily_closed_pnl": {key: money(val) for key, val in sorted(daily.items())},
    }


def validate_compatible(a: dict, b: dict) -> None:
    keys = ("backtest_start", "backtest_end", "max_open_trades", "stake_amount",
            "starting_balance", "timeframe")
    for key in keys:
        if a.get(key) != b.get(key):
            raise ValueError(f"ML/non-ML study mismatch: {key}")
    if set(a.get("pairlist", [])) != set(b.get("pairlist", [])):
        raise ValueError("ML/non-ML study uses different candidate lists")
    if float(a.get("max_open_trades")) != 1:
        raise ValueError("M2 must use one global slot for direct M1 comparison")


def evaluate(ai: dict, baseline: dict) -> dict:
    validate_compatible(ai, baseline)
    cases = {"AI_V6": ai, "NO_ML": baseline}
    result = {
        "study": "M2 matching-period NON-ML vs FreqAI technical benchmark",
        "period_utc": [ai.get("backtest_start"), ai.get("backtest_end")],
        "pair_count": len(ai.get("pairlist", [])),
        "max_open_trades": ai.get("max_open_trades"),
        "starting_balance_usdt": ai.get("starting_balance"),
        "assumptions": [
            "Official Freqtrade profit_abs is net of simulated exchange entry/exit fees and its funding treatment.",
            "Extra costs are an additive, hypothetical roundtrip bps stress on stake*leverage; NOT actual observed spread/slippage.",
            "Additive stress holds all fills, entry times, exit times, and original trade selection fixed.",
            "NO TRADE means zero trades, zero PnL, no exposure; it is a risk-free trading abstention benchmark (cash yields excluded).",
            "One seven-day window is not a profitability estimate, market-universe optimization, or scientific proof of AI incremental value.",
            "A valid model prediction is a forward close-price return estimate, NOT realized trade profit.",
        ],
        "benchmarks": {},
    }
    for name, stats in cases.items():
        trades = stats["trades"]
        official = float(stats["profit_total_abs"])
        reconstructed = aggregate(trades)
        if abs(official - reconstructed["pnl_usdt"]) > 0.02:
            raise ValueError(f"{name} official net PnL mismatch ({official} vs {reconstructed['pnl_usdt']})")
        result["benchmarks"][name] = {
            "official_profit_usdt": money(official),
            "official_profit_factor": stats.get("profit_factor"),
            "official_sharpe": stats.get("sharpe"),
            "official_max_drawdown_usdt": money(stats.get("max_drawdown_abs", 0)),
            "rejected_entry_signals": stats.get("rejected_signals"),
            "realized_by_scenario_extra_roundtrip_bps": {
                str(bps): aggregate(trades, extra_bps=bps) for bps in BPS
            },
        }
    result["benchmarks"]["NO_TRADE"] = {
        "official_profit_usdt": 0.0,
        "trades": 0,
        "additional_fee_or_slippage_cost": 0.0,
        "drawdown_usdt": 0.0,
    }
    no_ml = result["benchmarks"]["NO_ML"]["realized_by_scenario_extra_roundtrip_bps"]
    ai_cases = result["benchmarks"]["AI_V6"]["realized_by_scenario_extra_roundtrip_bps"]
    result["comparison"] = {
        "non_ml_minus_ai_usdt_at_fees_only": money(
            no_ml["0"]["pnl_usdt"] - ai_cases["0"]["pnl_usdt"]
        ),
        "non_ml_break_even_incremental_roundtrip_bps": money(
            10000 * float(baseline["profit_total_abs"]) /
            sum(float(t["stake_amount"]) * float(t.get("leverage", 1))
                for t in baseline["trades"])
        ) if baseline["trades"] else None,
        "ai_outperforms_nonml_at_baseline_costs": ai_cases["0"]["pnl_usdt"] > no_ml["0"]["pnl_usdt"],
        "nonml_outperforms_no_trade_at_all_tested_extra_costs": all(
            x["pnl_usdt"] > 0 for x in no_ml.values()
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(load_zip(args.ai, "NbotV6"), load_zip(args.baseline, "NbotV6NoML"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key in ("AI_V6", "NO_ML"):
        b = report["benchmarks"][key]
        print(f"{key}: {b['realized_by_scenario_extra_roundtrip_bps']['0']['trades']} trades, "
              f"{b['official_profit_usdt']:+.3f} USDT with simulated base fees")
        print("  Extra roundtrip cost (bps) -> adjusted total USDT:",
              {k: v["pnl_usdt"] for k, v in b["realized_by_scenario_extra_roundtrip_bps"].items()})
    print("NO_TRADE: 0 trades, 0.000 USDT")
    print("Comparison:", report["comparison"])
    print("Saved:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
