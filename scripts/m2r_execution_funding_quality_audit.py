"""Read-only funding/mark and execution-evidence limitations for V6 research.

Uses previously examined Sep–Oct 2026 history; it neither inspects the
pre-registered May–Aug trading outcomes nor executes Freqtrade strategies.
Funding-price events and price/mark basis cannot establish bid/ask spread,
slippage, stop-market fills, or a profitable trading edge.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--start", default="2026-09-01")
    p.add_argument("--end", default="2026-10-16")
    a = p.parse_args()
    start, end = pd.Timestamp(a.start, tz="UTC"), pd.Timestamp(a.end, tz="UTC")
    config = json.loads(a.config.read_text())
    assert config["exchange"]["key"] == config["exchange"]["secret"] == ""
    pairs = config["exchange"]["pair_whitelist"]
    assert len(pairs) == 25
    per_pair = []
    all_rates, mark_bases, next_open_gaps = [], [], []
    for pair in pairs:
        tok = pair.replace("/", "_").replace(":", "_")
        f = {kind: pd.read_feather(a.data / f"{tok}-{suffix}.feather") for kind, suffix in (
            ("five", "5m-futures"), ("futures", "1h-futures"),
            ("mark", "1h-mark"), ("funding", "1h-funding_rate")
        )}
        for kind, df in f.items():
            df["date"] = pd.to_datetime(df["date"], utc=True)
            assert df["date"].is_unique and df["date"].is_monotonic_increasing, (pair,kind)
            f[kind] = df.loc[(df["date"] >= start) & (df["date"] < end)].copy()
        rates = f["funding"]
        rate_col = "funding_rate"
        if rate_col not in rates.columns:
            raise RuntimeError(f"NO_FUNDING_RATE_OPEN_COLUMN: {pair}: {list(rates)}")
        r = rates[rate_col].to_numpy(dtype=float)
        assert len(r) > 2 and np.isfinite(r).all(), pair
        # Funding events may have gaps and are not assumed to be 1h candles.
        event_interval = rates["date"].diff().dropna()
        event_hours = (event_interval / pd.Timedelta(hours=1)).to_numpy(dtype=float)
        all_rates.extend(r.tolist())

        future = f["futures"][["date", "close"]].rename(columns={"close": "future_close"})
        mark = f["mark"][["date", "close"]].rename(columns={"close": "mark_close"})
        both = future.merge(mark, on="date", validate="one_to_one")
        assert len(both) > 0, pair
        mark_basis_bp = (both["mark_close"].to_numpy(dtype=float) /
                         both["future_close"].to_numpy(dtype=float) - 1) * 1e4
        assert np.isfinite(mark_basis_bp).all(), pair
        mark_bases.extend(mark_basis_bp.tolist())

        five = f["five"]
        next_bp = (five["open"].to_numpy(dtype=float)[1:] /
                   five["close"].to_numpy(dtype=float)[:-1] - 1) * 1e4
        # This is next-candle open vs previous close; NOT realized slippage.
        next_open_gaps.extend(next_bp.tolist())
        per_pair.append({
            "pair":pair,
            "funding_event_count":len(r),
            "funding_columns":list(rates.columns),
            "positive_funding_event_count":int((r>0).sum()),
            "negative_funding_event_count":int((r<0).sum()),
            "max_absolute_funding_rate_bp_per_event":float(abs(r).max()*1e4),
            "funding_inter_event_hours_values":sorted(set(event_hours.tolist())),
            "mark_futures_hourly_timestamp_matches":len(both),
            "mark_only_unmatched_hours":len(mark)-len(both),
            "futures_only_unmatched_hours":len(future)-len(both),
            "five_minute_candles":len(five),
        })

    rates=np.asarray(all_rates,dtype=float)
    basis=np.asarray(mark_bases,dtype=float)
    gaps=np.asarray(next_open_gaps,dtype=float)
    report={
        "scope":"V6 previously examined Sept 1-Oct 15 2026 candles only; NOT future May-Aug research periods",
        "from_inclusive_utc":str(start),"until_exclusive_utc":str(end),
        "pairs":len(pairs),"funding_events":len(rates),
        "funding_event_rate_positive_count":int((rates>0).sum()),
        "funding_event_rate_negative_count":int((rates<0).sum()),
        "funding_rate_abs_percentiles_bp":{str(q):float(np.percentile(abs(rates)*1e4,q)) for q in (50,90,95,99,100)},
        "funding_event_magnitude_above_1bp_count":int((abs(rates)*1e4>1.0).sum()),
        "label_assumed_funding_reserve_bp_per_trade":1.0,
        "funding_rate_per_event_caveat":"A complete trade may or may not cross funding events; sign depends on long/short and timestamp/exchange settlement. A constant 1bp trade-label reserve is not observed funding paid.",
        "mark_futures_hourly_matched_rows":len(basis),
        "mark_futures_basis_absolute_bp_percentiles":{str(q):float(np.percentile(abs(basis),q)) for q in (50,90,95,99,100)},
        "next_candle_open_previous_close_gap_abs_bp_percentiles":{str(q):float(np.percentile(abs(gaps),q)) for q in (50,90,95,99,100)},
        "realized_bid_ask_spreads_observed":False,
        "actual_order_book_depth_observed":False,
        "realized_trade_slippage_observed":False,
        "actual_stop_market_fill_paths_observed":False,
        "cost_and_fill_quality_gate_pass":False,
        "trading_notional_base_usdt":1000,
        "model_label_reserved_roundtrip_venue_fees_bp":10,
        "model_label_reserved_roundtrip_extra_slippage_bp":10,
        "model_label_reserved_flat_funding_bp":1,
        "audit_generated_utc":datetime.now(timezone.utc).isoformat(),
        "by_pair":per_pair,
    }
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print("AUDIT pairs",len(pairs),"funding_events",len(rates),
          "funding_events_abs_above_1bp",report["funding_event_magnitude_above_1bp_count"],
          "mark_futures_matched_hours",len(basis),
          "COST_GATE_PASS",report["cost_and_fill_quality_gate_pass"],flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
