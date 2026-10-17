"""Inspect official Freqtrade backtest ZIP artifacts; reads only, no trading."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from zipfile import ZipFile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.archives:
        with ZipFile(path) as z:
            print("\nARCHIVE:", path.name)
            for name in z.namelist():
                print("MEMBER:", name)
                if not name.endswith(".json") or name.endswith(".meta.json") or "_config" in name:
                    continue
                data = json.loads(z.read(name))
                if not isinstance(data, dict):
                    print("TYPE", type(data).__name__)
                    continue
                print("ROOT KEYS:", list(data)[:20])
                if "strategy" in data:
                    for strategy_name, strategy in data["strategy"].items():
                        print("STRATEGY:", strategy_name)
                        print("STATS KEYS:", list(strategy)[:65])
                        trades = strategy.get("trades", [])
                        print("TRADE COUNT:", len(trades))
                        if trades:
                            print("FIRST TRADE FIELD NAMES:", list(trades[0]))
                            print("FIRST TRADE PREVIEW:", {k:v for k,v in trades[0].items()
                                  if k in ("pair","stake_amount","profit_abs","profit_ratio",
                                           "leverage","open_date","close_date","is_short",
                                           "funding_fees","fee_open","fee_close")})
if __name__ == "__main__":
    main()
