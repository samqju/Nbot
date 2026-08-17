from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlencode

import requests
import websocket

from .execution import (
    AccountSnapshot,
    CloseFill,
    EntryPlan,
    ExchangePosition,
    Fill,
    Quote,
)


LOGGER = logging.getLogger("nbot.v2.testnet")
REQUIRED_CONFIRMATION = "I_ACCEPT_TESTNET_ORDER_EXECUTION"
ARM_FILE_CONTENT = "ARM_TESTNET_TRADING"
MECHANICAL_CANARY_AUTHORITY = "TESTNET_MECHANICAL_CANARY_V1"
MECHANICAL_CANARY_MODEL = "NONE_MECHANICAL_CANARY"
GUARD_STATE_VERSION = "NBOT_V2_TESTNET_GUARD_V1"


class TestnetExchangeError(RuntimeError):
    pass


class AmbiguousExecutionError(TestnetExchangeError):
    """The request may have reached Binance; never blindly resubmit it."""


@dataclass(frozen=True)
class TestnetExchangeConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://demo-fapi.binance.com"
    ws_base_url: str = "wss://demo-fstream.binance.com/ws"
    request_timeout_seconds: float = 5.0
    recv_window_ms: int = 5_000
    user_stream_ready_timeout_seconds: float = 20.0
    arm_file: Path = Path("/var/lib/nbot-execution/TESTNET_TRADING_ARMED")
    guard_state_path: Path = Path("/var/lib/nbot-execution/testnet_trading_guard.json")
    confirmation: str = ""
    max_session_entries: int = 100
    max_entry_notional_usd: float = 1000.0

    @classmethod
    def from_env(cls) -> "TestnetExchangeConfig":
        return cls(
            api_key=os.getenv("TESTNET_API_KEY", "").strip(),
            api_secret=os.getenv("TESTNET_API_SECRET", "").strip(),
            base_url=os.getenv("TESTNET_BASE_URL", "https://demo-fapi.binance.com").strip(),
            ws_base_url=os.getenv("TESTNET_WS_BASE_URL", "wss://demo-fstream.binance.com/ws").strip(),
            request_timeout_seconds=float(os.getenv("TESTNET_REST_TIMEOUT_SECONDS", "5")),
            recv_window_ms=int(os.getenv("TESTNET_RECV_WINDOW_MS", "5000")),
            user_stream_ready_timeout_seconds=float(os.getenv("TESTNET_USER_STREAM_READY_TIMEOUT", "20")),
            arm_file=Path(os.getenv("TESTNET_TRADING_ARM_FILE", "/var/lib/nbot-execution/TESTNET_TRADING_ARMED")),
            guard_state_path=Path(os.getenv("TESTNET_TRADING_GUARD_STATE_PATH", "/var/lib/nbot-execution/testnet_trading_guard.json")),
            confirmation=os.getenv("TESTNET_TRADING_CONFIRMATION", "").strip(),
            max_session_entries=int(os.getenv("TESTNET_MAX_SESSION_ENTRIES", "100")),
            max_entry_notional_usd=float(os.getenv("TESTNET_MAX_ENTRY_NOTIONAL_USD", "1000")),
        )

    def validate(self, *, require_credentials: bool = True) -> None:
        rest_host = (urlparse(self.base_url).hostname or "").lower()
        ws_host = (urlparse(self.ws_base_url).hostname or "").lower()
        if rest_host != "demo-fapi.binance.com":
            raise ValueError(f"TESTNET_REST_HOST_INVALID:{rest_host}")
        if ws_host != "demo-fstream.binance.com":
            raise ValueError(f"TESTNET_WS_HOST_INVALID:{ws_host}")
        if require_credentials and (not self.api_key or not self.api_secret):
            raise ValueError("TESTNET_CREDENTIALS_MISSING")
        if self.request_timeout_seconds <= 0 or self.recv_window_ms <= 0:
            raise ValueError("TESTNET_TIMEOUT_INVALID")
        if self.user_stream_ready_timeout_seconds <= 0:
            raise ValueError("TESTNET_USER_STREAM_TIMEOUT_INVALID")
        if self.max_session_entries <= 0 or self.max_entry_notional_usd <= 0:
            raise ValueError("TESTNET_EXECUTION_LIMIT_INVALID")


class TestnetTradingGuard:
    """Persistent Testnet arming/session guard for order-writing entry actions.

    Entry count is durable across Python restarts. Removing and recreating the
    valid arm file creates a new explicit Testnet session and resets the count.
    A missing/corrupt guard state while already armed fails closed rather than
    silently granting a fresh counter.
    """

    def __init__(self, config: TestnetExchangeConfig):
        self.config = config
        self._lock = threading.Lock()

    @property
    def _state_lock_path(self) -> Path:
        return Path(str(self.config.guard_state_path) + ".lock")

    def _arm_status(self) -> tuple[bool, str, str | None]:
        if self.config.confirmation != REQUIRED_CONFIRMATION:
            return False, "CONFIRMATION_MISSING", None
        if not self.config.arm_file.is_file():
            return False, "ARM_FILE_MISSING", None
        try:
            with self.config.arm_file.open("rb") as handle:
                raw = handle.read()
                stat = os.fstat(handle.fileno())
        except OSError:
            return False, "ARM_FILE_UNREADABLE", None
        try:
            content = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            return False, "ARM_FILE_INVALID", None
        if content != ARM_FILE_CONTENT:
            return False, "ARM_FILE_INVALID", None
        identity = {
            "device": int(stat.st_dev),
            "inode": int(stat.st_ino),
            "mtime_ns": int(stat.st_mtime_ns),
            "ctime_ns": int(stat.st_ctime_ns),
            "size": int(stat.st_size),
            "content": content,
        }
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return True, "ARMED", fingerprint

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "state_version": GUARD_STATE_VERSION,
            "arm_session_fingerprint": None,
            "session_entries": 0,
        }

    def _load_state_locked(self, *, armed: bool) -> dict[str, Any]:
        path = self.config.guard_state_path
        if not path.exists():
            if armed:
                raise TestnetExchangeError("GUARD_STATE_MISSING_WHILE_ARMED")
            state = self._empty_state()
            self._save_state_locked(state)
            return state
        try:
            state = json.loads(path.read_text())
            if state.get("state_version") != GUARD_STATE_VERSION:
                raise ValueError("version")
            entries = state.get("session_entries")
            fingerprint = state.get("arm_session_fingerprint")
            if not isinstance(entries, int) or entries < 0:
                raise ValueError("entries")
            if fingerprint is not None and not isinstance(fingerprint, str):
                raise ValueError("fingerprint")
            return state
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise TestnetExchangeError("GUARD_STATE_INVALID") from exc

    def _save_state_locked(self, state: dict[str, Any]) -> None:
        path = self.config.guard_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        try:
            with temp.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def _report_locked(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
        armed, reason, fingerprint = self._arm_status()
        try:
            state = self._load_state_locked(armed=armed)
        except TestnetExchangeError as exc:
            return ({
                "armed": False,
                "reason": str(exc),
                "session_entries": None,
                "max_session_entries": self.config.max_session_entries,
                "max_entry_notional_usd": self.config.max_entry_notional_usd,
            }, None)
        if armed and state.get("arm_session_fingerprint") != fingerprint:
            state = self._empty_state()
            state["arm_session_fingerprint"] = fingerprint
            self._save_state_locked(state)
        return ({
            "armed": armed,
            "reason": reason,
            "session_entries": int(state["session_entries"]),
            "max_session_entries": self.config.max_session_entries,
            "max_entry_notional_usd": self.config.max_entry_notional_usd,
        }, state)

    def _with_state_lock(self):
        class StateLock:
            def __init__(inner_self, outer):
                inner_self.outer = outer
                inner_self.handle = None

            def __enter__(inner_self):
                outer = inner_self.outer
                outer._state_lock_path.parent.mkdir(parents=True, exist_ok=True)
                inner_self.handle = outer._state_lock_path.open("a+", encoding="utf-8")
                os.chmod(outer._state_lock_path, 0o600)
                import fcntl
                fcntl.flock(inner_self.handle.fileno(), fcntl.LOCK_EX)
                return inner_self

            def __exit__(inner_self, exc_type, exc, tb):
                import fcntl
                fcntl.flock(inner_self.handle.fileno(), fcntl.LOCK_UN)
                inner_self.handle.close()

        return StateLock(self)

    def preflight(self) -> dict[str, Any]:
        with self._lock:
            with self._with_state_lock():
                report, _state = self._report_locked()
                return report

    def authorize_entry(self, *, symbol: str, quantity: float, price: float, position: ExchangePosition | None) -> None:
        with self._lock:
            with self._with_state_lock():
                report, state = self._report_locked()
                if not report["armed"] or state is None:
                    raise TestnetExchangeError(f"TESTNET_TRADING_NOT_ARMED:{report['reason']}")
                if position is not None:
                    raise TestnetExchangeError("TESTNET_ENTRY_BLOCKED_POSITION_EXISTS")
                if not symbol or quantity <= 0 or price <= 0:
                    raise TestnetExchangeError("TESTNET_ENTRY_PARAMETERS_INVALID")
                notional = quantity * price
                if notional > self.config.max_entry_notional_usd + 1e-9:
                    raise TestnetExchangeError(
                        f"TESTNET_ENTRY_NOTIONAL_LIMIT_EXCEEDED:{notional:.8f}>{self.config.max_entry_notional_usd:.8f}"
                    )
                if int(state["session_entries"]) >= self.config.max_session_entries:
                    raise TestnetExchangeError("TESTNET_SESSION_ENTRY_LIMIT_REACHED")
                # Reserve the entry durably before any Binance entry POST can occur.
                # A failed/ambiguous attempt conservatively consumes one session slot.
                state["session_entries"] = int(state["session_entries"]) + 1
                self._save_state_locked(state)


class BinanceTestnetExchange:
    """USD-M Futures Testnet adapter for the V2.7 capital boundary.

    It deliberately contains no candidate selection, model, or research logic.
    REST remains authoritative for position and stop truth. WebSocket user data
    is a health/timeliness channel, never the sole source of capital truth.
    """

    def __init__(self, config: TestnetExchangeConfig, *, logger: logging.Logger | None = None):
        config.validate()
        self.config = config
        self.log = logger or LOGGER
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": config.api_key})
        self.guard = TestnetTradingGuard(config)
        self._filters: dict[str, dict[str, float]] = {}
        self._connected = False
        self._user_stream_healthy = False
        self._user_stream_ready = threading.Event()
        self._user_stream_stop = threading.Event()
        self._user_stream_thread: threading.Thread | None = None
        self._user_ws = None
        self._last_user_event_ms = 0
        self._last_user_event_type: str | None = None
        self._last_algo_update: dict[str, Any] | None = None

    @staticmethod
    def _is_true(value: Any) -> bool:
        return value is True or str(value).lower() == "true"

    @staticmethod
    def _error_detail(response) -> str:
        try:
            payload = response.json()
            return f"code={payload.get('code')} msg={payload.get('msg')}"
        except Exception:
            return f"HTTP_{response.status_code}"

    def _signature(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self.config.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, *, signed: bool = False,
                 api_key_only: bool = False, ambiguous_write: bool = False):
        payload = dict(params or {})
        if signed:
            payload.setdefault("recvWindow", self.config.recv_window_ms)
            payload.setdefault("timestamp", int(time.time() * 1000))
            payload["signature"] = self._signature(payload)
        url = f"{self.config.base_url}{path}"
        try:
            response = self.session.request(method, url, params=payload, timeout=self.config.request_timeout_seconds)
        except requests.exceptions.Timeout as exc:
            if ambiguous_write:
                raise AmbiguousExecutionError(f"AMBIGUOUS_TIMEOUT:{method}:{path}") from exc
            raise TestnetExchangeError(f"REST_TIMEOUT:{method}:{path}") from exc
        except requests.RequestException as exc:
            if ambiguous_write:
                raise AmbiguousExecutionError(f"AMBIGUOUS_NETWORK:{method}:{path}:{exc}") from exc
            raise TestnetExchangeError(f"REST_NETWORK:{method}:{path}:{exc}") from exc

        if response.status_code != 200:
            detail = self._error_detail(response)
            if ambiguous_write and response.status_code == 503 and "unknown" in detail.lower():
                raise AmbiguousExecutionError(f"AMBIGUOUS_503:{path}:{detail}")
            raise TestnetExchangeError(f"REST_FAILED:{method}:{path}:{response.status_code}:{detail}")
        try:
            return response.json()
        except ValueError as exc:
            if response.text.strip() == "":
                return {}
            raise TestnetExchangeError(f"REST_JSON_INVALID:{method}:{path}") from exc

    def _public_get(self, path: str, params: dict[str, Any] | None = None):
        return self._request("GET", path, params)

    def _signed_get(self, path: str, params: dict[str, Any] | None = None):
        return self._request("GET", path, params, signed=True)

    def _signed_post(self, path: str, params: dict[str, Any], *, ambiguous: bool = False):
        return self._request("POST", path, params, signed=True, ambiguous_write=ambiguous)

    def _signed_delete(self, path: str, params: dict[str, Any]):
        return self._request("DELETE", path, params, signed=True)

    def _api_key_request(self, method: str, path: str):
        return self._request(method, path, {}, api_key_only=True)

    def _load_filters(self) -> None:
        data = self._public_get("/fapi/v1/exchangeInfo")
        filters: dict[str, dict[str, float]] = {}
        for row in data.get("symbols", []):
            symbol = str(row.get("symbol") or "")
            by_type = {item.get("filterType"): item for item in row.get("filters", [])}
            market = by_type.get("MARKET_LOT_SIZE") or by_type.get("LOT_SIZE")
            lot = by_type.get("LOT_SIZE") or market
            price = by_type.get("PRICE_FILTER")
            if not symbol or not market or not lot or not price:
                continue
            filters[symbol] = {
                "market_step": float(market["stepSize"]),
                "market_min": float(market["minQty"]),
                "market_max": float(market["maxQty"]),
                "lot_step": float(lot["stepSize"]),
                "tick": float(price["tickSize"]),
            }
        if not filters:
            raise TestnetExchangeError("TESTNET_SYMBOL_FILTERS_EMPTY")
        self._filters = filters

    @staticmethod
    def _quantize_down(value: float, step: float) -> float:
        value_d = Decimal(str(value))
        step_d = Decimal(str(step))
        if step_d <= 0:
            raise TestnetExchangeError("QUANTIZATION_STEP_INVALID")
        quantized = (value_d // step_d) * step_d
        return float(quantized.quantize(step_d, rounding=ROUND_DOWN))

    def _quantity(self, symbol: str, quantity: float) -> float:
        f = self._filters.get(symbol)
        if f is None:
            raise TestnetExchangeError(f"SYMBOL_FILTERS_MISSING:{symbol}")
        qty = self._quantize_down(quantity, f["market_step"])
        if qty < f["market_min"] or qty > f["market_max"]:
            raise TestnetExchangeError(f"MARKET_QUANTITY_OUT_OF_RANGE:{symbol}:{qty}")
        return qty

    def _stop_price(self, symbol: str, price: float) -> float:
        f = self._filters.get(symbol)
        if f is None:
            raise TestnetExchangeError(f"SYMBOL_FILTERS_MISSING:{symbol}")
        return self._quantize_down(price, f["tick"])

    def connect(self) -> None:
        self._public_get("/fapi/v1/ping")
        self._signed_get("/fapi/v3/balance")
        self._load_filters()
        self._start_user_stream()
        if not self._user_stream_ready.wait(self.config.user_stream_ready_timeout_seconds):
            raise TestnetExchangeError("TESTNET_USER_STREAM_READY_TIMEOUT")
        if not self._user_stream_healthy:
            raise TestnetExchangeError("TESTNET_USER_STREAM_UNHEALTHY_AT_STARTUP")
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False
        self._user_stream_stop.set()
        ws = self._user_ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def is_healthy(self) -> bool:
        return bool(self._connected and self._user_stream_healthy and self._user_stream_ready.is_set())

    def _start_user_stream(self) -> None:
        if self._user_stream_thread and self._user_stream_thread.is_alive():
            return
        self._user_stream_stop.clear()
        self._user_stream_ready.clear()
        self._user_stream_healthy = False

        def runner() -> None:
            while not self._user_stream_stop.is_set():
                ws = None
                try:
                    data = self._api_key_request("POST", "/fapi/v1/listenKey")
                    listen_key = str(data.get("listenKey") or "")
                    if not listen_key:
                        raise TestnetExchangeError("LISTEN_KEY_MISSING")
                    ws_url = f"{self.config.ws_base_url.rstrip('/')}/{listen_key}"
                    ws = websocket.create_connection(ws_url, timeout=self.config.request_timeout_seconds)
                    ws.settimeout(60)
                    self._user_ws = ws
                    self._user_stream_healthy = True
                    self._user_stream_ready.set()
                    self._last_user_event_ms = int(time.time() * 1000)

                    keepalive_stop = threading.Event()

                    def keepalive() -> None:
                        while not keepalive_stop.wait(30 * 60):
                            if self._user_stream_stop.is_set():
                                break
                            try:
                                self._api_key_request("PUT", "/fapi/v1/listenKey")
                            except Exception as exc:
                                self.log.warning("TESTNET_USER_STREAM_KEEPALIVE_FAILED %s", exc)
                                break

                    threading.Thread(target=keepalive, daemon=True).start()
                    while not self._user_stream_stop.is_set():
                        try:
                            message = ws.recv()
                        except websocket.WebSocketTimeoutException:
                            ws.ping()
                            continue
                        if not message:
                            raise TestnetExchangeError("USER_STREAM_CLOSED")
                        event = json.loads(message)
                        if not isinstance(event, dict):
                            continue
                        self._last_user_event_ms = int(time.time() * 1000)
                        self._last_user_event_type = str(event.get("e") or "") or None
                        if event.get("e") == "ALGO_UPDATE":
                            self._last_algo_update = event
                    keepalive_stop.set()
                except Exception as exc:
                    self._user_stream_healthy = False
                    self._user_stream_ready.clear()
                    if self._user_stream_stop.is_set():
                        break
                    self.log.warning("TESTNET_USER_STREAM_RESTARTING %s", exc)
                    if not self._user_stream_stop.wait(5):
                        continue
                finally:
                    if ws is not None:
                        try:
                            ws.close()
                        except Exception:
                            pass
            self._user_stream_healthy = False
            self._user_stream_ready.clear()

        self._user_stream_thread = threading.Thread(target=runner, daemon=True, name="nbot-v2-testnet-user-stream")
        self._user_stream_thread.start()

    def quote(self, symbol: str) -> Quote:
        data = self._public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        bid = float(data.get("bidPrice", 0) or 0)
        ask = float(data.get("askPrice", 0) or 0)
        if bid <= 0 or ask <= bid:
            raise TestnetExchangeError(f"TESTNET_QUOTE_INVALID:{symbol}")
        timestamp_ms = int(data.get("time") or int(time.time() * 1000))
        return Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)

    def account_snapshot(self) -> AccountSnapshot:
        rows = self._signed_get("/fapi/v3/balance")
        for row in rows:
            if row.get("asset") == "USDT":
                value = float(row.get("availableBalance", 0) or 0)
                if value < 0:
                    raise TestnetExchangeError("TESTNET_AVAILABLE_BALANCE_INVALID")
                return AccountSnapshot(available_balance_usd=value)
        raise TestnetExchangeError("TESTNET_USDT_BALANCE_MISSING")

    def position_snapshot(self) -> ExchangePosition | None:
        rows = self._signed_get("/fapi/v3/positionRisk")
        positions = []
        for row in rows:
            qty = float(row.get("positionAmt", 0) or 0)
            if abs(qty) <= 0:
                continue
            position_side = str(row.get("positionSide") or "BOTH").upper()
            if position_side != "BOTH":
                raise TestnetExchangeError("TESTNET_HEDGE_MODE_UNSUPPORTED")
            positions.append(
                ExchangePosition(
                    symbol=str(row["symbol"]),
                    side="LONG" if qty > 0 else "SHORT",
                    quantity=abs(qty),
                    entry_price=float(row.get("entryPrice", 0) or 0),
                )
            )
        if len(positions) > 1:
            raise TestnetExchangeError("TESTNET_MULTIPLE_POSITIONS_DETECTED")
        return positions[0] if positions else None

    def validate_protective_stop(self, symbol: str, side: str, stop_price: float) -> bool:
        if side not in {"LONG", "SHORT"} or not math.isfinite(stop_price) or stop_price <= 0:
            return False
        stop = self._stop_price(symbol, stop_price)
        q = self.quote(symbol)
        last = q.mid
        return stop < last if side == "LONG" else stop > last

    def set_leverage(self, symbol: str, leverage: int) -> None:
        gate = self.guard.preflight()
        if not gate["armed"]:
            raise TestnetExchangeError(f"TESTNET_TRADING_NOT_ARMED:{gate['reason']}")
        data = self._signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": int(leverage)})
        if int(data.get("leverage", 0) or 0) != int(leverage):
            raise TestnetExchangeError("TESTNET_LEVERAGE_NOT_CONFIRMED")

    def _query_order(self, symbol: str, client_order_id: str):
        try:
            return self._signed_get("/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_order_id})
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise

    def _fill_from_order(self, order: dict[str, Any], fallback_price: float, requested_qty: float) -> Fill | None:
        executed = float(order.get("executedQty", 0) or 0)
        if executed <= 0:
            return None
        avg = float(order.get("avgPrice", 0) or 0)
        if avg <= 0:
            cum_quote = float(order.get("cumQuote", 0) or 0)
            avg = cum_quote / executed if cum_quote > 0 else fallback_price
        return Fill(
            price=avg,
            quantity=executed,
            order_id=str(order.get("orderId") or "UNKNOWN"),
            client_order_id=str(order.get("clientOrderId") or "UNKNOWN"),
            timestamp_ms=int(order.get("updateTime") or order.get("time") or int(time.time() * 1000)),
        )

    def _resolve_entry(self, *, symbol: str, side: str, client_order_id: str, requested_qty: float,
                       fallback_price: float, timeout_seconds: float = 10.0) -> Fill:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            order = None
            try:
                order = self._query_order(symbol, client_order_id)
            except Exception:
                pass
            position = None
            try:
                position = self.position_snapshot()
            except Exception:
                pass
            if order is not None:
                status = str(order.get("status") or "").upper()
                fill = self._fill_from_order(order, fallback_price, requested_qty)
                if status == "FILLED" and fill is not None and position is not None and position.symbol == symbol:
                    return fill
                if status in {"CANCELED", "EXPIRED", "REJECTED"} and position is None:
                    raise TestnetExchangeError("TESTNET_ENTRY_NOT_FILLED")
            if position is not None and position.symbol == symbol:
                # Unknown order result + real position is unsafe because no stop
                # is confirmed yet. Flatten before returning control.
                self._flatten_unprotected(position, reason="AMBIGUOUS_ENTRY")
                raise TestnetExchangeError("TESTNET_AMBIGUOUS_ENTRY_EMERGENCY_FLATTENED")
            time.sleep(0.25)
        raise TestnetExchangeError("TESTNET_ENTRY_RESOLUTION_TIMEOUT")

    def open_market(self, plan: EntryPlan, *, client_order_id: str) -> Fill:
        quantity = self._quantity(plan.symbol, plan.quantity)
        self.guard.authorize_entry(
            symbol=plan.symbol,
            quantity=quantity,
            price=plan.expected_entry_price,
            position=self.position_snapshot(),
        )
        params = {
            "symbol": plan.symbol,
            "side": "BUY" if plan.side == "LONG" else "SELL",
            "type": "MARKET",
            "quantity": quantity,
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        try:
            order = self._signed_post("/fapi/v1/order", params, ambiguous=True)
        except AmbiguousExecutionError:
            return self._resolve_entry(
                symbol=plan.symbol,
                side=plan.side,
                client_order_id=client_order_id,
                requested_qty=quantity,
                fallback_price=plan.expected_entry_price,
            )
        fill = self._fill_from_order(order, plan.expected_entry_price, quantity)
        if fill is None or str(order.get("status") or "").upper() != "FILLED":
            return self._resolve_entry(
                symbol=plan.symbol,
                side=plan.side,
                client_order_id=client_order_id,
                requested_qty=quantity,
                fallback_price=plan.expected_entry_price,
            )
        position = self.position_snapshot()
        if position is None or position.symbol != plan.symbol or position.side != plan.side:
            raise TestnetExchangeError("TESTNET_ENTRY_NOT_CONFIRMED_BY_POSITION")
        return fill

    def _active_stops(self, symbol: str) -> list[dict[str, Any]]:
        rows = self._signed_get("/fapi/v1/openAlgoOrders", {"symbol": symbol})
        result = []
        for row in rows:
            if (
                str(row.get("algoType") or "").upper() == "CONDITIONAL"
                and str(row.get("orderType") or row.get("type") or "").upper() == "STOP_MARKET"
                and self._is_true(row.get("reduceOnly"))
            ):
                result.append(row)
        return result

    def _cancel_algo(self, symbol: str, algo_id: int) -> None:
        self._signed_delete("/fapi/v1/algoOrder", {"symbol": symbol, "algoId": int(algo_id)})

    def _place_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> dict[str, Any]:
        qty = self._quantity(symbol, quantity)
        stop = self._stop_price(symbol, stop_price)
        if not self.validate_protective_stop(symbol, side, stop):
            raise TestnetExchangeError("TESTNET_STOP_ALREADY_BREACHED_OR_INVALID")
        client_algo_id = f"NBV28SL-{uuid.uuid4().hex[:20]}"
        data = self._signed_post(
            "/fapi/v1/algoOrder",
            {
                "algoType": "CONDITIONAL",
                "symbol": symbol,
                "side": "SELL" if side == "LONG" else "BUY",
                "type": "STOP_MARKET",
                "quantity": qty,
                "triggerPrice": stop,
                "workingType": "CONTRACT_PRICE",
                "priceProtect": "true",
                "reduceOnly": "true",
                "clientAlgoId": client_algo_id,
            },
        )
        algo_id = data.get("algoId")
        if algo_id is None:
            raise TestnetExchangeError("TESTNET_STOP_ALGO_ID_MISSING")
        for row in self._active_stops(symbol):
            if int(row.get("algoId", -1)) == int(algo_id):
                return row
        raise TestnetExchangeError("TESTNET_STOP_PLACEMENT_NOT_CONFIRMED")

    def ensure_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> None:
        expected = self._stop_price(symbol, stop_price)
        tick = self._filters[symbol]["tick"]
        existing = self._active_stops(symbol)
        for row in existing:
            trigger = float(row.get("triggerPrice", 0) or 0)
            if abs(trigger - expected) <= tick / 2 + 1e-12:
                return
        self._place_stop(symbol, side, quantity, expected)

    def replace_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> None:
        old = self._active_stops(symbol)
        new = self._place_stop(symbol, side, quantity, stop_price)
        new_id = int(new["algoId"])
        for row in old:
            old_id = row.get("algoId")
            if old_id is None or int(old_id) == new_id:
                continue
            try:
                self._cancel_algo(symbol, int(old_id))
            except Exception as exc:
                self.log.warning("TESTNET_OLD_STOP_CANCEL_FAILED symbol=%s algo_id=%s error=%s", symbol, old_id, exc)

    def _flatten_unprotected(self, position: ExchangePosition, *, reason: str) -> CloseFill:
        return self._close_existing(position, reason=reason)

    def _close_existing(self, position: ExchangePosition, *, reason: str) -> CloseFill:
        quantity = self._quantity(position.symbol, position.quantity)
        client_order_id = f"NBV28C-{uuid.uuid4().hex[:20]}"
        params = {
            "symbol": position.symbol,
            "side": "SELL" if position.side == "LONG" else "BUY",
            "type": "MARKET",
            "quantity": quantity,
            "reduceOnly": "true",
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        order = None
        try:
            order = self._signed_post("/fapi/v1/order", params, ambiguous=True)
        except AmbiguousExecutionError:
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if self.position_snapshot() is None:
                    order = self._query_order(position.symbol, client_order_id)
                    break
                time.sleep(0.25)
            if self.position_snapshot() is not None:
                raise TestnetExchangeError("TESTNET_CLOSE_AMBIGUOUS_POSITION_STILL_OPEN")
        if self.position_snapshot() is not None:
            raise TestnetExchangeError("TESTNET_CLOSE_NOT_CONFIRMED_FLAT")
        try:
            for row in self._active_stops(position.symbol):
                if row.get("algoId") is not None:
                    self._cancel_algo(position.symbol, int(row["algoId"]))
        except Exception as exc:
            self.log.warning("TESTNET_ORPHAN_STOP_CLEANUP_FAILED %s", exc)
        fallback = self.quote(position.symbol).mid
        fill = self._fill_from_order(order or {}, fallback, quantity)
        price = fill.price if fill else fallback
        timestamp_ms = fill.timestamp_ms if fill else int(time.time() * 1000)
        return CloseFill(price=price, timestamp_ms=timestamp_ms, reason=reason)

    def close_position(self, symbol: str, side: str, *, reason: str) -> CloseFill:
        position = self.position_snapshot()
        if position is None:
            return CloseFill(price=self.quote(symbol).mid, timestamp_ms=int(time.time() * 1000), reason=f"{reason}_ALREADY_FLAT")
        if position.symbol != symbol or position.side != side:
            raise TestnetExchangeError("TESTNET_CLOSE_POSITION_MISMATCH")
        return self._close_existing(position, reason=reason)

    def position_price_stream(self, symbol: str):
        if symbol not in self._filters:
            raise TestnetExchangeError(f"SYMBOL_FILTERS_MISSING:{symbol}")
        url = f"{self.config.ws_base_url.rstrip('/')}/{symbol.lower()}@ticker"
        while self._connected:
            ws = None
            try:
                ws = websocket.create_connection(url, timeout=self.config.request_timeout_seconds)
                ws.settimeout(60)
                while self._connected:
                    try:
                        message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        ws.ping()
                        continue
                    event = json.loads(message)
                    if isinstance(event, dict) and isinstance(event.get("data"), dict):
                        event = event["data"]
                    if not isinstance(event, dict) or str(event.get("s") or "").upper() != symbol:
                        continue
                    price = float(event.get("c", 0) or 0)
                    if price > 0:
                        yield symbol, price, int(event.get("E") or int(time.time() * 1000))
            except Exception as exc:
                self.log.warning("TESTNET_POSITION_STREAM_RESTARTING symbol=%s error=%s", symbol, exc)
                time.sleep(1)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

    def preflight_report(self, symbol: str = "BTCUSDT") -> dict[str, Any]:
        position = self.position_snapshot()
        quote = self.quote(symbol)
        balance = self.account_snapshot()
        return {
            "environment": "TESTNET",
            "rest_host": (urlparse(self.config.base_url).hostname or ""),
            "ws_host": (urlparse(self.config.ws_base_url).hostname or ""),
            "credentials_loaded": bool(self.config.api_key and self.config.api_secret),
            "user_stream_healthy": self._user_stream_healthy,
            "last_user_event_type": self._last_user_event_type,
            "last_algo_update_seen": self._last_algo_update is not None,
            "available_balance_usd": balance.available_balance_usd,
            "position": None if position is None else {
                "symbol": position.symbol,
                "side": position.side,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
            },
            "preflight_symbol": symbol,
            "bid": quote.bid,
            "ask": quote.ask,
            "spread_pct": quote.spread_pct,
            "active_protective_stops": 0 if position is None else len(self._active_stops(position.symbol)),
            "trading_gate": self.guard.preflight(),
            "real_money": False,
            "research_evidence": False,
        }
