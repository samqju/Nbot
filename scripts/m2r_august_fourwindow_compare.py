"""Research-only 25-market August 2026 30/60/90/180 native engine comparison.

Read ZIPs written by real Freqtrade historical backtesting, not overlapping
hypothetical opportunity labels. Fail closed on inconsistent dates, markets,
stake, model count or identifiers. Extra costs are purely hypothetical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

WINDOWS=(30,60,90,180)
STRESS_BPS=(0,10,15,25)
PAIR_COUNT=25
STRATEGY="NbotV6TradeOutcomeFundingResearch"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(archive:Path):
    with ZipFile(archive) as z:
        js=[n for n in z.namelist() if n.endswith(".json") and not n.endswith("_config.json") and not n.endswith(".meta.json")]
        if len(js)!=1:
            raise RuntimeError("INVALID_ENGINE_ARCHIVE_JSON_COUNT")
        v=json.loads(z.read(js[0]))
        if set(v["strategy"]) != {STRATEGY}:
            raise RuntimeError("UNEXPECTED_STRATEGY")
        return v["strategy"][STRATEGY]


def score(folder:Path, days:int):
    files=sorted(folder.glob("backtest_results/*.zip"))
    if len(files)!=1:
        raise RuntimeError(f"REQUIRES_ONE_COMPLETE_BACKTEST_ARCHIVE_{days} found={len(files)}")
    stats=extract(files[0])
    expected=f"nbot-v6-m2r-multiwindow-aug2026-{days}d-20261017"
    if (stats["freqai_identifier"]!=expected or
            stats["max_open_trades"]!=1 or
            stats["stake_amount"]!=1000 or
            float(stats["starting_balance"])!=100000 or
            stats["timeframe"]!="5m" or
            stats["trading_mode"]!="futures" or
            stats["backtest_start"]!="2026-08-01 00:00:00" or
            stats["backtest_end"]!="2026-08-08 00:00:00" or
            len(stats["pairlist"])!=PAIR_COUNT):
        raise RuntimeError(f"INVALID_MATCHED_WINDOW_OR_RISK_CONFIG_{days}")
    trades=stats["trades"]
    if len(trades)!=stats["total_trades"]:
        raise RuntimeError(f"TRADE_COUNT_MISMATCH_{days}")
    total_nominal=0.
    for t in trades:
        if (not (0.95 <= float(t.get("leverage") or 0)<=1.05) or
            not (900 <= float(t["stake_amount"]) <= 1100) or
            abs(float(t["fee_open"])-0.0005)>1e-12 or
            abs(float(t["fee_close"])-0.0005)>1e-12):
            raise RuntimeError(f"WRONG_TRADE_RISK_FEE_ASSUMPTION_{days}")
        total_nominal+=float(t["stake_amount"])*float(t["leverage"])
    original_pnl=float(stats["profit_total_abs"])
    if abs(sum(float(t["profit_abs"]) for t in trades)-original_pnl)>0.001:
        raise RuntimeError(f"PNL_SUM_MISMATCH_{days}")
    model_files=sorted(folder.glob(f"models/{expected}/sub-train-*/*_model.joblib"))
    if len(model_files)!=PAIR_COUNT:
        raise RuntimeError(f"UNEXPECTED_FITTED_PAIR_COUNT_{days} found={len(model_files)}")
    stopped=sum(t["exit_reason"]=="stop_loss" for t in trades)
    return {
        "lookback_days":days,
        "fitted_model_artifacts":len(model_files),
        "engine_25_market_pairs":len(stats["pairlist"]),
        "trades":len(trades),
        "wins":sum(float(t["profit_abs"])>0 for t in trades),
        "shorts":sum(bool(t["is_short"]) for t in trades),
        "stops":stopped,
        "total_nominal_turnover_usdt":round(total_nominal,4),
        "engine_pnl_usdt":round(original_pnl,6),
        "engine_max_drawdown_abs_usdt":round(float(stats["max_drawdown_abs"]),6),
        "simulated_funding_sum_usdt":round(sum(float(t.get("funding_fees") or 0) for t in trades),8),
        "additional_cost_bps_roundtrip_to_total_usdt":{
            str(bp):round(original_pnl-total_nominal*bp/10000,6) for bp in STRESS_BPS},
        "source_archive_sha256":sha(files[0]),
        "model_sha256_sample":sha(model_files[0]),
        "engine_backtest_days":stats["backtest_days"],
        "date_start":stats["backtest_start"],
        "date_end":stats["backtest_end"],
        "fees_0_05percent_per_side":True,
        "no_trade_baseline_usdt":0,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    results=[score(a.root/f"w{w}",w) for w in WINDOWS]
    data={
        "scope":"Full native Freqtrade 2026.9 25-market Aug1-8 2026 historical operational pilot; source months known; NOT untouched blind M2 acceptance",
        "four_identical_strategy_model_hyperparam_and_cost_runs":True,
        "only_changed_dimension":"AI training 30/60/90/180 days, independent FreqAI model identifier",
        "model_strategy":STRATEGY,
        "fee_each_side_fraction":0.0005,
        "extra_roundtrip_cost_is_hypothetical":True,
        "historical_orderbook_spread_and_stop_fills_verified":False,
        "models_auto_promoted":False,
        "paper_or_live_trading_started":False,
        "formal_M2_gate":"NO-GO",
        "model_windows":results,
    }
    a.output.write_text(json.dumps(data,indent=2)+"\n")
    for x in results:
        print("AUDITED_WINDOW",x["lookback_days"],"trades",x["trades"],
              "pnl",x["engine_pnl_usdt"],"extra25bp",x["additional_cost_bps_roundtrip_to_total_usdt"]["25"],
              "dd",x["engine_max_drawdown_abs_usdt"],flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
