# ============================================================
# UNIVERSE SELECTOR — TESTNET (Universe v2)
# ============================================================
# Policy:
# - Top 30 symbols by quote_volume
# - Exclude extreme 24h movers (> +6% or < -6%)
# - USDT perpetual contracts only
# - Cron-safe execution
# - Deterministic output
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSE_SNAPSHOT_FILE = os.path.join(
    BASE_DIR,
    "universe_snapshot.json"
)

EXPECTED_SIZE = 30

BASE_URL = os.getenv("TESTNET_BASE_URL")
TIMEOUT = 5

CHANGE_THRESHOLD_PCT = 6.0  # Exclude beyond ±6%


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
# BUILD UNIVERSE
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

    # --------------------------------------------------------
    # Filter + Collect Candidates
    # --------------------------------------------------------

    candidates = []

    for t in tickers:
        symbol = t.get("symbol")

        if symbol not in supported:
            continue

        try:
            quote_volume = float(t["quoteVolume"])
            change_pct = float(t["priceChangePercent"])
        except Exception:
            continue

        # Exclude extreme movers
        if abs(change_pct) > CHANGE_THRESHOLD_PCT:
            continue

        candidates.append({
            "symbol": symbol,
            "quote_volume": quote_volume,
            "change_pct": change_pct,
        })

    # --------------------------------------------------------
    # Sort by quote volume descending
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: x["quote_volume"],
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
            f"[OK] Universe v2 built | "
            f"symbols={len(universe)} | "
            f"time={snapshot['generated_at']}"
        )

    except Exception as e:
        print(f"[ERROR] Universe build failed | {e}")


if __name__ == "__main__":
    main()
