"""Inspect Freqtrade-generated signal pickles only; never read unknown archives.

This script reports signal and rejected-entry counts for diagnosing
M2 historical candidate acceptance and abstention. Not a live strategy.
"""
from __future__ import annotations

import argparse
import io
import joblib
from pathlib import Path
from zipfile import ZipFile


def main():
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path)
    args = p.parse_args()
    with ZipFile(args.archive) as z:
        for suffix in ("_signals.pkl", "_rejected.pkl", "_exited.pkl"):
            members = [n for n in z.namelist() if n.endswith(suffix)]
            if len(members) != 1:
                print(suffix, "NOT FOUND")
                continue
            # Accept only our own official Freqtrade backtest exports.
            content = joblib.load(io.BytesIO(z.read(members[0])))
            print("\n", suffix, "TYPE", type(content).__name__)
            if isinstance(content, dict):
                print("STRATEGIES", list(content.keys())[:5])
                for strategy_name, per_pair in content.items():
                    print("STRATEGY", strategy_name, "TYPE", type(per_pair).__name__)
                    if isinstance(per_pair, dict):
                        total = 0
                        for pair, data in per_pair.items():
                            print("PAIR", pair, "ROWS", len(data),
                                  "COLUMNS", list(data.columns)[:20] if hasattr(data, "columns") else [])
                            total += len(data)
                        print("TOTAL ROWS", total)
                        break


if __name__ == "__main__":
    main()
