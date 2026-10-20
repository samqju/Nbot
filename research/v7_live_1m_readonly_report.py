#!/usr/bin/env python3
"""Read-only report for the public-market-only BTC/ETH/SOL 1m research.

Reads its isolated SQLite event ledger without running a model or placing
orders. Returns current, incomplete results as such until RESEARCH_END.
"""
from collections import Counter
from pathlib import Path
from urllib.parse import quote
import argparse,sqlite3,json
def report(root):
    root=Path(root)
    st=json.loads((root/"status.json").read_text())
    db=root/"virtual_1m.sqlite"
    c=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    try:
        counts=dict(c.execute("SELECT type,COUNT(*) FROM events GROUP BY type"))
        decisions=c.execute(
          "SELECT payload FROM events WHERE type='RAW_DECISION' ORDER BY seq DESC LIMIT 12"
        ).fetchall()
        closes=c.execute(
          "SELECT payload FROM events WHERE type='VIRTUAL_CLOSE' ORDER BY seq"
        ).fetchall()
        opens=c.execute(
          "SELECT payload FROM events WHERE type='VIRTUAL_OPEN' ORDER BY seq"
        ).fetchall()
        return {
          "status":st["status"],
          "updated_at_utc":st["updated_at_utc"],
          "cutoff_utc":st["cutoff_utc"],
          "last_market_candle_ms":st["last_market_candle_ms"],
          "model_fitted_asof_ms":st["model_fitted_asof_ms"],
          "event_counts":counts,
          "virtual_entries":len(opens),"virtual_closed":len(closes),
          "virtual_trades_cap":st["max_ever_new_trades"],
          "net_usdt_excluding_funding":st["realized_pnl_usdt_without_funding"],
          "currently_open":st["virtual_positions"],
          "latest_decisions":[json.loads(x["payload"]) for x in reversed(decisions)],
          "closed_trades":[json.loads(x["payload"]) for x in closes],
          "orders_sent":0,
          "complete":st["status"]=="COMPLETE",
          "research_limitations":"Fee+slippage paper OHLC proxy, no funding or orderbook, at most three selected trades, 1m model is not the prior 20-family 5m model."
        }
    finally:c.close()
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(report(a.run),indent=2,sort_keys=True))
