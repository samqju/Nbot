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


DEFAULT_ENV_FILE = Path("/home/ubuntu/.config/nbot/.env")
DEFAULT_STATE_PATH = Path("/var/lib/nbot-execution/execution_v2_state.json")
DEFAULT_OUTCOME_PATH = Path("/var/lib/nbot-execution/testnet_canary_outcomes.jsonl")
DEFAULT_LOCK_PATH = Path("/var/lib/nbot-execution/execution_v2.lock")


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
        worker = ExecutionWorker(cfg, exchange, proposal_client, outcome_sink, state=state)

        if args.testnet_reconcile:
            prepared = worker.prepare()
            result = worker.reconcile_open_position() if prepared == "POSITION_OPEN" else "FLAT"
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
        prepared = worker.prepare()
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
