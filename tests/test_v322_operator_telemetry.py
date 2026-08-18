from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from nbot.exchange.binance_testnet import BinanceTestnetExchange, TestnetExchangeConfig
from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef
from nbot.execution.canary import (
    MechanicalCanaryEmergencyFlattener,
    MechanicalCanaryEntryLifecycle,
    MechanicalCanaryReconciliationLifecycle,
    MechanicalCanaryTelemetry,
    MechanicalCanaryTestnetExchange,
    OneShotMechanicalProposalClient,
    make_mechanical_proposal,
)
from nbot.execution.entry import EntryLifecycle, EntryRejected
from nbot.execution.execution import ExecutionWorker, ExecutionWorkerError
from nbot.execution.reconciliation import ReconciliationResult

import run_execution


class V322OperatorTelemetryTests(unittest.TestCase):
    def test_telemetry_is_testnet_mechanical_only_and_records_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-1")
            telemetry.observe_latency("order_request_fill_ms", 12.5, status="PASS")
            telemetry.increment("recovery_attempts", recovery_type="ENTRY_INFLIGHT")
            summary = telemetry.finish("PASS")

            self.assertEqual(summary["authority"], "TESTNET_MECHANICAL_ONLY")
            self.assertEqual(summary["evidence_class"], "TESTNET_MECHANICAL_ONLY")
            self.assertIs(summary["research_evidence"], False)
            self.assertEqual(summary["latency_last_ms"]["order_request_fill_ms"], 12.5)
            self.assertEqual(summary["counters"]["recovery_attempts"], 1)
            self.assertGreaterEqual(summary["max_cpu_percent"], 0.0)
            self.assertGreater(summary["max_rss_mb"], 0.0)

            rows = [json.loads(line)["payload"] for line in Path(summary["telemetry_file"]).read_text().splitlines()]
            self.assertTrue(rows)
            self.assertTrue(all(row["authority"] == "TESTNET_MECHANICAL_ONLY" for row in rows))
            self.assertTrue(all(row["research_evidence"] is False for row in rows))
            self.assertTrue(any(row["event"] == "RESOURCE_SAMPLE" for row in rows))

    def test_one_shot_duplicate_prevention_is_counted(self):
        from nbot.exchange.contracts import Quote

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-DUP")
            client = OneShotMechanicalProposalClient(telemetry)
            proposal = make_mechanical_proposal(
                Quote("BTCUSDT", 99.0, 101.0, 1_000_000),
                side="LONG",
                now_ms=lambda: 1_000_000,
            )
            client.offer(proposal)
            with self.assertRaisesRegex(RuntimeError, "ALREADY_OFFERED"):
                client.offer(proposal)
            self.assertEqual(telemetry.summary()["counters"]["duplicate_preventions"], 1)

    def test_instrumented_testnet_exchange_records_required_latencies_and_close_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-X")
            cfg = TestnetExchangeConfig(api_key="x", api_secret="y", repo_root=Path(tmp))
            exchange = MechanicalCanaryTestnetExchange(cfg, telemetry)
            plan = EntryPlan(
                "BTCUSDT", "LONG", 1.0, 100.0, 99.0, 1.0, 100.0, 5
            )
            fill = Fill(100.0, 1.0, "ORDER-1", "CLIENT-1", 1_000_000)
            stop = ProtectiveStopRef("BTCUSDT", "LONG", 1.0, 99.0, stop_id="STOP-1")

            with mock.patch.object(BinanceTestnetExchange, "open_market", return_value=fill), \
                 mock.patch.object(BinanceTestnetExchange, "ensure_protective_stop", return_value=stop), \
                 mock.patch.object(BinanceTestnetExchange, "replace_protective_stop", return_value=stop), \
                 mock.patch.object(BinanceTestnetExchange, "close_position", return_value=mock.sentinel.close):
                self.assertIs(exchange.open_market(plan, client_order_id="CLIENT-1"), fill)
                self.assertIs(exchange.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 99.0), stop)
                self.assertIs(exchange.replace_protective_stop("BTCUSDT", "LONG", 1.0, 100.0), stop)
                self.assertIs(
                    exchange.close_position("BTCUSDT", "LONG", reason="RISK_CONTRACT_BREACH"),
                    mock.sentinel.close,
                )

            summary = telemetry.summary()
            self.assertIn("order_request_fill_ms", summary["latency_last_ms"])
            self.assertIn("initial_stop_place_verify_ms", summary["latency_last_ms"])
            self.assertIn("stop_replacement_ms", summary["latency_last_ms"])
            self.assertIn("close_request_settlement_ms", summary["latency_last_ms"])
            self.assertEqual(summary["counters"]["emergency_close_attempts"], 1)


    def test_instrumented_entry_counts_durable_duplicate_rejection(self):
        from nbot.exchange.contracts import Quote

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-EDUP")
            lifecycle = object.__new__(MechanicalCanaryEntryLifecycle)
            lifecycle.telemetry = telemetry
            proposal = make_mechanical_proposal(
                Quote("BTCUSDT", 99.0, 101.0, 1_000_000),
                side="LONG",
                now_ms=lambda: 1_000_000,
            )
            with mock.patch.object(EntryLifecycle, "execute", side_effect=EntryRejected("DUPLICATE_PROPOSAL")):
                with self.assertRaisesRegex(EntryRejected, "DUPLICATE_PROPOSAL"):
                    lifecycle.execute(proposal, now_ms=1_000_001)
            self.assertEqual(telemetry.summary()["counters"]["duplicate_preventions"], 1)

    def test_instrumented_reconciliation_records_latency_and_recovery_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="RECONCILE", run_id="RUN-R")
            lifecycle = object.__new__(MechanicalCanaryReconciliationLifecycle)
            lifecycle.telemetry = telemetry
            ticks = iter((10.0, 10.025))
            lifecycle._monotonic = lambda: next(ticks)
            result = ReconciliationResult(status="ENTRY_INFLIGHT_CLOSE_RECOVERED", outcome_id="OUT-1")
            with mock.patch(
                "nbot.execution.reconciliation.ReconciliationLifecycle.reconcile",
                return_value=result,
            ):
                observed = lifecycle.reconcile()
            self.assertIs(observed, result)
            summary = telemetry.summary()
            self.assertAlmostEqual(summary["latency_last_ms"]["reconciliation_ms"], 25.0, places=6)
            self.assertEqual(summary["counters"]["recovery_events"], 1)

    def test_verified_emergency_reports_success_and_failure(self):
        class FakeExchange:
            def __init__(self, fail=False):
                self.position = mock.Mock(symbol="BTCUSDT", side="LONG")
                self.fail = fail

            def position_snapshot(self):
                return self.position

            def close_position(self, symbol, side, *, reason):
                if self.fail:
                    raise RuntimeError("close failed")
                self.position = None
                return mock.sentinel.close

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-E")
            good = MechanicalCanaryEmergencyFlattener(
                exchange=FakeExchange(), telemetry=telemetry, sleep=lambda _: None
            )
            good.flatten_verified("BTCUSDT", "LONG", reason="RISK_CONTRACT_BREACH")
            self.assertEqual(telemetry.summary()["counters"]["emergency_successes"], 1)

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = MechanicalCanaryTelemetry(tmp, action="CANARY", run_id="RUN-EF")
            bad = MechanicalCanaryEmergencyFlattener(
                exchange=FakeExchange(fail=True), telemetry=telemetry, sleep=lambda _: None
            )
            with self.assertRaises(Exception):
                bad.flatten_verified("BTCUSDT", "LONG", reason="RISK_CONTRACT_BREACH")
            self.assertEqual(telemetry.summary()["counters"]["emergency_failures"], 1)

    def test_force_close_requires_yes_and_arm_before_exchange_construction(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_YES"):
                run_execution.run_testnet_force_close(
                    repo_root=Path(tmp), environment={}, confirmed=False
                )
            build_exchange.assert_not_called()

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=False), \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_ARM"):
                run_execution.run_testnet_force_close(
                    repo_root=Path(tmp), environment={}, confirmed=True
                )
            build_exchange.assert_not_called()

    def test_manual_reconcile_requires_yes_and_arm_before_exchange_construction(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_YES"):
                run_execution.run_testnet_reconcile(
                    repo_root=Path(tmp), environment={}, confirmed=False
                )
            build_exchange.assert_not_called()

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=False), \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_ARM"):
                run_execution.run_testnet_reconcile(
                    repo_root=Path(tmp), environment={}, confirmed=True
                )
            build_exchange.assert_not_called()

    def test_execution_worker_force_close_requires_verified_flat_then_reconciliation(self):
        class State:
            def __init__(self):
                self.open_position = mock.Mock(symbol="BTCUSDT", side="LONG")
                self.entry_inflight = None

        class Emergency:
            def __init__(self):
                self.calls = []

            def flatten_verified(self, symbol, side, *, reason):
                self.calls.append((symbol, side, reason))

        worker = object.__new__(ExecutionWorker)
        worker._prepared = True
        worker.state = State()
        worker.position = mock.Mock()
        worker.position.emergency = Emergency()
        worker.disable_new_entries = mock.Mock()
        worker._health_event = mock.Mock()

        def reconcile():
            worker.state.open_position = None
            return ReconciliationResult(status="POSITION_CLOSE_RECOVERED", outcome_id="OUT-1")

        worker._reconcile_now = reconcile
        result = ExecutionWorker.force_close_open_position(
            worker, reason="OPERATOR_TESTNET_FORCE_CLOSE"
        )
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        worker.disable_new_entries.assert_called_once_with()
        self.assertEqual(
            worker.position.emergency.calls,
            [("BTCUSDT", "LONG", "OPERATOR_TESTNET_FORCE_CLOSE")],
        )
        self.assertIsNone(worker.state.open_position)

    def test_force_close_fails_closed_when_reconciliation_does_not_prove_flat(self):
        class State:
            open_position = mock.Mock(symbol="BTCUSDT", side="LONG")
            entry_inflight = None

        worker = object.__new__(ExecutionWorker)
        worker._prepared = True
        worker.state = State()
        worker.position = mock.Mock()
        worker.position.emergency.flatten_verified.return_value = None
        worker.disable_new_entries = mock.Mock()
        worker._health_event = mock.Mock()
        worker._reconcile_now = mock.Mock(return_value=ReconciliationResult(status="POSITION_OPEN"))
        with self.assertRaisesRegex(ExecutionWorkerError, "FORCE_CLOSE_RECONCILIATION_NOT_FLAT"):
            ExecutionWorker.force_close_open_position(
                worker, reason="OPERATOR_TESTNET_FORCE_CLOSE"
            )

    def test_cli_exposes_reconcile_and_force_close_as_mutually_exclusive_actions(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                str(repo / "run_execution.py"),
                "--profile", "testnet-trade",
                "--testnet-reconcile",
                "--testnet-force-close",
            ],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowed with argument", result.stderr)

    def test_canary_loop_records_existing_position_management_latency(self):
        text = (Path(__file__).resolve().parents[1] / "run_execution.py").read_text()
        self.assertIn('"position_management_ms"', text)
        self.assertIn("health.last_position_manage_ms", text)
        self.assertIn("health.max_position_manage_ms", text)

    def test_nbotctl_distinguishes_accepted_core_from_active_v32_work(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [str(repo / "nbotctl"), "status"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["phase"], "V3.1")
        self.assertEqual(payload["active_execution_phase"], "V3.2")


if __name__ == "__main__":
    unittest.main()
