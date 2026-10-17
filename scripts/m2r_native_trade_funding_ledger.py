"""V6-only read-only native historical filled-trade funding/fee audit.

Uses actual Freqtrade BACKTEST trades (NOT live fills) and archived public
Binance funding event rates + last completed 1h mark candle as a PROXY.
No exchange credentials, no API, no orders. Audit can NOT certify actual
bid/ask spread, stop slippage, market impact, or funding settlement mark.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m2r_event_cost_labels import FundingSchedule


def read_engine_trades(path: Path, strategy_name: str):
    with ZipFile(path) as z:
        names = [
            n for n in z.namelist()
            if n.endswith(".json") and not n.endswith(("_config.json", ".meta.json"))
        ]
        if len(names) != 1:
            raise ValueError("BAD_ENGINE_BACKTEST_ZIP_LAYOUT")
        content = json.loads(z.read(names[0]))
        return content["strategy"][strategy_name]["trades"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    conf = json.loads(a.config.read_text())
    if not conf["dry_run"] or conf["exchange"]["key"] or conf["exchange"]["secret"]:
        raise RuntimeError("COST_AUDIT_MUST_BE_OFFLINE_NO_EXCHANGE_KEYS")
    pairs = set(conf["exchange"]["pair_whitelist"])
    assert len(pairs) == 25
    trades = read_engine_trades(a.archive, "NbotV6TradeOutcomeFundingResearch")
    assert len(trades) == 24, "EXPECTED_FROZEN_ORIGINAL_24_ENGINE_TRADES"
    sched_by_pair = {}
    funding_event_count = 0
    ambiguous_end_count = 0
    estimated_paid = []
    engine_funding_income = []
    engine_fee = []
    trade_results = []
    reasons = Counter()
    entry_open_match_counts = Counter()
    for trade in trades:
        pair = trade["pair"]
        if pair not in pairs:
            raise RuntimeError("UNEXPECTED_PAIR")
        token = pair.replace("/", "_").replace(":", "_")
        if pair not in sched_by_pair:
            def load(suffix):
                df = pd.read_feather(a.data / (token + suffix))
                df["date"] = pd.to_datetime(df["date"], utc=True)
                if not df["date"].is_unique or not df["date"].is_monotonic_increasing:
                    raise RuntimeError("BAD_HISTORICAL_SOURCE_ORDER")
                return df
            funding = load("-1h-funding_rate.feather")
            mark = load("-1h-mark.feather")
            candles = load("-5m-futures.feather")
            sched_by_pair[pair] = (FundingSchedule.from_candles(funding, mark), candles)
        sched, candle_df = sched_by_pair[pair]
        entry = pd.Timestamp(trade["open_date"])
        exit_at = pd.Timestamp(trade["close_date"])
        if not (entry.tzinfo is not None and exit_at > entry):
            raise RuntimeError("BAD_TRADE_TIMESTAMPS")
        side = -1 if trade["is_short"] else 1
        price = float(trade["open_rate"])
        amount = float(trade["amount"])
        stake = float(trade["stake_amount"])
        assert price > 0 and amount > 0 and 0 < stake <= 1001
        feeopen = float(trade["fee_open"])
        feeclose = float(trade["fee_close"])
        assert abs(feeopen - 0.0005) < 1e-12 and abs(feeclose - 0.0005) < 1e-12
        frac, events, ambiguous = sched.hypothetical_charge(entry, exit_at, price, side)
        paid_usdt = frac * price * amount
        engine_income = float(trade.get("funding_fees", 0))
        fees = amount * (price * feeopen + float(trade["close_rate"]) * feeclose)
        funding_event_count += events
        ambiguous_end_count += int(ambiguous)
        estimated_paid.append(paid_usdt)
        engine_funding_income.append(engine_income)
        engine_fee.append(fees)
        reasons[trade["exit_reason"]] += 1
        m = candle_df.loc[candle_df["date"] == entry]
        if len(m) == 1:
            entry_open_match_counts["matching_entry_timestamp"] += 1
            if np.isclose(price, float(m["open"].iloc[0]), rtol=1e-10, atol=1e-10):
                entry_open_match_counts["entry_price_equals_public_5m_open"] += 1
        trade_results.append({
            "pair": pair,
            "entry_utc": entry.isoformat(),
            "exit_utc": exit_at.isoformat(),
            "side": "short" if side < 0 else "long",
            "engine_exit_reason": trade["exit_reason"],
            "funding_event_count": events,
            "ambiguous_exact_exit_settlement_timing": ambiguous,
            "estimated_public_event_paid_usdt_mark_proxy": round(paid_usdt, 8),
            "backtest_engine_funding_fees_field_usdt": round(engine_income, 8),
            "backtest_simulated_fee_usdt_from_order_prices": round(fees, 8),
            "backtest_profit_usdt": round(float(trade["profit_abs"]), 8),
        })
    engine_income = np.asarray(engine_funding_income)
    estimated_paid = np.asarray(estimated_paid)
    # Backtest field is income (not paid); event mark-based PAID should be
    # compared with NEGATIVE engine field. No guaranteed identical mark.
    signed_difference = engine_income + estimated_paid
    response = {
        "scope": "Exactly 24 native Binance 25-pair simulated engine trades October 8-9 2026, read-only",
        "trades": len(trades),
        "distinct_traded_pairs": len(set(t["pair"] for t in trades)),
        "trade_exit_reasons": dict(reasons),
        "engine_reported_total_simulated_pnl_usdt": round(sum(float(t["profit_abs"]) for t in trades), 6),
        "total_model_fee_0_05pct_per_side_usdt": round(float(sum(engine_fee)), 6),
        "backtest_engine_funding_fees_field_sum_usdt": round(float(engine_income.sum()), 8),
        "estimated_signed_funding_paid_with_public_events_and_completed_mark_proxy_usdt": round(float(estimated_paid.sum()), 8),
        "estimated_signed_event_count_crossed_in_simulated_trades": funding_event_count,
        "ambiguous_trade_exit_exact_funding_boundaries": ambiguous_end_count,
        "engine_field_vs_negative_public_proxy_max_abs_diff_usdt": round(float(np.max(np.abs(signed_difference))), 8),
        "engine_field_vs_negative_public_proxy_sum_diff_usdt": round(float(signed_difference.sum()), 8),
        "entry_candle_timestamp_checks": dict(entry_open_match_counts),
        "funding_event_rates_are_historical_public_data": True,
        "mark_price_is_last_completed_hourly_close_proxy_not_settlement_mark": True,
        "actual_exchange_funding_receipts_observed": False,
        "actual_historic_bid_ask_spreads_observed": False,
        "actual_stop_market_fills_or_market_impact_observed": False,
        "actual_net_trading_cost_verified": False,
        "step3_cost_certification_gate": "NO-GO",
        "trade_rows": trade_results,
    }
    a.output.write_text(json.dumps(response, indent=2) + "\n")
    print("SIMULATED_TRADE_COST_LEDGER", json.dumps({
        k: v for k, v in response.items() if k != "trade_rows"
    }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
