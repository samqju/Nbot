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

from execution.exceptions import OperationalExchangeError


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
            qty = float(pos["positionAmt"])
            if abs(qty) > 0.0:
                symbol = pos["symbol"]

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
    # EXECUTION
    # ========================================================

    def place_entry(self, *, side: str, notional_usd: float, price: float) -> EntryAck:
        if side not in ("LONG", "SHORT"):
            raise OperationalExchangeError("INVALID_SIDE")

        order_side = "BUY" if side == "LONG" else "SELL"
        qty = notional_usd / price

        data = self._post(
            "/fapi/v1/order",
            {
                "symbol": "BTCUSDT",
                "side": order_side,
                "type": "MARKET",
                "quantity": qty,
                "timestamp": int(time.time() * 1000),
            },
        )

        filled_qty = float(data.get("executedQty", 0.0))
        avg_price = float(data.get("avgPrice", 0.0))

        if filled_qty <= 0 or avg_price <= 0:
            raise OperationalExchangeError("ENTRY_FILL_INVALID")

        return EntryAck(filled_qty, avg_price)

    def place_initial_sl(self, *, side: str, qty: float, stop_price: float):
        exit_side = "SELL" if side == "LONG" else "BUY"

        self._post(
            "/fapi/v1/order",
            {
                "symbol": "BTCUSDT",
                "side": exit_side,
                "type": "STOP_MARKET",
                "stopPrice": stop_price,
                "quantity": qty,
                "reduceOnly": "true",
                "timestamp": int(time.time() * 1000),
            },
        )

    def update_sl(self, *, side: str, qty: float, new_stop_price: float):
        orders = self._get(
            "/fapi/v1/openOrders",
            {
                "symbol": "BTCUSDT",
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
                        "symbol": "BTCUSDT",
                        "orderId": o["orderId"],
                        "timestamp": int(time.time() * 1000),
                    },
                )

        self.place_initial_sl(
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
                "reduceOnly": "true",
                "timestamp": int(time.time() * 1000),
            },
        )
