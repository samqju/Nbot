"""Execution-only operator diagnostics.

These helpers format cached/in-memory execution state for Telegram and the
operator audit log. They must never make a Binance or Observation network
request and must never change trading state.
"""

from __future__ import annotations

import time

from config import EXECUTION_MODE, TRADING_ENV


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(float(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _metric_line(label: str, metric: dict) -> str:
    return (
        f"{label}: {float(metric.get('avg', 0.0)):.2f} / "
        f"{float(metric.get('p95', 0.0)):.2f} / "
        f"{float(metric.get('max', 0.0)):.2f} ms"
    )


def build_execution_operator_status(
    *,
    state,
    execution_health,
    outcome_publisher,
) -> tuple[str, str]:
    """Return Telegram body and one compact operator-log line."""
    state_data = state.get_state()
    position = state.get_open_position()
    symbol = str(position.get("symbol")) if position else None
    snapshot = execution_health.snapshot(position_symbol=symbol)
    counters = snapshot["counters"]
    timings = snapshot["timings"]
    pending = outcome_publisher.pending_count()

    feed = "POSITION_ONLY" if position else "IDLE_FLAT"
    position_text = "FLAT" if position is None else f"OPEN {symbol}"
    body = "\n".join(
        (
            f"Environment: {TRADING_ENV}",
            f"Mode: {EXECUTION_MODE}",
            f"Engine: {state_data.get('engine_state')}",
            f"Position: {position_text}",
            f"Feed: {feed}",
            f"Uptime: {_format_duration(snapshot['uptime_seconds'])}",
            f"Activity age: {snapshot['activity_age_seconds']:.2f}s",
            f"Outbox pending: {pending}",
            "",
            f"Control cycles: {counters['control_cycles']}",
            f"Position ticks: {counters['position_symbol_ticks']}",
            f"Irrelevant ticks: {counters['irrelevant_open_ticks']}",
            f"WS disconnects: {counters['position_ws_disconnects']}",
            "REST fallback: "
            f"{counters['position_rest_fallback_success']} ok / "
            f"{counters['position_rest_fallback_failure']} failed",
            f"SL updates: {counters['sl_update_attempts']}",
            "",
            _metric_line(
                "Tick age avg/p95/max",
                timings["internal_tick_age_ms"],
            ),
            _metric_line(
                "Manage avg/p95/max",
                timings["position_manage_ms"],
            ),
            _metric_line(
                "SL roundtrip avg/p95/max",
                timings["sl_roundtrip_ms"],
            ),
            _metric_line(
                "State save avg/p95/max",
                timings["bot_state_save_ms"],
            ),
            _metric_line(
                "Paper save avg/p95/max",
                timings["paper_state_save_ms"],
            ),
        )
    )

    log_line = (
        "OPERATOR_EXECUTION_STATUS | "
        f"environment={TRADING_ENV} | mode={EXECUTION_MODE} | "
        f"engine={state_data.get('engine_state')} | "
        f"position={position_text.replace(' ', '_')} | "
        f"feed={feed} | outbox_pending={pending} | "
        f"control_cycles={counters['control_cycles']} | "
        f"position_ticks={counters['position_symbol_ticks']} | "
        f"irrelevant_ticks={counters['irrelevant_open_ticks']} | "
        f"ws_disconnects={counters['position_ws_disconnects']} | "
        f"rest_ok={counters['position_rest_fallback_success']} | "
        f"rest_failed={counters['position_rest_fallback_failure']} | "
        f"tick_age_avg_ms={timings['internal_tick_age_ms']['avg']:.3f} | "
        f"manage_avg_ms={timings['position_manage_ms']['avg']:.3f} | "
        f"sl_roundtrip_avg_ms={timings['sl_roundtrip_ms']['avg']:.3f}"
    )
    return body, log_line


def build_heartbeat_operator_status(
    *,
    state,
    exchange,
    market_state,
    execution_health,
) -> tuple[str, str]:
    """Return a cached position/account heartbeat without network I/O."""
    state_data = state.get_state()
    position = state.get_open_position()
    health = execution_health.snapshot(
        position_symbol=(position.get("symbol") if position else None)
    )

    account_state = None
    account = getattr(exchange, "account", None)
    snapshot_fn = getattr(account, "snapshot", None)
    if callable(snapshot_fn):
        try:
            account_state = snapshot_fn()
        except Exception:
            account_state = None

    balance = (
        account_state.get("balance_usd")
        if account_state is not None
        else state_data.get("balance")
    )
    realized = (
        account_state.get("realized_pnl_usd")
        if account_state is not None
        else state_data.get("daily_realized_pnl")
    )
    fees = account_state.get("fees_paid_usd") if account_state else None
    completed = (
        account_state.get("completed_trade_count")
        if account_state is not None
        else None
    )

    lines = [
        f"Environment: {TRADING_ENV}",
        f"Mode: {EXECUTION_MODE}",
        f"Engine: {state_data.get('engine_state')}",
        f"Worker activity age: {health['activity_age_seconds']:.2f}s",
    ]

    symbol = None
    observed_price = None
    unrealized = None
    tick_age_seconds = None
    if position is None:
        lines.append("Position: FLAT")
    else:
        symbol = str(position.get("symbol") or "").upper()
        side = str(position.get("side") or "").upper()
        lines.extend(
            (
                f"Position: OPEN {symbol} {side}",
                f"Qty: {position.get('qty')}",
                f"Entry: {position.get('entry_price')}",
                f"Stop: {position.get('stop_loss')}",
            )
        )
        if symbol and market_state.has_price(symbol):
            observed_price = float(market_state.get_price(symbol))
            lines.append(f"Observed price: {observed_price}")
            timestamp = market_state.get_timestamp(symbol)
            tick_age_seconds = max(
                0.0,
                (time.time() * 1000.0 - float(timestamp)) / 1000.0,
            )
            lines.append(f"Last position tick age: {tick_age_seconds:.2f}s")
            try:
                direction = 1.0 if side == "LONG" else -1.0
                unrealized = (
                    observed_price - float(position.get("entry_price"))
                ) * float(position.get("qty")) * direction
                lines.append(f"Unrealized PnL: {unrealized:+.2f} USD")
            except (TypeError, ValueError):
                unrealized = None

    if balance is not None:
        lines.append(f"Balance (cached): {float(balance):.2f} USD")
    if realized is not None:
        lines.append(f"Realized PnL (cached): {float(realized):+.2f} USD")
    if fees is not None:
        lines.append(f"Fees paid: {float(fees):.2f} USD")
    if completed is not None:
        lines.append(f"Completed trades: {int(completed)}")

    log_line = (
        "OPERATOR_HEARTBEAT_STATUS | "
        f"environment={TRADING_ENV} | mode={EXECUTION_MODE} | "
        f"engine={state_data.get('engine_state')} | "
        f"position={'FLAT' if position is None else 'OPEN'} | "
        f"symbol={symbol or 'NONE'} | "
        f"observed_price={observed_price} | "
        f"tick_age_seconds={tick_age_seconds} | "
        f"unrealized_pnl_usd={unrealized} | "
        f"balance_cached={balance} | realized_cached={realized} | "
        f"activity_age_seconds={health['activity_age_seconds']:.3f}"
    )
    return "\n".join(lines), log_line
