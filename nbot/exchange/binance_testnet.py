"""Binance USD-M Futures Testnet ExchangePort for NBOT V3.1.9.

This adapter is deliberately capital-only.  It contains no Observation,
research, candidate, model, or learning code.

Safety properties carried forward from the V2.8.5 execution reference:

* REST and WebSocket namespaces are hard-pinned to Binance Demo/Testnet hosts;
* signed requests use the configured recvWindow and HMAC-SHA256;
* entry order writes use the exact caller-supplied deterministic client ID;
* ambiguous entry writes are never blindly resubmitted;
* conditional STOP_MARKET protection uses Binance's current Algo Service;
* stop client IDs are deterministic and ambiguous writes recover by identity;
* replacement proves new protection before old protection is pruned;
* exchange-side close recovery uses Binance trades/orders/income evidence;
* missing close accounting is never replaced with invented zero PnL;
* Testnet entry writes require a durable explicit arm/session gate;
* session entry consumption is persisted before a market entry POST;
* one adapter instance owns the Testnet execution lock at a time.

The adapter uses only Python's standard library.  V3.2 may add dedicated market
stream plumbing around this ExchangePort without changing the capital contract.
"""

from __future__ import annotations

from nbot.common.binance_limits import ExchangeCooldown, budget_for, request_weight

import hashlib
import hmac
import json
import logging
import math
import os
import socket
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from nbot.common.atomic_io import atomic_write_json
from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    EntryNotSubmitted,
    EntryPlan,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
    Side,
)
from nbot.execution.models import EntryInflight, OpenPosition

LOGGER = logging.getLogger("nbot.v3.testnet")

TESTNET_REST_BASE_URL = "https://demo-fapi.binance.com"
TESTNET_WS_BASE_URL = "wss://demo-fstream.binance.com"
TESTNET_ARM_PROFILE = "testnet-trade"
TESTNET_GUARD_STATE_VERSION = "NBOT_V3_TESTNET_GUARD_V1"
USER_TRADES_MAX_WINDOW_MS = 7 * 24 * 60 * 60 * 1000


class TestnetExchangeError(RuntimeError):
    """A Testnet exchange truth or safety invariant failed."""


class TestnetEntryNotSubmitted(TestnetExchangeError, EntryNotSubmitted):
    """Testnet refusal proven before the capital-bearing entry POST."""


class AmbiguousExecutionError(TestnetExchangeError):
    """A write may have reached Binance; never blindly resubmit it."""


@dataclass(frozen=True, slots=True)
class TestnetExchangeConfig:
    api_key: str
    api_secret: str
    repo_root: Path
    base_url: str = TESTNET_REST_BASE_URL
    ws_base_url: str = TESTNET_WS_BASE_URL
    request_timeout_seconds: float = 5.0
    recv_window_ms: int = 5_000
    max_session_entries: int = 100
    max_entry_notional_usd: float = 1_000.0
    entry_resolution_timeout_seconds: float = 10.0
    stop_resolution_timeout_seconds: float = 10.0
    close_settlement_retries: int = 5
    close_settlement_retry_seconds: float = 0.5
    arm_file: Path | None = None
    guard_state_path: Path | None = None
    instance_lock_path: Path | None = None

    @classmethod
    def from_env(cls, *, repo_root: Path) -> "TestnetExchangeConfig":
        root = Path(repo_root)
        return cls(
            api_key=os.environ.get("TESTNET_API_KEY", "").strip(),
            api_secret=os.environ.get("TESTNET_API_SECRET", "").strip(),
            repo_root=root,
            base_url=os.environ.get("TESTNET_BASE_URL", TESTNET_REST_BASE_URL).strip(),
            ws_base_url=os.environ.get("TESTNET_WS_BASE_URL", TESTNET_WS_BASE_URL).strip(),
            request_timeout_seconds=float(os.environ.get("TESTNET_REST_TIMEOUT_SECONDS", "5")),
            recv_window_ms=int(os.environ.get("TESTNET_RECV_WINDOW_MS", "5000")),
            max_session_entries=int(os.environ.get("TESTNET_MAX_SESSION_ENTRIES", "100")),
            max_entry_notional_usd=float(os.environ.get("TESTNET_MAX_ENTRY_NOTIONAL_USD", "1000")),
            entry_resolution_timeout_seconds=float(os.environ.get("TESTNET_ENTRY_RESOLUTION_SECONDS", "10")),
            stop_resolution_timeout_seconds=float(os.environ.get("TESTNET_STOP_RESOLUTION_SECONDS", "10")),
            close_settlement_retries=int(os.environ.get("TESTNET_CLOSE_SETTLEMENT_RETRIES", "5")),
            close_settlement_retry_seconds=float(os.environ.get("TESTNET_CLOSE_SETTLEMENT_RETRY_SECONDS", "0.5")),
        )

    @property
    def resolved_arm_file(self) -> Path:
        return self.arm_file or self.repo_root / "runtime/execution/testnet/TESTNET_TRADING_ARMED"

    @property
    def resolved_guard_state_path(self) -> Path:
        return self.guard_state_path or self.repo_root / "data/execution/testnet/testnet_trading_guard.json"

    @property
    def resolved_instance_lock_path(self) -> Path:
        return self.instance_lock_path or self.repo_root / "runtime/execution/testnet/execution.lock"

    def validate(self, *, require_credentials: bool = True) -> None:
        rest = urlparse(self.base_url)
        ws = urlparse(self.ws_base_url)
        if rest.scheme.lower() != "https" or (rest.hostname or "").lower() != "demo-fapi.binance.com":
            raise ValueError("TESTNET_REST_HOST_INVALID")
        if rest.path not in {"", "/"} or rest.query or rest.fragment or rest.username or rest.password or rest.port:
            raise ValueError("TESTNET_REST_URL_INVALID")
        if ws.scheme.lower() != "wss" or (ws.hostname or "").lower() != "demo-fstream.binance.com":
            raise ValueError("TESTNET_WS_HOST_INVALID")
        if ws.path not in {"", "/", "/ws"} or ws.query or ws.fragment or ws.username or ws.password or ws.port:
            raise ValueError("TESTNET_WS_URL_INVALID")
        if require_credentials and (not self.api_key or not self.api_secret):
            raise ValueError("TESTNET_CREDENTIALS_MISSING")
        if self.request_timeout_seconds <= 0 or not math.isfinite(self.request_timeout_seconds):
            raise ValueError("TESTNET_TIMEOUT_INVALID")
        if self.recv_window_ms <= 0 or self.recv_window_ms > 60_000:
            raise ValueError("TESTNET_RECV_WINDOW_INVALID")
        if self.max_session_entries <= 0:
            raise ValueError("TESTNET_SESSION_LIMIT_INVALID")
        if self.max_entry_notional_usd <= 0 or not math.isfinite(self.max_entry_notional_usd):
            raise ValueError("TESTNET_NOTIONAL_LIMIT_INVALID")
        if self.entry_resolution_timeout_seconds <= 0 or self.stop_resolution_timeout_seconds <= 0:
            raise ValueError("TESTNET_RESOLUTION_TIMEOUT_INVALID")
        if self.close_settlement_retries <= 0 or self.close_settlement_retry_seconds < 0:
            raise ValueError("TESTNET_CLOSE_SETTLEMENT_CONFIG_INVALID")


class _InstanceLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        os.chmod(self.path, 0o600)
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise TestnetExchangeError("TESTNET_EXECUTION_INSTANCE_LOCK_HELD") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class TestnetTradingGuard:
    """Durable arm/session limiter for Testnet entry writes.

    The V3 operator arm file is the authority that a human explicitly enabled
    Testnet order writes.  A sidecar guard state binds its entry counter to the
    exact arm-file identity.  Recreating the arm file starts a new explicit
    session; deleting/corrupting the sidecar while already armed fails closed.
    """

    def __init__(self, config: TestnetExchangeConfig):
        self.config = config
        self._thread_lock = threading.Lock()

    @property
    def _state_lock_path(self) -> Path:
        return Path(str(self.config.resolved_guard_state_path) + ".lock")

    @staticmethod
    def _parse_arm(raw: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            if "=" not in line:
                raise TestnetExchangeError("TESTNET_ARM_FILE_INVALID")
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or not value or key in result:
                raise TestnetExchangeError("TESTNET_ARM_FILE_INVALID")
            result[key] = value
        if result.get("profile") != TESTNET_ARM_PROFILE:
            raise TestnetExchangeError("TESTNET_ARM_PROFILE_INVALID")
        if not result.get("sha") or not result.get("armed_at"):
            raise TestnetExchangeError("TESTNET_ARM_IDENTITY_INVALID")
        return result

    def _arm_status(self) -> tuple[bool, str, str | None]:
        path = self.config.resolved_arm_file
        if not path.is_file():
            return False, "ARM_FILE_MISSING", None
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = handle.read()
                stat = os.fstat(handle.fileno())
            parsed = self._parse_arm(raw)
        except (OSError, UnicodeError, TestnetExchangeError):
            return False, "ARM_FILE_INVALID", None
        identity = {
            "profile": parsed["profile"],
            "sha": parsed["sha"],
            "armed_at": parsed["armed_at"],
            "device": int(stat.st_dev),
            "inode": int(stat.st_ino),
            "ctime_ns": int(stat.st_ctime_ns),
        }
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return True, "ARMED", fingerprint

    @staticmethod
    def _state(fingerprint: str | None = None) -> dict[str, Any]:
        return {
            "state_version": TESTNET_GUARD_STATE_VERSION,
            "arm_session_fingerprint": fingerprint,
            "session_entries": 0,
        }

    def _save_state(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.config.resolved_guard_state_path, state, mode=0o600)

    def _load_state(self, *, armed: bool) -> dict[str, Any]:
        path = self.config.resolved_guard_state_path
        if not path.exists():
            if armed:
                raise TestnetExchangeError("TESTNET_GUARD_STATE_MISSING_WHILE_ARMED")
            state = self._state()
            self._save_state(state)
            return state
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TestnetExchangeError("TESTNET_GUARD_STATE_INVALID") from exc
        if not isinstance(raw, dict) or raw.get("state_version") != TESTNET_GUARD_STATE_VERSION:
            raise TestnetExchangeError("TESTNET_GUARD_STATE_INVALID")
        entries = raw.get("session_entries")
        fingerprint = raw.get("arm_session_fingerprint")
        if isinstance(entries, bool) or not isinstance(entries, int) or entries < 0:
            raise TestnetExchangeError("TESTNET_GUARD_STATE_INVALID")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise TestnetExchangeError("TESTNET_GUARD_STATE_INVALID")
        return raw

    def _with_lock(self):
        outer = self

        class Lock:
            def __enter__(self_inner):
                outer._state_lock_path.parent.mkdir(parents=True, exist_ok=True)
                self_inner.handle = outer._state_lock_path.open("a+", encoding="utf-8")
                os.chmod(outer._state_lock_path, 0o600)
                import fcntl
                fcntl.flock(self_inner.handle.fileno(), fcntl.LOCK_EX)
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                import fcntl
                fcntl.flock(self_inner.handle.fileno(), fcntl.LOCK_UN)
                self_inner.handle.close()

        return Lock()

    def initialize_unarmed_state(self) -> None:
        """Create initial state only while no arm file exists."""
        with self._thread_lock, self._with_lock():
            armed, _reason, _fingerprint = self._arm_status()
            if armed:
                raise TestnetExchangeError("TESTNET_GUARD_INITIALIZE_WHILE_ARMED")
            if not self.config.resolved_guard_state_path.exists():
                self._save_state(self._state())

    def initialize_new_arm_session(self) -> None:
        """Bind a fresh zero-count session to an already-created V3 arm file."""
        with self._thread_lock, self._with_lock():
            armed, reason, fingerprint = self._arm_status()
            if not armed or fingerprint is None:
                raise TestnetExchangeError(f"TESTNET_TRADING_NOT_ARMED:{reason}")
            self._save_state(self._state(fingerprint))

    def preflight(self) -> dict[str, Any]:
        with self._thread_lock, self._with_lock():
            armed, reason, fingerprint = self._arm_status()
            try:
                state = self._load_state(armed=armed)
            except TestnetExchangeError as exc:
                return {
                    "armed": False,
                    "reason": str(exc),
                    "session_entries": None,
                    "max_session_entries": self.config.max_session_entries,
                    "max_entry_notional_usd": self.config.max_entry_notional_usd,
                }
            if armed and state.get("arm_session_fingerprint") != fingerprint:
                return {
                    "armed": False,
                    "reason": "TESTNET_ARM_SESSION_STATE_MISMATCH",
                    "session_entries": int(state["session_entries"]),
                    "max_session_entries": self.config.max_session_entries,
                    "max_entry_notional_usd": self.config.max_entry_notional_usd,
                }
            return {
                "armed": bool(armed),
                "reason": reason,
                "session_entries": int(state["session_entries"]),
                "max_session_entries": self.config.max_session_entries,
                "max_entry_notional_usd": self.config.max_entry_notional_usd,
            }

    def authorize_entry(
        self,
        *,
        symbol: str,
        quantity: float,
        price: float,
        position: ExchangePosition | None,
    ) -> None:
        with self._thread_lock, self._with_lock():
            armed, reason, fingerprint = self._arm_status()
            if not armed or fingerprint is None:
                raise TestnetExchangeError(f"TESTNET_TRADING_NOT_ARMED:{reason}")
            state = self._load_state(armed=True)
            if state.get("arm_session_fingerprint") != fingerprint:
                raise TestnetExchangeError("TESTNET_ARM_SESSION_STATE_MISMATCH")
            if position is not None:
                raise TestnetExchangeError("TESTNET_ENTRY_BLOCKED_POSITION_EXISTS")
            if not symbol or quantity <= 0 or price <= 0:
                raise TestnetExchangeError("TESTNET_ENTRY_PARAMETERS_INVALID")
            notional = float(quantity) * float(price)
            if not math.isfinite(notional) or notional > self.config.max_entry_notional_usd + 1e-9:
                raise TestnetExchangeError("TESTNET_ENTRY_NOTIONAL_LIMIT_EXCEEDED")
            if int(state["session_entries"]) >= self.config.max_session_entries:
                raise TestnetExchangeError("TESTNET_SESSION_ENTRY_LIMIT_REACHED")
            # Reserve before the capital-bearing POST.  Failed/ambiguous attempts
            # conservatively consume one slot and survive Python restart.
            state["session_entries"] = int(state["session_entries"]) + 1
            self._save_state(state)


def initialize_testnet_guard_for_arm(repo_root: Path) -> None:
    """Called by nbotctl immediately after creating a Testnet arm file."""
    cfg = TestnetExchangeConfig(api_key="x", api_secret="x", repo_root=Path(repo_root))
    TestnetTradingGuard(cfg).initialize_new_arm_session()


class BinanceTestnetExchange:
    """Fail-closed Binance USD-M Futures Testnet ExchangePort."""

    def __init__(self, config: TestnetExchangeConfig, *, logger: logging.Logger | None = None):
        config.validate()
        self.config = config
        self.log = logger or LOGGER
        self.guard = TestnetTradingGuard(config)
        self._instance_lock = _InstanceLock(config.resolved_instance_lock_path)
        self._filters: dict[str, dict[str, float]] = {}
        self._connected = False
        self._server_epoch_ms: int | None = None
        self._server_monotonic = 0.0

    # --------------------------- transport ---------------------------

    @staticmethod
    def _error_detail(raw: bytes, status: int) -> str:
        try:
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, dict):
                return f"code={payload.get('code')} msg={payload.get('msg')}"
        except Exception:
            pass
        return f"HTTP_{status}"

    def _signature(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self.config.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    def _signed_timestamp_ms(self) -> int:
        now = time.monotonic()
        if self._server_epoch_ms is None or now - self._server_monotonic > 60:
            started = time.monotonic()
            response = self._public_get("/fapi/v1/time")
            finished = time.monotonic()
            if not isinstance(response, dict) or not isinstance(response.get("serverTime"), int):
                raise TestnetExchangeError("TESTNET_SERVER_TIME_INVALID")
            if finished - started > 1.0 or response["serverTime"] <= 0:
                raise TestnetExchangeError("TESTNET_SERVER_TIME_UNCERTAIN")
            self._server_epoch_ms = response["serverTime"]
            self._server_monotonic = (started + finished) / 2
        return self._server_epoch_ms + int((time.monotonic() - self._server_monotonic) * 1000)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
        ambiguous_write: bool = False,
    ) -> Any:
        budget = budget_for(self.config.base_url)
        try:
            budget.acquire(request_weight(path, params))
        except ExchangeCooldown as exc:
            raise TestnetExchangeError(str(exc)) from exc
        payload = dict(params or {})
        if signed:
            payload.setdefault("recvWindow", self.config.recv_window_ms)
            payload.setdefault("timestamp", self._signed_timestamp_ms())
            payload["signature"] = self._signature(payload)
        query = urlencode(payload)
        url = f"{self.config.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, method=method.upper())
        if signed:
            request.add_header("X-MBX-APIKEY", self.config.api_key)
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                budget.observe(getattr(response, "headers", {}))
                raw = response.read()
                status = int(response.status)
        except ExchangeCooldown as exc:
            if ambiguous_write:
                raise AmbiguousExecutionError("TESTNET_WRITE_BUDGET_PERSISTENCE_FAILED") from exc
            raise TestnetExchangeError(str(exc)) from exc
        except HTTPError as exc:
            budget.observe(exc.headers, exc.code)
            raw = exc.read()
            detail = self._error_detail(raw, exc.code)
            if "code=-1021" in detail:
                self._server_epoch_ms = None  # Resync next request; never replay a write here.
            if ambiguous_write and exc.code == 503 and "unknown" in detail.lower():
                raise AmbiguousExecutionError(f"AMBIGUOUS_503:{path}:{detail}") from exc
            raise TestnetExchangeError(f"REST_FAILED:{method}:{path}:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout, URLError, OSError) as exc:
            if ambiguous_write:
                raise AmbiguousExecutionError(f"AMBIGUOUS_NETWORK:{method}:{path}") from exc
            raise TestnetExchangeError(f"REST_NETWORK:{method}:{path}") from exc
        if status != 200:
            raise TestnetExchangeError(f"REST_FAILED:{method}:{path}:{status}")
        if not raw.strip():
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TestnetExchangeError(f"REST_JSON_INVALID:{method}:{path}") from exc

    def _public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params)

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params, signed=True)

    def _signed_post(self, path: str, params: dict[str, Any], *, ambiguous: bool = False) -> Any:
        return self._request("POST", path, params, signed=True, ambiguous_write=ambiguous)

    def _signed_delete(self, path: str, params: dict[str, Any], *, ambiguous: bool = False) -> Any:
        return self._request("DELETE", path, params, signed=True, ambiguous_write=ambiguous)

    # --------------------------- lifecycle ---------------------------

    def connect(self) -> None:
        if self.is_healthy():
            return
        self._instance_lock.acquire()
        try:
            self._public_get("/fapi/v1/ping")
            self._load_filters()
            # Authenticated exchange truth is proven before declaring healthy.
            self.position_snapshot()
            self._connected = True
        except Exception:
            self._connected = False
            self._instance_lock.release()
            raise

    def disconnect(self) -> None:
        self._connected = False
        self._instance_lock.release()

    def is_healthy(self) -> bool:
        return bool(self._connected and self._instance_lock.held)

    # --------------------------- filters ---------------------------

    def _load_filters(self) -> None:
        data = self._public_get("/fapi/v1/exchangeInfo")
        if not isinstance(data, dict):
            raise TestnetExchangeError("TESTNET_EXCHANGE_INFO_INVALID")
        filters: dict[str, dict[str, float]] = {}
        for row in data.get("symbols", []):
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "")
            if row.get("status") != "TRADING" or row.get("contractType") != "PERPETUAL" or row.get("quoteAsset") != "USDT":
                continue
            by_type = {str(item.get("filterType")): item for item in row.get("filters", []) if isinstance(item, dict)}
            market = by_type.get("MARKET_LOT_SIZE") or by_type.get("LOT_SIZE")
            lot = by_type.get("LOT_SIZE") or market
            price = by_type.get("PRICE_FILTER")
            if not symbol or not market or not lot or not price:
                continue
            try:
                filters[symbol] = {
                    "market_step": float(market["stepSize"]),
                    "market_min": float(market["minQty"]),
                    "market_max": float(market["maxQty"]),
                    "lot_step": float(lot["stepSize"]),
                    "tick": float(price["tickSize"]),
                    "price_min": float(price.get("minPrice", 0)),
                    "price_max": float(price.get("maxPrice", 0)),
                    "min_notional": float(by_type.get("MIN_NOTIONAL", {}).get("notional", 0)),
                }
            except (KeyError, TypeError, ValueError):
                continue
        if not filters:
            raise TestnetExchangeError("TESTNET_SYMBOL_FILTERS_EMPTY")
        self._filters = filters

    @staticmethod
    def _quantize_down(value: float, step: float) -> float:
        value_d = Decimal(str(value))
        step_d = Decimal(str(step))
        if step_d <= 0:
            raise TestnetExchangeError("QUANTIZATION_STEP_INVALID")
        return float(((value_d // step_d) * step_d).quantize(step_d, rounding=ROUND_DOWN))

    def _quantity(self, symbol: str, quantity: float) -> float:
        filt = self._filters.get(symbol)
        if filt is None:
            raise TestnetExchangeError(f"SYMBOL_FILTERS_MISSING:{symbol}")
        qty = self._quantize_down(quantity, filt["market_step"])
        if qty < filt["market_min"] or qty > filt["market_max"]:
            raise TestnetExchangeError(f"MARKET_QUANTITY_OUT_OF_RANGE:{symbol}:{qty}")
        return qty

    @staticmethod
    def _quantize_up(value: float, step: float) -> float:
        value_d = Decimal(str(value))
        step_d = Decimal(str(step))
        if step_d <= 0:
            raise TestnetExchangeError("QUANTIZATION_STEP_INVALID")
        units = (value_d / step_d).to_integral_value(rounding=ROUND_CEILING)
        return float((units * step_d).quantize(step_d))

    def _stop_price(self, symbol: str, side: Side, price: float) -> float:
        filt = self._filters.get(symbol)
        if filt is None:
            raise TestnetExchangeError(f"SYMBOL_FILTERS_MISSING:{symbol}")
        if price < filt.get("price_min", 0) or (filt.get("price_max", 0) > 0 and price > filt["price_max"]):
            raise TestnetExchangeError("STOP_PRICE_OUT_OF_RANGE")
        # A protective-stop quantization must never weaken the requested risk
        # boundary.  For LONG, a higher stop is tighter; for SHORT, a lower
        # stop is tighter.  Therefore LONG rounds up and SHORT rounds down.
        if side == "LONG":
            return self._quantize_up(price, filt["tick"])
        if side == "SHORT":
            return self._quantize_down(price, filt["tick"])
        raise TestnetExchangeError(f"STOP_SIDE_INVALID:{side}")

    # --------------------------- truth ---------------------------

    def quote(self, symbol: str) -> Quote:
        data = self._public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        if not isinstance(data, dict):
            raise TestnetExchangeError("TESTNET_QUOTE_INVALID")
        bid = float(data.get("bidPrice", 0) or 0)
        ask = float(data.get("askPrice", 0) or 0)
        if bid <= 0 or ask < bid:
            raise TestnetExchangeError(f"TESTNET_QUOTE_INVALID:{symbol}")
        timestamp_ms = int(data.get("time") or 0)
        if timestamp_ms <= 0:
            raise TestnetExchangeError("TESTNET_QUOTE_TIME_INVALID")
        return Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)

    def account_snapshot(self) -> AccountSnapshot:
        rows = self._signed_get("/fapi/v3/balance")
        if not isinstance(rows, list):
            raise TestnetExchangeError("TESTNET_BALANCE_RESPONSE_INVALID")
        for row in rows:
            if isinstance(row, dict) and row.get("asset") == "USDT":
                value = float(row.get("availableBalance", 0) or 0)
                if value < 0 or not math.isfinite(value):
                    raise TestnetExchangeError("TESTNET_AVAILABLE_BALANCE_INVALID")
                return AccountSnapshot(available_balance_usd=value)
        raise TestnetExchangeError("TESTNET_USDT_BALANCE_MISSING")

    def position_snapshot(self) -> ExchangePosition | None:
        rows = self._signed_get("/fapi/v3/positionRisk")
        if not isinstance(rows, list):
            raise TestnetExchangeError("TESTNET_POSITION_RESPONSE_INVALID")
        positions: list[ExchangePosition] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            qty = float(row.get("positionAmt", 0) or 0)
            if abs(qty) <= 0:
                continue
            if str(row.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_HEDGE_MODE_UNSUPPORTED")
            entry = float(row.get("entryPrice", 0) or 0)
            if entry <= 0:
                raise TestnetExchangeError("TESTNET_POSITION_ENTRY_PRICE_INVALID")
            positions.append(
                ExchangePosition(
                    symbol=str(row.get("symbol") or ""),
                    side="LONG" if qty > 0 else "SHORT",
                    quantity=abs(qty),
                    entry_price=entry,
                )
            )
        if len(positions) > 1:
            raise TestnetExchangeError("TESTNET_MULTIPLE_POSITIONS_DETECTED")
        return positions[0] if positions else None

    @staticmethod
    def _is_true(value: Any) -> bool:
        return value is True or str(value).lower() == "true"

    @staticmethod
    def _protected_side(order_side: str) -> Side:
        side = str(order_side).upper()
        if side == "SELL":
            return "LONG"
        if side == "BUY":
            return "SHORT"
        raise TestnetExchangeError("TESTNET_STOP_SIDE_INVALID")

    def _stop_ref(self, row: dict[str, Any], *, fallback_client_id: str | None = None, require_trigger_contract: bool = True) -> ProtectiveStopRef:
        if require_trigger_contract and not self._valid_trigger_contract(row):
            raise TestnetExchangeError("TESTNET_STOP_TRIGGER_CONTRACT_MISMATCH")
        trigger = float(row.get("triggerPrice", 0) or 0)
        quantity = float(row.get("quantity") or row.get("origQty") or row.get("actualQty") or 0)
        if trigger <= 0 or quantity <= 0:
            raise TestnetExchangeError("TESTNET_STOP_TRUTH_INVALID")
        algo_id = row.get("algoId")
        client = str(row.get("clientAlgoId") or fallback_client_id or "").strip() or None
        return ProtectiveStopRef(
            symbol=str(row.get("symbol") or ""),
            side=self._protected_side(str(row.get("side") or "")),
            quantity=quantity,
            trigger_price=trigger,
            stop_id=None if algo_id is None else str(algo_id),
            client_stop_id=client,
        )

    def _valid_trigger_contract(self, row):
        return row.get("workingType") == "CONTRACT_PRICE" and not self._is_true(row.get("priceProtect"))

    def _active_stops(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {} if symbol is None else {"symbol": symbol}
        rows = self._signed_get("/fapi/v1/openAlgoOrders", params)
        if not isinstance(rows, list):
            raise TestnetExchangeError("TESTNET_OPEN_ALGO_RESPONSE_INVALID")
        result: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (
                str(row.get("algoType") or "").upper() == "CONDITIONAL"
                and str(row.get("orderType") or row.get("type") or "").upper() == "STOP_MARKET"
                and self._is_true(row.get("reduceOnly"))
            ):
                result.append(row)
        return result

    def protective_stop_snapshot(self, symbol: str) -> ProtectiveStopRef | None:
        active = self._active_stops(symbol)
        if not active:
            return None
        if len(active) > 1:
            raise TestnetExchangeError(f"TESTNET_MULTIPLE_PROTECTIVE_STOPS_DETECTED:{symbol}:{len(active)}")
        if not self._valid_trigger_contract(active[0]):
            return None  # Reconciliation installs the required protection first.
        return self._stop_ref(active[0])

    def validate_protective_stop(self, symbol: str, side: Side, stop_price: float) -> bool:
        if side not in {"LONG", "SHORT"} or not math.isfinite(stop_price) or stop_price <= 0:
            return False
        stop = self._stop_price(symbol, side, stop_price)
        quote = self.quote(symbol)
        return stop < quote.bid if side == "LONG" else stop > quote.ask

    # --------------------------- entry ---------------------------

    def set_leverage(self, symbol: str, leverage: int) -> None:
        gate = self.guard.preflight()
        if not gate["armed"]:
            raise TestnetExchangeError(f"TESTNET_TRADING_NOT_ARMED:{gate['reason']}")
        data = self._signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": int(leverage)})
        if not isinstance(data, dict) or int(data.get("leverage", 0) or 0) != int(leverage):
            raise TestnetExchangeError("TESTNET_LEVERAGE_NOT_CONFIRMED")

    def _query_order(self, symbol: str, client_order_id: str) -> dict[str, Any] | None:
        try:
            row = self._signed_get("/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_order_id})
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise
        if not isinstance(row, dict):
            raise TestnetExchangeError("TESTNET_ORDER_QUERY_INVALID")
        return row

    def _query_order_by_id(self, symbol: str, order_id: str) -> dict[str, Any] | None:
        try:
            row = self._signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": int(order_id)})
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise
        if not isinstance(row, dict):
            raise TestnetExchangeError("TESTNET_ORDER_QUERY_INVALID")
        return row

    @staticmethod
    def _fill_from_order(order: dict[str, Any]) -> Fill | None:
        executed = float(order.get("executedQty", 0) or 0)
        if executed <= 0:
            return None

        # Binance order avgPrice may be rounded more coarsely than the
        # aggregate position entryPrice. When available, cumQuote /
        # executedQty is the higher-precision aggregate fill basis and keeps
        # durable entry identity aligned with later position reconciliation.
        cum_quote = float(order.get("cumQuote", 0) or 0)
        if cum_quote > 0:
            avg = cum_quote / executed
        else:
            avg = float(order.get("avgPrice", 0) or 0)
            if avg <= 0:
                raise TestnetExchangeError("TESTNET_FILL_PRICE_MISSING")

        order_id = str(order.get("orderId") or "").strip()
        client_id = str(order.get("clientOrderId") or "").strip()
        timestamp_ms = int(order.get("updateTime") or order.get("time") or 0)
        if not order_id or not client_id or timestamp_ms <= 0:
            raise TestnetExchangeError("TESTNET_FILL_IDENTITY_MISSING")
        return Fill(avg, executed, order_id, client_id, timestamp_ms)

    def open_market(self, plan: EntryPlan, *, client_order_id: str) -> Fill:
        # Everything in this block occurs before the capital-bearing POST.
        # Convert only known Testnet adapter/guard failures into the generic
        # EntryNotSubmitted contract so EntryLifecycle can safely clear its
        # journal instead of treating a deterministic local refusal as an
        # ambiguous order write.
        try:
            quantity = self._quantity(plan.symbol, plan.quantity)
            if quantity * plan.expected_entry_price < self._filters[plan.symbol].get("min_notional", 0):
                raise TestnetExchangeError("ENTRY_MIN_NOTIONAL_NOT_MET")
            position = self.position_snapshot()
            self.guard.authorize_entry(
                symbol=plan.symbol,
                quantity=quantity,
                price=plan.expected_entry_price,
                position=position,
            )
        except TestnetExchangeError as exc:
            raise TestnetEntryNotSubmitted(str(exc)) from exc
        params = {
            "symbol": plan.symbol,
            "side": "BUY" if plan.side == "LONG" else "SELL",
            "type": "MARKET",
            "quantity": format(Decimal(str(quantity)), "f"),
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        order = self._signed_post("/fapi/v1/order", params, ambiguous=True)
        if not isinstance(order, dict):
            raise TestnetExchangeError("TESTNET_ENTRY_RESPONSE_INVALID")
        fill = self._fill_from_order(order)
        if str(order.get("status") or "").upper() != "FILLED" or fill is None:
            raise TestnetExchangeError("TESTNET_ENTRY_NOT_CONFIRMED_FILLED")
        if fill.client_order_id != client_order_id:
            raise TestnetExchangeError("TESTNET_ENTRY_CLIENT_ID_MISMATCH")
        position = self.position_snapshot()
        if position is None or position.symbol != plan.symbol or position.side != plan.side:
            raise TestnetExchangeError("TESTNET_ENTRY_POSITION_NOT_CONFIRMED")
        return fill

    def recover_inflight_entry(self, plan: EntryPlan, *, client_order_id: str) -> Fill | None:
        deadline = time.monotonic() + self.config.entry_resolution_timeout_seconds
        last_status = "UNKNOWN"
        while time.monotonic() < deadline:
            order = self._query_order(plan.symbol, client_order_id)
            position = self.position_snapshot()
            if order is None:
                last_status = "MISSING"
                if position is None:
                    time.sleep(0.05)
                    continue
                if position.symbol != plan.symbol or position.side != plan.side:
                    raise TestnetExchangeError("TESTNET_INFLIGHT_ENTRY_POSITION_MISMATCH")
            else:
                status = str(order.get("status") or "").upper()
                last_status = status or "UNKNOWN"
                fill = self._fill_from_order(order)
                terminal = status in {"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"}
                if fill is not None and not terminal:
                    # A partially executed entry already bears risk. Protect
                    # proven exposure before trying to cancel the remainder.
                    if position is None or position.symbol != plan.symbol or position.side != plan.side:
                        raise TestnetExchangeError("TESTNET_PARTIAL_POSITION_UNRESOLVED")
                    distance = plan.initial_risk_usd / position.quantity
                    stop = position.entry_price - distance if plan.side == "LONG" else position.entry_price + distance
                    try:
                        self.ensure_protective_stop(plan.symbol, plan.side, position.quantity, stop)
                    except Exception:
                        # Preserve the journal even when flattening succeeds.
                        self.close_position(plan.symbol, plan.side, reason="PARTIAL_ENTRY_PROTECTION_FAILED")
                        raise
                    try:
                        self._signed_delete("/fapi/v1/order", {"symbol": plan.symbol, "origClientOrderId": client_order_id}, ambiguous=True)
                    except TestnetExchangeError:
                        pass  # Cancellation is not proof; query the identity again.
                if terminal and fill is not None:
                    if fill.client_order_id != client_order_id:
                        raise TestnetExchangeError("TESTNET_INFLIGHT_ENTRY_IDENTITY_MISMATCH")
                    if position is None:
                        # A historical fill is valid even after its exposure closed.
                        return fill
                    if position.symbol != plan.symbol or position.side != plan.side:
                        raise TestnetExchangeError("TESTNET_INFLIGHT_ENTRY_POSITION_MISMATCH")
                    return fill
                if terminal and fill is None and position is None:
                    return None
            time.sleep(0.05)
        # Repeated "not found" after a timed-out POST is not proof that a
        # delayed write cannot arrive. Keep the journal and block new entries.
        raise TestnetExchangeError(f"TESTNET_INFLIGHT_ENTRY_UNRESOLVED:{last_status}")

    # --------------------------- stops ---------------------------

    @staticmethod
    def deterministic_stop_client_id(symbol: str, side: Side, quantity: float, stop_price: float) -> str:
        seed = f"CONTRACT_PRICE_NO_PRICE_PROTECT_V2|{symbol}|{side}|{quantity:.12g}|{stop_price:.12g}"
        return "NBV3SL-" + hashlib.sha256(seed.encode()).hexdigest()[:24]

    def _query_algo_order(
        self,
        *,
        algo_id: str | None = None,
        client_algo_id: str | None = None,
    ) -> dict[str, Any] | None:
        if algo_id is None and not client_algo_id:
            raise TestnetExchangeError("TESTNET_ALGO_QUERY_ID_MISSING")
        params: dict[str, Any]
        if algo_id is not None:
            params = {"algoId": int(algo_id)}
        else:
            params = {"clientAlgoId": str(client_algo_id)}
        try:
            row = self._signed_get("/fapi/v1/algoOrder", params)
        except TestnetExchangeError as exc:
            text = str(exc)
            if "-2013" in text or "Order does not exist" in text:
                return None
            raise
        if not isinstance(row, dict):
            raise TestnetExchangeError("TESTNET_ALGO_QUERY_INVALID")
        return row

    def _resolve_stop_identity(self, symbol: str, client_id: str) -> ProtectiveStopRef:
        deadline = time.monotonic() + self.config.stop_resolution_timeout_seconds
        while time.monotonic() < deadline:
            row = self._query_algo_order(client_algo_id=client_id)
            if row is not None:
                status = str(row.get("algoStatus") or "").upper()
                if status == "NEW":
                    return self._stop_ref(row, fallback_client_id=client_id)
                if status in {"TRIGGERED", "FINISHED"}:
                    raise TestnetExchangeError("TESTNET_STOP_TRIGGERED_DURING_PLACEMENT")
                if status in {"CANCELED", "EXPIRED", "REJECTED"}:
                    raise TestnetExchangeError(f"TESTNET_STOP_NOT_ACTIVE:{status}")
            for active in self._active_stops(symbol):
                if str(active.get("clientAlgoId") or "") == client_id:
                    return self._stop_ref(active, fallback_client_id=client_id)
            time.sleep(0.05)
        raise TestnetExchangeError("TESTNET_AMBIGUOUS_STOP_RESOLUTION_TIMEOUT")

    def _place_stop(self, symbol: str, side: Side, quantity: float, stop_price: float) -> ProtectiveStopRef:
        qty = self._quantity(symbol, quantity)
        stop = self._stop_price(symbol, side, stop_price)
        if not self.validate_protective_stop(symbol, side, stop):
            raise TestnetExchangeError("TESTNET_STOP_ALREADY_BREACHED_OR_INVALID")
        client_id = self.deterministic_stop_client_id(symbol, side, qty, stop)

        existing = self._query_algo_order(client_algo_id=client_id)
        if existing is not None and str(existing.get("algoStatus") or "").upper() == "NEW":
            ref = self._stop_ref(existing, fallback_client_id=client_id)
            self._assert_stop_match(ref, symbol, side, qty, stop)
            return ref

        params = {
            "algoType": "CONDITIONAL",
            "symbol": symbol,
            "side": "SELL" if side == "LONG" else "BUY",
            "type": "STOP_MARKET",
            "quantity": format(Decimal(str(qty)), "f"),
            "triggerPrice": format(Decimal(str(stop)), "f"),
            "workingType": "CONTRACT_PRICE",
            "priceProtect": "false",
            "reduceOnly": "true",
            "clientAlgoId": client_id,
        }
        try:
            data = self._signed_post("/fapi/v1/algoOrder", params, ambiguous=True)
        except AmbiguousExecutionError:
            return self._resolve_stop_identity(symbol, client_id)
        if not isinstance(data, dict):
            return self._resolve_stop_identity(symbol, client_id)
        algo_id = data.get("algoId")
        if algo_id is None:
            return self._resolve_stop_identity(symbol, client_id)
        row = self._query_algo_order(algo_id=str(algo_id))
        if row is None or str(row.get("algoStatus") or "").upper() != "NEW":
            return self._resolve_stop_identity(symbol, client_id)
        ref = self._stop_ref(row, fallback_client_id=client_id)
        self._assert_stop_match(ref, symbol, side, qty, stop)
        return ref

    @staticmethod
    def _assert_stop_match(ref: ProtectiveStopRef, symbol: str, side: Side, qty: float, stop: float) -> None:
        if ref.symbol != symbol or ref.side != side:
            raise TestnetExchangeError("TESTNET_STOP_IDENTITY_MISMATCH")
        if not math.isclose(ref.quantity, qty, rel_tol=1e-9, abs_tol=1e-12):
            raise TestnetExchangeError("TESTNET_STOP_QUANTITY_MISMATCH")
        if not math.isclose(ref.trigger_price, stop, rel_tol=1e-9, abs_tol=1e-12):
            raise TestnetExchangeError("TESTNET_STOP_TRIGGER_MISMATCH")

    def _cancel_algo(self, row: dict[str, Any]) -> None:
        params: dict[str, Any] = {"symbol": str(row.get("symbol") or "")}
        if row.get("algoId") is not None:
            params["algoId"] = int(row["algoId"])
        elif row.get("clientAlgoId"):
            params["clientAlgoId"] = str(row["clientAlgoId"])
        else:
            raise TestnetExchangeError("TESTNET_STOP_CANCEL_ID_MISSING")
        try:
            self._signed_delete("/fapi/v1/algoOrder", params, ambiguous=True)
        except AmbiguousExecutionError:
            # Cancellation ambiguity is resolved from open-stop truth below.
            return

    def _prune_stops(self, symbol: str, keep: ProtectiveStopRef | None) -> None:
        keep_id = None if keep is None else keep.stop_id
        keep_client = None if keep is None else keep.client_stop_id
        for row in self._active_stops(symbol):
            same = (
                (keep_id is not None and str(row.get("algoId") or "") == keep_id)
                or (keep_client is not None and str(row.get("clientAlgoId") or "") == keep_client)
            )
            if not same:
                self._cancel_algo(row)
        remaining = self._active_stops(symbol)
        if keep is None:
            if remaining:
                raise TestnetExchangeError("TESTNET_ORPHAN_STOP_CLEANUP_UNVERIFIED")
            return
        matches = [
            row for row in remaining
            if (keep.stop_id is not None and str(row.get("algoId") or "") == keep.stop_id)
            or (keep.client_stop_id is not None and str(row.get("clientAlgoId") or "") == keep.client_stop_id)
        ]
        if len(matches) != 1:
            raise TestnetExchangeError("TESTNET_REPLACEMENT_STOP_NOT_VERIFIED")
        if len(remaining) != 1:
            raise TestnetExchangeError("TESTNET_OBSOLETE_STOP_PRUNE_UNVERIFIED")

    def ensure_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef:
        active = self._active_stops(symbol)
        if len(active) > 1:
            raise TestnetExchangeError("TESTNET_MULTIPLE_PROTECTIVE_STOPS_DETECTED")
        if len(active) == 1:
            if not self._valid_trigger_contract(active[0]):
                return self.replace_protective_stop(symbol, side, quantity, stop_price)
            ref = self._stop_ref(active[0])
            if ref.side == side and math.isclose(ref.quantity, self._quantity(symbol, quantity), rel_tol=1e-9, abs_tol=1e-12):
                requested = self._stop_price(symbol, side, stop_price)
                # Existing tighter protection is acceptable; never loosen it.
                tighter = ref.trigger_price >= requested if side == "LONG" else ref.trigger_price <= requested
                if tighter:
                    return ref
        return self.replace_protective_stop(symbol, side, quantity, stop_price)

    def replace_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef:
        old = self._active_stops(symbol)
        new_ref = self._place_stop(symbol, side, quantity, stop_price)
        # New protection is independently visible before any obsolete stop is removed.
        visible = self._active_stops(symbol)
        if not any(
            (new_ref.stop_id is not None and str(row.get("algoId") or "") == new_ref.stop_id)
            or (new_ref.client_stop_id is not None and str(row.get("clientAlgoId") or "") == new_ref.client_stop_id)
            for row in visible
        ):
            raise TestnetExchangeError("TESTNET_NEW_STOP_NOT_VISIBLE_BEFORE_PRUNE")
        # Do not allow the replacement itself to be looser than existing known protection.
        for row in old:
            ref = self._stop_ref(row, require_trigger_contract=False)
            if ref.side != side:
                raise TestnetExchangeError("TESTNET_EXISTING_STOP_SIDE_MISMATCH")
            if side == "LONG" and new_ref.trigger_price + 1e-12 < ref.trigger_price:
                raise TestnetExchangeError("TESTNET_STOP_REPLACEMENT_WOULD_LOOSEN")
            if side == "SHORT" and new_ref.trigger_price - 1e-12 > ref.trigger_price:
                raise TestnetExchangeError("TESTNET_STOP_REPLACEMENT_WOULD_LOOSEN")
        self._prune_stops(symbol, new_ref)
        return new_ref

    # --------------------------- close evidence ---------------------------

    @staticmethod
    def _local_view(local: OpenPosition | EntryInflight) -> dict[str, Any]:
        if isinstance(local, OpenPosition):
            return {
                "symbol": local.symbol,
                "side": local.side,
                "quantity": local.quantity,
                "entry_price": local.entry_price,
                "entry_timestamp_ms": local.entry_timestamp_ms,
                "entry_order_id": local.entry_order_id,
                "entry_client_order_id": local.entry_client_order_id,
                "protective_stop_id": local.protective_stop.stop_id,
                "protective_stop_client_id": local.protective_stop.client_stop_id,
            }
        if local.fill is None:
            raise TestnetExchangeError("TESTNET_INFLIGHT_CLOSE_RECOVERY_FILL_MISSING")
        return {
            "symbol": local.plan.symbol,
            "side": local.plan.side,
            "quantity": local.fill.quantity,
            "entry_price": local.fill.price,
            "entry_timestamp_ms": local.fill.timestamp_ms,
            "entry_order_id": local.fill.order_id,
            "entry_client_order_id": local.fill.client_order_id,
            "protective_stop_id": None,
            "protective_stop_client_id": None,
        }

    def _user_trades_since(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        return self._complete_history("/fapi/v1/userTrades", {"symbol": symbol}, start_ms, end_ms)

    def _complete_history(self, path: str, params: dict[str, Any], start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        """Split saturated time windows rather than silently dropping pages.

        A saturated single millisecond cannot prove completeness through this
        interface. Leave accounting unresolved instead of inventing a result.
        """
        rows: list[dict[str, Any]] = []
        windows = [(start_ms, end_ms)]
        while windows:
            start, end = windows.pop()
            if start > end:
                continue
            if end - start >= USER_TRADES_MAX_WINDOW_MS:
                split = start + USER_TRADES_MAX_WINDOW_MS - 1
                windows.extend([(split + 1, end), (start, split)])
                continue
            page = self._signed_get(path, {**params, "startTime": start, "endTime": end, "limit": 1000})
            if not isinstance(page, list):
                raise TestnetExchangeError("TESTNET_HISTORY_RESPONSE_INVALID")
            if any(not isinstance(row, dict) for row in page):
                raise TestnetExchangeError("TESTNET_HISTORY_ROW_INVALID")
            if len(page) >= 1000:
                if start == end:
                    raise TestnetExchangeError("TESTNET_HISTORY_MILLISECOND_SATURATED")
                split = (start + end) // 2
                windows.extend([(split + 1, end), (start, split)])
                continue
            rows.extend(page)
        return rows

    def _all_orders_between(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        return self._complete_history("/fapi/v1/allOrders", {"symbol": symbol}, start_ms, end_ms)

    def _all_algo_orders_between(self, symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        return self._complete_history("/fapi/v1/allAlgoOrders", {"symbol": symbol}, start_ms, end_ms)

    def _realized_pnl_income(self, symbol: str, start_ms: int, end_ms: int) -> float | None:
        rows = self._complete_history(
            "/fapi/v1/income",
            {
                "symbol": symbol,
                "incomeType": "REALIZED_PNL",
            },
            start_ms, end_ms,
        )
        if not isinstance(rows, list):
            raise TestnetExchangeError("TESTNET_INCOME_RESPONSE_INVALID")
        relevant = [row for row in rows if isinstance(row, dict) and str(row.get("incomeType") or "") == "REALIZED_PNL"]
        if not relevant:
            return None
        return sum(float(row.get("income", 0) or 0) for row in relevant)

    @staticmethod
    def _theoretical(local: dict[str, Any], price: float, qty: float) -> float:
        entry = float(local["entry_price"])
        return (price - entry) * qty if local["side"] == "LONG" else (entry - price) * qty

    def _recover_reason(self, local: dict[str, Any], order_ids: tuple[str, ...], closed_ms: int) -> str:
        close_ids = set(order_ids)
        sid = local.get("protective_stop_id")
        scid = local.get("protective_stop_client_id")
        if sid is not None or scid:
            try:
                row = self._query_algo_order(
                    algo_id=None if sid is None else str(sid),
                    client_algo_id=None if sid is not None else str(scid),
                )
                if row is not None:
                    actual = str(row.get("actualOrderId") or "").strip()
                    if str(row.get("orderType") or "").upper() == "STOP_MARKET" and self._is_true(row.get("reduceOnly")) and actual in close_ids:
                        return "PROTECTIVE_STOP_TRIGGERED"
            except Exception:
                pass
        try:
            for row in self._all_algo_orders_between(local["symbol"], int(local["entry_timestamp_ms"]), closed_ms):
                actual = str(row.get("actualOrderId") or "").strip()
                if str(row.get("orderType") or "").upper() == "STOP_MARKET" and self._is_true(row.get("reduceOnly")) and actual in close_ids:
                    return "PROTECTIVE_STOP_TRIGGERED"
        except Exception:
            pass
        return "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART"

    def _settle_from_trades(self, local: dict[str, Any], rows: list[dict[str, Any]]) -> CloseFill:
        symbol = local["symbol"]
        side = local["side"]
        target = float(local["quantity"])
        entry_order_id = str(local.get("entry_order_id") or "")
        entry_ts = int(local["entry_timestamp_ms"])
        exit_side = "SELL" if side == "LONG" else "BUY"
        entry_side = "BUY" if side == "LONG" else "SELL"
        step = self._filters[symbol]["market_step"]
        tolerance = max(step / 2.0, 1e-12)
        exits: list[dict[str, Any]] = []
        qty = 0.0
        for row in rows:
            if int(row.get("time", 0) or 0) < entry_ts:
                continue
            if str(row.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_HEDGE_MODE_UNSUPPORTED")
            if entry_order_id and str(row.get("orderId") or "") == entry_order_id:
                continue
            trade_side = str(row.get("side") or "").upper()
            rqty = float(row.get("qty", 0) or 0)
            price = float(row.get("price", 0) or 0)
            if rqty <= 0 or price <= 0:
                raise TestnetExchangeError("TESTNET_CLOSE_HISTORY_TRADE_INVALID")
            if trade_side == entry_side:
                raise TestnetExchangeError("TESTNET_POSITION_MUTATED_WHILE_EXECUTION_OFFLINE")
            if trade_side == exit_side:
                exits.append(row)
                qty += rqty
        if qty < target - tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_INCOMPLETE")
        if qty > target + tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_AMBIGUOUS_QUANTITY")
        if not exits:
            raise TestnetExchangeError("TESTNET_CLOSE_EVIDENCE_MISSING")
        price = sum(float(row["qty"]) * float(row["price"]) for row in exits) / qty
        realized = sum(float(row.get("realizedPnl", 0) or 0) for row in exits)
        closed_ms = max(int(row.get("time", 0) or 0) for row in exits)
        order_ids = tuple(sorted({str(row.get("orderId")) for row in exits if row.get("orderId") is not None}))
        theoretical = self._theoretical(local, price, qty)
        return CloseFill(
            price=price,
            timestamp_ms=closed_ms,
            reason=self._recover_reason(local, order_ids, closed_ms),
            realized_pnl_usd=realized,
            order_ids=order_ids,
            source="USER_TRADES_RECOVERY",
            theoretical_pnl_usd=theoretical,
            pnl_variance_usd=realized - theoretical,
        )

    def _settle_from_orders_income(self, local: dict[str, Any], end_ms: int) -> CloseFill:
        symbol = local["symbol"]
        side = local["side"]
        target = float(local["quantity"])
        entry_order_id = str(local.get("entry_order_id") or "")
        entry_ts = int(local["entry_timestamp_ms"])
        exit_side = "SELL" if side == "LONG" else "BUY"
        entry_side = "BUY" if side == "LONG" else "SELL"
        step = self._filters[symbol]["market_step"]
        tolerance = max(step / 2.0, 1e-12)
        exits: list[dict[str, Any]] = []
        qty = 0.0
        for row in self._all_orders_between(symbol, entry_ts, end_ms):
            oid = str(row.get("orderId") or "")
            rqty = float(row.get("executedQty", 0) or 0)
            if rqty <= 0 or (entry_order_id and oid == entry_order_id):
                continue
            if str(row.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_CLOSE_ORDER_HISTORY_HEDGE_MODE_UNSUPPORTED")
            order_side = str(row.get("side") or "").upper()
            if order_side == entry_side:
                raise TestnetExchangeError("TESTNET_POSITION_MUTATED_WHILE_EXECUTION_OFFLINE")
            if order_side != exit_side:
                continue
            if str(row.get("status") or "").upper() != "FILLED":
                continue
            price = float(row.get("avgPrice", 0) or 0)
            if price <= 0:
                raise TestnetExchangeError("TESTNET_CLOSE_ORDER_HISTORY_PRICE_INVALID")
            exits.append(row)
            qty += rqty
        if qty < target - tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_INCOMPLETE")
        if qty > target + tolerance:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_AMBIGUOUS_QUANTITY")
        if not exits:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_EVIDENCE_MISSING")
        # A time-bucket income total cannot establish ownership of a close.
        trades = [trade for order in exits for trade in self._order_trades(symbol, str(order["orderId"]))]
        return self._settle_from_trades(local, trades)

    def _settle_from_finished_stop(self, local: dict[str, Any], end_ms: int) -> CloseFill:
        symbol = local["symbol"]
        side = local["side"]
        target = float(local["quantity"])
        entry_ts = int(local["entry_timestamp_ms"])
        expected_side = "SELL" if side == "LONG" else "BUY"
        step = self._filters[symbol]["market_step"]
        tolerance = max(step / 2.0, 1e-12)
        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for algo in self._all_algo_orders_between(symbol, entry_ts, end_ms):
            if str(algo.get("algoStatus") or "").upper() != "FINISHED":
                continue
            if str(algo.get("orderType") or "").upper() != "STOP_MARKET" or not self._is_true(algo.get("reduceOnly")):
                continue
            if str(algo.get("side") or "").upper() != expected_side:
                continue
            if str(algo.get("positionSide") or "BOTH").upper() != "BOTH":
                raise TestnetExchangeError("TESTNET_ALGO_SETTLEMENT_HEDGE_MODE_UNSUPPORTED")
            actual_order_id = str(algo.get("actualOrderId") or "").strip()
            algo_qty = float(algo.get("actualQty") or algo.get("quantity") or 0)
            if not actual_order_id or abs(algo_qty - target) > tolerance:
                continue
            order = self._query_order_by_id(symbol, actual_order_id)
            if order is None or str(order.get("status") or "").upper() != "FILLED":
                continue
            candidates.append((algo, order))
        if not candidates:
            raise TestnetExchangeError("TESTNET_ALGO_CLOSE_EVIDENCE_MISSING")
        if len(candidates) > 1:
            raise TestnetExchangeError("TESTNET_ALGO_CLOSE_EVIDENCE_AMBIGUOUS")
        _algo, order = candidates[0]
        qty = float(order.get("executedQty", 0) or 0)
        price = float(order.get("avgPrice", 0) or 0)
        close_ms = int(order.get("updateTime") or order.get("time") or 0)
        if abs(qty - target) > tolerance or price <= 0 or close_ms <= 0:
            raise TestnetExchangeError("TESTNET_ALGO_CLOSE_ORDER_INVALID")
        return self._settle_from_trades(local, self._order_trades(symbol, str(order["orderId"])))

    def _recover_closed_local(self, local: dict[str, Any]) -> CloseFill:
        if self.position_snapshot() is not None:
            raise TestnetExchangeError("TESTNET_RECOVERY_POSITION_NOT_FLAT")
        symbol = str(local.get("symbol") or "")
        entry_ts = int(local.get("entry_timestamp_ms") or 0)
        if symbol not in self._filters or entry_ts <= 0:
            raise TestnetExchangeError("TESTNET_RECOVERY_LOCAL_POSITION_INVALID")
        last_error: Exception | None = None
        for attempt in range(self.config.close_settlement_retries):
            now_ms = int(time.time() * 1000)
            try:
                close = self._settle_from_trades(local, self._user_trades_since(symbol, entry_ts, now_ms))
                self._prune_stops(symbol, None)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                if "INCOMPLETE" not in str(exc) and "MISSING" not in str(exc):
                    raise
            try:
                close = self._settle_from_finished_stop(local, now_ms)
                self._prune_stops(symbol, None)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                if "MISSING" not in str(exc) and "INCOMPLETE" not in str(exc):
                    raise
            try:
                close = self._settle_from_orders_income(local, now_ms)
                self._prune_stops(symbol, None)
                return close
            except TestnetExchangeError as exc:
                last_error = exc
                if "MISSING" not in str(exc) and "INCOMPLETE" not in str(exc):
                    raise
            if attempt + 1 < self.config.close_settlement_retries:
                time.sleep(self.config.close_settlement_retry_seconds)
        raise TestnetExchangeError(f"TESTNET_EXTERNAL_CLOSE_SETTLEMENT_FAILED:{last_error}")

    def recover_closed_position(self, local_position: OpenPosition) -> CloseFill:
        return self._recover_closed_local(self._local_view(local_position))

    def recover_closed_inflight_entry(self, inflight: EntryInflight) -> CloseFill:
        return self._recover_closed_local(self._local_view(inflight))

    def cleanup_orphan_protective_stops(self) -> int:
        if self.position_snapshot() is not None:
            raise TestnetExchangeError("TESTNET_ORPHAN_CLEANUP_POSITION_OPEN")
        active = self._active_stops(None)
        for row in active:
            self._cancel_algo(row)
        if self._active_stops(None):
            raise TestnetExchangeError("TESTNET_ORPHAN_STOP_CLEANUP_UNVERIFIED")
        return len(active)

    # --------------------------- direct close ---------------------------

    @staticmethod
    def deterministic_close_client_id(position: ExchangePosition, reason: str) -> str:
        seed = f"{position.symbol}|{position.side}|{position.quantity:.12g}|{position.entry_price:.12g}|{reason}"
        return "NBV3C-" + hashlib.sha256(seed.encode()).hexdigest()[:24]

    def _order_trades(self, symbol: str, order_id: str) -> list[dict[str, Any]]:
        # Start at the oldest trade ID: an unqualified first page returns the
        # most recent fills and may silently omit the beginning of an order.
        result = []
        cursor = 0
        for _ in range(100):
            page = self._signed_get("/fapi/v1/userTrades", {
                "symbol": symbol, "orderId": int(order_id), "fromId": cursor, "limit": 1000,
            })
            if not isinstance(page, list):
                raise TestnetExchangeError("TESTNET_ORDER_TRADES_INVALID")
            for row in page:
                if not isinstance(row, dict) or str(row.get("orderId")) != str(order_id) or row.get("symbol") != symbol:
                    raise TestnetExchangeError("TESTNET_ORDER_TRADES_IDENTITY_MISMATCH")
                try:
                    numbers = [float(row[key]) for key in ("qty", "price", "realizedPnl")]
                    valid = all(math.isfinite(value) for value in numbers) and min(numbers[:2]) > 0 and int(row["time"]) > 0
                except (KeyError, TypeError, ValueError):
                    valid = False
                if not valid:
                    raise TestnetExchangeError("TESTNET_ORDER_TRADES_INVALID")
            result.extend(page)
            if len(page) < 1000:
                ids = [str(row["id"]) for row in result if "id" in row]
                if len(ids) != len(set(ids)):
                    raise TestnetExchangeError("TESTNET_ORDER_TRADES_DUPLICATE")
                return result
            try:
                ids = [int(row["id"]) for row in page]
            except (KeyError, TypeError, ValueError) as exc:
                raise TestnetExchangeError("TESTNET_ORDER_TRADES_CURSOR_MISSING") from exc
            if min(ids) < cursor or len(set(ids)) != len(ids):
                raise TestnetExchangeError("TESTNET_ORDER_TRADES_CURSOR_INVALID")
            cursor = max(ids) + 1
        raise TestnetExchangeError("TESTNET_ORDER_TRADES_INCOMPLETE")

    def _settle_close_order(self, position: ExchangePosition, order: dict[str, Any], reason: str) -> CloseFill:
        order_id = order.get("orderId")
        if order_id is None:
            raise TestnetExchangeError("TESTNET_CLOSE_ORDER_ID_MISSING")
        for attempt in range(self.config.close_settlement_retries):
            rows = self._order_trades(position.symbol, str(order_id))
            if isinstance(rows, list) and rows:
                qty = sum(float(row.get("qty", 0) or 0) for row in rows if isinstance(row, dict))
                if abs(qty - position.quantity) <= max(self._filters[position.symbol]["market_step"] / 2.0, 1e-12) and qty > 0:
                    price = sum(float(row["qty"]) * float(row["price"]) for row in rows if isinstance(row, dict)) / qty
                    realized = sum(float(row.get("realizedPnl", 0) or 0) for row in rows if isinstance(row, dict))
                    ts = max(int(row.get("time", 0) or 0) for row in rows if isinstance(row, dict))
                    theoretical = (price - position.entry_price) * qty if position.side == "LONG" else (position.entry_price - price) * qty
                    return CloseFill(price, ts, reason, realized, (str(order_id),), "USER_TRADES_ORDER", theoretical, realized - theoretical)
            if attempt + 1 < self.config.close_settlement_retries:
                time.sleep(self.config.close_settlement_retry_seconds)
        raise TestnetExchangeError("TESTNET_CLOSE_ACCOUNTING_UNAVAILABLE")

    def close_position(self, symbol: str, side: Side, *, reason: str) -> CloseFill:
        position = self.position_snapshot()
        if position is None:
            raise TestnetExchangeError("TESTNET_CLOSE_POSITION_ALREADY_FLAT_USE_RECOVERY")
        if position.symbol != symbol or position.side != side:
            raise TestnetExchangeError("TESTNET_CLOSE_POSITION_MISMATCH")
        quantity = self._quantity(position.symbol, position.quantity)
        client_id = self.deterministic_close_client_id(position, reason)
        params = {
            "symbol": position.symbol,
            "side": "SELL" if position.side == "LONG" else "BUY",
            "type": "MARKET",
            "quantity": format(Decimal(str(quantity)), "f"),
            "reduceOnly": "true",
            "newClientOrderId": client_id,
            "newOrderRespType": "RESULT",
        }
        try:
            order = self._signed_post("/fapi/v1/order", params, ambiguous=True)
        except AmbiguousExecutionError:
            order = self._query_order(position.symbol, client_id)
            if order is None:
                raise
        if not isinstance(order, dict):
            raise TestnetExchangeError("TESTNET_CLOSE_RESPONSE_INVALID")
        # A response object is not proof of flatness.
        if self.position_snapshot() is not None:
            raise TestnetExchangeError("TESTNET_CLOSE_NOT_CONFIRMED_FLAT")
        close = self._settle_close_order(position, order, reason)
        self._prune_stops(position.symbol, None)
        return close

    def preflight_report(self, symbol: str = "BTCUSDT") -> dict[str, Any]:
        quote = self.quote(symbol)
        position = self.position_snapshot()
        return {
            "adapter": "BINANCE_USDM_TESTNET_V3",
            "rest_host": urlparse(self.config.base_url).hostname,
            "ws_host": urlparse(self.config.ws_base_url).hostname,
            "connected": self._connected,
            "instance_lock_held": self._instance_lock.held,
            "credentials_loaded": bool(self.config.api_key and self.config.api_secret),
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
            "trading_gate": self.guard.preflight(),
            "real_money": False,
            "research_evidence": False,
            "evidence_lineage": "TESTNET_OPERATIONAL_ONLY",
        }
