"""Independent read-only audit: fixed saved FreqAI forecasts, 2% vs 1% stop.

No private API, no model execution, no orders, no changing saved outcomes.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research.freqai_v7_net_fit_and_replay import digest
from scripts.v7_three_coin_learning_audit import events

CF_POLICY="V7_5M_PAPER_BROKER_1STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_CF_V1"


def read_trades(path):
    with open(path,encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def audit(root,original,stop1,forecast):
    root=Path(root)
    summary=json.loads((root/"summary.json").read_text())
    if digest(original)!=summary["source_db_sha256"]:
        raise ValueError("ORIGINAL_2PCT_DATA_CHANGED")
    if digest(stop1)!=summary["alternative_db_sha256"]:
        raise ValueError("ONE_PERCENT_DATA_CHANGED")
    if digest(forecast)!=summary["original_saved_predictions_sha256"]:
        raise ValueError("SAVED_MODEL_PREDICTIONS_CHANGED")
    for filename,h in summary["receipts"].items():
        if digest(root/filename)!=h:raise ValueError("LEDGER_SHA_MISMATCH")
    c=sqlite3.connect(stop1.resolve().as_uri()+"?mode=ro",uri=True)
    if dict(c.execute("SELECT k,v FROM meta"))["policy"]!=CF_POLICY:
        raise ValueError("NOT_A_REAL_1PCT_COUNTERFACTUAL_DATASET")
    c.close()
    reports={}
    ids={}
    for key,db,account in (
        ("stop2",original,"RAW_SAVED_FREQAI_STOP_2PCT_CONTROL"),
        ("stop1",stop1,"RAW_SAVED_FREQAI_STOP_1PCT_CF"),
    ):
        result=summary[key]
        trs=read_trades(root/(account+"_trades.jsonl"))
        if not result["account_complete"] or len(trs)!=result["selected_trades"]:
            raise ValueError("PORTFOLIO_NOT_COMPLETE")
        if abs(sum(x["net_after_cost"]*1000 for x in trs)-result["net_pnl_usdt"])>0.0001:
            raise ValueError("TRADE_PNL_MISMATCH")
        if abs(result["stressed_pnl_usdt"]-(result["net_pnl_usdt"]-len(trs)*2.5))>0.001:
            raise ValueError("ADDITIONAL_COST_STRESS_MISMATCH")
        n=sum(e.get("event")=="decision" for e in events(root/(account+"_decisions.jsonl")))
        if n<30000:raise ValueError("MISSING_DECISION_HASHCHAIN")
        con=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
        reasons=Counter()
        wins=Counter()
        bymonth=defaultdict(lambda:{"trades":0,"pnl":0.0})
        try:
            for x in trs:
                why=con.execute("SELECT exit_reason FROM opportunity "
                    "WHERE decision_ms=? AND symbol=? AND side=? AND family=?",
                    (x["decision_ms"],x["symbol"],x["side"],x["family"])).fetchone()
                if why is None:raise ValueError("SOURCE_OPPORTUNITY_NOT_FOUND")
                reasons[why[0]]+=1
                wins["wins" if x["net_after_cost"]>0 else "nonwins"]+=1
                mo=datetime.fromtimestamp(x["exit_ms"]/1000,timezone.utc).strftime("%Y-%m")
                bymonth[mo]["trades"]+=1
                bymonth[mo]["pnl"]+=x["net_after_cost"]*1000
        finally:
            con.close()
        ids[key]={(x["decision_ms"],x["symbol"],x["side"],x["family"]) for x in trs}
        reports[key]={
            "trades":len(trs),"pnl_usdt":result["net_pnl_usdt"],
            "maxdrawdown_pct":result["max_drawdown_pct_of_sleeve"],
            "exit_reasons":dict(reasons),"wins":dict(wins),
            "decision_count":n,
            "month_by_exit":{mo:{"trades":v["trades"],
                   "net_usdt":round(v["pnl"],4)} for mo,v in sorted(bymonth.items())},
        }
    return {
        "audit":"PASSED_ONE_PERCENT_STOP_ONLY_SAME_MODEL_CONTINUOUS_NINE_MONTH",
        "source_2pct_sha":digest(original),
        "source_1pct_sha":digest(stop1),
        "saved_prediction_sha":digest(forecast),
        "pnl_delta_1pct_minus_2pct_usdt":summary["delta_stake_pnl_usdt"],
        "identical_entries_across_stop_versions":len(ids["stop1"]&ids["stop2"]),
        "entries_only_under_1pct":len(ids["stop1"]-ids["stop2"]),
        "entries_only_under_2pct":len(ids["stop2"]-ids["stop1"]),
        "portfolios":reports,
        "limitations":summary["notes"],
    }


def main():
    p=argparse.ArgumentParser()
    for nm in ("root","original","stop1","forecast","out"):
        p.add_argument("--"+nm,required=True,type=Path)
    x=p.parse_args()
    if x.out.exists():raise FileExistsError("REFUSE_OVERWRITE")
    result=audit(x.root,x.original,x.stop1,x.forecast)
    x.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
