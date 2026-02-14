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
from utils.logger import system_logger
from execution.exceptions import OperationalExchangeError, StopAlreadyBreached
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

    def __init__(self):

        if not BASE_URL or not API_KEY or not API_SECRET:
            raise RuntimeError("TESTNET_EXCHANGE_CONFIG_MISSING")

        self.log = system_logger()

        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": API_KEY
        })

        self._symbol_filters = self._load_symbol_filters()

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
            resp = self.session.get(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.log.critical(
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
                self.log.critical(
                    f"REST_POST_FAILED | path={path} | "
                    f"status={resp.status_code} | "
                    f"error={error_detail}"
                )
                raise OperationalExchangeError(
                    f"REST_POST_FAILED | path={path} | {error_detail}"
                )

            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("REST_TIMEOUT")
        except Exception as e:
            raise OperationalExchangeError(f"REST_ERROR | {e}")

    def _delete(self, path: str, params: dict):
        try:
            resp = self.session.delete(
                f"{BASE_URL}{path}",
                params=self._sign(params),
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                error_detail = self._extract_binance_error(resp)
                self.log.critical(
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
            self.log.critical(
                f"REST_DELETE_EXCEPTION | path={path} | error={e}"
            )
            raise OperationalExchangeError(
                f"REST_DELETE_EXCEPTION | path={path} | {e}"
            )

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
        REST-only price stream.
        Deterministic polling.
        No WebSocket usage.
        No silent fallback loops.
        """

        POLL_INTERVAL_SECONDS = 2

        while True:
            try:
                data = self._get(
                    "/fapi/v1/ticker/price",
                    {"timestamp": int(time.time() * 1000)},
                )

                ts = int(time.time() * 1000)

                for row in data:
                    symbol = row.get("symbol")
                    if not symbol or not symbol.endswith("USDT"):
                        continue

                    price = float(row.get("price", 0))
                    if price <= 0:
                        continue

                    yield PriceTick(
                        symbol=symbol,
                        price=price,
                        timestamp=ts,
                    )

            except Exception as e:
                raise OperationalExchangeError(
                    f"REST_PRICE_STREAM_FAILED | {e}"
                )

            time.sleep(POLL_INTERVAL_SECONDS)

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

        data = self._get(
            "/fapi/v2/positionRisk",
            {"timestamp": int(time.time() * 1000)},
        )

        for pos in data:

            self._require_fields(
                pos,
                ["positionAmt", "entryPrice", "symbol"],
                context="get_position"
            )

            qty = float(pos["positionAmt"])
            if abs(qty) > 0.0:

                symbol = pos["symbol"]
                liquidation_price = float(pos.get("liquidationPrice", 0.0))

                orders = self._get(
                    "/fapi/v1/openOrders",
                    {
                        "symbol": symbol,
                        "timestamp": int(time.time() * 1000),
                    },
                )

                stop_loss_price = None
                for o in orders:
                    if (
                        o.get("type") == "STOP_MARKET"
                        and o.get("reduceOnly") is True
                    ):
                        stop_loss_price = float(o.get("stopPrice"))
                        break

                return SimpleNamespace(
                    qty=abs(qty),
                    side="LONG" if qty > 0 else "SHORT",
                    entry_price=float(pos["entryPrice"]),
                    symbol=symbol,
                    stop_loss=stop_loss_price,
                    liquidation_price=liquidation_price,
                )

        return None

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
            time.sleep(1.0)
            pos = self.get_position()
            if pos and pos.symbol == symbol:
                filled_qty = pos.qty
                avg_price = pos.entry_price
            else:
                raise OperationalExchangeError("ENTRY_NOT_FILLED")

        fully_filled = abs(filled_qty - requested_qty) < 1e-12

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

        ticker = self._get(
            "/fapi/v1/ticker/price",
            {"symbol": symbol},
        )

        last_price = float(ticker["price"])

        filters = self._symbol_filters[symbol]
        stop_price = self._quantize_price(
            stop_price,
            filters["tickSize"],
        )
        self.log.info(
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

        self._post(
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


    def update_sl(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        new_stop_price: float,
    ):

        self.log.info(
            f"ADAPTER_UPDATE_SL | "
            f"symbol={symbol} | "
            f"side={side} | "
            f"qty={qty} | "
            f"new_stop_price={new_stop_price}"
        )

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
                self.log.info(
                    f"ADAPTER_DELETE_SL | "
                    f"symbol={symbol} | "
                    f"orderId={o.get('orderId')}"
                )
                self._delete(
                    "/fapi/v1/order",
                    {
                        "symbol": symbol,
                        "orderId": o["orderId"],
                        "timestamp": int(time.time() * 1000),
                    },
                )

        self.place_initial_sl(
            symbol=symbol,
            side=side,
            qty=qty,
            stop_price=new_stop_price,
        )


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

        pos = self.get_position()
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

        time.sleep(0.3)

        pos = self.get_position()
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

        time.sleep(0.5)
        final_pos = self.get_position()

        if final_pos is not None:
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
