# ============================================================
# TESTNET EXCHANGE ADAPTER
# ============================================================
# Binance Futures USDT-M Testnet Adapter
#
# PURPOSE:
# - Provide truthful exchange state
# - Execute real orders
# - Serve as the ONLY reality boundary
#
# NON-RESPONSIBILITIES:
# - No risk logic
# - No state mutation
# - No trading decisions
#
# GUARANTEES:
# - Idempotent emergency exit
# - REST boundary isolation
# - Schema validation
# - Quantization correctness
#
# ============================================================

# ============================================================
# SECTION 1 — IMPORTS
# ============================================================

import os
import json
import time
import hmac
import hashlib
import requests
import websocket
import threading
from urllib.parse import urlparse
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List
from decimal import Decimal, ROUND_DOWN
from config import (
    LEVERAGE,
    MAX_SPREAD_PCT,
    SHADOW_MODE,
    TRADING_ENV,
    EXECUTION_MODE,
)
from execution.exceptions import (
    OperationalExchangeError,
    EntryValidationError,
    MarketStateError,
    StopAlreadyBreached,
)
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# SECTION 2 — CONFIGURATION
# ============================================================

BASE_URL = os.getenv("TESTNET_BASE_URL")
API_KEY = os.getenv("TESTNET_API_KEY")
API_SECRET = os.getenv("TESTNET_API_SECRET")
MARKET_WS_URL = os.getenv("TESTNET_MARKET_WS_URL")
USER_WS_URL = os.getenv("TESTNET_USER_WS_URL")
USER_STREAM_READY_TIMEOUT = float(
    os.getenv("TESTNET_USER_STREAM_READY_TIMEOUT", "20")
)

TIMEOUT = 5  # seconds


# ============================================================
# SECTION 3 — DATA CONTRACTS
# ============================================================

@dataclass(frozen=True)
class EntryAck:
    filled_qty: float
    avg_price: float
    requested_qty: float
    fully_filled: bool
    order_id: int | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class PriceTick:
    symbol: str
    price: float
    timestamp: int


# ============================================================
# SECTION 4 — ADAPTER
# ============================================================

class TestnetExchange:
    """
    Binance Futures USDT-M Testnet Adapter.

    Architecture:
    - Stateless
    - Truth-bound
    - REST authoritative
    """

    # ========================================================
    # SECTION A — INITIALIZATION
    # ========================================================

    def __init__(self, system_log):
        self.system_log = system_log

        if TRADING_ENV != "TESTNET":
            raise RuntimeError(
                f"TESTNET_ADAPTER_ENVIRONMENT_MISMATCH | configured={TRADING_ENV}"
            )

        if EXECUTION_MODE not in {"SHADOW", "TRADE"}:
            raise RuntimeError(
                f"TESTNET_EXECUTION_MODE_INVALID | mode={EXECUTION_MODE}"
            )

        if not BASE_URL:
            raise RuntimeError("TESTNET_BASE_URL_MISSING")

        rest_host = (urlparse(BASE_URL).hostname or "").lower()
        if rest_host == "fapi.binance.com":
            raise RuntimeError("TESTNET_BASE_URL_POINTS_TO_MAINNET")
        if rest_host != "demo-fapi.binance.com":
            raise RuntimeError(
                f"TESTNET_REST_HOST_UNEXPECTED | host={rest_host}"
            )

        if not MARKET_WS_URL:
            raise RuntimeError("TESTNET_MARKET_WS_URL_MISSING")

        market_host = (urlparse(MARKET_WS_URL).hostname or "").lower()
        if market_host != "stream.binancefuture.com":
            raise RuntimeError(
                f"TESTNET_MARKET_WS_HOST_UNEXPECTED | host={market_host}"
            )

        if not SHADOW_MODE:
            if not USER_WS_URL:
                raise RuntimeError("TESTNET_USER_WS_URL_MISSING")
            user_host = (urlparse(USER_WS_URL).hostname or "").lower()
            if user_host != "stream.binancefuture.com":
                raise RuntimeError(
                    f"TESTNET_USER_WS_HOST_UNEXPECTED | host={user_host}"
                )

        if not API_KEY or not API_SECRET:
            raise RuntimeError("TESTNET_EXCHANGE_CREDENTIALS_MISSING")

        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": API_KEY})
        self._symbol_filters = self._load_symbol_filters()
        # =====================================================
        # HARDENING STATE TRACKERS
        # =====================================================
        self._active_sl_order_id = None
        self._user_stream_healthy = False
        self._user_stream_ready = threading.Event()
        self._last_user_event_ts = 0
        self._cached_position = None

    # ========================================================
    # SECTION B — LOW LEVEL REST BOUNDARY
    # ========================================================

    def _public_get(self, path: str, params: dict | None = None):
        try:
            resp = self.session.get(
                f"{BASE_URL}{path}",
                params=params or {},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                raise OperationalExchangeError(
                    f"PUBLIC_REST_GET_FAILED | path={path} | {error_detail}"
                )
            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("PUBLIC_REST_TIMEOUT")
        except OperationalExchangeError:
            raise
        except Exception as e:
            raise OperationalExchangeError(
                f"PUBLIC_REST_ERROR | path={path} | {e}"
            )

    def _require_fields(self, data: dict, required: list, context: str):
        missing = [k for k in required if k not in data]
        if missing:
            raise OperationalExchangeError(
                f"SCHEMA_MISMATCH | context={context} | missing={missing}"
            )

    def _sign(self, params: dict) -> dict:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        signature = hmac.new(
            API_SECRET.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _get(self, path: str, params: dict):
        try:
            start = time.perf_counter()
            resp = self.session.get(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.system_log.error(
                    f"REST_GET_FAILED | path={path} | "
                    f"status={resp.status_code} | "
                    f"error={error_detail}"
                )
                raise OperationalExchangeError(
                    f"REST_GET_FAILED | path={path} | {error_detail}"
                )

            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("REST_TIMEOUT")
        except Exception as e:
            # HARDENING: detect rate limit and backoff
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(1.0)
            raise OperationalExchangeError(f"REST_ERROR | {e}")

    def _post(self, path: str, params: dict):
        try:
            resp = self.session.post(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.system_log.error(
                    f"REST_POST_FAILED | path={path} | "
                    f"status={resp.status_code} | "
                    f"error={error_detail}"
                )
                raise OperationalExchangeError(
                    f"REST_POST_FAILED | path={path} | {error_detail}"
                )

            # Binance percent price filter (-4131) → market condition, not infra
            try:
                data = resp.json()
                code = data.get("code")
            except Exception:
                code = None

            if code == -4131:
                raise MarketStateError(
                    "PERCENT_PRICE_FILTER_VIOLATION"
                )

            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("REST_TIMEOUT")
        except Exception as e:
            raise OperationalExchangeError(
                f"REST_POST_EXCEPTION | "
                f"path={path} | "
                f"error={type(e).__name__}:{e}"
            )

    def _delete(self, path: str, params: dict):
        try:
            start = time.perf_counter()
            resp = self.session.delete(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.system_log.error(
                    f"REST_DELETE_FAILED | path={path} | "
                    f"status={resp.status_code} | "
                    f"error={error_detail}"
                )
                raise OperationalExchangeError(
                    f"REST_DELETE_FAILED | path={path} | {error_detail}"
                )

            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("REST_TIMEOUT")

        except Exception as e:
            self.system_log.error(
                f"REST_DELETE_EXCEPTION | path={path} | error={e}"
            )
            raise OperationalExchangeError(
                f"REST_DELETE_EXCEPTION | path={path} | {e}"
            )

    def _put(self, path: str, params: dict):
        try:
            start = time.perf_counter()
            resp = self.session.put(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                raise OperationalExchangeError(
                    f"REST_PUT_FAILED | {error_detail}"
                )

            return resp.json()
        except Exception as e:
            raise OperationalExchangeError(f"REST_PUT_ERROR | {e}")

    def _extract_binance_error(self, response):
        """
        Parse Binance JSON error body safely.
        """
        try:
            data = response.json()
            code = data.get("code")
            msg = data.get("msg")
            return f"BINANCE_ERROR | code={code} | msg={msg}"
        except Exception:
            return f"HTTP_{response.status_code}"

    def is_user_stream_healthy(self) -> bool:
        """Return whether the authenticated user stream is connected."""
        if SHADOW_MODE:
            return True
        return self._user_stream_healthy and self._user_stream_ready.is_set()

    def wait_for_user_stream_ready(self, timeout: float | None = None) -> bool:
        """Wait until the authenticated user stream completes its handshake."""
        if SHADOW_MODE:
            return True
        wait_timeout = (
            USER_STREAM_READY_TIMEOUT if timeout is None else float(timeout)
        )
        return self._user_stream_ready.wait(wait_timeout)

    # ========================================================
    # SECTION C — EXCHANGE CONTRACTS & QUANTIZATION
    # ========================================================

    def _load_symbol_filters(self):

        data = self._get(
            "/fapi/v1/exchangeInfo",
            {"timestamp": int(time.time() * 1000)},
        )

        filters = {}

        for s in data.get("symbols", []):
            symbol = s.get("symbol")
            if not symbol:
                continue

            lot = next(
                (f for f in s["filters"] if f["filterType"] == "LOT_SIZE"),
                None,
            )
            market_lot = next(
                (f for f in s["filters"] if f["filterType"] == "MARKET_LOT_SIZE"),
                None,
            )
            price_filter = next(
                (f for f in s["filters"] if f["filterType"] == "PRICE_FILTER"),
                None,
            )

            if not lot or not market_lot or not price_filter:
                continue

            filters[symbol] = {
                "stepSize": float(lot["stepSize"]),
                "minQty": float(lot["minQty"]),
                "maxQty": float(lot["maxQty"]),
                "marketMinQty": float(market_lot["minQty"]),
                "marketMaxQty": float(market_lot["maxQty"]),
                "tickSize": float(price_filter["tickSize"]),
            }

        return filters

    def _quantize_qty(self, qty: float, step: float) -> float:
        """
        Quantize quantity DOWN to Binance stepSize safely.
        Prevents float rounding errors and scientific notation drift.
        """
        qty_dec = Decimal(str(qty))
        step_dec = Decimal(str(step))
        quantized = (qty_dec // step_dec) * step_dec
        return float(quantized.quantize(step_dec, rounding=ROUND_DOWN))

    def _quantize_price(self, price: float, tick: float) -> float:
        """
        Quantize price DOWN to Binance tickSize safely.
        Guarantees no extra decimals (prevents 400 errors).
        """
        price_dec = Decimal(str(price))
        tick_dec = Decimal(str(tick))
        quantized = (price_dec // tick_dec) * tick_dec
        return float(quantized.quantize(tick_dec, rounding=ROUND_DOWN))

    # --------------------------------------------------------
    # Public Quantization Helper (Single Source of Truth)
    # --------------------------------------------------------

    def quantize_price(self, symbol: str, price: float) -> float:
        """
        Public price quantization.
        Lifecycle MUST use this for SL comparison.
        """
        filters = self._symbol_filters.get(symbol)
        if not filters:
            raise OperationalExchangeError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )

        return self._quantize_price(
            price,
            filters["tickSize"],
        )

    # ========================================================
    # SECTION D — LIFECYCLE
    # ========================================================

    def connect(self):
        self._public_get("/fapi/v1/ping")

        if SHADOW_MODE:
            self.system_log.info(
                "TESTNET_SHADOW_CONNECT_OK | auth_stream=SKIPPED"
            )
            return

        self._get(
            "/fapi/v2/account",
            {"timestamp": int(time.time() * 1000)},
        )

        self._start_user_stream()

        if not self.wait_for_user_stream_ready():
            raise OperationalExchangeError(
                "TESTNET_USER_STREAM_READY_TIMEOUT | "
                f"timeout={USER_STREAM_READY_TIMEOUT}"
            )

        if not self.is_user_stream_healthy():
            raise OperationalExchangeError(
                "TESTNET_USER_STREAM_UNHEALTHY_AT_STARTUP"
            )

        self.system_log.info(
            "TESTNET_TRADE_CONNECT_OK | auth_stream=READY"
        )

    def disconnect(self):
        return

    # ========================================================
    # SECTION E — LEVERAGE ENFORCEMENT
    # ========================================================

    def set_leverage(self, *, symbol: str, leverage: int):
        try:
            self._post(
                "/fapi/v1/leverage",
                {
                    "symbol": symbol,
                    "leverage": leverage,
                    "timestamp": int(time.time() * 1000),
                },
            )
        except Exception as e:
            raise OperationalExchangeError(
                f"LEVERAGE_SET_FAILED | symbol={symbol} | {e}"
            )

    def enforce_leverage_for_universe(self, symbols: List[str]):
        for symbol in symbols:
            self.set_leverage(symbol=symbol, leverage=LEVERAGE)

    # ========================================================
    # SECTION F — MARKET DATA
    # ========================================================

    def price_stream(self):
        """
        WebSocket-driven price stream.
        Event-driven.
        """

        ws = websocket.create_connection(MARKET_WS_URL)

        try:
            while True:
                message = ws.recv()
                data = json.loads(message)
                ts = int(time.time() * 1000)

                for row in data:
                    symbol = row.get("s")
                    if not symbol or not symbol.endswith("USDT"):
                        continue

                    price = float(row.get("c", 0))
                    if price <= 0:
                        continue

                    yield PriceTick(
                        symbol=symbol,
                        price=price,
                        timestamp=ts,
                    )

        except Exception as e:
            raise OperationalExchangeError(
                f"WS_PRICE_STREAM_FAILED | {e}"
            )
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def get_historical_candles(self, *, symbol: str, interval: str, limit: int):
        """Return only fully closed Binance klines in OHLC tuple format."""
        data = self._get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "timestamp": int(time.time() * 1000),
            },
        )

        now_ms = int(time.time() * 1000)
        candles = []

        for candle in data:
            if not isinstance(candle, (list, tuple)) or len(candle) < 7:
                raise OperationalExchangeError(
                    f"HISTORICAL_CANDLE_SCHEMA_INVALID | symbol={symbol}"
                )

            open_time = int(candle[0])
            close_time = int(candle[6])

            # Binance includes the currently forming kline in this endpoint.
            # It must never enter completed-candle strategy history.
            if close_time >= now_ms:
                continue

            o = float(candle[1])
            h = float(candle[2])
            l = float(candle[3])
            c = float(candle[4])

            if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c):
                raise OperationalExchangeError(
                    f"HISTORICAL_CANDLE_VALUES_INVALID | symbol={symbol} | "
                    f"open_time={open_time}"
                )

            candles.append((open_time, o, h, l, c))

        return candles

    def get_current_spread_pct(self, *, symbol: str) -> float:
        data = self._get(
            "/fapi/v1/ticker/bookTicker",
            {
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
            },
        )

        bid = float(data["bidPrice"])
        ask = float(data["askPrice"])

        if bid <= 0 or ask <= 0:
            return 999.0

        mid = (bid + ask) / 2.0
        return ((ask - bid) / mid) * 100.0

    def get_last_price(self, symbol: str) -> float:
        data = self._get(
            "/fapi/v1/ticker/price",
            {
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
            },
        )
        self._require_fields(data, ["price"], context="get_last_price")
        return float(data["price"])

    # ========================================================
    # SECTION G — POSITION TRUTH
    # ========================================================

    def get_position(self):
        now = int(time.time() * 1000)
        data = self._get(
            "/fapi/v2/positionRisk",
            {"timestamp": now},
        )

        for pos in data:
            qty = float(pos["positionAmt"])
            if abs(qty) > 0.0:
                position = SimpleNamespace(
                    qty=abs(qty),
                    side="LONG" if qty > 0 else "SHORT",
                    entry_price=float(pos["entryPrice"]),
                    symbol=pos["symbol"],
                    liquidation_price=float(pos.get("liquidationPrice", 0.0)),
                )

                # Attempt to fetch active SL
                sl_price = self._get_active_stop_loss(position.symbol)

                # DO NOT hard-fail if SL missing.
                # Let reconciliation lifecycle decide recovery.
                if sl_price is None:
                    position.stop_loss = None
                else:
                    position.stop_loss = sl_price
                return position
        return None

    def recover_active_stop_loss(self, symbol: str):
        """Recover the active conditional stop and its Binance algo ID."""

        ref = self._get_active_stop_loss_ref(symbol)
        if ref is None:
            return None

        self._active_sl_order_id = ref["algo_id"]
        return ref["stop_price"]

    def get_active_sl_order_id(self):
        return self._active_sl_order_id

    # ========================================================
    # INTERNAL SL QUERY
    # ========================================================

    def _get_active_stop_loss_ref(self, symbol: str, algo_id=None):
        """Return active STOP_MARKET metadata, optionally for one algoId."""

        try:
            orders = self._get(
                "/fapi/v1/openAlgoOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )

            for order in orders:
                if not (
                    order.get("algoType") == "CONDITIONAL"
                    and order.get("orderType") == "STOP_MARKET"
                    and order.get("reduceOnly") is True
                ):
                    continue

                current_id = order.get("algoId")
                if current_id is None:
                    continue
                current_id = int(current_id)

                if algo_id is not None and current_id != int(algo_id):
                    continue

                return {
                    "algo_id": current_id,
                    "stop_price": float(order.get("triggerPrice")),
                }

            return None

        except Exception as error:
            raise OperationalExchangeError(
                f"GET_ACTIVE_SL_FAILED | {error}"
            )

    def _get_active_stop_loss(self, symbol: str):
        ref = self._get_active_stop_loss_ref(symbol)
        if ref is None:
            return None

        self._active_sl_order_id = ref["algo_id"]
        return ref["stop_price"]

    def _start_user_stream(self):
        """
        Start hardened Binance user data stream with reconnect + keepalive.
        """

        if SHADOW_MODE:
            self.system_log.info(
                "USER_STREAM_SKIPPED | reason=SHADOW_MODE"
            )
            return

        if not USER_WS_URL:
            raise RuntimeError("TESTNET_USER_WS_URL_MISSING")

        self._user_stream_ready.clear()
        self._user_stream_healthy = False

        def _run():
            while True:
                try:
                    # Create listenKey
                    data = self._post(
                        "/fapi/v1/listenKey",
                        {"timestamp": int(time.time() * 1000)},
                    )

                    listen_key = data.get("listenKey")
                    if not listen_key:
                        raise OperationalExchangeError("LISTEN_KEY_FAILED")

                    ws_url = f"{USER_WS_URL.rstrip('/')}/{listen_key}"
                    ws = websocket.create_connection(ws_url)
                    ws.settimeout(60)

                    self._last_user_event_ts = int(time.time() * 1000)
                    self._user_stream_healthy = True
                    self._user_stream_ready.set()
                    self.system_log.info("USER_STREAM_CONNECTED")

                    # Start keepalive thread
                    def _keepalive():
                        while True:
                            time.sleep(30 * 60)  # 30 minutes
                            try:
                                self._put(
                                    "/fapi/v1/listenKey",
                                    {
                                        "listenKey": listen_key,
                                        "timestamp": int(time.time() * 1000),
                                    },
                                )
                            except Exception:
                                break

                    threading.Thread(
                        target=_keepalive,
                        daemon=True
                    ).start()

                    while True:
                        try:
                            msg = ws.recv()
                        except websocket.WebSocketTimeoutException:
                            # An idle authenticated stream is normal when no
                            # orders or account changes are occurring. Probe
                            # the socket instead of reconnecting every minute.
                            ws.ping()
                            continue

                        if not msg:
                            raise OperationalExchangeError(
                                "USER_STREAM_CLOSED_WITHOUT_MESSAGE"
                            )

                        event = json.loads(msg)

                        self._last_user_event_ts = int(time.time() * 1000)

                        if event.get("e") == "ACCOUNT_UPDATE":
                            for p in event.get("a", {}).get("P", []):
                                qty = float(p.get("pa", 0))
                                if abs(qty) > 0:
                                    self._cached_position = SimpleNamespace(
                                        qty=abs(qty),
                                        side="LONG" if qty > 0 else "SHORT",
                                        entry_price=float(p.get("ep", 0)),
                                        symbol=p.get("s"),
                                        stop_loss=None,
                                        liquidation_price=float(p.get("lp", 0)),
                                    )
                                else:
                                    self._cached_position = None

                except Exception as e:
                    self._user_stream_healthy = False
                    self._user_stream_ready.clear()
                    try:
                        ws.close()
                    except Exception:
                        pass
                    self.system_log.error(
                        f"USER_STREAM_RESTARTING | {e}"
                    )
                    time.sleep(5)

        threading.Thread(target=_run, daemon=True).start()

    # ========================================================
    # SECTION H — REALIZED PNL
    # ========================================================

    def get_realized_pnl(self, utc_day):

        start_ts = int(time.mktime(utc_day.timetuple()) * 1000)
        end_ts = start_ts + 24 * 60 * 60 * 1000

        trades = self._get(
            "/fapi/v1/userTrades",
            {
                "startTime": start_ts,
                "endTime": end_ts,
                "timestamp": int(time.time() * 1000),
            },
        )

        pnl = 0.0
        for t in trades:
            pnl += float(t.get("realizedPnl", 0.0))

        return pnl

    def get_trade_realized_pnl(
        self,
        *,
        symbol: str,
        since_timestamp: int,
    ) -> dict:

        now = int(time.time() * 1000)

        trades = self._get(
            "/fapi/v1/userTrades",
            {
                "symbol": symbol,
                "startTime": since_timestamp,
                "endTime": now,
                "timestamp": now,
            },
        )

        pnl = 0.0
        total_exit_qty = 0.0
        weighted_exit_value = 0.0

        for t in trades:
            realized = float(t.get("realizedPnl", 0.0))
            qty = float(t.get("qty", 0.0))
            price = float(t.get("price", 0.0))

            if realized != 0.0:
                pnl += realized
                total_exit_qty += qty
                weighted_exit_value += qty * price

        exit_price = (
            weighted_exit_value / total_exit_qty
            if total_exit_qty > 0
            else 0.0
        )

        return {
            "pnl": pnl,
            "exit_price": exit_price,
        }

    # ========================================================
    # SECTION I — EXECUTION
    # ========================================================

    def place_entry(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: str,
    ) -> EntryAck:

        if side not in ("LONG", "SHORT"):
            raise EntryValidationError(f"INVALID_SIDE | side={side}")

        order_side = "BUY" if side == "LONG" else "SELL"

        filters = self._symbol_filters.get(symbol)
        if not filters:
            raise EntryValidationError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )

        requested_qty = self._quantize_qty(quantity, filters["stepSize"])

        if requested_qty <= 0:
            raise EntryValidationError(
                f"QTY_ROUNDED_TO_ZERO | requested={quantity} | "
                f"step={filters['stepSize']}"
            )

        if Decimal(str(requested_qty)) % Decimal(str(filters["stepSize"])) != 0:
            raise EntryValidationError(
                f"QTY_STEP_MISALIGNMENT | qty={requested_qty} | "
                f"step={filters['stepSize']}"
            )

        if requested_qty < filters["marketMinQty"]:
            raise EntryValidationError(
                f"QTY_BELOW_MIN | qty={requested_qty} | "
                f"min={filters['marketMinQty']}"
            )

        if requested_qty > filters["marketMaxQty"]:
            raise EntryValidationError(
                f"QTY_ABOVE_MAX | qty={requested_qty} | "
                f"max={filters['marketMaxQty']}"
            )

        data = self._post(
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": order_side,
                "type": "MARKET",
                "quantity": requested_qty,
                "newClientOrderId": client_order_id,
                "recvWindow": 5000,
                "timestamp": int(time.time() * 1000),
            },
        )

        # Some valid Futures market-order responses omit cumQuote.
        # executedQty and status remain mandatory; average price is derived
        # from avgPrice, cumQuote, or confirmed position truth.
        self._require_fields(
            data,
            ["executedQty", "status"],
            context="place_entry"
        )

        filled_qty = float(data["executedQty"])

        # --------------------------------------------------------
        # Testnet Quirk Handling:
        # If executedQty == 0, derive fill from position delta
        # --------------------------------------------------------

        if filled_qty <= 0:

            # Poll position briefly for update
            timeout = time.time() + 1.0
            confirmed = None

            while time.time() < timeout:

                try:
                    confirmed = self.get_position()
                except Exception:
                    confirmed = None

                if confirmed and confirmed.symbol == symbol:
                    filled_qty = confirmed.qty
                    avg_price = confirmed.entry_price
                    break

                time.sleep(0.1)

            if not confirmed or confirmed.symbol != symbol:
                raise OperationalExchangeError("ENTRY_NOT_FILLED")
        else:
            avg_price = float(data.get("avgPrice", 0.0) or 0.0)

            if avg_price <= 0:
                cum_quote = float(data.get("cumQuote", 0.0) or 0.0)
                if cum_quote > 0:
                    avg_price = cum_quote / filled_qty

            if avg_price <= 0:
                # Final fallback is replaced below by authoritative REST
                # position truth before the acknowledgement is returned.
                avg_price = price

        fully_filled = abs(filled_qty - requested_qty) < 1e-12

        # REST confirmation before proceeding
        confirmed = self.get_position()
        if not confirmed or confirmed.symbol != symbol:
            raise OperationalExchangeError(
                "ENTRY_NOT_CONFIRMED_BY_REST"
            )

        return EntryAck(
            filled_qty=filled_qty,
            avg_price=avg_price,
            requested_qty=requested_qty,
            fully_filled=fully_filled,
            order_id=(
                int(data["orderId"])
                if data.get("orderId") is not None
                else None
            ),
            client_order_id=str(
                data.get("clientOrderId") or client_order_id
            ),
        )


    def query_order_by_client_id(
        self,
        *,
        symbol: str,
        client_order_id: str,
    ):
        """Return an order by client ID, or None when Binance says absent."""

        try:
            return self._get(
                "/fapi/v1/order",
                {
                    "symbol": symbol,
                    "origClientOrderId": client_order_id,
                    "recvWindow": 5000,
                    "timestamp": int(time.time() * 1000),
                },
            )
        except OperationalExchangeError as error:
            message = str(error)
            if "code=-2013" in message or "Order does not exist" in message:
                return None
            raise

    def resolve_ambiguous_entry(
        self,
        *,
        symbol: str,
        client_order_id: str,
        requested_qty: float,
        fallback_price: float,
        timeout_seconds: float = 10.0,
    ) -> dict:
        """
        Resolve a timed-out market entry without resubmitting it.

        The exact order is queried by origClientOrderId while position truth
        is polled in parallel. A confirmed fill returns an EntryAck. Any
        position without a confirmed full-fill acknowledgement is returned as
        an unprotected position so the engine can emergency-flatten it.
        """

        deadline = time.monotonic() + max(1.0, timeout_seconds)
        last_order_error = None
        last_position_error = None
        latest_order = None
        latest_position = None

        while time.monotonic() < deadline:
            try:
                latest_order = self.query_order_by_client_id(
                    symbol=symbol,
                    client_order_id=client_order_id,
                )
                last_order_error = None
            except Exception as error:
                last_order_error = error

            try:
                position = self.get_position()
                latest_position = (
                    position
                    if position is not None and position.symbol == symbol
                    else None
                )
                last_position_error = None
            except Exception as error:
                last_position_error = error

            if latest_order is not None:
                status = str(latest_order.get("status", "")).upper()
                executed_qty = float(latest_order.get("executedQty", 0.0) or 0.0)

                if status == "FILLED" and executed_qty > 0:
                    avg_price = float(latest_order.get("avgPrice", 0.0) or 0.0)
                    if avg_price <= 0:
                        cum_quote = float(latest_order.get("cumQuote", 0.0) or 0.0)
                        avg_price = (
                            cum_quote / executed_qty
                            if cum_quote > 0
                            else fallback_price
                        )

                    requested = self._quantize_qty(
                        requested_qty,
                        self._symbol_filters[symbol]["stepSize"],
                    )
                    fully_filled = abs(executed_qty - requested) < 1e-12

                    if latest_position is not None and fully_filled:
                        return {
                            "outcome": "FILLED",
                            "ack": EntryAck(
                                filled_qty=executed_qty,
                                avg_price=avg_price,
                                requested_qty=requested,
                                fully_filled=True,
                                order_id=(
                                    int(latest_order["orderId"])
                                    if latest_order.get("orderId") is not None
                                    else None
                                ),
                                client_order_id=str(
                                    latest_order.get("clientOrderId")
                                    or client_order_id
                                ),
                            ),
                        }

                if status in {"CANCELED", "EXPIRED", "REJECTED"} and latest_position is None:
                    return {"outcome": "NOT_FILLED"}

            if latest_position is not None:
                # Position truth takes precedence. Without a confirmed full
                # fill response, the position has no verified protective SL.
                return {
                    "outcome": "POSITION_EXISTS",
                    "position": latest_position,
                }

            time.sleep(0.5)

        self.system_log.error(
            f"ENTRY_RESOLUTION_TIMEOUT | "
            f"symbol={symbol} | "
            f"client_order_id={client_order_id} | "
            f"order_seen={latest_order is not None} | "
            f"position_seen={latest_position is not None} | "
            f"order_error={last_order_error} | "
            f"position_error={last_position_error}"
        )

        return {"outcome": "UNRESOLVED"}

    def place_initial_sl(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
    ):

        last_price = self.get_last_price(symbol)

        filters = self._symbol_filters[symbol]
        qty = self._quantize_qty(qty, filters["stepSize"])
        stop_price = self._quantize_price(
            stop_price,
            filters["tickSize"],
        )
        self.system_log.info(
            f"ADAPTER_PLACE_SL | "
            f"symbol={symbol} | "
            f"side={side} | "
            f"qty={qty} | "
            f"stop_price={stop_price} | "
            f"last_price={last_price}"
        )

        if Decimal(str(stop_price)) % Decimal(str(filters["tickSize"])) != 0:
            raise OperationalExchangeError("STOP_PRICE_TICK_MISALIGNMENT")

        if side == "LONG" and stop_price >= last_price:
            raise StopAlreadyBreached("STOP_ALREADY_BREACHED")

        if side == "SHORT" and stop_price <= last_price:
            raise StopAlreadyBreached("STOP_ALREADY_BREACHED")

        exit_side = "SELL" if side == "LONG" else "BUY"

        # HARDENING: retry SL placement (network/rate limit safety)
        attempts = 3
        for attempt in range(attempts):
            try:
                payload = {
                    "symbol": symbol,
                    "side": exit_side,
                    "algoType": "CONDITIONAL",
                    "type": "STOP_MARKET",
                    "quantity": qty,
                    "triggerPrice": stop_price,
                    "reduceOnly": "true",
                    "priceProtect": "TRUE",
                    "workingType": "CONTRACT_PRICE",
                    "timestamp": int(time.time() * 1000),
                }

                data = self._post(
                    "/fapi/v1/algoOrder",
                    payload,
                )
                break

            except Exception:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))

        if not isinstance(data, dict) or data.get("algoId") is None:
            raise OperationalExchangeError("SL_ALGO_ID_MISSING")

        new_algo_id = int(data["algoId"])
        ref = self._get_active_stop_loss_ref(
            symbol,
            algo_id=new_algo_id,
        )
        if ref is None:
            raise OperationalExchangeError(
                "SL_PLACEMENT_NOT_CONFIRMED"
            )

        self._active_sl_order_id = new_algo_id
        return ref

    def update_sl(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        new_stop_price: float,
    ):

        self.system_log.info(
            f"ADAPTER_UPDATE_SL | "
            f"symbol={symbol} | "
            f"side={side} | "
            f"qty={qty} | "
            f"new_stop_price={new_stop_price}"
        )

        old_algo_id = self._active_sl_order_id

        # Place and verify the new stop before cancelling the old one.
        new_ref = self.place_initial_sl(
            symbol=symbol,
            side=side,
            qty=qty,
            stop_price=new_stop_price,
        )
        new_algo_id = new_ref["algo_id"]

        if old_algo_id and old_algo_id != new_algo_id:
            try:
                self._delete(
                    "/fapi/v1/algoOrder",
                    {
                        "symbol": symbol,
                        "algoId": old_algo_id,
                        "timestamp": int(time.time() * 1000),
                    },
                )
            except Exception as error:
                # The new stop is confirmed. Keep managing safely, but record
                # that an obsolete stop may still require cleanup.
                self.system_log.warning(
                    f"OLD_SL_CANCEL_FAILED | "
                    f"symbol={symbol} | "
                    f"old_algo_id={old_algo_id} | "
                    f"new_algo_id={new_algo_id} | "
                    f"error={error}"
                )

        self._active_sl_order_id = new_algo_id
        return new_ref

    def cancel_pending_entries(self):

        # Cancel normal entry orders only (NOT algo SL)
        orders = self._get(
            "/fapi/v1/openOrders",
            {
                "timestamp": int(time.time() * 1000),
            },
        )

        for o in orders:
            if not o.get("reduceOnly"):
                self._delete(
                    "/fapi/v1/order",
                    {
                        "symbol": o["symbol"],
                        "orderId": o["orderId"],
                        "timestamp": int(time.time() * 1000),
                    },
                )

    # ========================================================
    # SECTION J — EMERGENCY EXIT
    # ========================================================

    def emergency_exit(self):

        # Force authoritative REST truth (never trust WS for emergency).
        data = self._get(
            "/fapi/v2/positionRisk",
            {"timestamp": int(time.time() * 1000)},
        )

        pos = None
        for p in data:
            qty = float(p["positionAmt"])
            if abs(qty) > 0.0:
                pos = SimpleNamespace(
                    qty=abs(qty),
                    side="LONG" if qty > 0 else "SHORT",
                    symbol=p["symbol"],
                )
                break

        if pos is None:
            return

        symbol = pos.symbol

        # Keep the existing protective stop alive while submitting the
        # reduce-only market close. Removing protection before the flatten
        # is confirmed creates an unnecessary unprotected interval.
        filters = self._symbol_filters.get(symbol)
        if not filters:
            raise OperationalExchangeError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )

        qty = self._quantize_qty(pos.qty, filters["stepSize"])

        if Decimal(str(qty)) % Decimal(str(filters["stepSize"])) != 0:
            raise OperationalExchangeError("FLATTEN_STEP_MISALIGNMENT")

        if qty <= 0:
            raise OperationalExchangeError(
                f"FLATTEN_QTY_INVALID | symbol={symbol} | qty={qty}"
            )

        if qty < filters["marketMinQty"]:
            raise OperationalExchangeError(
                f"FLATTEN_QTY_BELOW_MARKET_MIN | qty={qty}"
            )

        side = "SELL" if pos.side == "LONG" else "BUY"

        self._post(
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": qty,
                "reduceOnly": True,
                "timestamp": int(time.time() * 1000),
            },
        )

        # Final authoritative REST check. Do not remove protective orders or
        # clear local SL state unless exchange truth confirms the position is
        # completely flat.
        data = self._get(
            "/fapi/v2/positionRisk",
            {"timestamp": int(time.time() * 1000)},
        )

        remaining = []
        for p in data:
            remaining_qty = float(p["positionAmt"])
            if abs(remaining_qty) > 0.0:
                remaining.append((p["symbol"], remaining_qty))

        if remaining:
            raise OperationalExchangeError(
                f"EMERGENCY_FLATTEN_NOT_CONFIRMED | remaining={remaining}"
            )

        # Exchange is flat. Protective orders are now orphans and can be
        # removed safely.
        try:
            algo_orders = self._get(
                "/fapi/v1/openAlgoOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )

            for o in algo_orders:
                if (
                    o.get("algoType") == "CONDITIONAL"
                    and o.get("reduceOnly") is True
                ):
                    try:
                        self._delete(
                            "/fapi/v1/algoOrder",
                            {
                                "symbol": symbol,
                                "algoId": o["algoId"],
                                "timestamp": int(time.time() * 1000),
                            },
                        )
                    except Exception:
                        pass

        except Exception as e:
            raise OperationalExchangeError(
                f"FLATTEN_FETCH_ALGO_FAILED | {e}"
            )

        try:
            open_orders = self._get(
                "/fapi/v1/openOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )

            for o in open_orders:
                if o.get("reduceOnly") is True:
                    try:
                        self._delete(
                            "/fapi/v1/order",
                            {
                                "symbol": symbol,
                                "orderId": o["orderId"],
                                "timestamp": int(time.time() * 1000),
                            },
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        self._active_sl_order_id = None


    # ========================================================
    # SECTION K — ACCOUNT
    # ========================================================

    def get_available_balance(self, *, asset: str = "USDT") -> float:

        data = self._get(
            "/fapi/v2/balance",
            {"timestamp": int(time.time() * 1000)},
        )

        for entry in data:
            if entry.get("asset") == asset:
                if "availableBalance" not in entry:
                    raise OperationalExchangeError(
                        "SCHEMA_MISMATCH | context=get_available_balance"
                    )
                return float(entry["availableBalance"])

        raise OperationalExchangeError(
            f"BALANCE_NOT_FOUND | asset={asset}"
        )
