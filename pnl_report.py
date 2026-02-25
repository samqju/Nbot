# ==========================================================
# PNL REPORT MODULE
# ==========================================================

import os
from datetime import datetime, timezone
import re

TRADES_LOG_PATH = "logs/trades.txt"


def _utc_today_string():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def generate_daily_pnl_summary():

    if not os.path.exists(TRADES_LOG_PATH):
        return "No trades log found."

    today_str = _utc_today_string()

    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    total_profit = 0.0
    total_loss = 0.0

    with open(TRADES_LOG_PATH, "r") as f:
        for line in f:

            # Example log format:
            # [2026-02-17 05:52:18,100] [INFO] [trades] TRADE_CLOSE | ... pnl=12.34

            if "TRADE_CLOSE" not in line:
                continue

            # Filter only today's UTC trades
            if today_str not in line:
                continue

            match = re.search(r"pnl=([-+]?\d*\.?\d+)", line)
            if not match:
                continue

            pnl = float(match.group(1))

            total_trades += 1

            if pnl > 0:
                winning_trades += 1
                total_profit += pnl
            elif pnl < 0:
                losing_trades += 1
                total_loss += pnl

    net_pnl = total_profit + total_loss

    summary = (
        f"📊 <b>DAILY PnL SUMMARY (UTC)</b>\n\n"
        f"Total Trades Closed: {total_trades}\n"
        f"Winning Trades: {winning_trades}\n"
        f"Losing Trades: {losing_trades}\n\n"
        f"Total Profit: {total_profit:.2f} USD\n"
        f"Total Loss: {total_loss:.2f} USD\n"
        f"Net PnL: {net_pnl:.2f} USD\n"
    )

    return summary
