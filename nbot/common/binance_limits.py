"""Conservative Binance admission shared through a durable SQLite budget.

Processes using the same file share admission and exchange cooldowns. Headers
account for other callers on the same IP. Separate machines and unrelated apps
still require reserved headroom; this is not a distributed quota allocator.
Writes are never automatically retried by this module.
"""
from __future__ import annotations

import threading
import time
import os
import math
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlparse


class ExchangeCooldown(RuntimeError):
    pass


class RequestBudget:
    def __init__(self, *, clock=time.monotonic, ceiling=1200, state_path=None, wall_clock=time.time, host="default"):
        self.clock = clock
        self.ceiling = ceiling
        self.lock = threading.Lock()
        self.window = clock()
        self.used = 0
        self.cooldown_until = 0.0
        self.state_path = None if state_path is None else Path(state_path)
        self.wall_clock = wall_clock
        self.host = host

    @contextmanager
    def _persistent(self):
        if self.state_path is None:
            yield None
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.state_path, timeout=10)
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("CREATE TABLE IF NOT EXISTS budgets(host TEXT PRIMARY KEY, window REAL, used INTEGER, until REAL, last_seen REAL)")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _read(self, conn, now):
        if not math.isfinite(now):
            raise ExchangeCooldown("BINANCE_CLOCK_INVALID")
        row = conn.execute("SELECT window,used,until,last_seen FROM budgets WHERE host=?", (self.host,)).fetchone()
        if row is None:
            return now, 0, 0.0
        window, used, until, last_seen = row
        if now < last_seen - 1:
            raise ExchangeCooldown("BINANCE_CLOCK_MOVED_BACKWARD")
        if now - window >= 60:
            window, used = now, 0
        return window, used, until

    def _save(self, conn, window, used, until, now):
        conn.execute("INSERT OR REPLACE INTO budgets VALUES(?,?,?,?,?)", (self.host, window, used, until, now))

    def acquire(self, weight=40):
        with self.lock:
            now = self.clock()
            if now < self.cooldown_until:
                raise ExchangeCooldown("BINANCE_COOLDOWN_ACTIVE")
            if self.state_path is not None:
                try:
                    with self._persistent() as conn:
                        epoch = self.wall_clock()
                        window, used, until = self._read(conn, epoch)
                        if epoch < until:
                            raise ExchangeCooldown("BINANCE_COOLDOWN_ACTIVE")
                        if used + weight > self.ceiling:
                            raise ExchangeCooldown("BINANCE_LOCAL_WEIGHT_BUDGET_EXHAUSTED")
                        self._save(conn, window, used + weight, until, epoch)
                    return
                except (OSError, sqlite3.Error) as exc:
                    raise ExchangeCooldown("BINANCE_BUDGET_STORAGE_UNAVAILABLE") from exc
            if now - self.window >= 60:
                self.window, self.used = now, 0
            if self.used + weight > self.ceiling:
                raise ExchangeCooldown("BINANCE_LOCAL_WEIGHT_BUDGET_EXHAUSTED")
            self.used += weight

    def observe(self, headers, status=200):
        headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        with self.lock:
            delay = 0.0
            try:
                self.used = max(self.used, int(headers.get("x-mbx-used-weight-1m", 0)))
            except (TypeError, ValueError):
                pass
            if status in (418, 429):
                # Missing/malformed retry advice must not mean immediate retry.
                try:
                    delay = float(headers.get("retry-after", 180 if status == 429 else 86400))
                    if not 0 < delay < float("inf"):
                        raise ValueError
                except (TypeError, ValueError):
                    delay = 180 if status == 429 else 86400
                self.cooldown_until = max(self.cooldown_until, self.clock() + delay)
            if self.state_path is not None:
                try:
                    with self._persistent() as conn:
                        epoch = self.wall_clock()
                        window, used, until = self._read(conn, epoch)
                        try:
                            remote = max(0, int(headers.get("x-mbx-used-weight-1m", 0)))
                        except (TypeError, ValueError):
                            remote = 0
                        self._save(conn, window, max(used, remote), max(until, epoch + delay), epoch)
                except (OSError, sqlite3.Error) as exc:
                    raise ExchangeCooldown("BINANCE_BUDGET_STORAGE_UNAVAILABLE") from exc


_budgets = {}
_registry_lock = threading.Lock()


def request_weight(path, params=None):
    params = params or {}
    if path.endswith(("/ping", "/time", "/exchangeInfo", "/order", "/algoOrder", "/leverage", "/openAlgoOrders")):
        return 1
    if path.endswith("/ticker/bookTicker"):
        return 2 if params.get("symbol") else 5
    if path.endswith("/ticker/24hr"):
        return 1 if params.get("symbol") else 40
    if path.endswith("/premiumIndex"):
        return 1 if params.get("symbol") else 10
    if path.endswith("/income"):
        return 30
    if path.endswith("/klines"):
        limit = int(params.get("limit", 500))
        return 1 if limit < 100 else 2 if limit < 500 else 5 if limit <= 1000 else 10
    return 5


def budget_for(base_url):
    host = urlparse(base_url).hostname
    path = Path(os.environ.get("NBOT_BINANCE_BUDGET_PATH", str(Path(__file__).resolve().parents[2] / "data/common/binance_budget.sqlite")))
    with _registry_lock:
        key = (host, str(path.resolve()))
        if key not in _budgets:
            _budgets[key] = RequestBudget(state_path=path, host=host)
        return _budgets[key]
