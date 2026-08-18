#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from nbot.execution import (
    ExecutionConfig,
    ExecutionInstanceLock,
    ExecutionSafetyError,
    ExecutionStateStore,
    ExecutionWorker,
    INTEGER_R_STEP_CONTROL,
    NO_ENTRY_AUTHORITY,
)
from nbot.execution_protocol import ExecutionProposal, TradeResponse
from nbot.runtime_ops import TelegramOperator, configure_role_logging, telegram_escape_plain


DEFAULT_ENV_FILE = Path("/home/ubuntu/.config/nbot/.env")
DEFAULT_STATE_PATH = Path("/var/lib/nbot-execution/execution_v2_state.json")
DEFAULT_OUTCOME_PATH = Path("/var/lib/nbot-execution/testnet_canary_outcomes.jsonl")
DEFAULT_LOCK_PATH = Path("/var/lib/nbot-execution/execution_v2.lock")
DEFAULT_EXECUTION_LOG_PATH = Path("/var/lib/nbot-execution/logs/execution.log")
DEFAULT_TRADE_LOG_PATH = Path("/var/lib/nbot-execution/logs/execution-trades.log")


class StaticProposalClient:
    def __init__(self, proposal: ExecutionProposal | None = None):
        self.proposal = proposal
        self.used = False

    def request_trade(self, _request):
        if self.proposal is None or self.used:
            return TradeResponse.no_trade()
        self.used = True
        return TradeResponse.proposal_response(self.proposal)


class MechanicalOutcomeSink:
    """Local V2.8-only outcome sink. Never writes research evidence."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def send_outcome(self, outcome) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    existing.add(str(json.loads(line).get("outcome_id") or ""))
                except Exception:
                    raise ExecutionSafetyError("TESTNET_CANARY_OUTCOME_LOG_CORRUPT")
        if outcome.outcome_id in existing:
            return "ALREADY_RECORDED"
        row = outcome.to_dict()
        row["evidence_class"] = "TESTNET_MECHANICAL_ONLY"
        row["research_evidence"] = False
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return "RECORDED"


def load_env_file(path: Path) -> None:
    """Small strict dotenv reader; does not override already-exported values."""
    if not path.is_file():
        raise ExecutionSafetyError(f"EXECUTION_ENV_FILE_MISSING:{path}")
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ExecutionSafetyError(f"EXECUTION_ENV_FILE_INVALID_LINE:{lineno}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or not key[0].isalpha():
            raise ExecutionSafetyError(f"EXECUTION_ENV_KEY_INVALID:{lineno}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def execution_config_from_env(*, enable_canary: bool) -> ExecutionConfig:
    if os.getenv("NBOT_EXECUTION_ENV", "TESTNET").strip().upper() != "TESTNET":
        raise ExecutionSafetyError("V2_8_TESTNET_ONLY_ENVIRONMENT_REQUIRED")
    state_path = Path(os.getenv("TESTNET_EXECUTION_STATE_PATH", str(DEFAULT_STATE_PATH)))
    base = ExecutionConfig(
        environment="TESTNET",
        state_path=state_path,
        risk_per_trade_usd=float(os.getenv("TESTNET_RISK_PER_TRADE_USD", "10")),
        max_notional_usd=float(os.getenv("TESTNET_MAX_ENTRY_NOTIONAL_USD", "1000")),
        leverage=int(os.getenv("TESTNET_LEVERAGE", "5")),
        max_spread_pct=float(os.getenv("TESTNET_MAX_SPREAD_PCT", "0.25")),
        max_reference_price_drift_pct=float(os.getenv("TESTNET_MAX_REFERENCE_PRICE_DRIFT_PCT", "0.25")),
        notional_tolerance_pct=float(os.getenv("NBOT_EXECUTION_NOTIONAL_TOLERANCE_PCT", "1.0")),
        risk_tolerance_pct=float(os.getenv("NBOT_EXECUTION_RISK_TOLERANCE_PCT", "10.0")),
        max_entry_slippage_pct=float(os.getenv("NBOT_EXECUTION_MAX_ENTRY_SLIPPAGE_PCT", "1.0")),
        daily_profit_lock_trigger_r=float(os.getenv("NBOT_EXECUTION_DAILY_PROFIT_LOCK_TRIGGER_R", "100.0")),
        daily_normal_giveback_r=float(os.getenv("NBOT_EXECUTION_DAILY_NORMAL_GIVEBACK_R", "95.0")),
        daily_profit_giveback_r=float(os.getenv("NBOT_EXECUTION_DAILY_PROFIT_GIVEBACK_R", "3.0")),
        emergency_flatten_attempts=int(os.getenv("NBOT_EXECUTION_EMERGENCY_FLATTEN_ATTEMPTS", "2")),
        emergency_verify_delay_seconds=float(os.getenv("NBOT_EXECUTION_EMERGENCY_VERIFY_DELAY_SECONDS", "0.5")),
        allowed_entry_authorities=(),
        allowed_exit_policies=(),
    )
    if enable_canary:
        from nbot.testnet_exchange import MECHANICAL_CANARY_AUTHORITY
        return replace(
            base,
            allowed_entry_authorities=(MECHANICAL_CANARY_AUTHORITY,),
            allowed_exit_policies=(INTEGER_R_STEP_CONTROL,),
        )
    return base


def build_exchange():
    from nbot.testnet_exchange import BinanceTestnetExchange, TestnetExchangeConfig
    cfg = TestnetExchangeConfig.from_env()
    cfg.validate()
    return BinanceTestnetExchange(cfg)


def make_canary_proposal(exchange, *, symbol: str, side: str) -> ExecutionProposal:
    from nbot.testnet_exchange import MECHANICAL_CANARY_AUTHORITY, MECHANICAL_CANARY_MODEL
    now_ms = int(time.time() * 1000)
    quote = exchange.quote(symbol)
    reference = quote.ask if side == "LONG" else quote.bid
    return ExecutionProposal.create(
        proposal_id=f"CANARY-{now_ms}-{symbol}-{side}",
        environment="TESTNET",
        symbol=symbol,
        direction=side,
        generated_at_ms=now_ms,
        expires_at_ms=now_ms + 30_000,
        reference_price=reference,
        entry_authority=MECHANICAL_CANARY_AUTHORITY,
        model_version=MECHANICAL_CANARY_MODEL,
        exit_policy_version=INTEGER_R_STEP_CONTROL,
        feature_version="NONE_MECHANICAL_CANARY",
        data_generation_id="TESTNET_MECHANICAL_CANARY_V1",
        market_event_id=f"MECHANICAL-{now_ms}",
        advisory_initial_risk={"source": "EXECUTION_LOCAL_MECHANICAL_CANARY"},
        selection_score=0.0,
    )


def _execution_status_text(worker: ExecutionWorker) -> str:
    status = worker.status()
    daily = status.get("daily_risk") or {}
    position = worker.state.open_position
    position_text = "FLAT"
    if position is not None:
        position_text = (
            f"OPEN {position.get('symbol')} {position.get('side')} "
            f"qty={position.get('quantity')} stop={position.get('stop_price')}"
        )
    return (
        f"Environment: {status['environment']}\n"
        f"Position: {position_text}\n"
        f"New entries: {'ENABLED' if status['trading_enabled'] else 'DISABLED'}\n"
        f"Entry inflight: {status['entry_inflight']}\n"
        f"Pending outcomes: {status['pending_outcomes']}\n"
        f"Daily realized: ${float(daily.get('realized_pnl_usd', 0.0)):+.2f}\n"
        f"Daily peak: ${float(daily.get('peak_realized_pnl_usd', 0.0)):+.2f}\n"
        f"Daily floor: {daily.get('loss_floor_usd')}\n"
        f"Daily halted: {bool(daily.get('halted', False))}"
    )


def _execution_operator_command(worker: ExecutionWorker, operator: TelegramOperator, text: str) -> None:
    parts = str(text or "").strip().split()
    if not parts:
        return
    command = parts[0].split("@", 1)[0].lower()
    try:
        if command in {"/status", "/execution"}:
            operator.info("EXECUTION STATUS", _execution_status_text(worker))
        elif command == "/pnl":
            daily = worker.status().get("daily_risk") or {}
            operator.info(
                "DAILY PNL",
                f"UTC day: {daily.get('utc_day')}\n"
                f"Realized: ${float(daily.get('realized_pnl_usd', 0.0)):+.2f}\n"
                f"Peak: ${float(daily.get('peak_realized_pnl_usd', 0.0)):+.2f}\n"
                f"Loss floor: {daily.get('loss_floor_usd')}\n"
                f"Trades closed: {int(daily.get('trades_closed', 0))}\n"
                f"Halted: {bool(daily.get('halted', False))}",
            )
        elif command == "/position":
            position = worker.state.open_position
            operator.info(
                "EXECUTION POSITION",
                "FLAT" if position is None else json.dumps(position, indent=2, sort_keys=True),
            )
        elif command in {"/health", "/heartbeat"}:
            health = worker.status().get("health") or {}
            operator.info(
                "EXECUTION HEALTH",
                f"Prepare calls: {int(health.get('prepare_calls', 0))}\n"
                f"Flat cycles: {int(health.get('flat_cycles', 0))}\n"
                f"Open ticks: {int(health.get('open_position_ticks', 0))}\n"
                f"Stop updates: {int(health.get('stop_updates', 0))}\n"
                f"Emergency exits: {int(health.get('emergency_exits', 0))}\n"
                f"Reconciliations: {int(health.get('reconciliations', 0))}\n"
                f"Last manage ms: {float(health.get('last_position_manage_ms', 0.0)):.3f}\n"
                f"Max manage ms: {float(health.get('max_position_manage_ms', 0.0)):.3f}\n"
                f"Last event: {telegram_escape_plain(health.get('last_event'))}",
            )
        elif command == "/recent":
            history = list(worker.state.data.get("execution_outcome_history", []))
            if not history:
                operator.info("RECENT EXECUTION", "No completed execution outcome recorded.")
            else:
                row = history[-1]
                operator.info(
                    "RECENT EXECUTION",
                    f"{row.get('symbol')} {row.get('side')}\n"
                    f"PnL: ${float(row.get('realized_pnl_usd', 0.0)):+.4f}\n"
                    f"R: {float(row.get('r_multiple', 0.0)):+.3f}\n"
                    f"Reason: {telegram_escape_plain(row.get('exit_reason'))}\n"
                    f"Outcome: {telegram_escape_plain(row.get('outcome_id'))}",
                )
        elif command == "/disable":
            worker.disable_new_entries()
            operator.warning("NEW ENTRIES DISABLED", "Open-position management and reconciliation remain active.")
        elif command == "/enable":
            # This does not bypass Testnet arm gates, proposal authority, daily
            # risk, exchange health, spread, margin, or any local risk check.
            worker.enable_new_entries()
            operator.info("NEW ENTRIES ENABLED", "All normal local safety gates still apply.")
        elif command == "/help":
            operator.info(
                "EXECUTION COMMANDS",
                "/status — capital-boundary status\n"
                "/position — current local position\n"
                "/health — execution hot-path health/latency\n"
                "/recent — latest completed execution\n"
                "/pnl — current UTC-day PnL/risk floor\n"
                "/enable — allow new entries subject to every safety gate\n"
                "/disable — block new entries only\n"
                "/help — show commands\n\n"
                "Emergency flatten remains an explicit local/CLI action; Telegram cannot bypass that boundary.",
            )
        else:
            operator.warning("UNKNOWN EXECUTION COMMAND", f"{telegram_escape_plain(command)}\nUse /help.")
    except Exception as exc:
        worker.logger.error("OPERATOR_TELEGRAM_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
        operator.warning("COMMAND FAILED", f"{telegram_escape_plain(command)}: {telegram_escape_plain(type(exc).__name__)}")


def self_check() -> int:
    cfg = ExecutionConfig()
    cfg.validate()
    print(json.dumps({
        "phase": "V2.8",
        "role": "EXECUTION_CAPITAL_BOUNDARY",
        "environment": cfg.environment,
        "entry_authority": NO_ENTRY_AUTHORITY,
        "approved_exit_policies": list(cfg.allowed_exit_policies),
        "order_adapter": "TESTNET_AVAILABLE_BUT_NOT_ARMED_BY_SELF_CHECK",
        "env_file": str(DEFAULT_ENV_FILE),
        "status": "PASS_FAIL_CLOSED",
    }, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V2.8 Testnet TRADE mechanical canary")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--testnet-preflight", action="store_true")
    parser.add_argument("--testnet-reconcile", action="store_true")
    parser.add_argument("--testnet-canary", action="store_true")
    parser.add_argument("--testnet-emergency-flat", action="store_true")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--side", choices=("LONG", "SHORT"), default="LONG")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    actions = sum(bool(x) for x in (
        args.self_check, args.testnet_preflight, args.testnet_reconcile,
        args.testnet_canary, args.testnet_emergency_flat,
    ))
    if actions != 1:
        parser.error("choose exactly one execution action")
    if args.self_check:
        return self_check()

    load_env_file(args.env_file)
    execution_log_path = Path(os.getenv("NBOT_EXECUTION_LOG_PATH", str(DEFAULT_EXECUTION_LOG_PATH)))
    trade_log_path = Path(os.getenv("NBOT_EXECUTION_TRADE_LOG_PATH", str(DEFAULT_TRADE_LOG_PATH)))
    execution_log, trade_log = configure_role_logging(
        "EXECUTION", log_path=execution_log_path, trade_log_path=trade_log_path, stderr=True,
    )
    execution_log.info("NBOT_EXECUTION_START action=%s", next(
        name for name, enabled in (
            ("PREFLIGHT", args.testnet_preflight), ("RECONCILE", args.testnet_reconcile),
            ("CANARY", args.testnet_canary), ("EMERGENCY_FLAT", args.testnet_emergency_flat),
        ) if enabled
    ))
    operator = TelegramOperator.from_env("EXECUTION", execution_log)
    exchange = build_exchange()
    outcome_path = Path(os.getenv("TESTNET_CANARY_OUTCOMES_PATH", str(DEFAULT_OUTCOME_PATH)))
    outcome_sink = MechanicalOutcomeSink(outcome_path)

    if args.testnet_preflight:
        exchange.connect()
        try:
            report = exchange.preflight_report(args.symbol.upper())
            report["env_file"] = str(args.env_file)
            report["state_path"] = os.getenv("TESTNET_EXECUTION_STATE_PATH", str(DEFAULT_STATE_PATH))
            report["status"] = "PASS" if report["user_stream_healthy"] else "FAIL"
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report["status"] == "PASS" else 2
        finally:
            exchange.disconnect()

    enable_canary = bool(args.testnet_canary)
    cfg = execution_config_from_env(enable_canary=enable_canary)
    lock_path = Path(os.getenv("TESTNET_EXECUTION_LOCK_PATH", str(DEFAULT_LOCK_PATH)))

    # Capital-mutating/reconciliation actions are single-instance. Read-only
    # preflight remains available from a second terminal while a canary runs.
    with ExecutionInstanceLock(lock_path):
        state = ExecutionStateStore(cfg.state_path)
        proposal_client = StaticProposalClient()
        worker = ExecutionWorker(
            cfg, exchange, proposal_client, outcome_sink, state=state,
            logger=execution_log, trade_logger=trade_log, notifier=operator,
        )

        if args.testnet_reconcile:
            prepared = worker.prepare()
            if prepared == "POSITION_OPEN":
                result = worker.reconcile_open_position()
            elif prepared == "RECOVERED_CLOSED_POSITION":
                worker.process_flat_cycle()  # deliver recovered mechanical outcome; never requests a trade here
                result = "POSITION_CLOSE_RECOVERED"
            else:
                result = "FLAT"
            print(json.dumps({"prepare": prepared, "reconcile": result, "status": worker.status()}, indent=2, sort_keys=True))
            exchange.disconnect()
            return 0

        if args.testnet_emergency_flat:
            if not args.yes:
                print("REFUSED: --testnet-emergency-flat requires --yes", file=sys.stderr)
                return 2
            worker.prepare()
            result = worker.force_close_open_position(reason="OPERATOR_TESTNET_FLATTEN")
            worker.process_flat_cycle()  # deliver mechanical-only outcome locally; no proposal authority
            print(json.dumps({"result": result, "status": worker.status()}, indent=2, sort_keys=True))
            exchange.disconnect()
            return 0

        if not args.yes:
            print("REFUSED: --testnet-canary places Binance Testnet orders and requires --yes", file=sys.stderr)
            return 2
        if operator is not None:
            operator.start_listener(lambda text: _execution_operator_command(worker, operator, text))
            operator.info("EXECUTION CANARY STARTED", "Testnet mechanical canary process is active. Use /status for state.")
        prepared = worker.prepare()
        if prepared == "RECOVERED_CLOSED_POSITION":
            worker.process_flat_cycle()  # settle/deliver first; require a fresh explicit invocation for any new entry
            print(json.dumps({"entry_result": "RECOVERED_CLOSED_POSITION_NO_ENTRY", "status": worker.status()}, indent=2, sort_keys=True))
            exchange.disconnect()
            return 0
        if prepared == "FLAT":
            proposal_client.proposal = make_canary_proposal(exchange, symbol=args.symbol.upper(), side=args.side)
            worker.enable_new_entries()
            result = worker.process_flat_cycle()
            worker.disable_new_entries()
            if result != "ENTRY_OPENED":
                print(json.dumps({"entry_result": result, "status": worker.status()}, indent=2, sort_keys=True))
                exchange.disconnect()
                return 2
        else:
            result = "RESUMED_EXISTING_POSITION"

        print(json.dumps({"entry_result": result, "status": worker.status()}, indent=2, sort_keys=True))
        print("V2.8 canary managing protected Testnet position. Ctrl+C leaves it protected for restart/reconcile testing.")
        try:
            position = worker.state.open_position
            if position is None:
                raise ExecutionSafetyError("TESTNET_CANARY_POSITION_MISSING_AFTER_ENTRY")
            for symbol, price, timestamp_ms in exchange.position_price_stream(str(position["symbol"])):
                state_result = worker.process_open_price(symbol, price, timestamp_ms)
                if state_result == "POSITION_CLOSED":
                    break
        except KeyboardInterrupt:
            print("TESTNET_CANARY_INTERRUPTED_POSITION_LEFT_PROTECTED")
            return 0
        finally:
            exchange.disconnect()

        # Flat again: persist the mechanical result outside research evidence.
        worker.process_flat_cycle()
        print(json.dumps({"result": "CANARY_CLOSED", "status": worker.status()}, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
