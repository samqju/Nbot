from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import nbot_admin
from nbot.observation.challengers import (
    AUTHORITY,
    CHALLENGER_FAMILY,
    EVALUATION_PREFIX,
    ContinuousChallengerCycle,
)
from nbot.observation.research_memory import LEDGER_COLUMNS, RIDGE_COLUMNS, ResearchMemoryStore
from nbot.observation.retention import ARCHIVE_VERSION, _encode_training_rows
from nbot.observation.selection import FEATURE_VECTOR_NAMES, RidgeSufficientStatistics, SELECTION_CONFIG, _digest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class V391ContinuousChallengerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.memory = ResearchMemoryStore(Path(self.tmp.name) / "research_memory.db")
        self.memory.initialize(generation="TEST_V391", generation_floor_ms=0)
        self.release_sha = "a" * 40
        self.next_event = 300_000

    def tearDown(self):
        self.tmp.cleanup()

    def _feature_vector(self) -> str:
        vector = {name: 0.0 for name in FEATURE_VECTOR_NAMES}
        vector["atr14_frac"] = 0.01
        return canonical(vector)

    def _event_rows(self, event: int, *, target: float = -1.0):
        rows = []
        for symbol, side in (("AAAUSDT", "LONG"), ("ZZZUSDT", "SHORT")):
            example = {
                "event_open_ms": event,
                "symbol": symbol,
                "side": side,
                "feature_vector_json": self._feature_vector(),
                "target_net_r": target,
                "target_net_return_frac": target * 0.01,
                "target_mfe_r": max(0.5, target if target > 0 else 0.5),
                "target_mae_r": 1.0,
                "source_policy_result_digest": f"policy-{event}-{symbol}-{side}",
                "source_feature_digest": f"feature-{event}",
                "source_signal_digest": f"signal-{event}",
                "example_digest": f"example-{event}-{symbol}-{side}",
            }
            rows.append(example)
        return rows

    def _append_events(self, count: int, state: RidgeSufficientStatistics, *, target: float = -1.0):
        ledger = []
        for _ in range(count):
            event = self.next_event
            self.next_event += 300_000
            rows = self._event_rows(event, target=target)
            blob, training_digest, raw_bytes = _encode_training_rows(rows)
            selector_summary = {}
            policy_summary = {}
            build_manifest = {}
            selector_json = canonical(selector_summary)
            policy_json = canonical(policy_summary)
            manifest_json = canonical(build_manifest)
            archive_digest = digest_text(canonical({
                "archive_version": ARCHIVE_VERSION,
                "event_open_ms": event,
                "selector_summary": selector_summary,
                "policy_summary": policy_summary,
                "build_manifest": build_manifest,
                "training_digest": training_digest,
                "example_row_count": len(rows),
            }))
            row = (
                event,
                ARCHIVE_VERSION,
                event + 1,
                len(rows),
                "ZLIB_CANONICAL_JSON_V1",
                blob,
                training_digest,
                raw_bytes,
                len(blob),
                selector_json,
                policy_json,
                manifest_json,
                archive_digest,
                AUTHORITY,
            )
            self.assertEqual(len(row), len(LEDGER_COLUMNS))
            ledger.append(row)
            state.add_event(event, rows)
        self.memory.import_ledger_rows(ledger, source_generation="TEST_V391")
        payload = state.to_payload()
        ridge_row = (
            SELECTION_CONFIG.lab_version,
            SELECTION_CONFIG.learned_selector_version,
            state.through_event_ms,
            state.event_count,
            state.row_count,
            canonical(payload),
            _digest(payload),
            self.next_event,
        )
        self.assertEqual(len(ridge_row), len(RIDGE_COLUMNS))
        self.memory.replace_ridge_state(ridge_row)

    def test_first_cycle_freezes_research_only_artifacts_and_waits_for_future(self):
        state = RidgeSufficientStatistics.empty()
        self._append_events(25, state)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        report = cycle.cycle()
        self.assertEqual(report["action"], "TRAIN")
        self.assertEqual(report["status"], "TRAINED_WAIT_FOR_FUTURE_EVIDENCE")
        self.assertEqual(report["authority"], AUTHORITY)
        self.assertFalse(report["automatic_promotion"])
        status = cycle.status()
        self.assertEqual(status["challenger_artifacts"], 1)
        self.assertEqual(status["evaluation_artifacts"], 0)
        self.assertEqual(status["challenger_family"], CHALLENGER_FAMILY)
        self.assertEqual(status["active_future_evidence"]["available_future_events"], 0)
        self.assertTrue(cycle.audit()["healthy"])

    def test_future_window_is_frozen_and_abstention_is_zero_r_not_a_fake_trade(self):
        state = RidgeSufficientStatistics.empty()
        self._append_events(25, state, target=-1.0)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        first = cycle.cycle()
        cutoff = first["training_cutoff_event_ms"]

        self._append_events(40, state, target=-1.0)
        second = cycle.cycle()
        self.assertEqual(second["action"], "EVALUATE_FINAL_AND_TRAIN_NEXT")
        evaluation = second["evaluation"]
        self.assertEqual(evaluation["status"], "REJECT_RESEARCH_GATE")
        self.assertFalse(evaluation["automatic_promotion"])
        self.assertFalse(evaluation["research_champion_created"])

        stored = self.memory.artifact(EVALUATION_PREFIX + first["challenger_version"])
        self.assertIsNotNone(stored)
        detail = stored["payload"]
        self.assertTrue(all(int(event) > cutoff for event in detail["validation_events"] + detail["test_events"]))
        self.assertEqual(len(detail["validation_events"]), 20)
        self.assertEqual(len(detail["test_events"]), 20)
        self.assertEqual(detail["final_test"]["trade_utilization"]["trade_events"], 0)
        self.assertEqual(detail["final_test"]["candidate"]["mean_net_r"], 0.0)
        self.assertFalse(detail["promotion_gates"]["minimum_trade_events"])
        self.assertTrue(cycle.audit()["healthy"])

    def test_artifact_identity_is_immutable(self):
        payload = {"authority": AUTHORITY, "value": 1}
        first = self.memory.persist_artifact("v39:test:one", payload, recorded_at_ms=1)
        second = self.memory.persist_artifact("v39:test:one", payload, recorded_at_ms=2)
        self.assertEqual(first["artifact_digest"], second["artifact_digest"])
        with self.assertRaisesRegex(RuntimeError, "ARTIFACT_IDENTITY_CONFLICT"):
            self.memory.persist_artifact("v39:test:one", {"authority": AUTHORITY, "value": 2})

    def _seed_pending_epoch_transition(self, *, epoch_id: str, target_end_ms: int):
        self.memory.challenger_transition_status()
        with self.memory._connect() as conn:
            conn.execute(
                "INSERT INTO research_epoch_commits("
                "epoch_id,generation,target_start_ms,target_end_ms,event_count,"
                "imported_at_ms,source_digest,elapsed_seconds) VALUES(?,?,?,?,?,?,?,?)",
                (epoch_id, "TEST_V391", target_end_ms - 95 * 300_000,
                 target_end_ms, 96, target_end_ms + 1, "d" * 64, 1.0),
            )
            conn.execute(
                "INSERT INTO research_epoch_challenger_transitions("
                "epoch_id,target_end_ms,state,created_at_ms,attempt_count) "
                "VALUES(?,?,'PENDING',?,0)",
                (epoch_id, target_end_ms, target_end_ms + 2),
            )

    def test_epoch_transition_retry_detects_anchored_challenger_without_second_cycle(self):
        epoch_id = "EPOCH-TEST-REPLAY"
        cutoff = 9_600_000
        self._seed_pending_epoch_transition(epoch_id=epoch_id, target_end_ms=cutoff)
        self.memory.persist_artifact("v39:challenger:C-REPLAY", {
            "challenger_version": "C-REPLAY",
            "training_cutoff_event_ms": cutoff,
            "authority": AUTHORITY,
        })

        sync = mock.Mock()
        sync.sync.return_value = {"status": "PASS"}
        with (
            mock.patch.object(nbot_admin, "_memory", return_value=self.memory),
            mock.patch.object(
                nbot_admin, "_challenger_cycle",
                side_effect=AssertionError("duplicate challenger cycle"),
            ),
            mock.patch.object(nbot_admin, "_governance", return_value=sync),
            mock.patch.object(nbot_admin, "_market_regimes", return_value=sync),
        ):
            report = nbot_admin._run_epoch_challenger_transition()

        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["replay_detected"])
        self.assertEqual(report["challenger_version"], "C-REPLAY")
        self.assertEqual(report["cycle"]["action"], "REPLAY_ANCHORED_CHALLENGER")
        self.assertIsNone(self.memory.pending_challenger_transition())
        status = self.memory.challenger_transition_status()
        self.assertEqual(status["pending"], 0)
        self.assertEqual(status["completed"], 1)
        self.assertEqual(status["latest"]["challenger_training_cutoff_ms"], cutoff)

    def test_epoch_transition_failure_remains_pending_and_retryable(self):
        epoch_id = "EPOCH-TEST-FAIL"
        cutoff = 19_200_000
        self._seed_pending_epoch_transition(epoch_id=epoch_id, target_end_ms=cutoff)
        cycle = mock.Mock()
        cycle.cycle.side_effect = RuntimeError("synthetic challenger failure")
        with (
            mock.patch.object(nbot_admin, "_memory", return_value=self.memory),
            mock.patch.object(nbot_admin, "_challenger_cycle", return_value=cycle),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic challenger failure"):
                nbot_admin._run_epoch_challenger_transition()

        pending = self.memory.pending_challenger_transition()
        self.assertIsNotNone(pending)
        self.assertEqual(pending["epoch_id"], epoch_id)
        self.assertEqual(pending["state"], "PENDING")
        self.assertEqual(pending["attempt_count"], 1)
        self.assertIn("synthetic challenger failure", pending["last_error"])

    def test_admin_parser_exposes_challenger_commands(self):
        parser = nbot_admin.build_parser()
        for command in ("challenger-cycle", "challenger-status", "challenger-audit"):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
