#!/usr/bin/env python3
"""Read-only verification of live public-feed virtual trade events and 1m paths.

No external calls, exchange orders, model execution, dataset edits or PnL
invented from predictions. Requires EXACT ledger path reproducibility.
"""
from __future__ import annotations
import argparse,json,sqlite3
from pathlib import Path
from hashlib import sha256
from nbot_v7.data import Bar
from nbot_v7.runtime.broker import PaperBroker
from nbot_v7.runtime.risk import RiskPolicy
from research.v7_live_1m_virtual_15day import S,ONE,MAX_ENTRIES,EXPERIMENT


def verify(root):
    root=Path(root)
    status=json.loads((root/"status.json").read_text())
    conn=sqlite3.connect((root/"virtual_1m.sqlite").resolve().as_uri()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    try:
        meta={r["k"]:json.loads(r["v"]) for r in conn.execute("SELECT k,v FROM meta")}
        if meta.get("experiment")!=EXPERIMENT or status.get("orders_sent")!=0 or status["api_credentials_used"] is not False:
            raise ValueError("INVALID_PUBLIC_ONLY_SOURCE_CONTRACT")
        ev=[{"seq":r["seq"],"kind":r["type"],"data":json.loads(r["payload"])}
            for r in conn.execute("SELECT seq,type,payload FROM events ORDER BY seq")]
        opens=[e for e in ev if e["kind"]=="VIRTUAL_OPEN"]
        closes=[e for e in ev if e["kind"]=="VIRTUAL_CLOSE"]
        if not len(opens)==len(closes)==MAX_ENTRIES or len(opens)>meta["new_entry_count"]:
            raise ValueError("NOT_EXACT_THREE_CLOSED_VIRTUAL_TRADES")
        if status["virtual_positions"] or meta["positions"] or meta["pending"]:
            raise ValueError("UNRESOLVED_VIRTUAL_POSITIONS_PENDING")
        if len([e for e in ev if e["kind"]=="MODEL_FITTED"])<1:
            raise ValueError("NO_SAVED_FREQAI_MODEL_FITTED")
        if len(set(e["data"]["symbol"] for e in opens))!=MAX_ENTRIES:
            raise ValueError("THREE_COIN_SCOPE_MISMATCH")
        by_symbol={}
        for opened in opens:
            op=opened["data"]
            symbol=op["symbol"]
            assert symbol in S
            matching=[e for e in closes if e["data"]["symbol"]==symbol]
            if len(matching)!=1 or opened["seq"]>=matching[0]["seq"]:
                raise ValueError("OPEN_CLOSE_EVENT_RECONCILIATION_FAILED")
            cl=matching[0]["data"]
            if op["side"]!=cl["side"] or op["entry_time_ms"]!=cl["entered_at_ms"]:
                raise ValueError("VIRTUAL_TRADE_ENTRY_IDENTITY_MISMATCH")
            if cl["exit_reason"] not in ("STOP","TARGET","HORIZON","STOP_AMBIGUOUS"):
                raise ValueError("UNKNOWN_EXIT_REASON")
            t0=op["entry_time_ms"]
            t1=cl["exit_time_ms"]
            if t0%ONE or t1%ONE or t1<=t0 or t1-t0>3600000:
                raise ValueError("INVALID_MINUTE_PATH_OR_HORIZON")
            recorded=[Bar(*r) for r in conn.execute(
                "SELECT t,o,h,l,c,v FROM bars WHERE symbol=? AND t>=? AND t<? ORDER BY t",
                (symbol,t0,t1))]
            if len(recorded)!=(t1-t0)//ONE or recorded[0].t!=t0:
                raise ValueError("MISSING_PUBLIC_1M_CANDLE_HISTORY")
            if any(b.t-a.t!=ONE for a,b in zip(recorded,recorded[1:])):
                raise ValueError("MARKET_BARS_HAVE_TIME_GAP")
            broker=PaperBroker()
            policy=RiskPolicy()
            position=broker.submit({
                "id":"READ_ONLY_RECOMPUTE_SOURCE","symbol":symbol,
                "side":op["side"],"time_ms":t0,"quote":recorded[0].o},policy)
            if abs(position["entry_price"]-op["entry_price"])>1e-6 or abs(position["stop"]-op["stop"])>1e-6 or abs(position["target"]-op["target"])>1e-6:
                raise ValueError("ENTRY_NOT_SOURCE_MARKET_OPEN")
            actual=None
            for bar in recorded:
                actual,position=broker.on_bar(position,bar,bar.t+ONE,policy)
                if actual is not None:break
            if actual is None or actual["available_ms"]!=t1 or actual["reason"]!=cl["exit_reason"]:
                raise ValueError("INDEPENDENT_EXIT_REASON_OR_TIME_MISMATCH")
            for p,q in (("entry_price",cl["entry_price"]),
                        ("exit_price",cl["exit_price"]),
                        ("fees_usdt",cl["fees_usdt"]),
                        ("net_usdt",cl["pnl_usdt_without_funding"])):
                if abs(float(actual[p])-float(q))>1e-7:
                    raise ValueError("SOURCE_REPLAY_ECONOMICS_NOT_MATCH:"+p)
            sign=1 if op["side"]=="LONG" else -1
            favorable=sign*(cl["exit_price"]/cl["entry_price"]-1)
            by_symbol[symbol]={
                "side":op["side"],"entry_ms":t0,"exit_ms":t1,
                "duration_minutes":(t1-t0)//ONE,
                "entry_price":cl["entry_price"],"exit_price":cl["exit_price"],
                "price_direction_correct_at_exit":favorable>0,
                "gross_direction_pct":round(favorable*100,5),
                "model_predicted_aftercost_bp":round(cl["predicted_net_fraction"]*10000,4),
                "actual_aftercost_bp":round(cl["actual_aftercost_net_fraction"]*10000,4),
                "fees_usdt":round(cl["fees_usdt"],6),
                "net_usdt_without_funding":round(cl["pnl_usdt_without_funding"],6),
                "exit_reason":cl["exit_reason"],
                "independent_replay":"EXACT_1M_BARS_ENTRY_EXIT_NET_MATCH",
            }
        summed=sum(x["net_usdt_without_funding"] for x in by_symbol.values())
        if abs(summed-status["realized_pnl_usdt_without_funding"])>0.00011 or abs(summed-meta["realized_usdt"])>0.000001:
            raise ValueError("ACCOUNT_REALIZED_PNL_RECONCILIATION_MISMATCH")
        if status["virtual_trades_started"]!=len(opens):
            raise ValueError("TRADE_CAP_NOT_MATCHED")
        hashes={x:sha256((root/x).read_bytes()).hexdigest() for x in ("status.json",)}
        return {
            "audit":"EXACT_THREE_PUBLIC_1M_VIRTUAL_TRADES_CLOSED_INDEPENDENT_REPLAY_PASS",
            "market":"BINANCE_PUBLIC_USDM_1M",
            "event_counts":{k:sum(e["kind"]==k for e in ev) for k in ("MODEL_FITTED","RAW_DECISION","VIRTUAL_OPEN","VIRTUAL_CLOSE","FAIL_CLOSED_SOURCE")},
            "positions":by_symbol,
            "sum_pnl_without_funding":round(summed,6),
            "virtual_equity_without_funding":round(10000+summed,6),
            "fee_and_slippage_proxy":True,"funding_not_modeled":True,
            "orders_sent":0,
            "experiment_still_running":status["status"]=="RUNNING",
            "experiment_status":status["status"],
            "latest_status_utc":status["updated_at_utc"],
            "status_sha256":hashes["status.json"],
            "source_quality":"1M_OHLC_PATH_WITH_POST_CLOSE_FINALITY_DELAY_NO_NATIVE_ORDERBOOK",
            "sample_warning":"THREE_TRADES_NOT_STATISTICALLY_MEANINGFUL_EDGE_TEST",
        }
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    result=verify(a.run)
    print(json.dumps(result,indent=2,sort_keys=True))
    if a.out:
        if a.out.exists():raise FileExistsError("REFUSE_TO_OVERWRITE_PREVIOUS_AUDIT")
        a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")


if __name__=="__main__":
    main()
