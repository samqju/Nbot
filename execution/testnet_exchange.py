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
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List
from decimal import Decimal, ROUND_DOWN
from config import LEVERAGE, MAX_SPREAD_PCT
from execution.exceptions import OperationalExchangeError, MarketStateError, StopAlreadyBreached
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# SECTION 2 — CONFIGURATION
# ============================================================

BASE_URL = os.getenv("TESTNET_BASE_URL")
API_KEY = os.getenv("TESTNET_API_KEY")
API_SECRET = os.getenv("TESTNET_API_SECRET")

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

    def __init__(self, system_log, error_log):
        self.system_log = system_log
        self.error_log = error_log
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": API_KEY})
        self._symbol_filters = self._load_symbol_filters()

        if not BASE_URL or not API_KEY or not API_SECRET:
            raise RuntimeError("TESTNET_EXCHANGE_CONFIG_MISSING")

        # =====================================================
        # HARDENING STATE TRACKERS
        # =====================================================
        self._active_sl_order_id = None
        self._user_stream_healthy = False
        self._last_user_event_ts = 0
        self._cached_position = None

    # ========================================================
    # SECTION B — LOW LEVEL REST BOUNDARY
    # ========================================================

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
                self.error_log.error(
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
            start = time.perf_counter()
            resp = self.session.post(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.error_log.error(
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
            raise OperationalExchangeError(f"REST_ERROR | {e}")

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
                self.error_log.error(
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
            self.error_log.error(
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
        """
        HARDENING: Detect WS stall.
        """
        if not self._user_stream_healthy:
            return False

        if (time.time() * 1000) - self._last_user_event_ts > 60000:
            self.error_log.error("USER_STREAM_STALLED")
            return False

        return True

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
        self._get(
            "/fapi/v2/account",
            {"timestamp": int(time.time() * 1000)},
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

        stream_url = "wss://stream.binancefuture.com/ws/!ticker@arr"

        ws = websocket.create_connection(stream_url)

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
        data = self._get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "timestamp": int(time.time() * 1000),
            },
        )

        return [
            (
                int(c[0]),
                float(c[1]),
                float(c[2]),
                float(c[3]),
                float(c[4]),
            )
            for c in data
        ]

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
                    self.error_log.error(
                        "POSITION_WITHOUT_ACTIVE_SL_DETECTED"
                    )
                    position.stop_loss = None
                else:
                    position.stop_loss = sl_price
                return position
        return None

    def recover_active_stop_loss(self, symbol: str):
        """
        One-time recovery of active STOP_MARKET order.
        Used only during reconciliation, not per tick.
        """

        orders = self._get(
            "/fapi/v1/openOrders",
            {
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
            },
        )

        for o in orders:
            if (
                o.get("type") == "STOP_MARKET"
                and o.get("reduceOnly") is True
            ):
                self._active_sl_order_id = o.get("orderId")
                return float(o.get("stopPrice"))

        return None

    # ========================================================
    # INTERNAL SL QUERY
    # ========================================================

    def _get_active_stop_loss(self, symbol: str):
        """
        Return current active STOP_MARKET reduce-only SL price.
        Returns float stopPrice or None.
        """

        try:
            orders = self._get(
                "/fapi/v1/openOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )

            for o in orders:
                if (
                    o.get("type") == "STOP_MARKET"
                    and o.get("reduceOnly") is True
                ):
                    self._active_sl_order_id = o.get("orderId")
                    return float(o.get("stopPrice"))

            return None

        except Exception as e:
            raise OperationalExchangeError(
                f"GET_ACTIVE_SL_FAILED | {e}"
            )

    def _start_user_stream(self):
        """
        Start hardened Binance user data stream with reconnect + keepalive.
        """

        import threading

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

                    ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
                    ws = websocket.create_connection(ws_url)
                    ws.settimeout(60)

                    self._user_stream_healthy = True
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
                        msg = ws.recv()
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
                    try:
                        ws.close()
                    except Exception:
                        pass
                    self.error_log.error(
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
    ) -> EntryAck:

        if side not in ("LONG", "SHORT"):
            raise OperationalExchangeError("INVALID_SIDE")

        order_side = "BUY" if side == "LONG" else "SELL"

        filters = self._symbol_filters.get(symbol)
        if not filters:
            raise OperationalExchangeError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )

        requested_qty = self._quantize_qty(quantity, filters["stepSize"])

        if requested_qty <= 0:
            raise OperationalExchangeError("QTY_ROUNDED_TO_ZERO")

        if Decimal(str(requested_qty)) % Decimal(str(filters["stepSize"])) != 0:
            raise OperationalExchangeError("QTY_STEP_MISALIGNMENT")

        if requested_qty < filters["marketMinQty"]:
            raise OperationalExchangeError("QTY_BELOW_MIN")

        if requested_qty > filters["marketMaxQty"]:
            raise OperationalExchangeError("QTY_ABOVE_MAX")

        data = self._post(
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": order_side,
                "type": "MARKET",
                "quantity": requested_qty,
                "timestamp": int(time.time() * 1000),
            },
        )

        self._require_fields(
            data,
            ["executedQty", "cumQuote", "status"],
            context="place_entry"
        )

        filled_qty = float(data["executedQty"])

        if filled_qty > 0:
            cum_quote = float(data["cumQuote"])
            if cum_quote > 0:
                avg_price = cum_quote / filled_qty
            else:
                avg_price = price
        else:
            # Wait up to 3 seconds for WS update
            timeout = time.time() + 3
            while time.time() < timeout:
                pos = self.get_position()
                if pos and pos.symbol == symbol:
                    filled_qty = pos.qty
                    avg_price = pos.entry_price
                    break
                time.sleep(0.2)
            else:
                raise OperationalExchangeError("ENTRY_NOT_FILLED")

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
        )


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
                data = self._post(
                    "/fapi/v1/order",
                    {
                        "symbol": symbol,
                        "side": exit_side,
                        "type": "STOP_MARKET",
                        "stopPrice": stop_price,
                        "quantity": qty,
                        "reduceOnly": True,
                        "timestamp": int(time.time() * 1000),
                    },
                )
                break
            except Exception as e:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))

        # Verify SL exists
        actual_sl = self._get_active_stop_loss(symbol)
        if actual_sl is None:
            raise OperationalExchangeError(
                "SL_PLACEMENT_NOT_CONFIRMED"
            )
        # Track SL order id to avoid openOrders scan
        if isinstance(data, dict) and "orderId" in data:
            self._active_sl_order_id = data["orderId"]

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

        # ======================================================
        # ATOMIC SL REPLACEMENT (ABSOLUTELY SAFE PATTERN)
        # ======================================================

        old_order_id = self._active_sl_order_id

        # STEP 1 — Place NEW SL FIRST (never leave position unprotected)
        self.place_initial_sl(
            symbol=symbol,
            side=side,
            qty=qty,
            stop_price=new_stop_price,
        )

        # STEP 2 — Confirm new SL exists
        actual_sl = self._get_active_stop_loss(symbol)
        if actual_sl is None:
            raise OperationalExchangeError(
                "SL_UPDATE_NOT_CONFIRMED"
            )

        # Ensure internal pointer tracks the NEW stop order
        try:
            orders = self._get(
                "/fapi/v1/openOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )

            for o in orders:
                if (
                    o.get("type") == "STOP_MARKET"
                    and o.get("reduceOnly") is True
                ):
                    self._active_sl_order_id = o.get("orderId")
                    break
        except Exception:
            raise OperationalExchangeError(
                "SL_UPDATE_ORDER_TRACKING_FAILED"
            )

        # STEP 3 — Only AFTER confirmation, delete old SL
        if old_order_id:
            try:
                self._delete(
                    "/fapi/v1/order",
                    {
                        "symbol": symbol,
                        "orderId": old_order_id,
                        "timestamp": int(time.time() * 1000),
                    },
                )
            except Exception:
                # Not fatal — old SL may already be filled/cancelled
                pass

    def cancel_pending_entries(self):

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

        # Force authoritative REST truth (never trust WS for emergency)
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

        try:
            open_orders = self._get(
                "/fapi/v1/openOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )
        except Exception as e:
            raise OperationalExchangeError(f"FLATTEN_FETCH_ORDERS_FAILED | {e}")

        for o in open_orders:
            if (
                o.get("type") == "STOP_MARKET"
                and o.get("reduceOnly") is True
            ):
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

        # Re-check position via REST after SL deletions
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

        filters = self._symbol_filters.get(symbol)
        if not filters:
            raise OperationalExchangeError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )

        qty = self._quantize_qty(pos.qty, filters["stepSize"])

        if Decimal(str(qty)) % Decimal(str(filters["stepSize"])) != 0:
            raise OperationalExchangeError("FLATTEN_STEP_MISALIGNMENT")

        if qty <= 0:
            return

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

        # Final authoritative REST check
        data = self._get(
            "/fapi/v2/positionRisk",
            {"timestamp": int(time.time() * 1000)},
        )

        still_open = False
        for p in data:
            if abs(float(p["positionAmt"])) > 0.0:
                still_open = True
                break

        if still_open:
            raise OperationalExchangeError(
                f"EMERGENCY_EXIT_FAILED_NOT_FLAT | symbol={symbol}"
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
