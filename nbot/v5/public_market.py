"""Public Binance USD-M market snapshots for V5 observation ONLY.

Fixed public GET endpoints, no API credentials, no order or execution imports.
A manually invoked probe is not a background collector or production feed.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import re
import ssl
import time
from typing import Callable, Mapping, Sequence
from urllib.parse import urlencode

from nbot.v5.observation_contract import INTERVAL_MS, MAX_SYMBOLS
from nbot.v5.pattern_adapter import build_observations_from_closed_candles

_HOST = "fapi.binance.com"
_PATHS = frozenset({
    "/fapi/v1/time", "/fapi/v1/exchangeInfo",
    "/fapi/v1/ticker/24hr", "/fapi/v1/klines",
})
_MAX_BYTES = 3_000_000
_MAX_TIMEOUT = 6
_RE = re.compile(r"^[A-Z0-9]{3,24}$")
HISTORY = 96


class PublicMarketDataError(ValueError):
    """External information was missing or unsafe; no trade is permitted."""


def _json_digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def public_get(path: str, params: Mapping[str, str] | None = None) -> object:
    """Use only pinned public routes and HTTPS GET, never headers with secrets."""
    if path not in _PATHS:
        raise PublicMarketDataError("V5_PUBLIC_ENDPOINT_NOT_ALLOWED")
    query = urlencode(params or {})
    conn = http.client.HTTPSConnection(
        _HOST, timeout=_MAX_TIMEOUT, context=ssl.create_default_context()
    )
    try:
        conn.request("GET", path + ("?" + query if query else ""),
                     headers={"Accept": "application/json", "User-Agent": "NBOT-V5-Observation-Probe/1"})
        response = conn.getresponse()
        if response.status != 200:
            raise PublicMarketDataError("V5_PUBLIC_HTTP_ERROR_" + str(response.status))
        raw = response.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise PublicMarketDataError("V5_PUBLIC_RESPONSE_TOO_LARGE")
        return json.loads(raw.decode("utf-8"), parse_constant=lambda x:
                          (_ for _ in ()).throw(PublicMarketDataError("V5_NONFINITE_JSON")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicMarketDataError("V5_PUBLIC_DATA_UNAVAILABLE") from exc
    finally:
        conn.close()


def closed_event_from_server_time(server_response: object) -> tuple[int, int]:
    """Choose latest fully closed 5-minute UTC interval, never current live bar."""
    if not isinstance(server_response, dict):
        raise PublicMarketDataError("V5_SERVER_TIME_INVALID")
    server_ms = server_response.get("serverTime")
    if type(server_ms) is not int or server_ms < INTERVAL_MS * 96:
        raise PublicMarketDataError("V5_SERVER_TIME_INVALID")
    return ((server_ms // INTERVAL_MS) - 1) * INTERVAL_MS, server_ms


def select_universe(exchange: object, ticker: object, *, limit: int) -> tuple[str, ...]:
    """Snapshot top eligible liquid USDT perpetual futures by 24h quote turnover.

    This is a *current* snapshot, not a historical backfill or proof of quality.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_SYMBOLS:
        raise PublicMarketDataError("V5_UNIVERSE_LIMIT_INVALID")
    if not isinstance(exchange, dict) or not isinstance(exchange.get("symbols"), list):
        raise PublicMarketDataError("V5_EXCHANGE_INFO_INVALID")
    if not isinstance(ticker, list):
        raise PublicMarketDataError("V5_TICKER_INVALID")
    eligible: set[str] = set()
    for item in exchange["symbols"]:
        if not isinstance(item, dict):
            raise PublicMarketDataError("V5_EXCHANGE_SYMBOL_INVALID")
        sym = item.get("symbol")
        if (isinstance(sym, str) and _RE.fullmatch(sym)
                and item.get("contractType") == "PERPETUAL"
                and item.get("status") == "TRADING"
                and item.get("quoteAsset") == "USDT"
                and item.get("marginAsset") == "USDT"):
            if sym in eligible:
                raise PublicMarketDataError("V5_EXCHANGE_DUPLICATE_SYMBOL")
            eligible.add(sym)
    if "BTCUSDT" not in eligible:
        raise PublicMarketDataError("V5_BTC_CONTEXT_NOT_ELIGIBLE")
    turnover: dict[str, float] = {}
    for item in ticker:
        if not isinstance(item, dict):
            raise PublicMarketDataError("V5_TICKER_ROW_INVALID")
        symbol = item.get("symbol")
        if symbol not in eligible:
            continue
        if symbol in turnover:
            raise PublicMarketDataError("V5_TICKER_DUPLICATE")
        try:
            value = float(item["quoteVolume"])
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            raise PublicMarketDataError("V5_TICKER_VOLUME_INVALID") from exc
        if not math.isfinite(value) or value < 0:
            raise PublicMarketDataError("V5_TICKER_VOLUME_INVALID")
        if value > 0:
            turnover[symbol] = value
    if len(turnover) < limit or "BTCUSDT" not in turnover:
        raise PublicMarketDataError("V5_UNIVERSE_INCOMPLETE")
    return tuple(sorted(turnover, key=lambda s: (-turnover[s], s))[:limit])


def decode_klines(payload: object, *, event_open_ms: int) -> tuple[tuple, ...]:
    """Require exactly 96 time-aligned historical *closed* 5-minute bars."""
    if not isinstance(payload, list) or len(payload) != HISTORY:
        raise PublicMarketDataError("V5_CANDLE_HISTORY_INCOMPLETE")
    start = event_open_ms - (HISTORY - 1) * INTERVAL_MS
    output = []
    for i, row in enumerate(payload):
        if not isinstance(row, list) or len(row) < 7:
            raise PublicMarketDataError("V5_CANDLE_SHAPE_INVALID")
        open_ms = row[0]
        close_ms = row[6]
        if (type(open_ms) is not int or open_ms != start + i * INTERVAL_MS
                or type(close_ms) is not int
                or close_ms != open_ms + INTERVAL_MS - 1):
            raise PublicMarketDataError("V5_CANDLE_WINDOW_INVALID")
        try:
            numbers = tuple(float(x) for x in row[1:6])
        except (ValueError, TypeError, OverflowError) as exc:
            raise PublicMarketDataError("V5_CANDLE_VALUE_INVALID") from exc
        o, h, l, c, volume = numbers
        if (not all(math.isfinite(x) for x in numbers)
                or min(o, h, l, c) <= 0 or volume < 0
                or h < max(o, c) or l > min(o, c) or l > h):
            raise PublicMarketDataError("V5_CANDLE_VALUE_INVALID")
        output.append((open_ms, o, h, l, c, volume))
    return tuple(output)


def collect_once(
    *, limit: int = 12, getter: Callable = public_get,
    clock_ms: Callable[[], int] | None = None,
) -> dict:
    """Bounded, one-shot, observe-only preview. Does not write to any database.

    Individual missing symbol candles stay in the observation denominator.
    Only live exchange/ticker data seen now can select the universe for now.
    """
    clock_ms = clock_ms or (lambda: int(time.time() * 1000))
    event, server_ms = closed_event_from_server_time(getter("/fapi/v1/time"))
    local_ms = clock_ms()
    if abs(local_ms - server_ms) > 90_000:
        raise PublicMarketDataError("V5_CLOCK_SKEW_OR_SERVER_STALE")
    exchange = getter("/fapi/v1/exchangeInfo")
    ticker = getter("/fapi/v1/ticker/24hr")
    eligible = select_universe(exchange, ticker, limit=limit)
    symbols_to_read = tuple(sorted(set(eligible) | {"BTCUSDT"}))
    candles: dict[str, tuple] = {}
    refused: dict[str, str] = {}
    for symbol in symbols_to_read:
        try:
            payload = getter("/fapi/v1/klines", {
                "symbol": symbol,
                "interval": "5m",
                "startTime": str(event - (HISTORY - 1) * INTERVAL_MS),
                "endTime": str(event + INTERVAL_MS - 1),
                "limit": str(HISTORY),
            })
            candles[symbol] = decode_klines(payload, event_open_ms=event)
        except PublicMarketDataError as exc:
            refused[symbol] = str(exc)
    completed_ms = clock_ms()
    # Crossing the *next* event before finalization would yield stale decisions.
    if not (server_ms <= completed_ms < event + 2 * INTERVAL_MS):
        raise PublicMarketDataError("V5_PROBE_EVENT_BECAME_STALE")
    observations = build_observations_from_closed_candles(
        event_open_ms=event, decision_at_ms=completed_ms,
        observed_at_ms=completed_ms, eligible_symbols=eligible,
        candles_by_symbol=candles,
    )
    return {
        "mode": "OBSERVATION_ONLY_NO_ORDERS",
        "source": "BINANCE_USDM_PUBLIC_GET",
        "event_open_ms": event,
        "server_time_ms": server_ms,
        "complete_at_ms": completed_ms,
        "selection_version": "USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
        "universe_digest": _json_digest({"event": event, "eligible": eligible}),
        "eligible_symbols": eligible,
        "btc_context_available": "BTCUSDT" in candles,
        "candle_failures": refused,
        "observations": len(observations),
        "observed": sum(r["status"] == "OBSERVED" for r in observations),
        "unscorable": sum(r["status"] == "UNSCORABLE" for r in observations),
        "pattern_matches": sum(
            state == "MATCH" for r in observations
            for state in r["patterns"].values()
        ),
        "order_authority": "NONE",
        "paper_trades": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot public Binance V5 market probe; NO ORDERS")
    parser.add_argument("--top", type=int, default=12, help="1..50 most active eligible markets; default 12")
    args = parser.parse_args(argv)
    try:
        result = collect_once(limit=args.top)
    except PublicMarketDataError as exc:
        print("V5_PUBLIC_PROBE_HOLD:", str(exc))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
