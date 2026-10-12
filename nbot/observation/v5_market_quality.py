"""Credential-free, bounded public exchange-info/depth snapshot bridge for V5.

Captured AFTER a completed 5m market observation and BEFORE a V5 decision.
No historical depth invention, no private credentials, no orders, no I/O at import.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

from .v5_selection import DepthSnapshot, Instrument

ORDER_AUTHORITY = "NONE"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _num(value: Any, field: str, *, positive: bool = True) -> float:
    try:
        x = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("V5_MARKET_QUALITY_INVALID_" + field) from exc
    if not math.isfinite(x) or (positive and x <= 0) or (not positive and x < 0):
        raise ValueError("V5_MARKET_QUALITY_INVALID_" + field)
    return x


def _capture_window(capture: Any) -> tuple[int, int]:
    start, finished = capture.started_at_ms, capture.finished_at_ms
    if (type(start) is not int or type(finished) is not int
            or start < 0 or finished < start):
        raise ValueError("V5_CAPTURE_WINDOW_INVALID")
    return start, finished


def parse_exchange_info(payload: object, capture: Any, *,
                        symbols: Iterable[str]) -> dict[str, Instrument]:
    """Never synthesize missing tick/lot/notional rules or wrong contracts."""
    _, finished = _capture_window(capture)
    wanted = set(symbols)
    if not wanted or len(wanted) > 100 or not all(x and x == x.upper() for x in wanted):
        raise ValueError("V5_EXCHANGE_UNIVERSE_INVALID")
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("V5_EXCHANGE_INFO_INVALID")
    digest = _digest({"payload": payload, "start": capture.started_at_ms,
                      "finish": finished, "source": "PUBLIC_EXCHANGE_INFO"})
    output: dict[str, Instrument] = {}
    for row in payload["symbols"]:
        if not isinstance(row, dict) or row.get("symbol") not in wanted:
            continue
        symbol = row["symbol"]
        if symbol in output:
            raise ValueError("V5_EXCHANGE_INFO_DUPLICATE")
        if row.get("quoteAsset") != "USDT" or row.get("contractType") != "PERPETUAL":
            raise ValueError("V5_EXCHANGE_INSTRUMENT_CONTRACT_INVALID")
        if not isinstance(row.get("filters"), list):
            raise ValueError("V5_EXCHANGE_FILTERS_MISSING")
        f: dict[str, dict] = {}
        for item in row["filters"]:
            if not isinstance(item, dict):
                raise ValueError("V5_EXCHANGE_FILTER_INVALID")
            typ = item.get("filterType")
            if typ in f:
                raise ValueError("V5_EXCHANGE_FILTER_DUPLICATE")
            if isinstance(typ, str):
                f[typ] = item
        try:
            tick = _num(f["PRICE_FILTER"]["tickSize"], "TICK")
            lot = f["LOT_SIZE"]
            step = _num(lot["stepSize"], "STEP")
            minimum = _num(lot["minQty"], "MIN_QTY")
            maximum = _num(lot["maxQty"], "MAX_QTY")
            notional_record = f["MIN_NOTIONAL"]
            if "notional" not in notional_record:
                raise KeyError("notional")
            min_notional = _num(notional_record["notional"], "MIN_NOTIONAL")
        except KeyError as exc:
            raise ValueError("V5_EXCHANGE_FILTERS_MISSING") from exc
        if minimum > maximum:
            raise ValueError("V5_EXCHANGE_LOT_RANGE_INVALID")
        output[symbol] = Instrument(
            symbol, tick, step, min_notional, row.get("status") == "TRADING",
            finished, min_qty=minimum, max_qty=maximum, source_digest=digest,
        )
    if output.keys() != wanted:
        raise ValueError("V5_EXCHANGE_SYMBOL_MISSING")
    return output


def parse_depth(payload: object, capture: Any, *, symbol: str) -> DepthSnapshot:
    start, end = _capture_window(capture)
    if not symbol or symbol != symbol.upper() or not isinstance(payload, dict):
        raise ValueError("V5_DEPTH_PAYLOAD_INVALID")
    try:
        update_id = int(payload["lastUpdateId"])
        raw_bids, raw_asks = payload["bids"], payload["asks"]
        if (not isinstance(raw_bids, list) or not isinstance(raw_asks, list)
                or not 1 <= len(raw_bids) <= 100 or not 1 <= len(raw_asks) <= 100):
            raise ValueError("V5_DEPTH_ROWS_INVALID")
        def levels(items: list) -> tuple[tuple[float, float], ...]:
            out = []
            for item in items:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise ValueError("V5_DEPTH_LEVEL_INVALID")
                out.append((_num(item[0], "PRICE"), _num(item[1], "QUANTITY")))
            return tuple(out)
        bids, asks = levels(raw_bids), levels(raw_asks)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("V5_DEPTH_PAYLOAD_INVALID") from exc
    if update_id <= 0:
        raise ValueError("V5_DEPTH_UPDATE_ID_INVALID")
    return DepthSnapshot(
        symbol, start, end, update_id, bids, asks,
        _digest({"payload": payload, "start": start, "finish": end,
                 "symbol": symbol, "source": "PUBLIC_FUTURES_DEPTH"}),
    )


def capture_public_quality(client: Any, symbols: Iterable[str]) -> tuple[
        dict[str, Instrument], dict[str, DepthSnapshot]]:
    """Use the existing public Binance client: strict endpoint allow-list only.

    This opt-in function is never called automatically by V4 or V5.
    """
    wanted = sorted(set(symbols))
    if not wanted or len(wanted) > 100 or not all(
            isinstance(s, str) and s and s == s.upper() for s in wanted):
        raise ValueError("V5_MARKET_CAPTURE_SYMBOLS_INVALID")
    # This dedicated public-client guard prevents accepting arbitrary objects
    # that can return synthetic/future-looking information without provenance.
    from .binance_public import BinanceUsdMPublicClient
    if not isinstance(client, BinanceUsdMPublicClient):
        raise ValueError("V5_MARKET_CAPTURE_PUBLIC_CLIENT_REQUIRED")
    info, captured = client._get_timed("v5_exchange_info", "/fapi/v1/exchangeInfo")
    rules = parse_exchange_info(info, captured, symbols=wanted)
    books: dict[str, DepthSnapshot] = {}
    for symbol in wanted:
        body, timed = client._get_timed("v5_depth", "/fapi/v1/depth",
                                        {"symbol": symbol, "limit": 20})
        books[symbol] = parse_depth(body, timed, symbol=symbol)
    return rules, books


def submit_order(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
