"""Append-only V5 WSS source epoch audit in the existing isolated candle DB.

A process restart after a prior connected epoch is explicitly recorded as
an interrupted source generation, never proof of restored quote/trade health.
No background services, keys, orders, V4 paths or research approvals.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3


class SourceEpochHold(ValueError):
    pass


class SourceEpochAudit:
    ROUTES = ("market", "public")
    STATES = ("CONNECTED", "DISCONNECTED", "UNCLEAN_RESTART")

    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS v5_source_epochs (
                serial INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL CHECK(route IN ('market','public')),
                generation INTEGER NOT NULL CHECK(generation > 0),
                transition TEXT NOT NULL
                    CHECK(transition IN ('CONNECTED','DISCONNECTED','UNCLEAN_RESTART')),
                observed_ms INTEGER NOT NULL CHECK(observed_ms > 0),
                evidence_sha TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS v5_source_epochs_no_update
                BEFORE UPDATE ON v5_source_epochs BEGIN
                SELECT RAISE(ABORT,'V5_SOURCE_EPOCH_IMMUTABLE');
            END;
            CREATE TRIGGER IF NOT EXISTS v5_source_epochs_no_delete
                BEFORE DELETE ON v5_source_epochs BEGIN
                SELECT RAISE(ABORT,'V5_SOURCE_EPOCH_IMMUTABLE');
            END;
        """)

    def latest(self, route: str) -> tuple[int, str] | None:
        if route not in self.ROUTES:
            raise SourceEpochHold("V5_EPOCH_ROUTE_INVALID")
        result = self.db.execute(
            "SELECT generation, transition FROM v5_source_epochs "
            "WHERE route=? ORDER BY serial DESC LIMIT 1", (route,),
        ).fetchone()
        return tuple(result) if result else None

    def append(self, route: str, generation: int, transition: str, *,
               at_ms: int) -> None:
        prior = self.latest(route)
        if (type(generation) is not int or generation <= 0
                or type(at_ms) is not int or at_ms <= 0
                or transition not in self.STATES):
            raise SourceEpochHold("V5_EPOCH_ARGUMENT_INVALID")
        if transition == "CONNECTED":
            if prior and prior[1] == "CONNECTED":
                raise SourceEpochHold("V5_EPOCH_PREVIOUS_STILL_LIVE")
            if generation != (prior[0] + 1 if prior else 1):
                raise SourceEpochHold("V5_EPOCH_MONOTONIC_INVALID")
        elif prior != (generation, "CONNECTED"):
            raise SourceEpochHold("V5_EPOCH_TRANSITION_INVALID")
        payload = json.dumps(
            [route, generation, transition, at_ms], separators=(",", ":")
        )
        with self.db:
            self.db.execute(
                "INSERT INTO v5_source_epochs "
                "(route,generation,transition,observed_ms,evidence_sha) "
                "VALUES (?,?,?,?,?)",
                (route, generation, transition, at_ms,
                 hashlib.sha256(payload.encode()).hexdigest()),
            )

    def recover_unclosed(self, *, at_ms: int) -> dict[str, int]:
        """After a crash, record every previous still-connected epoch."""
        crashed = {}
        for route in self.ROUTES:
            last = self.latest(route)
            if last and last[1] == "CONNECTED":
                self.append(route, last[0], "UNCLEAN_RESTART", at_ms=at_ms)
                crashed[route] = last[0]
        return crashed

    def overview(self) -> dict:
        latest = {route: self.latest(route) for route in self.ROUTES}
        return {"source_generations": {
            route: {"generation": info[0], "last_state": info[1]}
            if info else {"generation": 0, "last_state": "NEVER_CONNECTED"}
            for route, info in latest.items()
        }, "research_ready": False, "order_authority": "NONE"}
