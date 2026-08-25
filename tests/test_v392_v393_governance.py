from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.observation.challengers import AUTHORITY, ContinuousChallengerCycle
from nbot.observation.governance import (
    CONFIG,
    CHAMPION_POINTER_GENESIS_KEY,
    CONTRACT_KEY,
    ELIGIBILITY_EPOCH_KEY,
    MODEL_REGISTRY_PREFIX,
    ROLLBACK_STATE_GENESIS_KEY,
    ModelGovernanceRegistry,
)
from nbot.observation.research_memory import LEDGER_COLUMNS, RIDGE_COLUMNS, ResearchMemoryStore
from nbot.observation.retention import ARCHIVE_VERSION, _encode_training_rows
from nbot.observation.selection import FEATURE_VECTOR_NAMES, RidgeSufficientStatistics, SELECTION_CONFIG, _digest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class V392V393GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.memory = ResearchMemoryStore(root / "research_memory.db")
        self.memory.initialize(generation="TEST_V392", generation_floor_ms=0)
        self.artifact_root = root / "model_artifacts"
        self.governance = ModelGovernanceRegistry(self.memory, self.artifact_root)
        self.release_sha = "b" * 40
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
            rows.append({
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
            })
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
                event, ARCHIVE_VERSION, event + 1, len(rows),
                "ZLIB_CANONICAL_JSON_V1", blob, training_digest, raw_bytes,
                len(blob), canonical(selector_summary), canonical(policy_summary),
                canonical(build_manifest), archive_digest, AUTHORITY,
            )
            self.assertEqual(len(row), len(LEDGER_COLUMNS))
            ledger.append(row)
            state.add_event(event, rows)
        self.memory.import_ledger_rows(ledger, source_generation="TEST_V392")
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

    def test_registry_materializes_model_file_and_safe_genesis_state(self):
        state = RidgeSufficientStatistics.empty()
        self._append_events(25, state)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        trained = cycle.cycle()
        self.assertEqual(trained["action"], "TRAIN")

        synced = self.governance.sync()
        self.assertEqual(synced["models_synced"], 1)
        self.assertEqual(synced["challengers_synced"], 1)
        status = self.governance.status()
        self.assertEqual(status["registered_models"], 1)
        self.assertEqual(status["registered_challengers"], 1)
        self.assertIsNone(status["champion_pointer"]["current_research_champion"])
        self.assertFalse(status["champion_pointer"]["automatic_promotion"])
        self.assertEqual(status["rollback_state"]["status"], "DISABLED_NO_RESEARCH_CHAMPION")
        self.assertFalse(status["paper_champion_authority"])

        model_version = trained["model_version"]
        model_memory = self.memory.artifact("v39:model:" + model_version)
        registry = self.memory.artifact(MODEL_REGISTRY_PREFIX + model_version)
        self.assertIsNotNone(model_memory)
        self.assertIsNotNone(registry)
        model_path = self.artifact_root / registry["payload"]["artifact_file"]
        self.assertTrue(model_path.is_file())
        self.assertEqual(hashlib.sha256(model_path.read_bytes()).hexdigest(), model_memory["artifact_digest"])
        self.assertIsNotNone(self.memory.artifact(CONTRACT_KEY))
        epoch = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        self.assertIsNotNone(epoch)
        self.assertEqual(epoch["payload"]["start_challenger_version"], trained["challenger_version"])
        self.assertIsNotNone(self.memory.artifact(CHAMPION_POINTER_GENESIS_KEY))
        self.assertIsNotNone(self.memory.artifact(ROLLBACK_STATE_GENESIS_KEY))
        self.assertTrue(self.governance.audit()["healthy"])

    def test_final_windows_become_immutable_rolling_reports_and_track_drift(self):
        state = RidgeSufficientStatistics.empty()
        self._append_events(25, state, target=-1.0)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        cycle.cycle()
        self._append_events(40, state, target=-1.0)
        first_final = cycle.cycle()
        self.assertEqual(first_final["action"], "EVALUATE_FINAL_AND_TRAIN_NEXT")
        self.assertEqual(first_final["evaluation"]["status"], "REJECT_RESEARCH_GATE")
        self.governance.sync()
        status_after_sync = self.governance.status()
        first = status_after_sync["latest_rolling_window"]
        self.assertEqual(first["status"], "REJECT_RESEARCH_GATE")
        self.assertFalse(first["historical_final_test_mutable"])
        self.assertEqual(first["calibration_brier"]["status"], "NOT_APPLICABLE")
        self.assertEqual(first["live_operational_degradation"]["status"], "DEFERRED")
        eligibility = status_after_sync["research_champion_eligibility"]
        self.assertEqual(eligibility["all_historical_final_windows"], 1)
        self.assertEqual(eligibility["available_final_windows"], 0)
        self.assertEqual(eligibility["excluded_pre_governance_windows"], 1)
        self.assertEqual(
            eligibility["eligibility_epoch"]["start_challenger_version"],
            first_final["next_challenger"]["challenger_version"],
        )

        self._append_events(40, state, target=-1.0)
        second_final = cycle.cycle()
        self.assertEqual(second_final["action"], "EVALUATE_FINAL_AND_TRAIN_NEXT")
        self.governance.sync()
        status = self.governance.status()
        self.assertEqual(status["rolling_final_windows"], 2)
        self.assertEqual(status["research_champion_eligibility"]["available_final_windows"], 1)
        self.assertEqual(status["research_champion_eligibility"]["excluded_pre_governance_windows"], 1)
        latest = status["latest_rolling_window"]
        self.assertEqual(latest["drift"]["status"], "MONITORED")
        self.assertAlmostEqual(latest["drift"]["rms_standardized_mean_shift"], 0.0)
        self.assertFalse(status["research_champion_eligibility"]["eligible_for_research_champion_review"])
        self.assertFalse(status["automatic_promotion"])
        self.assertTrue(self.governance.audit()["healthy"])

    def test_contract_freezes_multi_window_review_gate_before_promotion(self):
        contract = self.governance.contract()
        gate = contract["research_champion_review_gate"]
        self.assertEqual(gate["consecutive_pass_windows"], 3)
        self.assertEqual(gate["total_untouched_test_events"], 60)
        self.assertEqual(gate["total_trade_events"], 15)
        self.assertEqual(gate["minimum_elapsed_hours"], 48.0)
        self.assertEqual(gate["distinct_test_utc_dates"], 3)
        self.assertEqual(gate["drift_transitions_monitored"], 2)
        self.assertEqual(
            gate["pre_governance_windows"],
            "AUDIT_ONLY_EXCLUDED_FROM_ELIGIBILITY",
        )
        self.assertFalse(gate["automatic_promotion"])
        self.assertEqual(CONFIG.min_consecutive_pass_windows, 3)

    def test_audit_detects_model_file_tampering(self):
        state = RidgeSufficientStatistics.empty()
        self._append_events(25, state)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        trained = cycle.cycle()
        self.governance.sync()
        path = self.artifact_root / f"{trained['model_version']}.json"
        path.write_text("tampered", encoding="utf-8")
        audit = self.governance.audit()
        self.assertFalse(audit["healthy"])
        self.assertEqual(audit["model_file_digest_mismatch"], 1)

    def test_admin_parser_exposes_governance_commands(self):
        parser = nbot_admin.build_parser()
        for command in ("governance-sync", "governance-status", "governance-audit"):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
