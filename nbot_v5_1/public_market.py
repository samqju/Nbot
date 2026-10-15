"""Explicitly invoked Binance USD-M *public GET-only* REST adapter.

No network at import time, no API keys, no futures accounts or order methods,
no arbitrary URL, redirect or retry on rate-limit. Offline by default.
Original-source economic provenance is NOT inferred from public 5m REST OHLCV.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

PUBLIC_API_SCHEMA = "NBOT_V5_1_PUBLIC_USDM_V1"
ORIGIN = "https://fapi.binance.com"
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")


class PublicMarketHold(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PublicMarketHold("G2_PUBLIC_REDIRECT_REJECTED")


@dataclass(frozen=True)
class PublicResponse:
    kind: str
    path: str
    received_at_ms: int
    body_sha256: str
    body: object
    request_weight: int
    raw_bytes: bytes = b""  # exact public HTTP response bytes, unqualified

    def __post_init__(self):
        if (type(self.received_at_ms) is not int or
                type(self.body_sha256) is not str or len(self.body_sha256) != 64
                or type(self.raw_bytes) is not bytes
                or (self.raw_bytes and hashlib.sha256(self.raw_bytes).hexdigest() != self.body_sha256)):
            raise PublicMarketHold("G2_PUBLIC_RESULT_INVALID")


class PublicUsdMClient:
    """No secret-capable endpoints. Network requires explicit opted-in object."""

    def __init__(self, *, allow_public_network: bool = False, weight_budget: int = 600,
                 timeout_sec: int = 7, transport=None, now=None):
        if type(allow_public_network) is not bool or type(weight_budget) is not int or not 1 <= weight_budget <= 600:
            raise ValueError("G2_NETWORK_CONFIG_INVALID")
        if type(timeout_sec) is not int or not 1 <= timeout_sec <= 20:
            raise ValueError("G2_NETWORK_TIMEOUT_INVALID")
        self.allowed = allow_public_network
        self.budget = weight_budget
        self.timeout = timeout_sec
        self._used = 0
        self._window_start = time.monotonic()
        self._transport = transport
        self._now = now

    @property
    def weight_used(self) -> int:
        return self._used

    def _request(self, name: str, path: str, params: dict, weight: int) -> PublicResponse:
        if not self.allowed:
            raise PublicMarketHold("G2_PUBLIC_NETWORK_LOCKED")
        if name not in ("EXCHANGE_INFO", "TICKER_24HR", "BOOK_TICKER", "KLINES"):
            raise PublicMarketHold("G2_PUBLIC_ENDPOINT_DENIED")
        if time.monotonic() - self._window_start >= 60:
            self._used, self._window_start = 0, time.monotonic()
        if self._used + weight > self.budget:
            raise PublicMarketHold("G2_PUBLIC_RATE_BUDGET")
        self._used += weight
        url = ORIGIN + path + ("?" + urllib.parse.urlencode(params) if params else "")
        # Whitelist paths above; no raw user-supplied domain/URI/method/credentials.
        if self._transport is None:
            req = urllib.request.Request(url, method="GET",
                                         headers={"Accept": "application/json",
                                                  "User-Agent": "NBOT-V5.1-PUBLIC-OBSERVE"})
            try:
                with urllib.request.build_opener(_NoRedirect()).open(req, timeout=self.timeout) as resp:
                    if resp.status != 200:
                        raise PublicMarketHold("G2_PUBLIC_HTTP_STATUS")
                    data = resp.read(4 * 1024 * 1024 + 1)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                raise PublicMarketHold("G2_PUBLIC_SOURCE_UNAVAILABLE") from exc
        else:
            # Injection seam for 100% offline unit tests; never import custom
            # transports from the network or evaluate server-provided code.
            data = self._transport(url)
        if type(data) is not bytes or not data or len(data) > 4 * 1024 * 1024:
            raise PublicMarketHold("G2_PUBLIC_PAYLOAD_SIZE")
        try:
            body = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(
                PublicMarketHold("G2_PUBLIC_JSON_NONFINITE")))
        except (ValueError, UnicodeError) as exc:
            raise PublicMarketHold("G2_PUBLIC_JSON_INVALID") from exc
        received = int((self._now() if self._now is not None else time.time()) * 1000)
        return PublicResponse(name, path, received, hashlib.sha256(data).hexdigest(),
                              body, weight, data)

    def exchange_info(self) -> PublicResponse:
        return self._request("EXCHANGE_INFO", "/fapi/v1/exchangeInfo", {}, 1)

    def tickers_24hr(self) -> PublicResponse:
        return self._request("TICKER_24HR", "/fapi/v1/ticker/24hr", {}, 40)

    def book_tickers(self) -> PublicResponse:
        return self._request("BOOK_TICKER", "/fapi/v1/ticker/bookTicker", {}, 5)

    def closed_klines(self, symbol: str, *, limit: int = 100) -> PublicResponse:
        if type(symbol) is not str or not _SYMBOL.fullmatch(symbol):
            raise ValueError("G2_PUBLIC_SYMBOL_INVALID")
        if type(limit) is not int or not 96 <= limit <= 500:
            raise ValueError("G2_PUBLIC_HISTORY_LIMIT_INVALID")
        # REST response includes an unfinished latest candle: the caller MUST
        # reject it using the decision as-of clock in rest_closed_bar().
        weight = 1 if limit < 100 else 2
        return self._request("KLINES", "/fapi/v1/klines", {
            "symbol": symbol, "interval": "5m", "limit": limit}, weight)


def select_from_public_responses(
    exchange: PublicResponse, ticker: PublicResponse, book: PublicResponse,
    history_closed: dict[str, int], source_health: dict[str, bool],
    *, selected_at_ms: int,
):
    """Select only from a coherently timestamped, hashed public GET bundle.

    Three independently received timestamps and SHA-256 identities are bound
    to the cohort manifest; mismatches/older snapshots fail closed. Exact
    raw HTTP bytes remain public-source metadata, not exchange fill evidence.
    """
    from .universe import select_universe
    sources = (exchange, ticker, book)
    expected = (
        ("EXCHANGE_INFO", "/fapi/v1/exchangeInfo", dict),
        ("TICKER_24HR", "/fapi/v1/ticker/24hr", list),
        ("BOOK_TICKER", "/fapi/v1/ticker/bookTicker", list),
    )
    for value, (kind, path, shape) in zip(sources, expected):
        if type(value) is not PublicResponse or value.kind != kind or value.path != path:
            raise PublicMarketHold("G2_PUBLIC_SOURCE_KIND_MISMATCH")
        if type(value.body) is not shape:
            raise PublicMarketHold("G2_PUBLIC_SOURCE_SCHEMA_MISMATCH")
        if (type(value.raw_bytes) is not bytes or not value.raw_bytes or
                hashlib.sha256(value.raw_bytes).hexdigest() != value.body_sha256):
            raise PublicMarketHold("G2_PUBLIC_SOURCE_DIGEST_MISMATCH")
    if type(selected_at_ms) is not int:
        raise PublicMarketHold("G2_PUBLIC_ASOF_INVALID")
    received = tuple(s.received_at_ms for s in sources)
    if (any(type(n) is not int or n > selected_at_ms or n < 0 for n in received)
            or selected_at_ms - min(received) > 60_000
            or max(received) - min(received) > 15_000):
        raise PublicMarketHold("G2_PUBLIC_SOURCE_CLOCK_HOLD")
    receipts = tuple(sorted((s.kind, s.body_sha256, s.received_at_ms)
                            for s in sources))
    return select_universe(exchange.body, ticker.body, book.body,
                           history_closed, source_health,
                           source_received_at_ms=min(received),
                           selected_at_ms=selected_at_ms,
                           public_receipts=receipts)
