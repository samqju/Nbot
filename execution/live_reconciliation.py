"""Read-only reconciliation for Binance Futures mainnet.

Phase 2.4 compares local engine expectations with live Binance account truth.
It never places, changes, or cancels an order. Any mismatch is reported and
the caller may fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LiveReconciliationReport:
    status: str
    exchange_positions: tuple[dict, ...]
    open_orders: tuple[dict, ...]
    protective_stops: tuple[dict, ...]
    issues: tuple[str, ...]

    @property
    def safe(self) -> bool:
        return not self.issues

    def require_safe(self) -> "LiveReconciliationReport":
        if not self.safe:
            raise RuntimeError(
                "LIVE_RECONCILIATION_UNSAFE | "
                f"issues={','.join(self.issues)}"
            )
        return self


class LiveReconciler:
    """Build deterministic, observation-only account reconciliation reports."""

    def __init__(self, *, exchange, system_log):
        self.exchange = exchange
        self.system_log = system_log

    @staticmethod
    def _normalize_local_position(local_position: Any) -> dict | None:
        if local_position is None:
            return None
        if isinstance(local_position, dict):
            source = local_position
        else:
            source = {
                "symbol": getattr(local_position, "symbol", None),
                "side": getattr(local_position, "side", None),
                "qty": getattr(local_position, "qty", None),
                "entry_price": getattr(local_position, "entry_price", None),
                "stop_loss": getattr(local_position, "stop_loss", None),
            }
        symbol = str(source.get("symbol") or "").upper()
        side = str(source.get("side") or "").upper()
        qty = float(source.get("qty") or 0.0)
        if not symbol or side not in {"LONG", "SHORT"} or qty <= 0:
            raise RuntimeError("LIVE_RECONCILIATION_LOCAL_POSITION_INVALID")
        return {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": float(source.get("entry_price") or 0.0),
            "stop_loss": (
                None
                if source.get("stop_loss") is None
                else float(source.get("stop_loss"))
            ),
        }

    @staticmethod
    def _qty_matches(expected: float, actual: float) -> bool:
        tolerance = max(1e-9, abs(expected) * 1e-6)
        return abs(expected - actual) <= tolerance

    def run(self, *, local_position=None) -> LiveReconciliationReport:
        expected = self._normalize_local_position(local_position)
        positions = tuple(self.exchange.list_open_positions())
        orders = tuple(self.exchange.list_open_orders())
        stops = tuple(self.exchange.list_protective_stops())

        issues: list[str] = []

        if len(positions) > 1:
            issues.append("MULTIPLE_LIVE_POSITIONS")

        if expected is None:
            if positions:
                issues.append("UNEXPECTED_LIVE_POSITION")
            if stops:
                issues.append("ORPHAN_PROTECTIVE_STOP")
        else:
            matching = [
                p for p in positions if p["symbol"] == expected["symbol"]
            ]
            if not matching:
                issues.append("EXPECTED_POSITION_MISSING")
            else:
                actual = matching[0]
                if actual["side"] != expected["side"]:
                    issues.append("POSITION_SIDE_MISMATCH")
                if not self._qty_matches(expected["qty"], actual["qty"]):
                    issues.append("POSITION_QTY_MISMATCH")

                symbol_stops = [
                    s for s in stops if s["symbol"] == expected["symbol"]
                ]
                if not symbol_stops:
                    issues.append("PROTECTIVE_STOP_MISSING")
                elif len(symbol_stops) > 1:
                    issues.append("MULTIPLE_PROTECTIVE_STOPS")

        position_symbols = {p["symbol"] for p in positions}
        for stop in stops:
            if stop["symbol"] not in position_symbols:
                if "ORPHAN_PROTECTIVE_STOP" not in issues:
                    issues.append("ORPHAN_PROTECTIVE_STOP")

        for order in orders:
            if not order.get("reduce_only", False):
                issues.append("NON_REDUCE_ONLY_OPEN_ORDER")
                break

        status = "SAFE" if not issues else "UNSAFE"
        report = LiveReconciliationReport(
            status=status,
            exchange_positions=positions,
            open_orders=orders,
            protective_stops=stops,
            issues=tuple(issues),
        )
        log = self.system_log.info if report.safe else self.system_log.error
        log(
            "LIVE_RECONCILIATION_REPORT | "
            f"status={report.status} | "
            f"positions={len(positions)} | "
            f"open_orders={len(orders)} | "
            f"protective_stops={len(stops)} | "
            f"issues={','.join(report.issues) if report.issues else 'NONE'} | "
            "mode=READ_ONLY"
        )
        return report
