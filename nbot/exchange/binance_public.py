"""Execution-owned credential-free Binance USD-M LIVE public market adapter.

V3.8 uses this adapter only for current LIVE market truth on the Execution VPS.
It accepts no Binance API key/secret, has no signed/private request path and has
no order methods. Local PAPER capital remains in nbot.exchange.paper.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nbot.exchange.contracts import Quote


LIVE_PUBLIC_REST_BASE_URL = "https://fapi.binance.com"
USER_AGENT = "NBOT-V3-Execution-Public/3.8"


class BinanceLivePublicMarketError(RuntimeError):
    """LIVE public market truth could not be obtained or validated safely."""


@dataclass(frozen=True, slots=True)
class BinanceLivePublicMarketConfig:
    base_url: str = LIVE_PUBLIC_REST_BASE_URL
    request_timeout_seconds: float = 3.0
    max_clock_skew_ms: int = 5_000

    def validate(self) -> None:
        if self.base_url != LIVE_PUBLIC_REST_BASE_URL:
            raise ValueError("LIVE_PUBLIC_BINANCE_HOST_NOT_PINNED")

        timeout = float(self.request_timeout_seconds)
        if not (0.1 <= timeout <= 30.0):
            raise ValueError("LIVE_PUBLIC_REQUEST_TIMEOUT_INVALID")

        if (
            isinstance(self.max_clock_skew_ms, bool)
            or not isinstance(self.max_clock_skew_ms, int)
            or not (0 <= self.max_clock_skew_ms <= 30_000)
        ):
            raise ValueError("LIVE_PUBLIC_CLOCK_SKEW_LIMIT_INVALID")


class BinanceLivePublicMarketData:
    """Direct Binance LIVE public quote boundary owned by Execution.

    This is deliberately not a Binance execution adapter. It exposes no
    credentials, signed/private request path, leverage write or order method.
    """

    def __init__(
        self,
        config: BinanceLivePublicMarketConfig | None = None,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
        now_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        self.config = config or BinanceLivePublicMarketConfig()
        self.config.validate()
        self._urlopen = urlopen_fn
        self._now_ms = now_ms_fn or (lambda: int(time.time() * 1000))
        self._connected = False

    def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        if path not in {
            "/fapi/v1/time",
            "/fapi/v1/ticker/bookTicker",
        }:
            raise BinanceLivePublicMarketError("LIVE_PUBLIC_PATH_FORBIDDEN")

        query = urlencode(sorted((params or {}).items()))
        url = self.config.base_url + path
        if query:
            url = f"{url}?{query}"

        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._urlopen(
                request,
                timeout=float(self.config.request_timeout_seconds),
            ) as response:
                raw = response.read()
        except HTTPError as exc:
            raise BinanceLivePublicMarketError(
                f"LIVE_PUBLIC_HTTP_ERROR:{path}:{exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise BinanceLivePublicMarketError(
                f"LIVE_PUBLIC_NETWORK_ERROR:{path}:{type(exc).__name__}"
            ) from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_JSON_INVALID"
            ) from exc

    def connect(self) -> None:
        if self._connected:
            return
        local_before = int(self._now_ms())
        payload = self._get("/fapi/v1/time")
        local_after = int(self._now_ms())

        if (
            local_before <= 0
            or local_after < local_before
            or not isinstance(payload, dict)
        ):
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_CLOCK_EVIDENCE_INVALID"
            )

        try:
            server_time = int(payload["serverTime"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_SERVER_TIME_INVALID"
            ) from exc

        local_mid = local_before + ((local_after - local_before) // 2)
        if abs(server_time - local_mid) > int(self.config.max_clock_skew_ms):
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_CLOCK_SKEW_EXCEEDED"
            )

        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_healthy(self) -> bool:
        return self._connected

    def quote(self, symbol: str) -> Quote:
        if not self._connected:
            raise BinanceLivePublicMarketError("LIVE_PUBLIC_NOT_CONNECTED")

        symbol = str(symbol).strip().upper()
        if not symbol or not symbol.isalnum():
            raise ValueError("LIVE_PUBLIC_SYMBOL_INVALID")

        payload = self._get(
            "/fapi/v1/ticker/bookTicker",
            {"symbol": symbol},
        )
        if not isinstance(payload, dict) or payload.get("symbol") != symbol:
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_BOOK_TICKER_INVALID"
            )

        try:
            bid = float(payload["bidPrice"])
            ask = float(payload["askPrice"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_BOOK_TICKER_INVALID"
            ) from exc

        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid <= 0
            or ask <= 0
            or ask < bid
        ):
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_BOOK_TICKER_INVALID"
            )

        observed_at = int(self._now_ms())
        if observed_at <= 0:
            raise BinanceLivePublicMarketError(
                "LIVE_PUBLIC_QUOTE_TIME_INVALID"
            )

        source_time = payload.get("time")
        try:
            timestamp_ms = (
                int(source_time)
                if source_time not in (None, "")
                else observed_at
            )
        except (TypeError, ValueError):
            timestamp_ms = observed_at

        if timestamp_ms <= 0:
            timestamp_ms = observed_at

        return Quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            timestamp_ms=timestamp_ms,
        )
