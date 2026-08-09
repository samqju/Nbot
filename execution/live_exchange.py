"""Read-only Binance Futures mainnet adapter for Phase 2.2.

This adapter proves authenticated live account connectivity and satisfies the
engine exchange contract, while every account-changing operation is blocked.
It must not be considered a trading-capable adapter.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from types import SimpleNamespace
from urllib.parse import urlencode, urlparse

import requests

from execution.binance_market_client import BinanceMarketClient
from execution.exceptions import OperationalExchangeError
from execution.live_user_stream import LiveUserStream
from execution.live_reconciliation import LiveReconciler
from execution.live_snapshot import LiveSnapshotStore


class LiveExchange:
    READ_ONLY = True
    SUPPORTS_REAL_ORDERS = False

    def __init__(
        self,
        system_log,
        *,
        session=None,
        market_client=None,
        user_stream=None,
    ):
        self.system_log = system_log
        self.base_url = os.getenv("LIVE_BASE_URL", "https://fapi.binance.com").rstrip("/")
        self.api_key = os.getenv("LIVE_API_KEY", "").strip()
        self.api_secret = os.getenv("LIVE_API_SECRET", "").strip()
        self.user_ws_url = os.getenv("LIVE_USER_WS_URL", "wss://fstream.binance.com/ws").strip()

        if (urlparse(self.base_url).hostname or "").lower() != "fapi.binance.com":
            raise RuntimeError("LIVE_REST_HOST_UNEXPECTED")
        if not self.api_key or not self.api_secret:
            raise RuntimeError("LIVE_EXCHANGE_CREDENTIALS_MISSING")

        self.session = session or requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self.market_client = market_client or BinanceMarketClient(system_log=system_log)
        self.user_stream = user_stream or LiveUserStream(
            system_log=system_log,
            session=self.session,
            base_url=self.base_url,
            user_ws_url=self.user_ws_url,
        )
        self._active_sl_order_id = None
        self._connected = False

    def _public_get(self, path, params=None):
        try:
            response = self.session.get(
                f"{self.base_url}{path}", params=params or {}, timeout=15
            )
        except requests.RequestException as exc:
            raise OperationalExchangeError(f"LIVE_PUBLIC_REST_ERROR | {exc}") from exc
        if response.status_code != 200:
            raise OperationalExchangeError(
                f"LIVE_PUBLIC_REST_FAILED | status={response.status_code} | body={response.text[:300]}"
            )
        return response.json()

    def _signed_get(self, path, params=None):
        payload = dict(params or {})
        payload.setdefault("timestamp", int(time.time() * 1000))
        payload.setdefault("recvWindow", 5000)
        query = urlencode(payload)
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        payload["signature"] = signature
        try:
            response = self.session.get(
                f"{self.base_url}{path}", params=payload, timeout=15
            )
        except requests.RequestException as exc:
            raise OperationalExchangeError(f"LIVE_SIGNED_REST_ERROR | {exc}") from exc
        if response.status_code != 200:
            raise OperationalExchangeError(
                f"LIVE_SIGNED_REST_FAILED | path={path} | status={response.status_code} | body={response.text[:300]}"
            )
        return response.json()

    @staticmethod
    def _block_write(operation):
        raise RuntimeError(
            f"LIVE_ADAPTER_READ_ONLY | operation={operation} | real_orders=BLOCKED"
        )

    def capability_report(self):
        return {
            "adapter": type(self).__name__,
            "read_only": self.READ_ONLY,
            "supports_real_orders": self.SUPPORTS_REAL_ORDERS,
            "write_operations": "BLOCKED",
        }

    def connect(self):
        self._public_get("/fapi/v1/ping")
        account = self._signed_get("/fapi/v2/account")
        if not isinstance(account, dict):
            raise OperationalExchangeError("LIVE_ACCOUNT_SCHEMA_INVALID")
        self.user_stream.start()
        if not self.user_stream.wait_ready():
            self.user_stream.stop()
            raise OperationalExchangeError(
                "LIVE_USER_STREAM_READY_TIMEOUT | "
                f"timeout={self.user_stream.ready_timeout_seconds}"
            )
        if not self.user_stream.is_healthy():
            self.user_stream.stop()
            raise OperationalExchangeError(
                "LIVE_USER_STREAM_UNHEALTHY_AT_STARTUP"
            )
        self._connected = True
        self.system_log.info(
            "LIVE_ADAPTER_READ_ONLY_CONNECTED | "
            "auth=SIGNED_REST+USER_STREAM | real_orders=BLOCKED"
        )

    def disconnect(self):
        self.user_stream.stop()
        self._connected = False

    def price_stream(self):
        return self.market_client.price_stream()

    def position_price_stream(self, symbol):
        return self.market_client.position_price_stream(symbol)

    def set_execution_health_monitor(self, monitor):
        attach = getattr(self.market_client, "set_execution_health_monitor", None)
        if callable(attach):
            attach(monitor)

    def get_historical_candles(self, *, symbol, interval, limit):
        return self.market_client.get_historical_candles(
            symbol=symbol, interval=interval, limit=limit
        )

    def get_current_spread_pct(self, *, symbol):
        return self.market_client.get_current_spread_pct(symbol=symbol)

    def get_last_price(self, symbol):
        return self.market_client.get_last_price(symbol)

    def quantize_price(self, symbol, price):
        return self.market_client.quantize_price(symbol, price)

    def is_user_stream_healthy(self):
        return self.user_stream.is_healthy()

    def wait_for_user_stream_ready(self, timeout=None):
        return self.user_stream.wait_ready(timeout)

    def drain_user_stream_events(self, limit=None):
        return self.user_stream.drain_events(limit)

    def list_open_positions(self):
        data = self._signed_get("/fapi/v2/positionRisk")
        positions = []
        for row in data:
            qty_signed = float(row.get("positionAmt", 0.0))
            if qty_signed == 0:
                continue
            positions.append(
                {
                    "symbol": str(row.get("symbol", "")).upper(),
                    "side": "LONG" if qty_signed > 0 else "SHORT",
                    "qty": abs(qty_signed),
                    "entry_price": float(row.get("entryPrice", 0.0)),
                    "mark_price": float(row.get("markPrice", 0.0)),
                    "liquidation_price": float(
                        row.get("liquidationPrice", 0.0)
                    ),
                    "unrealized_pnl": float(
                        row.get("unRealizedProfit", 0.0)
                    ),
                }
            )
        return positions

    def list_open_orders(self, symbol=None):
        params = {}
        if symbol:
            params["symbol"] = str(symbol).upper()
        data = self._signed_get("/fapi/v1/openOrders", params)
        orders = []
        for row in data:
            orders.append(
                {
                    "symbol": str(row.get("symbol", "")).upper(),
                    "order_id": int(row.get("orderId", 0)),
                    "client_order_id": row.get("clientOrderId"),
                    "type": row.get("type"),
                    "side": row.get("side"),
                    "status": row.get("status"),
                    "reduce_only": bool(row.get("reduceOnly", False)),
                    "price": float(row.get("price", 0.0)),
                    "stop_price": float(row.get("stopPrice", 0.0)),
                }
            )
        return orders

    def list_protective_stops(self, symbol=None):
        params = {}
        if symbol:
            params["symbol"] = str(symbol).upper()
        data = self._signed_get("/fapi/v1/openAlgoOrders", params)
        stops = []
        for row in data:
            if row.get("algoType") != "CONDITIONAL":
                continue
            if row.get("orderType") != "STOP_MARKET":
                continue
            if row.get("reduceOnly") is not True:
                continue
            stops.append(
                {
                    "symbol": str(row.get("symbol", "")).upper(),
                    "algo_id": int(row.get("algoId", 0)),
                    "side": row.get("side"),
                    "reduce_only": True,
                    "stop_price": float(row.get("triggerPrice", 0.0)),
                }
            )
        return stops

    def reconcile_read_only(self, *, local_position=None, require_safe=False):
        report = LiveReconciler(
            exchange=self,
            system_log=self.system_log,
        ).run(local_position=local_position)
        if require_safe:
            report.require_safe()
        return report

    def read_only_account_snapshot(self):
        """Return one observation-only view of current live account truth."""
        return {
            "capabilities": self.capability_report(),
            "available_balance_usdt": self.get_available_balance(asset="USDT"),
            "positions": self.list_open_positions(),
            "open_orders": self.list_open_orders(),
            "protective_stops": self.list_protective_stops(),
            "user_stream_healthy": self.is_user_stream_healthy(),
        }

    def export_live_snapshot(
        self,
        *,
        path,
        reconciliation,
        previous_snapshot=None,
    ):
        payload = self.read_only_account_snapshot()
        payload["reconciliation"] = {
            "status": reconciliation.status,
            "issues": list(reconciliation.issues),
        }
        store = LiveSnapshotStore(path)
        drift = store.compare(previous_snapshot, payload)
        payload["drift"] = {
            "status": drift.status,
            "issues": list(drift.issues),
            "balance_delta_usdt": drift.balance_delta_usdt,
        }
        document = store.write(payload)
        self.system_log.info(
            "LIVE_SNAPSHOT_WRITTEN | "
            f"path={store.path} | drift={drift.status} | "
            f"issues={','.join(drift.issues) if drift.issues else 'NONE'} | "
            "mode=READ_ONLY"
        )
        return document

    def get_available_balance(self, *, asset="USDT"):
        data = self._signed_get("/fapi/v2/balance")
        for row in data:
            if row.get("asset") == asset:
                return float(row["availableBalance"])
        raise OperationalExchangeError(f"LIVE_BALANCE_NOT_FOUND | asset={asset}")

    def get_position(self):
        data = self._signed_get("/fapi/v2/positionRisk")
        for row in data:
            qty = float(row.get("positionAmt", 0.0))
            if qty == 0:
                continue
            position = SimpleNamespace(
                qty=abs(qty),
                side="LONG" if qty > 0 else "SHORT",
                entry_price=float(row.get("entryPrice", 0.0)),
                symbol=row.get("symbol"),
                liquidation_price=float(row.get("liquidationPrice", 0.0)),
                stop_loss=None,
            )
            position.stop_loss = self.recover_active_stop_loss(position.symbol)
            return position
        return None

    def get_realized_pnl(self, utc_day=None):
        params = {"incomeType": "REALIZED_PNL", "limit": 1000}
        if utc_day is not None:
            params["startTime"] = int(utc_day.timestamp() * 1000)
        data = self._signed_get("/fapi/v1/income", params)
        return sum(float(row.get("income", 0.0)) for row in data)

    def get_trade_realized_pnl(self, *args, **kwargs):
        return self.get_realized_pnl(kwargs.get("utc_day"))

    def _active_stop_ref(self, symbol):
        data = self._signed_get("/fapi/v1/openAlgoOrders", {"symbol": symbol})
        for row in data:
            if row.get("algoType") != "CONDITIONAL":
                continue
            if row.get("orderType") != "STOP_MARKET":
                continue
            if row.get("reduceOnly") is not True:
                continue
            algo_id = row.get("algoId")
            trigger = row.get("triggerPrice")
            if algo_id is None or trigger is None:
                continue
            return {"algo_id": int(algo_id), "stop_price": float(trigger)}
        return None

    def recover_active_stop_loss(self, symbol):
        ref = self._active_stop_ref(symbol)
        if ref is None:
            return None
        self._active_sl_order_id = ref["algo_id"]
        return ref["stop_price"]

    def get_active_sl_order_id(self):
        return self._active_sl_order_id

    def set_leverage(self, *args, **kwargs):
        self._block_write("set_leverage")

    def enforce_leverage_for_universe(self, symbols):
        self._block_write("enforce_leverage_for_universe")

    def place_entry(self, *args, **kwargs):
        self._block_write("place_entry")

    def query_order_by_client_id(self, *args, **kwargs):
        return None

    def resolve_ambiguous_entry(self, *args, **kwargs):
        self._block_write("resolve_ambiguous_entry")

    def place_initial_sl(self, *args, **kwargs):
        self._block_write("place_initial_sl")

    def update_sl(self, *args, **kwargs):
        self._block_write("update_sl")

    def cancel_pending_entries(self, *args, **kwargs):
        self._block_write("cancel_pending_entries")

    def emergency_exit(self, *args, **kwargs):
        self._block_write("emergency_exit")
