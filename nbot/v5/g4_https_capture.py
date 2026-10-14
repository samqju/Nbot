"""Bounded public HTTPS acquisition for G4 ORIGINAL source transport receipts.

Offline-ready, not scheduled, no DB/filesystem mutation, no trading auth.
A successful HTTPS GET is transport-provenance evidence only: Binance's
public REST/archive bytes are not cryptographically signed by the exchange.
Never mistake a REST bookTicker fetched later for a quote at an earlier exit.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import ssl
import time
from typing import Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

CAPTURE_VERSION = "NBOT_V5_G4_PUBLIC_HTTPS_CAPTURE_V1"
_ALLOWED = {"data.binance.vision", "fapi.binance.com"}
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
_DATE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
_MAX = {
    "DAILY_AGGTRADES_ZIP": 50_000_000,
    "DAILY_AGGTRADES_CHECKSUM": 1_024,
    "BOOK_TICKER_AT_CAPTURE": 16_384,
    "FUNDING_HISTORY": 262_144,
    "RECENT_AGGTRADES": 512_000,
}
_KEY_FIELDS = frozenset(("a", "p", "q", "f", "l", "T", "m"))


@dataclass(frozen=True)
class SourceReceipt:
    kind: str
    symbol: str
    request_url: str
    response_url: str
    request_at_ms: int
    received_at_ms: int
    http_status: int
    content_sha256: str
    length: int
    metadata_sha256: str
    source_capture_mode: str
    transport_hostname: str
    independently_exchange_signed: bool = False
    order_authority: str = "NONE"
    economic_label_authority: str = "NONE"


def _utc_clock():
    return time.time_ns() // 1_000_000


def _valid_clock(v):
    return type(v) is int and v > 0


def _safe_symbol(value):
    if not isinstance(value, str) or not _SYMBOL.fullmatch(value):
        raise ValueError("G4_HTTPS_SYMBOL_INVALID")


def _path(kind, symbol, *, on_date=None, since_ms=None, until_ms=None):
    _safe_symbol(symbol)
    if kind in ("DAILY_AGGTRADES_ZIP", "DAILY_AGGTRADES_CHECKSUM"):
        if not isinstance(on_date, str) or not _DATE.fullmatch(on_date):
            raise ValueError("G4_HTTPS_ARCHIVE_DATE_INVALID")
        from datetime import date
        try:
            if date.fromisoformat(on_date).isoformat() != on_date:
                raise ValueError("bad date")
        except ValueError as exc:
            raise ValueError("G4_HTTPS_ARCHIVE_DATE_INVALID") from exc
        filename = f"{symbol}-aggTrades-{on_date}.zip"
        if kind == "DAILY_AGGTRADES_CHECKSUM":
            filename += ".CHECKSUM"
        return ("https://data.binance.vision/data/futures/um/daily/aggTrades/"
                f"{symbol}/{filename}")
    if kind == "BOOK_TICKER_AT_CAPTURE":
        return ("https://fapi.binance.com/fapi/v1/ticker/bookTicker?"
                + urlencode({"symbol": symbol}))
    if kind in ("FUNDING_HISTORY", "RECENT_AGGTRADES"):
        if (not _valid_clock(since_ms) or not _valid_clock(until_ms)
                or since_ms >= until_ms):
            raise ValueError("G4_HTTPS_WINDOW_INVALID")
        delta = until_ms - since_ms
        if kind == "RECENT_AGGTRADES" and delta >= 3_600_000:
            raise ValueError("G4_HTTPS_AGGTRADES_WINDOW_TOO_LARGE")
        if kind == "FUNDING_HISTORY" and delta > 24 * 60 * 60 * 1000:
            raise ValueError("G4_HTTPS_FUNDING_WINDOW_TOO_LARGE")
        endpoint = ("aggTrades" if kind == "RECENT_AGGTRADES"
                    else "fundingRate")
        return (f"https://fapi.binance.com/fapi/v1/{endpoint}?"
                + urlencode({"symbol": symbol, "startTime": since_ms,
                             "endTime": until_ms, "limit": 1000}))
    raise ValueError("G4_HTTPS_KIND_UNSUPPORTED")


def _real_open(request: Request, timeout: int):
    return urlopen(request, timeout=timeout, context=ssl.create_default_context())


def _validate_json(kind, raw: bytes, symbol: str, req_at: int, recv_at: int):
    if kind in ("DAILY_AGGTRADES_ZIP", "DAILY_AGGTRADES_CHECKSUM"):
        return
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("G4_HTTPS_RESPONSE_JSON_INVALID") from exc
    if kind == "BOOK_TICKER_AT_CAPTURE":
        from decimal import Decimal, InvalidOperation
        if not isinstance(value, dict) or value.get("symbol") != symbol:
            raise ValueError("G4_HTTPS_BOOK_SYMBOL_INVALID")
        try:
            bid = Decimal(value["bidPrice"])
            ask = Decimal(value["askPrice"])
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError("G4_HTTPS_BOOK_PRICE_INVALID") from exc
        if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask <= bid:
            raise ValueError("G4_HTTPS_BOOK_PRICE_INVALID")
        # The server's bookTicker event clock, if present, must not be future.
        if "time" in value and (type(value["time"]) is not int
                                or value["time"] > recv_at
                                or value["time"] < req_at - 5_000):
            raise ValueError("G4_HTTPS_BOOK_TIME_INVALID")
        return
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError("G4_HTTPS_LIST_SHAPE_INVALID")
    if kind == "RECENT_AGGTRADES":
        for item in value:
            if (not isinstance(item, dict) or not _KEY_FIELDS.issubset(item)
                    or type(item["a"]) is not int or type(item["T"]) is not int
                    or type(item["m"]) is not bool):
                raise ValueError("G4_HTTPS_AGGTRADE_SHAPE_INVALID")
    else:
        for item in value:
            if (not isinstance(item, dict) or item.get("symbol") != symbol
                    or type(item.get("fundingTime")) is not int
                    or not isinstance(item.get("fundingRate"), str)):
                raise ValueError("G4_HTTPS_FUNDING_SHAPE_INVALID")


def acquire_public_artifact(*, kind: str, symbol: str, on_date: str | None = None,
                            since_ms: int | None = None,
                            until_ms: int | None = None,
                            opener: Callable | None = None,
                            clock: Callable[[], int] | None = None
                            ) -> tuple[SourceReceipt, bytes]:
    """At most one synchronous HTTP GET. No retries, persistence or transactions.

    For a replayable original source, preserve returned raw bytes unchanged and
    write their SHA plus this receipt to an independently reviewed manifest.
    Error/timeout/429/redirect/oversize never degrades to fabricated empty data.
    Passing a test opener disables the real-HTTPS transport assertion.
    """
    if kind not in _MAX:
        raise ValueError("G4_HTTPS_KIND_UNSUPPORTED")
    request_url = _path(kind, symbol, on_date=on_date,
                        since_ms=since_ms, until_ms=until_ms)
    host = urlparse(request_url).hostname
    if host not in _ALLOWED:
        raise ValueError("G4_HTTPS_HOST_NOT_ALLOWED")
    clock = _utc_clock if clock is None else clock
    now = clock()
    if not _valid_clock(now):
        raise ValueError("G4_HTTPS_CLOCK_INVALID")
    req = Request(request_url, headers={"Accept": "application/json,application/zip,*/*",
                                        "User-Agent": "NBOT-V5-G4-research-only/1"})
    # Explicitly inject only through tests; never claim that such results are
    # real TLS-authenticated original exchange data.
    fetch = _real_open if opener is None else opener
    with fetch(req, timeout=15) as response:
        status = response.status
        resolved = response.geturl()
        parsed = urlparse(resolved)
        if (status != 200 or parsed.scheme != "https"
                or parsed.hostname != host or resolved != request_url):
            raise ValueError("G4_HTTPS_REDIRECT_OR_HTTP_UNTRUSTED")
        data = response.read(_MAX[kind] + 1)
        if not data or len(data) > _MAX[kind]:
            raise ValueError("G4_HTTPS_RESPONSE_EMPTY_OR_TOO_LARGE")
    received = clock()
    if not _valid_clock(received) or received < now:
        raise ValueError("G4_HTTPS_RECEIPT_CLOCK_REWIND")
    _validate_json(kind, data, symbol, now, received)
    sha = hashlib.sha256(data).hexdigest()
    identity = {
        "capture_contract": CAPTURE_VERSION, "kind": kind,
        "symbol": symbol, "request_url": request_url,
        "response_url": resolved, "request_at_ms": now,
        "received_at_ms": received, "http_status": status,
        "content_sha256": sha, "length": len(data),
        "source_capture_mode": (
            "VERIFIED_STDLIB_TLS_HTTPS" if opener is None
            else "INJECTED_TEST_TRANSPORT_UNVERIFIED"),
    }
    metadata_sha = hashlib.sha256(json.dumps(identity, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    receipt = SourceReceipt(kind=kind, symbol=symbol,
                            request_url=request_url, response_url=resolved,
                            request_at_ms=now, received_at_ms=received,
                            http_status=status, content_sha256=sha,
                            length=len(data), metadata_sha256=metadata_sha,
                            source_capture_mode=identity["source_capture_mode"],
                            transport_hostname=host)
    return receipt, data
