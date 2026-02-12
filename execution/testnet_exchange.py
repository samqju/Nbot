# ============================================================
# testnet_exchange.py
# ============================================================
# Binance Futures USDT-M TESTNET Adapter
#
# PURPOSE:
# - Provide truthful exchange state
# - Execute real orders
# - Serve as the ONLY reality boundary
#
# STATUS:
# - Adapter-first ready
# - No skeletons
# - No phase leakage
#
# ============================================================

import os
import time
import hmac
import hashlib
import requests
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List
from config import LEVERAGE, MAX_SPREAD_PCT
from execution.exceptions import OperationalExchangeError, StopAlreadyBreached

# ============================================================
# CONFIG
# ============================================================

BASE_URL = os.getenv("TESTNET_BASE_URL")
API_KEY = os.getenv("TESTNET_API_KEY")
API_SECRET = os.getenv("TESTNET_API_SECRET")

TIMEOUT = 5  # seconds


# ============================================================
# DATA STRUCTURES
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
# ADAPTER
# ============================================================

class TestnetExchange:
    """
    Binance Futures USDT-M Testnet Adapter.

    This adapter is:
    - Truthful
    - Stateless
    - REST-based
    """

    def __init__(self):
        if not BASE_URL or not API_KEY or not API_SECRET:
            raise RuntimeError("TESTNET_EXCHANGE_CONFIG_MISSING")

        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": API_KEY
        })

        # Cache exchange contract filters
        self._symbol_filters = self._load_symbol_filters()

    # --------------------------------------------------------
    # SCHEMA VALIDATION
    # --------------------------------------------------------
    def _require_fields(self, data: dict, required: list, context: str):
        missing = [k for k in required if k not in data]
        if missing:
            raise OperationalExchangeError(
                f"SCHEMA_MISMATCH | context={context} | missing={missing}"
            )

    # --------------------------------------------------------
    # INTERNAL HELPERS
    # --------------------------------------------------------

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
            resp.raise_for_status()
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
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise OperationalExchangeError("REST_TIMEOUT")
        except Exception as e:
            raise OperationalExchangeError(f"REST_ERROR | {e}")

    # --------------------------------------------------------
    # EXCHANGE CONTRACTS
    # --------------------------------------------------------

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
        # Safer quantization to avoid floating precision issues
        precision = str(step)[::-1].find(".")
        quantized = (qty // step) * step
        return round(quantized, precision)

    def _quantize_price(self, price: float, tick: float) -> float:
        return round((price // tick) * tick, 10)

    # ========================================================
    # LIFECYCLE
    # ========================================================

    def connect(self):
        """
        Validate credentials by pinging account endpoint.
        """
        self._get(
            "/fapi/v2/account",
            {"timestamp": int(time.time() * 1000)},
        )

    # ========================================================
    # LEVERAGE ENFORCEMENT (STEP 6.4)
    # ========================================================

    def set_leverage(self, *, symbol: str, leverage: int):
        """
        Explicitly set leverage for a symbol.
        """
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
        """
        Enforce configured leverage across tradable universe.
        """
        for symbol in symbols:
            self.set_leverage(symbol=symbol, leverage=LEVERAGE)

    def disconnect(self):
        """
        REST-based adapter — nothing to close.
        """
        return

    # ========================================================
    # MARKET DATA
    # ========================================================

    def price_stream(self):
        """
        Poll mark price for all USDT symbols every second.
        """
        while True:
            data = self._get(
                "/fapi/v1/premiumIndex",
                {"timestamp": int(time.time() * 1000)},
            )

            ts = int(time.time() * 1000)

            for row in data:
                symbol = row.get("symbol")
                if not symbol or not symbol.endswith("USDT"):
                    continue

                yield PriceTick(
                    symbol=symbol,
                    price=float(row["markPrice"]),
                    timestamp=ts,
                )

            time.sleep(1)

    def get_historical_candles(self, *, symbol: str, interval: str, limit: int):
        """
        Return historical candles for warmup.
        """
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
            (int(c[0]), float(c[4]))  # (open_time, close_price)
            for c in data
        ]

    # --------------------------------------------------------
    # STEP 6.7 — Spread / Illiquidity Guard
    # --------------------------------------------------------

    def get_current_spread_pct(self, *, symbol: str) -> float:
        """
        Return current bid-ask spread percentage.
        """
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
        spread_pct = ((ask - bid) / mid) * 100.0

        return spread_pct

    # ========================================================
    # POSITION TRUTH
    # ========================================================

    def get_position(self):
        """
        Return authoritative position snapshot.

        Contract:
        - None  => exchange is flat
        - object => open position exists
        """

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

                # Fetch open stop-loss order for this symbol
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
    # REALIZED PNL
    # ========================================================

    def get_realized_pnl(self, utc_day):
        """
        Return realized PnL for the given UTC day.
        """
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

    # ========================================================
    # TRADE-LEVEL REALIZED PNL (AUTHORITATIVE)
    # ========================================================

    def get_trade_realized_pnl(
        self,
        *,
        symbol: str,
        since_timestamp: int,
    ) -> dict:
        """
        Return authoritative trade close data:
        {
            "pnl": float,
            "exit_price": float
        }
        """

        trades = self._get(
            "/fapi/v1/userTrades",
            {
                "symbol": symbol,
                "startTime": since_timestamp,
                "timestamp": int(time.time() * 1000),
            },
        )

        pnl = 0.0
        total_exit_qty = 0.0
        weighted_exit_value = 0.0

        for t in trades:
            realized = float(t.get("realizedPnl", 0.0))
            qty = float(t.get("qty", 0.0))
            price = float(t.get("price", 0.0))

            # realizedPnl only non-zero on closing fills
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
    # EXECUTION
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
            # Compute true average fill price
            cum_quote = float(data["cumQuote"])
            if cum_quote > 0:
                avg_price = cum_quote / filled_qty
            else:
                avg_price = price
        else:
            # Fallback: wait briefly and fetch position
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

    def place_initial_sl(self, *, symbol: str, side: str, qty: float, stop_price: float):

        ticker = self._get(
            "/fapi/v1/ticker/price",
            {"symbol": symbol},
        )
        last_price = float(ticker["price"])

        if side == "LONG" and stop_price >= last_price:
            raise StopAlreadyBreached("STOP_ALREADY_BREACHED")

        if side == "SHORT" and stop_price <= last_price:
            raise StopAlreadyBreached("STOP_ALREADY_BREACHED")
        exit_side = "SELL" if side == "LONG" else "BUY"

        filters = self._symbol_filters[symbol]
        stop_price = self._quantize_price(
            stop_price,
            filters["tickSize"],
        )

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
                self._post(
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
        """
        Cancel all open non-reduceOnly orders.
        """
        orders = self._get(
            "/fapi/v1/openOrders",
            {
                "timestamp": int(time.time() * 1000),
            },
        )

        for o in orders:
            if not o.get("reduceOnly"):
                self._post(
                    "/fapi/v1/order",
                    {
                        "symbol": o["symbol"],
                        "orderId": o["orderId"],
                        "timestamp": int(time.time() * 1000),
                    },
                )

    # ------------------------------------------------------
    # Emergency Exit
    # ------------------------------------------------------

    def emergency_exit(self):
        """
        Emergency flatten — market reduceOnly.
        """
        pos = self.get_position()
        if pos is None:
            return

        side = "SELL" if pos.side == "LONG" else "BUY"

        self._post(
            "/fapi/v1/order",
            {
                "symbol": pos.symbol,
                "side": side,
                "type": "MARKET",
                "quantity": pos.qty,
                "reduceOnly": True,
                "timestamp": int(time.time() * 1000),
            },
        )

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    def get_available_balance(self, *, asset: str = "USDT") -> float:
        """
       Fetch available balance from futures account.
        """
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
