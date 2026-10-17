from pathlib import Path
import json
p=Path("/root/nbot-v6-m1-20261016/source/user_data/backtest_results/m2-september-funding.json")
j=json.loads(p.read_text())
for name,r in j["results"].items():
 print(name,"trades",r["trades"],"events",r["settlement_events_in_trade_windows"],
       "external",r["total_external_estimate_usdt"],"engine",r["total_engine_funding_field_usdt"],
       "sum_abs_delta",r["absolute_delta_sum_usdt"],"max_delta",r["max_trade_abs_delta_usdt"])
 for t in r["trade_differences"]:
  if abs(t["delta_usdt"]) > .05:
   print("FLAGGED",t)
