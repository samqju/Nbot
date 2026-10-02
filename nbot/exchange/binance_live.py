"""Mainnet USD-M transport with explicitly isolated configuration and session state.

Reuses the tested USD-M order/stop/reconciliation implementation. Construction
and account preflight grant no entry permission. Runtime integration separately
controls recommendation authority and operator authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Mapping
from urllib.request import HTTPRedirectHandler, build_opener

from .binance_testnet import (
    BinanceTestnetExchange, TestnetExchangeConfig, TestnetTradingGuard,
    TestnetExchangeError,
)

LIVE_REST_BASE_URL = "https://fapi.binance.com"
LIVE_WS_BASE_URL = "wss://fstream.binance.com"


@dataclass(frozen=True, slots=True)
class LiveExchangeConfig(TestnetExchangeConfig):
    PROFILE_NAME: ClassVar[str] = "live-trade"
    REST_HOST: ClassVar[str] = "fapi.binance.com"
    WS_HOST: ClassVar[str] = "fstream.binance.com"
    base_url: str = LIVE_REST_BASE_URL
    ws_base_url: str = LIVE_WS_BASE_URL
    risk_per_trade_usd: float = 0.25
    leverage: int = 1
    max_session_entries: int = 1
    max_entry_notional_usd: float = 25.0

    @classmethod
    def from_env(cls, *, repo_root: Path, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        return cls(
            api_key=env.get("LIVE_API_KEY", "").strip(),
            api_secret=env.get("LIVE_API_SECRET", "").strip(),
            repo_root=Path(repo_root),
            base_url=env.get("LIVE_BASE_URL", LIVE_REST_BASE_URL).strip(),
            ws_base_url=env.get("LIVE_WS_BASE_URL", LIVE_WS_BASE_URL).strip(),
            request_timeout_seconds=float(env.get("LIVE_REST_TIMEOUT_SECONDS", "5")),
            recv_window_ms=int(env.get("LIVE_RECV_WINDOW_MS", "5000")),
            risk_per_trade_usd=float(env.get("LIVE_RISK_PER_TRADE_USD", "0.25")),
            leverage=int(env.get("LIVE_LEVERAGE", "1")),
            max_session_entries=int(env.get("LIVE_MAX_SESSION_ENTRIES", "1")),
            max_entry_notional_usd=float(env.get("LIVE_MAX_ENTRY_NOTIONAL_USD", "25")),
        )

    def authorization_digest(self):
        value = {
            "api_key_digest": hashlib.sha256(self.api_key.encode()).hexdigest(),
            "notional": self.max_entry_notional_usd, "risk": self.risk_per_trade_usd,
            "leverage": self.leverage, "entries": self.max_session_entries,
            "profile": self.PROFILE_NAME,
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

    @property
    def resolved_arm_file(self):
        return self.arm_file or self.repo_root / "runtime/execution/real/LIVE_TRADING_ARMED"

    @property
    def resolved_guard_state_path(self):
        return self.guard_state_path or self.repo_root / "data/execution/real/live_trading_guard.json"

    @property
    def resolved_instance_lock_path(self):
        return self.instance_lock_path or self.repo_root / "runtime/execution/real/execution.lock"

    def validate(self, *, require_credentials=True):
        # The parent validates against this class's immutable host allowlist.
        try:
            super(LiveExchangeConfig, self).validate(require_credentials=require_credentials)
        except ValueError as exc:
            raise ValueError(str(exc).replace("TESTNET_", "LIVE_")) from exc
        for name in ("recv_window_ms", "max_session_entries", "close_settlement_retries"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("LIVE_INTEGER_LIMIT_INVALID:" + name)
        for name in ("entry_resolution_timeout_seconds", "stop_resolution_timeout_seconds",
                     "close_settlement_retry_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError("LIVE_TIMEOUT_INVALID:" + name)
        if (isinstance(self.risk_per_trade_usd, bool) or not math.isfinite(self.risk_per_trade_usd)
                or not 0 < self.risk_per_trade_usd <= 1
                or self.risk_per_trade_usd >= self.max_entry_notional_usd
                or self.max_entry_notional_usd > 100 or self.max_session_entries > 10
                or isinstance(self.leverage, bool) or self.leverage not in {1, 2}):
            raise ValueError("LIVE_SMALL_TRIAL_LIMIT_EXCEEDED")
        expected = (
            (self.resolved_arm_file, self.repo_root / "runtime/execution/real/LIVE_TRADING_ARMED"),
            (self.resolved_guard_state_path, self.repo_root / "data/execution/real/live_trading_guard.json"),
            (self.resolved_instance_lock_path, self.repo_root / "runtime/execution/real/execution.lock"),
        )
        if any(Path(actual).resolve() != expected_path.resolve() for actual, expected_path in expected):
            raise ValueError("LIVE_STATE_PATH_OVERRIDE_FORBIDDEN")


class LiveTradingGuard(TestnetTradingGuard):
    PROFILE_NAME = "live-trade"
    STATE_VERSION = "NBOT_V3_LIVE_GUARD_V1"

    def _arm_status(self):
        armed, reason, fingerprint = super()._arm_status()
        if not armed:
            return armed, reason, fingerprint
        try:
            fields = self._parse_arm(self.config.resolved_arm_file.read_text())
            if (fields.get("authorization") != "EXPLICIT_SMALL_MAINNET_TRIAL_V1"
                    or fields.get("settings_digest") != self.config.authorization_digest()):
                return False, "LIVE_EXPLICIT_TRIAL_AUTHORIZATION_MISMATCH", None
        except (OSError, ValueError, TestnetExchangeError):
            return False, "LIVE_EXPLICIT_TRIAL_AUTHORIZATION_INVALID", None
        return True, reason, fingerprint


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BinanceLiveExchange(BinanceTestnetExchange):
    """Mainnet uses identical order semantics, never Testnet credentials/state."""
    PROFILE_NAME = "live-trade"
    GUARD_CLASS = LiveTradingGuard

    def __init__(self, config: LiveExchangeConfig, *, logger=None):
        super().__init__(config, logger=logger or logging.getLogger("nbot.v3.live"))

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage != self.config.leverage:
            raise TestnetExchangeError("LIVE_LEVERAGE_OUTSIDE_APPROVED_SETTINGS")
        super().set_leverage(symbol, leverage)

    def _open_request(self, request, *, timeout):
        # Signed requests must never forward API credentials through a redirect.
        return build_opener(_NoRedirect()).open(request, timeout=timeout)

    def connect(self):
        was_connected = self.is_healthy()
        if was_connected:
            return
        try:
            super().connect()
            # Refuse incompatible account types; do not silently change them.
            position_mode = self._signed_get("/fapi/v1/positionSide/dual")
            if not isinstance(position_mode, dict) or position_mode.get("dualSidePosition") is not False:
                raise TestnetExchangeError("LIVE_ONE_WAY_ACCOUNT_REQUIRED")
            margin_mode = self._signed_get("/fapi/v1/multiAssetsMargin")
            if not isinstance(margin_mode, dict) or margin_mode.get("multiAssetsMargin") is not False:
                raise TestnetExchangeError("LIVE_SINGLE_ASSET_MARGIN_REQUIRED")
            self.account_snapshot()
        except Exception:
            self.disconnect()
            raise
