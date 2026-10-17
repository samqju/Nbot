import json
from pathlib import Path
p=Path("/root/nbot-v6-m1-20261016/source/user_data/backtest_results/m2-historical-depth.json")
d=json.loads(p.read_text())
for k in ("trades","entry_exit_events","status_counts","valid_liquidity_ge_order_count","matched_depth_multiple_of_order_min","matched_depth_multiple_of_order_median","archive_files_checked","download_missing_files"):
 print(k, d.get(k))
print("STALE EVENTS",[{"pair":t["pair"],"sides":[x for x in t["sides"] if x["state"]!="MATCH"]} for t in d["trade_events"] if any(x["state"]!="MATCH" for x in t["sides"])][:5])
