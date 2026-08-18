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
    ProtectiveStopRef,
    Quote,
)


LOGGER = logging.getLogger("nbot.v2.testnet")
REQUIRED_CONFIRMATION = "I_ACCEPT_TESTNET_ORDER_EXECUTION"
ARM_FILE_CONTENT = "ARM_TESTNET_TRADING"
MECHANICAL_CANARY_AUTHORITY = "TESTNET_MECHANICAL_CANARY_V1"
MECHANICAL_CANARY_MODEL = "NONE_MECHANICAL_CANARY"
GUARD_STATE_VERSION = "NBOT_V2_TESTNET_GUARD_V1"
USER_TRADES_MAX_WINDOW_MS = 7 * 24 * 60 * 60 * 1000
CLOSE_SETTLEMENT_RETRIES = 5
CLOSE_SETTLEMENT_RETRY_SECONDS = 0.5


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
        # Balance is an entry/margin prerequisite, not a reconciliation
        # prerequisite. V1 capital-first startup reconciled position truth
        # independently of available balance. The worker's prepare() performs
        # an authenticated position read immediately after connect, while
        # account_snapshot() remains mandatory before any new entry.
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

    def protective_stop_snapshot(self, symbol: str) -> ProtectiveStopRef | None:
        active = self._active_stops(symbol)
        if not active:
            return None
        if len(active) > 1:
            raise TestnetExchangeError(f"TESTNET_MULTIPLE_PROTECTIVE_STOPS_DETECTED:{symbol}:{len(active)}")
        return self._stop_ref(active[0])

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

    def _query_order_by_id(self, symbol: str, order_id: str):
        try:
            return self._signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": int(order_id)})
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise

    @staticmethod
    def _stop_ref(row: dict[str, Any], *, fallback_client_id: str | None = None) -> ProtectiveStopRef:
        trigger = float(row.get("triggerPrice", 0) or 0)
        if trigger <= 0:
            raise TestnetExchangeError("TESTNET_STOP_TRIGGER_PRICE_MISSING")
        algo_id = row.get("algoId")
        client = str(row.get("clientAlgoId") or fallback_client_id or "").strip() or None
        return ProtectiveStopRef(
            trigger_price=trigger,
            algo_id=None if algo_id is None else str(algo_id),
            client_algo_id=client,
        )

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

    def recover_inflight_entry(self, plan: EntryPlan, *, client_order_id: str) -> Fill | None:
        """Resolve a persisted pre-order journal without submitting a new entry.

        A known terminal non-fill may be cleared. Any still-ambiguous state
        remains fail-closed; a real exchange position is never guessed away.
        """
        deadline = time.monotonic() + 10.0
        last_status = "UNKNOWN"
        last_position = None
        while time.monotonic() < deadline:
            order = self._query_order(plan.symbol, client_order_id)
            position = self.position_snapshot()
            last_position = position
            if order is None:
                last_status = "MISSING"
            if order is not None:
                status = str(order.get("status") or "").upper()
                last_status = status or "UNKNOWN"
                fill = self._fill_from_order(order, plan.expected_entry_price, plan.quantity)
                if status == "FILLED" and fill is not None:
                    if position is not None and (position.symbol != plan.symbol or position.side != plan.side):
                        raise TestnetExchangeError("TESTNET_INFLIGHT_ENTRY_POSITION_MISMATCH")
                    return fill
                if status in {"CANCELED", "EXPIRED", "REJECTED"} and position is None:
                    return None
            if position is not None:
                # Position exists but the exact entry order is not yet proven.
                # Never adopt it from symbol/side coincidence alone.
                if position.symbol != plan.symbol or position.side != plan.side:
                    raise TestnetExchangeError("TESTNET_INFLIGHT_ENTRY_POSITION_MISMATCH")
            time.sleep(0.25)
        # _query_order returns None only for Binance's authoritative
        # "order does not exist" response; transport/API failures propagate.
        # After a bounded recheck window, exact-order missing + exchange flat
        # proves that a crash occurred before the entry reached Binance.
        if last_status == "MISSING" and last_position is None:
            return None
        raise TestnetExchangeError(f"TESTNET_INFLIGHT_ENTRY_UNRESOLVED:{last_status}")

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

    def _query_algo_order(self, *, algo_id: str | None = None, client_algo_id: str | None = None):
        if algo_id is None and not client_algo_id:
            raise TestnetExchangeError("TESTNET_ALGO_QUERY_ID_MISSING")
        params: dict[str, Any] = {}
        if algo_id is not None:
            params["algoId"] = int(algo_id)
        else:
            params["clientAlgoId"] = str(client_algo_id)
        try:
            return self._signed_get("/fapi/v1/algoOrder", params)
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise

    def _resolve_ambiguous_stop(self, symbol: str, client_algo_id: str, *, timeout_seconds: float = 10.0) -> ProtectiveStopRef:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                row = self._query_algo_order(client_algo_id=client_algo_id)
                if row is not None:
                    status = str(row.get("algoStatus") or "").upper()
                    if status == "NEW":
                        return self._stop_ref(row, fallback_client_id=client_algo_id)
                    if status in {"TRIGGERED", "FINISHED"}:
                        raise TestnetExchangeError("TESTNET_STOP_TRIGGERED_DURING_AMBIGUOUS_PLACEMENT")
                    if status in {"CANCELED", "EXPIRED", "REJECTED"}:
                        raise TestnetExchangeError(f"TESTNET_STOP_NOT_ACTIVE:{status}")
            except TestnetExchangeError as exc:
                if "TESTNET_STOP_TRIGGERED_DURING_AMBIGUOUS_PLACEMENT" in str(exc) or "TESTNET_STOP_NOT_ACTIVE" in str(exc):
                    raise
            for active in self._active_stops(symbol):
                if str(active.get("clientAlgoId") or "") == client_algo_id:
                    return self._stop_ref(active, fallback_client_id=client_algo_id)
            time.sleep(0.25)
        raise TestnetExchangeError("TESTNET_AMBIGUOUS_STOP_RESOLUTION_TIMEOUT")

    def _place_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> ProtectiveStopRef:
        qty = self._quantity(symbol, quantity)
        stop = self._stop_price(symbol, stop_price)
        if not self.validate_protective_stop(symbol, side, stop):
            raise TestnetExchangeError("TESTNET_STOP_ALREADY_BREACHED_OR_INVALID")
        client_algo_id = f"NBV28SL-{uuid.uuid4().hex[:20]}"
        params = {
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
        }
        try:
            data = self._signed_post("/fapi/v1/algoOrder", params, ambiguous=True)
        except AmbiguousExecutionError:
            return self._resolve_ambiguous_stop(symbol, client_algo_id)
        algo_id = data.get("algoId")
        if algo_id is None:
            # The write returned, but without a usable identifier. Recover by
            # the deterministic clientAlgoId rather than submitting again.
            return self._resolve_ambiguous_stop(symbol, client_algo_id)
        for row in self._active_stops(symbol):
            if int(row.get("algoId", -1)) == int(algo_id):
                return self._stop_ref(row, fallback_client_id=client_algo_id)
        recovered = self._query_algo_order(algo_id=str(algo_id))
        if recovered is not None and str(recovered.get("algoStatus") or "").upper() == "NEW":
            return self._stop_ref(recovered, fallback_client_id=client_algo_id)
        raise TestnetExchangeError("TESTNET_STOP_PLACEMENT_NOT_CONFIRMED")

    def _prune_protective_stops(self, symbol: str, keep_algo_id: str | None) -> None:
        keep = None if keep_algo_id is None else int(keep_algo_id)
        for row in self._active_stops(symbol):
            algo_id = row.get("algoId")
            if algo_id is None or (keep is not None and int(algo_id) == keep):
                continue
            try:
                self._cancel_algo(symbol, int(algo_id))
            except Exception as exc:
                # A DELETE timeout can itself be ambiguous. Verify exchange
                # truth instead of assuming the cancellation failed.
                remaining = {int(r["algoId"]) for r in self._active_stops(symbol) if r.get("algoId") is not None}
                if int(algo_id) in remaining:
                    raise TestnetExchangeError(f"TESTNET_OLD_STOP_CANCEL_UNRESOLVED:{algo_id}:{exc}") from exc
        remaining = [r for r in self._active_stops(symbol) if r.get("algoId") is not None]
        if keep is None:
            if remaining:
                raise TestnetExchangeError("TESTNET_ORPHAN_PROTECTIVE_STOP_REMAINS")
            return
        kept = [r for r in remaining if int(r["algoId"]) == keep]
        extras = [r for r in remaining if int(r["algoId"]) != keep]
        if len(kept) != 1 or extras:
            raise TestnetExchangeError("TESTNET_PROTECTIVE_STOP_SET_NOT_CANONICAL")

    def ensure_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> ProtectiveStopRef:
        expected = self._stop_price(symbol, stop_price)
        tick = self._filters[symbol]["tick"]
        existing = self._active_stops(symbol)
        ref = None
        for row in existing:
            trigger = float(row.get("triggerPrice", 0) or 0)
            if abs(trigger - expected) <= tick / 2 + 1e-12:
                ref = self._stop_ref(row)
                break
        if ref is None:
            ref = self._place_stop(symbol, side, quantity, expected)
        self._prune_protective_stops(symbol, ref.algo_id)
        return ref

    def replace_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> ProtectiveStopRef:
        # Preserve V1's capital-first invariant: establish and verify the new
        # stop before removing any existing protection.
        new = self._place_stop(symbol, side, quantity, stop_price)
        self._prune_protective_stops(symbol, new.algo_id)
        return new

    def _user_trades_since(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        if start_ms <= 0 or end_ms < start_ms:
            raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_RANGE_INVALID")
        rows: dict[str, dict[str, Any]] = {}
        cursor = int(start_ms)
        while cursor <= end_ms:
            window_end = min(end_ms, cursor + USER_TRADES_MAX_WINDOW_MS - 1)
            batch = self._signed_get(
                "/fapi/v1/userTrades",
                {"symbol": symbol, "startTime": cursor, "endTime": window_end, "limit": 1000},
            )
            if len(batch) >= 1000:
                raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_WINDOW_TRUNCATED")
            for row in batch:
                key = str(row.get("id") or f"{row.get('orderId')}:{row.get('time')}:{row.get('qty')}:{row.get('price')}")
                rows[key] = row
            cursor = window_end + 1
        return sorted(rows.values(), key=lambda row: (int(row.get("time", 0) or 0), int(row.get("id", 0) or 0)))

    def _all_algo_orders_between(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        if start_ms <= 0 or end_ms < start_ms:
            raise TestnetExchangeError("TESTNET_ALGO_HISTORY_RANGE_INVALID")
        rows: dict[str, dict[str, Any]] = {}
        cursor = int(start_ms)
        while cursor <= end_ms:
            window_end = min(end_ms, cursor + USER_TRADES_MAX_WINDOW_MS - 1)
            batch = self._signed_get(
                "/fapi/v1/allAlgoOrders",
                {"symbol": symbol, "startTime": cursor, "endTime": window_end, "limit": 1000},
            )
            if len(batch) >= 1000:
                raise TestnetExchangeError("TESTNET_ALGO_HISTORY_WINDOW_TRUNCATED")
            for row in batch:
                key = str(row.get("algoId") or row.get("clientAlgoId") or "")
                if key:
                    rows[key] = row
            cursor = window_end + 1
        return sorted(rows.values(), key=lambda row: (int(row.get("createTime", 0) or 0), int(row.get("algoId", 0) or 0)))

    def _all_orders_between(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        if start_ms <= 0 or end_ms < start_ms:
            raise TestnetExchangeError("TESTNET_ORDER_HISTORY_RANGE_INVALID")
        rows: dict[str, dict[str, Any]] = {}
        cursor = int(start_ms)
        while cursor <= end_ms:
            window_end = min(end_ms, cursor + USER_TRADES_MAX_WINDOW_MS - 1)
            batch = self._signed_get(
                "/fapi/v1/allOrders",
                {"symbol": symbol, "startTime": cursor, "endTime": window_end, "limit": 1000},
            )
            if len(batch) >= 1000:
                raise TestnetExchangeError("TESTNET_ORDER_HISTORY_WINDOW_TRUNCATED")
            for row in batch:
                key = str(row.get("orderId") or row.get("clientOrderId") or "")
                if key:
                    rows[key] = row
            cursor = window_end + 1
        return sorted(
            rows.values(),
            key=lambda row: (int(row.get("updateTime") or row.get("time") or 0), int(row.get("orderId", 0) or 0)),
        )

    def _realized_pnl_income(self, symbol: str, start_ms: int, end_ms: int) -> float | None:
        if start_ms <= 0 or end_ms < start_ms:
            raise TestnetExchangeError("TESTNET_INCOME_HISTORY_RANGE_INVALID")
        rows = self._signed_get(
            "/fapi/v1/income",
            {
                "symbol": symbol,
                "incomeType": "REALIZED_PNL",
                "startTime": int(start_ms),
                "endTime": int(end_ms),
                "limit": 1000,
            },
        )
        realized_rows = [
            row for row in rows
            if str(row.get("symbol") or "").upper() == symbol
            and str(row.get("incomeType") or "").upper() == "REALIZED_PNL"
        ]
        if not realized_rows:
            return None
        return sum(float(row.get("income", 0) or 0) for row in realized_rows)

    @staticmethod
    def _theoretical_close_pnl(local: dict[str, Any], exit_price: float, quantity: float) -> float | None:
        entry = float(local.get("entry_price", 0) or 0)
        side = str(local.get("side") or "").upper()
        if entry <= 0 or quantity <= 0 or side not in {"LONG", "SHORT"}:
            return None
        return (exit_price - entry) * quantity if side == "LONG" else (entry - exit_price) * quantity

    def _assert_no_unexpected_filled_orders(
        self, local: dict[str, Any], *, allowed_order_ids: set[str], end_ms: int,
    ) -> None:
        symbol = str(local["symbol"]).upper()
        entry_ts = int(local["entry_timestamp_ms"])
        entry_order_id = str(local.get("entry_order_id") or "")
        allowed = set(allowed_order_ids)
        if entry_order_id:
            allowed.add(entry_order_id)
        for order in self._all_orders_between(symbol, entry_ts, end_ms):
            order_id = str(order.get("orderId") or "")
            executed_qty = float(order.get("executedQty", 0) or 0)
            if executed_qty <= 0 or order_id in allowed:
                continue
            when = int(order.get("updateTime") or order.get("time") or 0)
            if when < entry_ts:
                continue
            raise TestnetExchangeError(
                f"TESTNET_POSITION_MUTATED_WHILE_EXECUTION_OFFLINE:UNEXPECTED_ORDER:{order_id or 'UNKNOWN'}"
            )

    def _settle_local_position_from_order_history(self, local: dict[str, Any], end_ms: int) -> CloseFill:
        """Generic V1-style exchange-flat recovery when userTrades is absent.

        Binance order history proves the exact opposite-side executed quantity
        and price; Binance REALIZED_PNL income remains the accounting authority.
        Local arithmetic is audit-only.
        """
        symbol = str(local["symbol"]).upper()
        side = str(local["side"]).upper()
        target_qty = float(local["quantity"])
        entry_ts = int(local["entry_timestamp_ms"])
        entry_order_id = str(local.get("entry_order_id") or "")
        exit_side = "SELL" if side == "LONG" else "BUY"
        entry_side = "BUY" if side == "LONG" else "SELL"
        step = float(self._filters[symbol]["market_step"])
        tolerance = max(step / 2.0, 1e-12)
        exit_orders: list[dict[str, Any]] = []
        exit_qty = 0.0

        for order in self._all_orders_between(symbol, entry_ts, end_ms):
            order_id = str(order.get("orderId") or "")
            if entry_order_id and order_id == entry_order_id:
                continue
            executed_qty = float(order.get("executedQty", 0) or 0)
            if executed_qty <= 0:
                continue
            when = int(order.get("updateTime") or order.get("time") or 0)
            if when < entry_ts:
                continue
            if str(order.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_CLOSE_ORDER_HISTORY_HEDGE_MODE_UNSUPPORTED")
            order_side = str(order.get("side") or "").upper()
            if order_side == entry_side:
                raise TestnetExchangeError("TESTNET_POSITION_MUTATED_WHILE_EXECUTION_OFFLINE")
            if order_side != exit_side:
                continue
            avg_price = float(order.get("avgPrice", 0) or 0)
            if avg_price <= 0:
                raise TestnetExchangeError("TESTNET_CLOSE_ORDER_HISTORY_PRICE_INVALID")
            exit_orders.append(order)
            exit_qty += executed_qty

        if exit_qty < target_qty - tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_INCOMPLETE")
        if exit_qty > target_qty + tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_AMBIGUOUS_QUANTITY")
        if not exit_orders:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_MISSING")

        weighted = sum(float(row["executedQty"]) * float(row["avgPrice"]) for row in exit_orders)
        exit_price = weighted / exit_qty
        close_ms = max(int(row.get("updateTime") or row.get("time") or 0) for row in exit_orders)
        first_ms = min(int(row.get("updateTime") or row.get("time") or 0) for row in exit_orders)
        start_second = (first_ms // 1000) * 1000
        end_second = (close_ms // 1000) * 1000 + 999
        realized = self._realized_pnl_income(symbol, start_second, end_second)
        if realized is None:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_REALIZED_PNL_MISSING")
        order_ids = tuple(sorted(str(row.get("orderId")) for row in exit_orders if row.get("orderId") is not None))
        reason = self._recover_close_reason(local, order_ids, close_ms)
        theoretical = self._theoretical_close_pnl(local, exit_price, exit_qty)
        variance = None if theoretical is None else realized - theoretical
        if variance is not None and abs(variance) > 1e-6:
            self.log.warning(
                "TESTNET_ACCOUNTING_AUDIT_VARIANCE source=ORDER_HISTORY symbol=%s exchange_pnl=%.8f theoretical_pnl=%.8f variance=%.8f",
                symbol, realized, theoretical, variance,
            )
        return CloseFill(
            price=exit_price, timestamp_ms=close_ms, reason=reason,
            realized_pnl_usd=realized, order_ids=order_ids, source="ORDER_HISTORY_INCOME_RECOVERY",
            theoretical_pnl_usd=theoretical, pnl_variance_usd=variance,
        )

    def _settle_local_position_from_trades(self, local: dict[str, Any], rows: list[dict[str, Any]]) -> CloseFill:
        symbol = str(local["symbol"]).upper()
        side = str(local["side"]).upper()
        target_qty = float(local["quantity"])
        entry_order_id = str(local.get("entry_order_id") or "")
        entry_ts = int(local["entry_timestamp_ms"])
        exit_side = "SELL" if side == "LONG" else "BUY"
        entry_side = "BUY" if side == "LONG" else "SELL"
        step = float(self._filters[symbol]["market_step"])
        tolerance = max(step / 2.0, 1e-12)
        exit_rows: list[dict[str, Any]] = []
        exit_qty = 0.0

        for row in rows:
            if int(row.get("time", 0) or 0) < entry_ts:
                continue
            if str(row.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_HEDGE_MODE_UNSUPPORTED")
            order_id = str(row.get("orderId") or "")
            if entry_order_id and order_id == entry_order_id:
                continue
            trade_side = str(row.get("side") or "").upper()
            qty = float(row.get("qty", 0) or 0)
            price = float(row.get("price", 0) or 0)
            if qty <= 0 or price <= 0:
                raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_TRADE_INVALID")
            if trade_side == entry_side:
                raise TestnetExchangeError("TESTNET_POSITION_MUTATED_WHILE_EXECUTION_OFFLINE")
            if trade_side != exit_side:
                continue
            exit_rows.append(row)
            exit_qty += qty

        if exit_qty < target_qty - tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_INCOMPLETE")
        if exit_qty > target_qty + tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_AMBIGUOUS_QUANTITY")
        weighted = sum(float(row["qty"]) * float(row["price"]) for row in exit_rows)
        if not exit_rows or exit_qty <= 0:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_MISSING")
        exit_price = weighted / exit_qty
        realized = sum(float(row.get("realizedPnl", 0) or 0) for row in exit_rows)
        closed_ms = max(int(row.get("time", 0) or 0) for row in exit_rows)
        order_ids = tuple(sorted({str(row.get("orderId") or "") for row in exit_rows if row.get("orderId") is not None}))
        reason = self._recover_close_reason(local, order_ids, closed_ms)
        theoretical = self._theoretical_close_pnl(local, exit_price, exit_qty)
        variance = None if theoretical is None else realized - theoretical
        return CloseFill(
            price=exit_price,
            timestamp_ms=closed_ms,
            reason=reason,
            realized_pnl_usd=realized,
            order_ids=order_ids,
            source="USER_TRADES_RECOVERY",
            theoretical_pnl_usd=theoretical,
            pnl_variance_usd=variance,
        )

    def _settle_local_position_from_finished_stop(self, local: dict[str, Any], end_ms: int) -> CloseFill:
        """Recover a Testnet close when userTrades omits the spawned stop fill.

        USD-M Testnet can expose a FINISHED reduce-only STOP_MARKET in algo
        history and its FILLED child order while returning no rows from
        ``/fapi/v1/userTrades``.  Accept that path only when independent
        exchange evidence agrees on direction, quantity, price and realized
        PnL.  Any disagreement remains fail-closed.
        """
        symbol = str(local["symbol"]).upper()
        side = str(local["side"]).upper()
        target_qty = float(local["quantity"])
        entry_price = float(local.get("entry_price", 0) or 0)
        entry_ts = int(local["entry_timestamp_ms"])
        if target_qty <= 0 or entry_price <= 0:
            raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_LOCAL_POSITION_INVALID")

        expected_side = "SELL" if side == "LONG" else "BUY"
        step = float(self._filters[symbol]["market_step"])
        tick = float(self._filters[symbol]["tick"])
        qty_tolerance = max(step / 2.0, 1e-12)
        price_tolerance = max(tick / 2.0, 1e-12)

        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for algo in self._all_algo_orders_between(symbol, entry_ts, end_ms):
            if str(algo.get("algoStatus") or "").upper() != "FINISHED":
                continue
            if str(algo.get("orderType") or algo.get("type") or "").upper() != "STOP_MARKET":
                continue
            if not self._is_true(algo.get("reduceOnly")):
                continue
            if str(algo.get("side") or "").upper() != expected_side:
                continue
            if str(algo.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_HEDGE_MODE_UNSUPPORTED")
            actual_order_id = str(algo.get("actualOrderId") or "").strip()
            if not actual_order_id:
                continue
            algo_qty = float(algo.get("actualQty") or algo.get("quantity") or 0)
            if abs(algo_qty - target_qty) > qty_tolerance:
                continue

            order = self._query_order_by_id(symbol, actual_order_id)
            if order is None:
                continue
            if str(order.get("status") or "").upper() != "FILLED":
                continue
            if str(order.get("side") or "").upper() != expected_side:
                continue
            if str(order.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_HEDGE_MODE_UNSUPPORTED")
            if not self._is_true(order.get("reduceOnly")):
                continue
            executed_qty = float(order.get("executedQty", 0) or 0)
            if abs(executed_qty - target_qty) > qty_tolerance:
                continue
            avg_price = float(order.get("avgPrice", 0) or 0)
            if avg_price <= 0:
                continue
            actual_price = float(algo.get("actualPrice", 0) or 0)
            if actual_price > 0 and abs(actual_price - avg_price) > price_tolerance:
                raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_PRICE_MISMATCH")
            algo_client = str(algo.get("clientAlgoId") or "").strip()
            order_client = str(order.get("clientOrderId") or "").strip()
            if algo_client and order_client and algo_client != order_client:
                raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_CLIENT_ID_MISMATCH")
            candidates.append((algo, order))

        if not candidates:
            raise TestnetExchangeError("TESTNET_ALGO_CLOSE_EVIDENCE_MISSING")
        if len(candidates) != 1:
            raise TestnetExchangeError("TESTNET_ALGO_CLOSE_EVIDENCE_AMBIGUOUS")

        algo, order = candidates[0]
        order_id = str(order.get("orderId") or algo.get("actualOrderId") or "").strip()
        exit_price = float(order["avgPrice"])
        close_ms = int(order.get("updateTime") or order.get("time") or algo.get("updateTime") or 0)
        if close_ms < entry_ts:
            raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_TIMESTAMP_INVALID")

        # Testnet may omit the corresponding userTrades rows. The finished
        # reduce-only STOP_MARKET and its FILLED child order prove execution
        # identity. Before attributing same-symbol REALIZED_PNL income, reject
        # any other filled order during the local position lifetime.
        self._assert_no_unexpected_filled_orders(
            local, allowed_order_ids={order_id}, end_ms=close_ms,
        )
        first_fill_ms = int(order.get("time") or close_ms)
        income_start = (min(first_fill_ms, close_ms) // 1000) * 1000
        income_end = (max(first_fill_ms, close_ms) // 1000) * 1000 + 999
        realized = self._realized_pnl_income(symbol, income_start, income_end)
        if realized is None:
            raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_REALIZED_PNL_MISSING")

        theoretical = self._theoretical_close_pnl(local, exit_price, target_qty)
        variance = None if theoretical is None else realized - theoretical
        # Exchange accounting is authoritative. The local reconstruction is a
        # diagnostic only because Binance may use fill-level cost basis/precision
        # that differs slightly from our stored aggregate entry price.
        if variance is not None and abs(variance) > 1e-6:
            self.log.warning(
                "TESTNET_ACCOUNTING_AUDIT_VARIANCE source=ALGO symbol=%s exchange_pnl=%.8f theoretical_pnl=%.8f variance=%.8f",
                symbol, realized, theoretical, variance,
            )

        return CloseFill(
            price=exit_price,
            timestamp_ms=close_ms,
            reason="PROTECTIVE_STOP_TRIGGERED",
            realized_pnl_usd=realized,
            order_ids=(order_id,),
            source="ALGO_ACTUAL_ORDER_INCOME_RECOVERY",
            theoretical_pnl_usd=theoretical,
            pnl_variance_usd=variance,
        )

    def _recover_close_reason(self, local: dict[str, Any], close_order_ids: tuple[str, ...], closed_ms: int) -> str:
        close_ids = set(close_order_ids)
        algo_id = local.get("protective_stop_algo_id")
        client_algo_id = local.get("protective_stop_client_algo_id")
        if algo_id is not None or client_algo_id:
            try:
                row = self._query_algo_order(
                    algo_id=None if algo_id is None else str(algo_id),
                    client_algo_id=None if algo_id is not None else str(client_algo_id),
                )
                if row is not None:
                    actual_order_id = str(row.get("actualOrderId") or "").strip()
                    if (
                        str(row.get("orderType") or row.get("type") or "").upper() == "STOP_MARKET"
                        and self._is_true(row.get("reduceOnly"))
                        and actual_order_id in close_ids
                    ):
                        return "PROTECTIVE_STOP_TRIGGERED"
            except Exception as exc:
                self.log.warning("TESTNET_STOP_HISTORY_LOOKUP_FAILED %s", exc)

        # The operator/exchange may have replaced the original stop while the
        # worker was offline. Current Binance algo history exposes the actual
        # child order ID after a conditional order triggers, so scan the
        # position lifetime and only call it a stop when that exact child order
        # is one of the closing fills. If this cannot be proven, stay
        # conservative rather than guessing the reason.
        try:
            start_ms = int(local.get("entry_timestamp_ms") or 0)
            if start_ms > 0 and closed_ms >= start_ms:
                expected_side = "SELL" if str(local.get("side") or "").upper() == "LONG" else "BUY"
                for row in self._all_algo_orders_between(str(local["symbol"]).upper(), start_ms, closed_ms):
                    actual_order_id = str(row.get("actualOrderId") or "").strip()
                    if (
                        str(row.get("orderType") or row.get("type") or "").upper() == "STOP_MARKET"
                        and self._is_true(row.get("reduceOnly"))
                        and str(row.get("side") or "").upper() == expected_side
                        and actual_order_id in close_ids
                    ):
                        return "PROTECTIVE_STOP_TRIGGERED"
        except Exception as exc:
            self.log.warning("TESTNET_ALL_STOP_HISTORY_LOOKUP_FAILED %s", exc)
        return "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART"

    def _cleanup_orphan_protective_stops(self, symbol: str) -> None:
        # A flat account with a lingering reduce-only stop is not a clean
        # execution boundary: that orphan could interfere with a later entry.
        # Reuse the same verified pruning path and fail closed if exchange truth
        # cannot confirm that all protective stops are gone.
        self._prune_protective_stops(symbol, None)

    def recover_closed_position(self, local_position: dict[str, Any]) -> CloseFill:
        if self.position_snapshot() is not None:
            raise TestnetExchangeError("TESTNET_RECOVERY_POSITION_NOT_FLAT")
        symbol = str(local_position.get("symbol") or "").upper()
        entry_ts = int(local_position.get("entry_timestamp_ms") or 0)
        if symbol not in self._filters or entry_ts <= 0:
            raise TestnetExchangeError("TESTNET_RECOVERY_LOCAL_POSITION_INVALID")
        last_error: Exception | None = None
        for attempt in range(CLOSE_SETTLEMENT_RETRIES):
            now_ms = int(time.time() * 1000)
            try:
                rows = self._user_trades_since(symbol, entry_ts, now_ms)
                close = self._settle_local_position_from_trades(local_position, rows)
                self._cleanup_orphan_protective_stops(symbol)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                if "TESTNET_CLOSE_EVIDENCE_INCOMPLETE" not in str(exc) and "TESTNET_CLOSE_EVIDENCE_MISSING" not in str(exc):
                    raise

            # Binance USD-M Testnet can expose the completed conditional algo
            # and spawned actual order while returning an empty userTrades
            # result. Identity is proven from exchange order state; Binance
            # REALIZED_PNL is accounting truth. Local arithmetic is audit-only.
            try:
                close = self._settle_local_position_from_finished_stop(local_position, now_ms)
                self._cleanup_orphan_protective_stops(symbol)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                retryable = (
                    "TESTNET_ALGO_CLOSE_EVIDENCE_MISSING" in str(exc)
                    or "TESTNET_ALGO_SETTLEMENT_REALIZED_PNL_MISSING" in str(exc)
                )
                if not retryable:
                    raise

            # V1 reconciled any exchange-side close, not only stops. If
            # userTrades and algo history cannot settle it, use full Binance
            # order history plus REALIZED_PNL income. Unexpected extra fills
            # remain a hard mutation error rather than being guessed through.
            try:
                close = self._settle_local_position_from_order_history(local_position, now_ms)
                self._cleanup_orphan_protective_stops(symbol)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                retryable = (
                    "TESTNET_CLOSE_ORDER_EVIDENCE_MISSING" in str(exc)
                    or "TESTNET_CLOSE_ORDER_EVIDENCE_INCOMPLETE" in str(exc)
                    or "TESTNET_CLOSE_ORDER_REALIZED_PNL_MISSING" in str(exc)
                )
                if not retryable:
                    raise
                if attempt + 1 < CLOSE_SETTLEMENT_RETRIES:
                    time.sleep(CLOSE_SETTLEMENT_RETRY_SECONDS)
        raise TestnetExchangeError(f"TESTNET_EXTERNAL_CLOSE_SETTLEMENT_FAILED:{last_error}")

    def _settle_close_order(self, position: ExchangePosition, order: dict[str, Any], fallback: Fill | None, reason: str) -> CloseFill:
        order_id = order.get("orderId")
        if order_id is not None:
            for attempt in range(CLOSE_SETTLEMENT_RETRIES):
                rows = self._signed_get(
                    "/fapi/v1/userTrades",
                    {"symbol": position.symbol, "orderId": int(order_id), "limit": 1000},
                )
                if rows:
                    qty = sum(float(row.get("qty", 0) or 0) for row in rows)
                    if qty > 0:
                        price = sum(float(row["qty"]) * float(row["price"]) for row in rows) / qty
                        realized = sum(float(row.get("realizedPnl", 0) or 0) for row in rows)
                        ts = max(int(row.get("time", 0) or 0) for row in rows)
                        return CloseFill(price, ts, reason, realized, (str(order_id),), "USER_TRADES_ORDER")

                # Testnet may omit userTrades even for an order that Binance
                # itself reports FILLED. In that case use the order's exchange
                # price/quantity and Binance REALIZED_PNL, never local PnL as
                # authoritative accounting.
                known = order if order else self._query_order_by_id(position.symbol, str(order_id))
                if known is not None and str(known.get("status") or "").upper() == "FILLED":
                    qty = float(known.get("executedQty", 0) or 0)
                    price = float(known.get("avgPrice", 0) or 0)
                    ts = int(known.get("updateTime") or known.get("time") or 0)
                    step = float(self._filters[position.symbol]["market_step"])
                    if abs(qty - float(position.quantity)) <= max(step / 2.0, 1e-12) and price > 0 and ts > 0:
                        first_fill_ms = int(known.get("time") or ts)
                        income_start = (min(first_fill_ms, ts) // 1000) * 1000
                        income_end = (max(first_fill_ms, ts) // 1000) * 1000 + 999
                        realized = self._realized_pnl_income(position.symbol, income_start, income_end)
                        if realized is not None:
                            theoretical = (price - position.entry_price) * qty if position.side == "LONG" else (position.entry_price - price) * qty
                            return CloseFill(
                                price, ts, reason, realized, (str(order_id),), "ORDER_INCOME_SETTLEMENT",
                                theoretical, realized - theoretical,
                            )
                if attempt + 1 < CLOSE_SETTLEMENT_RETRIES:
                    time.sleep(CLOSE_SETTLEMENT_RETRY_SECONDS)
        if fallback is None:
            raise TestnetExchangeError("TESTNET_CLOSE_FILL_EVIDENCE_MISSING")
        # A flat exchange plus a returned fill proves the price/quantity but not
        # authoritative realized PnL. Preserve local OPEN so restart recovery
        # can retry Binance accounting rather than inventing a close result.
        raise TestnetExchangeError(
            f"TESTNET_CLOSE_ACCOUNTING_UNAVAILABLE:order_id={order_id}:price={fallback.price}:qty={fallback.quantity}"
        )

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
        self._cleanup_orphan_protective_stops(position.symbol)
        fallback_price = self.quote(position.symbol).mid
        fill = self._fill_from_order(order or {}, fallback_price, quantity)
        if fill is None and order is None:
            # Ambiguous close can still be settled from the exact client ID.
            recovered_order = self._query_order(position.symbol, client_order_id)
            if recovered_order is not None:
                order = recovered_order
                fill = self._fill_from_order(order, fallback_price, quantity)
        return self._settle_close_order(position, order or {}, fill, reason)

    def close_position(self, symbol: str, side: str, *, reason: str) -> CloseFill:
        position = self.position_snapshot()
        if position is None:
            raise TestnetExchangeError("TESTNET_CLOSE_POSITION_ALREADY_FLAT_USE_RECOVERY")
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
