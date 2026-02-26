# ============================================================
# UNIVERSE SELECTOR — MAINNET (Universe v3 - Velocity Weighted)
# ============================================================
# Policy:
# - USDT perpetual contracts only
# - Liquidity × Volatility weighted ranking
# - Remove dead pairs (< MIN_CHANGE_PCT)
# - Remove extreme blow-off pairs (> MAX_CHANGE_PCT)
# - Deterministic output
# - Cron-safe execution
# ============================================================

from dotenv import load_dotenv
load_dotenv()

import os
import json
import requests
from datetime import datetime, timezone

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
UNIVERSE_SNAPSHOT_FILE = "/home/ubuntu/nbot/universe_snapshot.json"
EXPECTED_SIZE = 30

BASE_URL = os.getenv("TESTNET_BASE_URL")
TIMEOUT = 5

# --- Velocity Filters ---
MIN_CHANGE_PCT = 1.0     # Remove dead pairs
MAX_CHANGE_PCT = 15.0    # Remove extreme parabolic pairs
VOL_CAP_FOR_SCORING = 10.0  # Cap volatility normalization


# ============================================================
# HELPERS
# ============================================================

def fetch_exchange_info():
    resp = requests.get(
        f"{BASE_URL}/fapi/v1/exchangeInfo",
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_24h_tickers():
    resp = requests.get(
        f"{BASE_URL}/fapi/v1/ticker/24hr",
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


# ============================================================
# BUILD UNIVERSE (Velocity Weighted)
# ============================================================

def build_universe():

    exchange_info = fetch_exchange_info()
    tickers = fetch_24h_tickers()

    # --------------------------------------------------------
    # Supported USDT Perpetual Symbols
    # --------------------------------------------------------

    supported = {
        s["symbol"]
        for s in exchange_info["symbols"]
        if (
            s["contractType"] == "PERPETUAL"
            and s["quoteAsset"] == "USDT"
            and s["status"] == "TRADING"
        )
    }

    candidates = []

    for t in tickers:

        symbol = t.get("symbol")

        # Reject non-ascii or weird symbols
        if not isinstance(symbol, str):
            continue

        if not symbol.isascii():
            continue

        if not symbol.endswith("USDT"):
            continue

        base = symbol.replace("USDT", "")
        if not base.isalnum():
            continue

        if symbol not in supported:
            continue

        try:
            quote_volume = float(t["quoteVolume"])
            change_pct = abs(float(t["priceChangePercent"]))
        except Exception:
            continue

        # --------------------------------------------------------
        # Velocity Filters
        # --------------------------------------------------------

        # Remove dead pairs
        if change_pct < MIN_CHANGE_PCT:
            continue

        # Remove extreme blow-offs
        if change_pct > MAX_CHANGE_PCT:
            continue

        # --------------------------------------------------------
        # Velocity Weighted Score
        # --------------------------------------------------------

        normalized_vol = min(change_pct, VOL_CAP_FOR_SCORING) / VOL_CAP_FOR_SCORING

        velocity_score = quote_volume * normalized_vol

        candidates.append({
            "symbol": symbol,
            "quote_volume": quote_volume,
            "change_pct": change_pct,
            "score": velocity_score,
        })

    # --------------------------------------------------------
    # Sort by Velocity Score
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    universe = [
        c["symbol"]
        for c in candidates[:EXPECTED_SIZE]
    ]

    return universe


# ============================================================
# ENTRYPOINT (CRON SAFE)
# ============================================================

def main():
    try:
        universe = build_universe()

        if len(universe) < EXPECTED_SIZE:
            raise RuntimeError(
                f"INSUFFICIENT_SYMBOLS | found={len(universe)}"
            )

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(universe),
            "symbols": universe,
        }

        with open(UNIVERSE_SNAPSHOT_FILE, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)

        print(
            f"[OK] Universe v3 built | "
            f"symbols={len(universe)} | "
            f"time={snapshot['generated_at']}"
        )

    except Exception as e:
        print(f"[ERROR] Universe build failed | {e}")


if __name__ == "__main__":
    main()
