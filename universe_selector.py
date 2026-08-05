# ============================================================
# EXECUTION UNIVERSE SELECTOR — 5M MARKET STRUCTURE
# ============================================================

from dotenv import load_dotenv
load_dotenv()

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import (
    STRUCTURE_UNIVERSE_CANDLE_LIMIT,
    STRUCTURE_UNIVERSE_ENABLED,
    STRUCTURE_UNIVERSE_MARKET_BASE_URL,
    STRUCTURE_UNIVERSE_MAX_BREAKOUT,
    STRUCTURE_UNIVERSE_MAX_CHANGE_PCT,
    STRUCTURE_UNIVERSE_MAX_REVERSION,
    STRUCTURE_UNIVERSE_MAX_TREND,
    STRUCTURE_UNIVERSE_MAX_WORKERS,
    STRUCTURE_UNIVERSE_MIN_CHANGE_PCT,
    STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES,
    STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME,
    STRUCTURE_UNIVERSE_MIN_SCORE,
    STRUCTURE_UNIVERSE_PREFILTER_SIZE,
    STRUCTURE_UNIVERSE_RETENTION_BONUS,
    STRUCTURE_UNIVERSE_SIZE,
    TRADING_ENV,
    UNIVERSE_SNAPSHOT_PATH,
)
from strategy.universe_structure import UniverseStructureAnalyzer


BASE_DIR = Path(__file__).resolve().parent
UNIVERSE_SNAPSHOT_FILE = Path(UNIVERSE_SNAPSHOT_PATH)
if not UNIVERSE_SNAPSHOT_FILE.is_absolute():
    UNIVERSE_SNAPSHOT_FILE = BASE_DIR / UNIVERSE_SNAPSHOT_FILE
EXPECTED_SIZE = STRUCTURE_UNIVERSE_SIZE
BASE_URL = STRUCTURE_UNIVERSE_MARKET_BASE_URL.rstrip("/")
TIMEOUT = 5
INTERVAL = "5m"

_LAST_BUILD_METADATA = {}


def fetch_exchange_info():
    response = requests.get(
        f"{BASE_URL}/fapi/v1/exchangeInfo",
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fetch_24h_tickers():
    response = requests.get(
        f"{BASE_URL}/fapi/v1/ticker/24hr",
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fetch_klines(symbol):
    try:
        response = requests.get(
            f"{BASE_URL}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": INTERVAL,
                "limit": STRUCTURE_UNIVERSE_CANDLE_LIMIT,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        rows = response.json()
        # Binance's final row is normally the currently-forming candle.
        completed = rows[:-1] if len(rows) > 1 else []
        return symbol, completed, None
    except Exception as exc:
        return symbol, None, str(exc)


def get_last_build_metadata():
    return json.loads(json.dumps(_LAST_BUILD_METADATA))


def build_universe():
    global _LAST_BUILD_METADATA

    supported = _supported_symbols(fetch_exchange_info())
    liquid = _liquid_prefilter(
        fetch_24h_tickers(),
        supported,
    )
    previous = _load_previous_symbols()

    if not STRUCTURE_UNIVERSE_ENABLED:
        selected = [
            row["symbol"]
            for row in liquid[:EXPECTED_SIZE]
        ]
        if len(selected) != EXPECTED_SIZE:
            raise RuntimeError(
                f"UNIVERSE_INSUFFICIENT_LIQUID_SYMBOLS | "
                f"found={len(selected)}"
            )
        _LAST_BUILD_METADATA = {
            "selector_version": 2,
            "mode": "LIQUIDITY_FALLBACK",
            "selected": [
                {
                    **row,
                    "selection_reason": "STRUCTURE_DISABLED",
                }
                for row in liquid[:EXPECTED_SIZE]
            ],
        }
        return selected

    analyzed = _analyze_candidates(
        liquid[:STRUCTURE_UNIVERSE_PREFILTER_SIZE],
        previous,
    )
    eligible = [
        row for row in analyzed
        if (
            row["universe_score"] >= STRUCTURE_UNIVERSE_MIN_SCORE
            and "UNSTABLE" not in row["regime"]
        )
    ]
    selected = _select_diversified(eligible)

    if len(selected) != EXPECTED_SIZE:
        raise RuntimeError(
            "STRUCTURE_UNIVERSE_INSUFFICIENT | "
            f"analyzed={len(analyzed)} | "
            f"eligible={len(eligible)} | "
            f"selected={len(selected)}"
        )

    _LAST_BUILD_METADATA = {
        "selector_version": 2,
        "mode": "MARKET_STRUCTURE",
        "market_base_url": BASE_URL,
        "interval": INTERVAL,
        "completed_candle_requirement": (
            STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES
        ),
        "prefilter_count": len(liquid),
        "analyzed_count": len(analyzed),
        "eligible_count": len(eligible),
        "category_counts": _category_counts(selected),
        "selected": selected,
        "top_rejected": [
            {
                **row,
                "selection_reason": "RANKED_OUT",
            }
            for row in eligible
            if row["symbol"] not in {
                selected_row["symbol"]
                for selected_row in selected
            }
        ][:20],
    }
    return [row["symbol"] for row in selected]


def _supported_symbols(exchange_info):
    return {
        item["symbol"]
        for item in exchange_info.get("symbols", [])
        if (
            item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
        )
    }


def _liquid_prefilter(tickers, supported):
    rows = []
    for ticker in tickers:
        symbol = ticker.get("symbol")
        if not _valid_symbol(symbol) or symbol not in supported:
            continue
        try:
            quote_volume = float(ticker["quoteVolume"])
            change_pct = abs(
                float(ticker["priceChangePercent"])
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            quote_volume < STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME
            or change_pct < STRUCTURE_UNIVERSE_MIN_CHANGE_PCT
            or change_pct > STRUCTURE_UNIVERSE_MAX_CHANGE_PCT
        ):
            continue
        activity = math.log10(max(quote_volume, 1.0)) * (
            1.0 + change_pct / 10.0
        )
        rows.append({
            "symbol": symbol,
            "quote_volume": quote_volume,
            "change_pct": change_pct,
            "activity_score_raw": activity,
        })

    rows.sort(
        key=lambda row: (
            -row["activity_score_raw"],
            row["symbol"],
        )
    )
    if rows:
        maximum = max(row["activity_score_raw"] for row in rows)
        minimum = min(row["activity_score_raw"] for row in rows)
        span = max(maximum - minimum, 1e-9)
        for row in rows:
            row["liquidity_score"] = (
                row["activity_score_raw"] - minimum
            ) / span
    return rows


def _analyze_candidates(rows, previous):
    analyzer = UniverseStructureAnalyzer()
    ticker_by_symbol = {
        row["symbol"]: row for row in rows
    }
    results = []
    with ThreadPoolExecutor(
        max_workers=STRUCTURE_UNIVERSE_MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(fetch_klines, row["symbol"]):
            row["symbol"]
            for row in rows
        }
        for future in as_completed(futures):
            symbol, candles, error = future.result()
            if (
                error is not None
                or candles is None
                or len(candles)
                < STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES
            ):
                continue
            try:
                analysis = analyzer.analyze(candles)
            except Exception:
                continue

            ticker = ticker_by_symbol[symbol]
            retention_bonus = (
                STRUCTURE_UNIVERSE_RETENTION_BONUS
                if symbol in previous else 0.0
            )
            setup_score = analysis.best_setup_score
            score = min(
                1.0,
                0.20 * ticker["liquidity_score"]
                + 0.20 * analysis.structure_score
                + 0.15 * analysis.volatility_score
                + 0.20 * setup_score
                + 0.10 * analysis.directional_score
                + 0.15 * analysis.candle_quality_score
                + retention_bonus,
            )
            results.append({
                "symbol": symbol,
                "universe_score": round(score, 8),
                "liquidity_score": round(
                    ticker["liquidity_score"], 8
                ),
                "quote_volume": ticker["quote_volume"],
                "change_pct": ticker["change_pct"],
                "structure_score": round(
                    analysis.structure_score, 8
                ),
                "volatility_score": round(
                    analysis.volatility_score, 8
                ),
                "candle_quality_score": round(
                    analysis.candle_quality_score, 8
                ),
                "directional_score": round(
                    analysis.directional_score, 8
                ),
                "regime": list(analysis.regime),
                "category": analysis.category,
                "best_setup": analysis.best_setup,
                "best_setup_score": round(
                    analysis.best_setup_score, 8
                ),
                "setup_readiness": analysis.setup_readiness,
                "features": {
                    key: round(value, 10)
                    for key, value in analysis.features.items()
                },
                "retained": symbol in previous,
                "retention_bonus": retention_bonus,
            })

    results.sort(
        key=lambda row: (
            -row["universe_score"],
            -row["best_setup_score"],
            -row["quote_volume"],
            row["symbol"],
        )
    )
    return results


def _select_diversified(ranked):
    limits = {
        "TREND": STRUCTURE_UNIVERSE_MAX_TREND,
        "BREAKOUT": STRUCTURE_UNIVERSE_MAX_BREAKOUT,
        "REVERSION": STRUCTURE_UNIVERSE_MAX_REVERSION,
    }
    counts = {key: 0 for key in limits}
    selected = []

    for row in ranked:
        category = row["category"]
        if counts[category] >= limits[category]:
            continue
        selected.append({
            **row,
            "selection_reason": (
                "RETAINED_STRUCTURE_QUALITY"
                if row["retained"]
                else "HIGH_STRUCTURE_SETUP_READINESS"
            ),
        })
        counts[category] += 1
        if len(selected) == EXPECTED_SIZE:
            break

    # If one category is scarce, fill remaining places by score while
    # preserving the already-selected rows. This avoids fragile startup.
    if len(selected) < EXPECTED_SIZE:
        chosen = {row["symbol"] for row in selected}
        for row in ranked:
            if row["symbol"] in chosen:
                continue
            selected.append({
                **row,
                "selection_reason": "DIVERSITY_BACKFILL",
            })
            chosen.add(row["symbol"])
            if len(selected) == EXPECTED_SIZE:
                break

    return selected


def _load_previous_symbols():
    if not UNIVERSE_SNAPSHOT_FILE.exists():
        return set()
    try:
        document = json.loads(
            UNIVERSE_SNAPSHOT_FILE.read_text()
        )
        return {
            symbol
            for symbol in document.get("symbols", [])
            if _valid_symbol(symbol)
        }
    except Exception:
        return set()


def _valid_symbol(symbol):
    return (
        isinstance(symbol, str)
        and symbol.isascii()
        and " " not in symbol
        and symbol.endswith("USDT")
        and symbol.removesuffix("USDT").isalnum()
    )


def _category_counts(rows):
    counts = {
        "TREND": 0,
        "BREAKOUT": 0,
        "REVERSION": 0,
    }
    for row in rows:
        counts[row["category"]] += 1
    return counts


def main():
    try:
        universe = build_universe()
        if len(universe) != EXPECTED_SIZE:
            raise RuntimeError(
                f"UNIVERSE_INVALID_SIZE | found={len(universe)}"
            )

        snapshot = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "count": len(universe),
            "symbols": universe,
            "selection": get_last_build_metadata(),
            "environment": TRADING_ENV,
        }
        UNIVERSE_SNAPSHOT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary = UNIVERSE_SNAPSHOT_FILE.with_suffix(
            ".json.tmp"
        )
        temporary.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True)
        )
        os.replace(temporary, UNIVERSE_SNAPSHOT_FILE)

        print(
            "[OK] Structure universe built | "
            f"symbols={len(universe)} | "
            f"mode={snapshot['selection'].get('mode')} | "
            f"time={snapshot['generated_at']}"
        )
    except Exception as exc:
        print(f"[ERROR] Universe build failed | {exc}")
        raise


if __name__ == "__main__":
    main()
