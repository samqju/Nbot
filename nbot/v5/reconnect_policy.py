"""V5 G1e public WSS connection epochs and conservative bounded retry policy.

Network reconnection cannot restore missing aggregate trades or executable
quotes. A new WSS generation is always untrusted pending independent as-of
REST candle reconciliation, explicit fresh quote/trade verification and a
future owner-approved feed-health certification gate. Never automatically
promote a stream to research-ready.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class FeedRecoveryHold(ValueError):
    """Transport may continue collecting but must not qualify research."""


@dataclass
class RouteEpoch:
    generation: int = 0
    connected: bool = False
    faults: int = 0
    retry_attempts: int = 0
    reconciliation_required: bool = True
    reasons: set[str] = field(default_factory=set)


class ReconnectPolicy:
    """Fixed-memory state for exactly two public-only WSS route generations.

    Initial fresh connections start at generation 1. Any interruption bumps
    the next generation and marks the old quote/trade/candle continuity
    unverifiable. Backoff is deterministic, capped and never busy-loops.
    """

    MAX_ATTEMPTS = 3
    BACKOFF_SECONDS = (2, 5, 12)

    def __init__(self):
        self.routes = {"market": RouteEpoch(), "public": RouteEpoch()}
        self.candle_gap_symbols: set[str] = set()
        self.trade_gap_symbols: set[str] = set()
        self.global_incidents = 0

    def _route(self, route: str) -> RouteEpoch:
        try:
            return self.routes[route]
        except KeyError as exc:
            raise FeedRecoveryHold("V5_G1E_UNKNOWN_ROUTE") from exc

    def on_connect(self, route: str) -> int:
        state = self._route(route)
        if state.connected:
            raise FeedRecoveryHold("V5_G1E_DOUBLE_CONNECT")
        state.generation += 1
        state.connected = True
        state.reconciliation_required = True
        state.reasons.add("COHORT_NOT_VERIFIED")
        return state.generation

    def on_disconnect(self, route: str, reason: str = "CONNECTION_LOST") -> None:
        state = self._route(route)
        if not isinstance(reason, str) or not reason or len(reason) > 80:
            raise FeedRecoveryHold("V5_G1E_INVALID_REASON")
        state.connected = False
        state.faults += 1
        state.reconciliation_required = True
        state.reasons.add(reason)
        state.reasons.add("RECONNECT_REQUIRES_NEW_SOURCE_PROOF")
        self.global_incidents += 1

    def retry_delay(self, route: str) -> int:
        state = self._route(route)
        if state.connected:
            raise FeedRecoveryHold("V5_G1E_RETRY_WHILE_CONNECTED")
        if state.retry_attempts >= self.MAX_ATTEMPTS:
            raise FeedRecoveryHold("V5_G1E_RETRY_BUDGET_EXHAUSTED")
        delay = self.BACKOFF_SECONDS[state.retry_attempts]
        state.retry_attempts += 1
        return delay

    def record_gap(self, kind: str, symbol: str) -> None:
        if kind == "CANDLE":
            self.candle_gap_symbols.add(symbol)
        elif kind == "TRADE":
            self.trade_gap_symbols.add(symbol)
        else:
            raise FeedRecoveryHold("V5_G1E_GAP_TYPE_INVALID")
        self.global_incidents += 1

    def candle_reconciled(self, symbol: str) -> None:
        """One REST overlap may repair candle history, NEVER trade/quote."""
        self.candle_gap_symbols.discard(symbol)

    def status(self) -> dict:
        return {
            "routes": {
                name: {
                    "generation": state.generation,
                    "connected": state.connected,
                    "faults": state.faults,
                    "retry_attempts": state.retry_attempts,
                    "reconciliation_required": state.reconciliation_required,
                    "reasons": sorted(state.reasons),
                } for name, state in self.routes.items()
            },
            "candle_gap_symbols": sorted(self.candle_gap_symbols),
            "trade_gap_symbols": sorted(self.trade_gap_symbols),
            "global_incidents": self.global_incidents,
            "research_ready": False,
            "order_authority": "NONE",
        }
