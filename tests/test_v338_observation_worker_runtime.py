from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.config.profiles import get_profile
from nbot.observation import (
    BinancePublicMarketError,
    CollectionResult,
    EvidenceDatabase,
    EvidenceDatabaseError,
    FundingSyncResult,
    GapRecoveryResult,
    ObservationCollectionNotReady,
    ObservationRuntimeAlreadyRunning,
    ObservationRuntimeLock,
    ObservationWorker,
    observation_config_for_profile,
    observation_runtime_lock_path,
)


REPO = Path(__file__).resolve().parents[1]


def load_run_observation():
    spec = importlib.util.spec_from_file_location(
        "nbot_v338_run_observation", REPO / "run_observation.py"
    )
    if spec is None or spec.loader is None:
        raise AssertionError("run_observation import spec missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def live_config():
    return observation_config_for_profile(get_profile("live-paper"))


def complete(status: str = "COMPLETE") -> CollectionResult:
    return CollectionResult(
        event_open_ms=1_800_000,
        requested_symbols=2,
        stored_symbols=2 if status == "COMPLETE" else 0,
        errors=0 if status == "COMPLETE" else 1,
        status=status,
        skipped=status == "ALREADY_COMPLETE",
        capture_duration_ms=100,
        context_delay_ms=500,
        clock_skew_before_ms=10,
        clock_skew_after_ms=12,
    )


def recovery() -> GapRecoveryResult:
    return GapRecoveryResult(1, 1, 1, 1, 0, 0)


def funding(reason: str = "COMPLETE") -> FundingSyncResult:
    return FundingSyncResult(False, 3, 1_000, 2_000, reason)


class FakeDatabase:
    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.initialized = 0

    def initialize(self) -> None:
        self.initialized += 1

    def integrity_check(self):
        return {"ok": self.healthy}


class FakeClient:
    pass


class FakeCollector:
    def __init__(self, collections):
        self.collections = list(collections)
        self.recovery_calls = 0
        self.funding_calls = 0
        self.wait_calls = 0
        self.wait_seconds = 7.5

    def collect_once(self):
        value = self.collections.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def recover_gaps(self):
        self.recovery_calls += 1
        return recovery()

    def sync_funding_history(self):
        self.funding_calls += 1
        return funding()

    def seconds_until_next_collection(self):
        self.wait_calls += 1
        return self.wait_seconds


class V338ObservationWorkerRuntimeTests(unittest.TestCase):
    def worker(self, *, healthy: bool = True, events=None):
        db = FakeDatabase(healthy=healthy)
        emitted = []
        worker = ObservationWorker(live_config(), FakeClient(), db, event_sink=emitted.append)
        collector = FakeCollector(events or [complete()])
        worker.collector = collector
        waits = []
        worker._wait = lambda seconds: waits.append(seconds)
        return worker, db, collector, emitted, waits

    def test_initialize_requires_database_integrity(self):
        worker, db, _, _, _ = self.worker(healthy=False)
        with self.assertRaisesRegex(RuntimeError, "DB_INTEGRITY_FAILED"):
            worker.initialize()
        self.assertEqual(db.initialized, 1)

    def test_complete_cycle_runs_live_then_recovery_then_funding(self):
        worker, _, collector, emitted, _ = self.worker()
        result = worker.run_cycle()
        self.assertEqual(result.collection.status, "COMPLETE")
        self.assertEqual(result.gap_recovery.recovered, 1)
        self.assertEqual(result.funding_sync.rows, 3)
        self.assertFalse(result.retry_fresh_event)
        self.assertEqual(collector.recovery_calls, 1)
        self.assertEqual(collector.funding_calls, 1)
        self.assertEqual(emitted[-1]["event"], "CYCLE")

    def test_already_complete_restart_cycle_still_recovers_and_syncs(self):
        worker, _, collector, _, _ = self.worker(events=[complete("ALREADY_COMPLETE")])
        result = worker.run_cycle()
        self.assertEqual(result.collection.status, "ALREADY_COMPLETE")
        self.assertEqual(collector.recovery_calls, 1)
        self.assertEqual(collector.funding_calls, 1)

    def test_unknown_collection_status_fails_closed(self):
        worker, _, _, _, _ = self.worker(events=[complete("UNKNOWN")])
        with self.assertRaisesRegex(RuntimeError, "COLLECTION_STATUS_INVALID"):
            worker.run_cycle()

    def test_fresh_partial_event_is_not_immediately_gap_recovered(self):
        worker, _, collector, _, _ = self.worker(events=[complete("PARTIAL_REJECTED")])
        result = worker.run_cycle()
        self.assertTrue(result.retry_fresh_event)
        self.assertIsNone(result.gap_recovery)
        self.assertIsNone(result.funding_sync)
        self.assertEqual(collector.recovery_calls, 0)
        self.assertEqual(collector.funding_calls, 0)

    def test_run_retries_fresh_partial_before_counting_successful_cycle(self):
        worker, _, collector, _, waits = self.worker(
            events=[complete("PARTIAL_REJECTED"), complete()]
        )
        cycles = worker.run(max_cycles=1)
        self.assertEqual(cycles, 1)
        self.assertEqual(waits, [worker.config.retry_seconds])
        self.assertEqual(collector.recovery_calls, 1)
        self.assertEqual(collector.funding_calls, 1)

    def test_not_ready_waits_exact_requested_delay_then_retries(self):
        worker, _, _, _, waits = self.worker()
        fake = FakeCollector([ObservationCollectionNotReady(1250), complete()])
        worker.collector = fake
        cycles = worker.run(max_cycles=1)
        self.assertEqual(cycles, 1)
        self.assertEqual(waits, [1.25])

    def test_transient_binance_failure_retries_without_process_failure(self):
        worker, _, _, emitted, waits = self.worker()
        fake = FakeCollector([BinancePublicMarketError("temporary"), complete()])
        worker.collector = fake
        cycles = worker.run(max_cycles=1)
        self.assertEqual(cycles, 1)
        self.assertEqual(waits, [worker.config.retry_seconds])
        self.assertTrue(any(row["event"] == "TRANSIENT_ERROR" for row in emitted))

    def test_database_failure_is_fatal_not_retried(self):
        worker, _, _, _, waits = self.worker()
        worker.collector = FakeCollector([EvidenceDatabaseError("db failed")])
        with self.assertRaises(EvidenceDatabaseError):
            worker.run(max_cycles=1)
        self.assertEqual(waits, [])

    def test_successful_cycles_sleep_to_next_canonical_collection(self):
        worker, _, collector, _, waits = self.worker(events=[complete(), complete()])
        cycles = worker.run(max_cycles=2)
        self.assertEqual(cycles, 2)
        self.assertEqual(waits, [collector.wait_seconds])
        self.assertEqual(collector.wait_calls, 1)

    def test_stop_prevents_second_cycle(self):
        worker, _, collector, _, _ = self.worker(events=[complete(), complete()])
        original = worker.run_cycle

        def stop_after_first():
            result = original()
            worker.stop()
            return result

        worker.run_cycle = stop_after_first
        cycles = worker.run()
        self.assertEqual(cycles, 1)
        self.assertEqual(len(collector.collections), 1)

    def test_event_sink_failure_cannot_crash_worker(self):
        db = FakeDatabase()
        worker = ObservationWorker(
            live_config(), FakeClient(), db,
            event_sink=lambda _payload: (_ for _ in ()).throw(RuntimeError("logger down")),
        )
        worker.collector = FakeCollector([complete()])
        self.assertEqual(worker.run(max_cycles=1), 1)

    def test_runtime_lock_paths_separate_live_and_testnet(self):
        live = observation_runtime_lock_path(Path("/repo"), "LIVE")
        testnet = observation_runtime_lock_path(Path("/repo"), "TESTNET")
        self.assertEqual(live, Path("/repo/runtime/observation/live/observation.lock"))
        self.assertEqual(testnet, Path("/repo/runtime/observation/testnet/observation.lock"))
        self.assertNotEqual(live, testnet)

    def test_duplicate_same_environment_runtime_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "observation.lock"
            first = ObservationRuntimeLock(path)
            second = ObservationRuntimeLock(path)
            first.acquire()
            try:
                with self.assertRaises(ObservationRuntimeAlreadyRunning):
                    second.acquire()
            finally:
                first.release()

    def test_runtime_lock_releases_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "observation.lock"
            with ObservationRuntimeLock(path):
                pass
            with ObservationRuntimeLock(path):
                pass

    def test_run_observation_has_no_execution_or_order_import(self):
        text = (REPO / "run_observation.py").read_text(encoding="utf-8")
        # V3.5 deliberately adds the authenticated communication service to
        # Observation, but never execution/order authority.
        for token in ("nbot.execution", "nbot.exchange"):
            self.assertNotIn(token, text)
        self.assertIn("nbot.communication.server", text)
        self.assertNotIn("API_KEY", text)
        self.assertNotIn("API_SECRET", text)

    def test_run_observation_help_needs_no_machine_role(self):
        module = load_run_observation()
        with mock.patch("sys.argv", ["run_observation.py", "--help"]):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    module.main()
        self.assertEqual(caught.exception.code, 0)

    def test_build_worker_rejects_wrong_machine_role(self):
        module = load_run_observation()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".nbot-role").write_text("EXECUTION\n")
            with self.assertRaisesRegex(ValueError, "WRONG_MACHINE_ROLE"):
                module.build_observation_worker(
                    repo_root=root,
                    profile_name="live-paper",
                    environment={},
                )

    def test_build_worker_rejects_private_order_secret_environment(self):
        module = load_run_observation()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".nbot-role").write_text("OBSERVATION\n")
            with self.assertRaisesRegex(ValueError, "PRIVATE_CREDENTIAL_FORBIDDEN"):
                module.build_observation_worker(
                    repo_root=root,
                    profile_name="live-paper",
                    environment={"BINANCE_API_KEY": "forbidden"},
                )

    def test_build_worker_rejects_actual_v32_testnet_execution_secret_names(self):
        module = load_run_observation()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".nbot-role").write_text("OBSERVATION\n")
            with self.assertRaisesRegex(ValueError, "PRIVATE_CREDENTIAL_FORBIDDEN"):
                module.build_observation_worker(
                    repo_root=root,
                    profile_name="testnet-trade",
                    environment={"TESTNET_API_SECRET": "forbidden"},
                )

    def test_live_trade_profile_is_explicitly_forbidden_before_v310(self):
        module = load_run_observation()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".nbot-role").write_text("OBSERVATION\n")
            with self.assertRaisesRegex(ValueError, "LIVE_TRADE_PROFILE_FORBIDDEN_BEFORE_V3_10"):
                module.build_observation_worker(
                    repo_root=root,
                    profile_name="live-trade",
                    environment={},
                )

    def test_real_evidence_database_startup_integrity_on_clean_db(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = live_config()
            cfg = type(cfg)(
                **{
                    **cfg.__dict__,
                    "database_path": Path(td) / "observer.db",
                    "backup_directory": Path(td) / "backups",
                }
            )
            # The canonical config intentionally requires canonical relative
            # paths, so directly exercise DB integrity using a patched validated
            # test config rather than weakening production path validation.
            with mock.patch.object(type(cfg), "validate", return_value=None):
                db = EvidenceDatabase(cfg)
                db.initialize()
                self.assertTrue(db.integrity_check()["ok"])


if __name__ == "__main__":
    unittest.main()
