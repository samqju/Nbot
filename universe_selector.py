# ============================================================
# UNIVERSE SELECTOR — MAINNET (5M Structure Optimized)
# ============================================================

from dotenv import load_dotenv
load_dotenv()

import os
import json
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIG (COMPATIBLE)
# ============================================================

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
UNIVERSE_SNAPSHOT_FILE = "/home/ubuntu/nbot/universe_snapshot.json"
EXPECTED_SIZE = 30

BASE_URL = os.getenv("TESTNET_BASE_URL")
TIMEOUT = 3  # Reduced timeout (important)

MIN_CHANGE_PCT = 1.0
MAX_CHANGE_PCT = 12.0
MIN_QUOTE_VOLUME = 15_000_000

INTERVAL = "5m"
CANDLE_LIMIT = 60

MAX_PRE_KLINE_SYMBOLS = 60  # Critical optimization
MAX_WORKERS = 4  # Safe for 1 vCPU


# ============================================================
# REST HELPERS
# ============================================================

def fetch_exchange_info():
    resp = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_24h_tickers():
    resp = requests.get(f"{BASE_URL}/fapi/v1/ticker/24hr", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_klines(symbol):
    try:
        resp = requests.get(
            f"{BASE_URL}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": INTERVAL,
                "limit": CANDLE_LIMIT,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return symbol, resp.json()
    except Exception:
        return symbol, None


# ============================================================
# STRUCTURE LOGIC
# ============================================================

def avg_wick_ratio(candles):
    ratios = []
    for c in candles:
        o = float(c[1])
        h = float(c[2])
        l = float(c[3])
        close = float(c[4])
        total = h - l
        if total <= 0:
            continue
        body = abs(close - o)
        wick = total - body
        ratios.append(wick / total)
    return sum(ratios) / len(ratios) if ratios else 1.0


def classify_structure(candles):
    ranges = []
    closes = []

    for c in candles:
        h = float(c[2])
        l = float(c[3])
        close = float(c[4])
        ranges.append(h - l)
        closes.append(close)

    short_avg = sum(ranges[-10:]) / 10
    long_avg = sum(ranges) / len(ranges)
    if long_avg <= 0:
        return None

    vol_ratio = short_avg / long_avg

    trend_score = 0
    for i in range(-5, -1):
        if closes[i] > closes[i - 1]:
            trend_score += 1
        elif closes[i] < closes[i - 1]:
            trend_score -= 1

    if abs(trend_score) >= 3 and vol_ratio > 1.0:
        return "TREND"

    if vol_ratio < 0.8:
        return "COMPRESSION"

    return None


# ============================================================
# BUILD UNIVERSE
# ============================================================

def build_universe():

    exchange_info = fetch_exchange_info()
    tickers = fetch_24h_tickers()

    supported = {
        s["symbol"]
        for s in exchange_info["symbols"]
        if (
            s["contractType"] == "PERPETUAL"
            and s["quoteAsset"] == "USDT"
            and s["status"] == "TRADING"
        )
    }

    pre_candidates = []

    for t in tickers:
        symbol = t.get("symbol")

        # --------------------------------------------------
        # STRICT SYMBOL SANITIZATION (Testnet Hardening)
        # --------------------------------------------------
        if (
            not isinstance(symbol, str)
            or not symbol.isascii()
            or " " in symbol
            or not symbol.endswith("USDT")
            or not symbol.replace("USDT", "").isalnum()
            or symbol not in supported
        ):
            continue

        try:
            quote_volume = float(t["quoteVolume"])
            change_pct = abs(float(t["priceChangePercent"]))
        except Exception:
            continue

        if (
            change_pct < MIN_CHANGE_PCT
            or change_pct > MAX_CHANGE_PCT
            or quote_volume < MIN_QUOTE_VOLUME
        ):
            continue

        pre_candidates.append(
            (symbol, quote_volume, change_pct)
        )

    # Sort by liquidity × volatility
    pre_candidates.sort(
        key=lambda x: x[1] * x[2],
        reverse=True
    )

    symbols_for_kline = [
        s for s, _, _ in pre_candidates[:MAX_PRE_KLINE_SYMBOLS]
    ]

    trend_bucket = []
    compression_bucket = []
    fallback_bucket = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_klines, symbol): symbol
            for symbol in symbols_for_kline
        }

        for future in as_completed(futures):
            symbol, candles = future.result()

            if not candles or len(candles) < CANDLE_LIMIT:
                continue

            if avg_wick_ratio(candles) > 0.55:
                continue

            structure = classify_structure(candles)

            # Find volume and volatility again
            for s, vol, chg in pre_candidates:
                if s == symbol:
                    score = vol * chg
                    break
            else:
                score = 0

            if structure == "TREND":
                trend_bucket.append((symbol, score))

            elif structure == "COMPRESSION":
                compression_bucket.append((symbol, score))

            else:
                fallback_bucket.append((symbol, score))

    trend_bucket.sort(key=lambda x: x[1], reverse=True)
    compression_bucket.sort(key=lambda x: x[1], reverse=True)
    fallback_bucket.sort(key=lambda x: x[1], reverse=True)

    selected = (
        [s for s, _ in trend_bucket[:15]] +
        [s for s, _ in compression_bucket[:15]]
    )

    # Fallback fill
    if len(selected) < EXPECTED_SIZE:
        needed = EXPECTED_SIZE - len(selected)
        fallback_symbols = [
            s for s, _ in fallback_bucket
            if s not in selected
        ]
        selected.extend(fallback_symbols[:needed])

    return selected[:EXPECTED_SIZE]

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
            f"[OK] Universe 5M built | "
            f"symbols={len(universe)} | "
            f"time={snapshot['generated_at']}"
        )

    except Exception as e:
        print(f"[ERROR] Universe build failed | {e}")


if __name__ == "__main__":
    main()
