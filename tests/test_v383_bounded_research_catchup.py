from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import nbot_admin

from nbot.config.profiles import get_profile
from nbot.observation.catchup import (
    BoundedResearchCatchupController,
    CATCHUP_CONFIG,
    ResearchCatchupError,
)
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.worker import ObservationRuntimeLock, observation_runtime_lock_path
from tests.test_v343_future_paths import store_live


class _FakeRetention:
    def __init__(self, owner):
        self.owner = owner

    def audit(self):
        return {"healthy": True, "live_bytes": 800_000_000}

    def maintain(self, *, seal_max_events, compact_max_events):
        state = self.owner.state
        pending = int(state["pending_unsealed_events"])
        sealed_now = min(int(seal_max_events), pending)
        state["ledger_events"] += sealed_now
        state["sealed_events"] += sealed_now
        state["pending_unsealed_events"] -= sealed_now
        state["compactable_events"] = int(state.get("compactable_events", 0)) + sealed_now

        # The production fixture represented by this harness is already beyond
        # the 60+64 protection boundary, so every newly sealed event moves one
        # older SEALED event into the compactable middle window.
        compacted_now = min(int(compact_max_events), sealed_now)
        state["sealed_events"] -= compacted_now
        state["compacted_events"] += compacted_now
        state["detailed_selection_events"] -= compacted_now
        state["compactable_events"] -= compacted_now
        return {
            "seal": {
                "attempted_events": sealed_now,
                "sealed_events": sealed_now,
            },
            "compact": {
                "attempted_events": compacted_now,
                "compacted_events": compacted_now,
                "compacted_event_open_ms": list(range(compacted_now)),
            },
            "audit": {
                "healthy": True,
                "live_bytes": 800_000_000,
                "reusable_bytes": compacted_now * 5_000_000,
            },
            "hard_live_bytes_ok": True,
        }

    def compact(self, *, max_events):
        state = self.owner.state
        compacted_now = min(int(max_events), int(state.get("compactable_events", 0)))
        state["sealed_events"] -= compacted_now
        state["compacted_events"] += compacted_now
        state["detailed_selection_events"] -= compacted_now
        state["compactable_events"] -= compacted_now
        return {
            "attempted_events": compacted_now,
            "compacted_events": compacted_now,
            "compacted_event_open_ms": list(range(compacted_now)),
        }


class _HarnessController(BoundedResearchCatchupController):
    def __init__(
        self, repo_root: Path, *, selection_progress: int = 8, state=None,
        fail_component: str | None = None,
    ):
        self.repo_root = Path(repo_root)
        self.config = CATCHUP_CONFIG
        self.selection_progress = int(selection_progress)
        self.fail_component = fail_component
        self.state = dict(state or {
            "ledger_events": 125,
            "sealed_events": 124,
            "compacted_events": 1,
            "detailed_selection_events": 124,
            "pending_unsealed_events": 0,
            "compactable_events": 0,
        })
        self.retention = _FakeRetention(self)
        self._champion = {
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "evaluation": [
                "REJECT_RESEARCH_CHAMPION", 40, 20, 20, 0,
                "INTRADAY_BASELINE_V1", "frozen-digest",
            ],
            "champion": None,
        }
        self.gates = []
        self.build_calls = []

    @property
    def lock_path(self):
        return self.repo_root / "runtime" / "observation" / "live" / "research-catchup.lock"

    def _champion_fingerprint(self):
        return dict(self._champion)

    def _gate(
        self, baseline_champion, *, stage, deep_research=True,
        require_build_headroom=False,
    ):
        if self._champion_fingerprint() != baseline_champion:
            self._fail("NBOT_V383_CHAMPION_FINGERPRINT_CHANGED", stage=stage)
        self.gates.append((stage, deep_research))
        return {
            "collector": {"healthy": True},
            "integrity": {"healthy": True},
            "retention_live_bytes": 800_000_000,
            "research_healthy": True if deep_research else None,
            "champion": dict(self._champion),
        }

    def _lifecycle_counts(self):
        return dict(self.state)

    def _build_component(self, component, batch_events):
        self.build_calls.append((component, batch_events))
        if component == self.fail_component:
            raise RuntimeError("synthetic-build-failure")
        if component == "selection" and self.selection_progress:
            self.state["detailed_selection_events"] += self.selection_progress
            self.state["pending_unsealed_events"] += self.selection_progress
        return {"component": component, "max_events": batch_events}


class V383BoundedResearchCatchupTests(unittest.TestCase):
    def test_00_controller_uses_detail_count_not_ledger_count_for_plus_eight(self):
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(Path(td), selection_progress=8)
            report = controller.run(batch_events=8, max_cycles=1)

        self.assertTrue(report["healthy"], report)
        self.assertEqual(report["completed_cycles"], 1)
        self.assertEqual(report["final_counts"]["ledger_events"], 133)
        self.assertEqual(report["final_counts"]["detailed_selection_events"], 124)
        self.assertEqual(report["final_counts"]["compacted_events"], 9)
        cycle = report["cycles"][0]
        self.assertEqual(cycle["selection_events_built"], 8)
        self.assertEqual(cycle["ledger_delta"], 8)
        self.assertEqual(cycle["compacted_delta"], 8)
        self.assertEqual(
            [name for name, _ in controller.build_calls],
            ["features", "signals", "outcomes", "policies", "selection"],
        )

    def test_01_no_mature_selection_event_stops_without_compaction(self):
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(Path(td), selection_progress=0)
            report = controller.run(batch_events=8, max_cycles=4)

        self.assertTrue(report["healthy"], report)
        self.assertEqual(report["status"], "WAIT_FOR_MATURE_EVIDENCE")
        self.assertEqual(report["completed_cycles"], 0)
        self.assertEqual(report["final_counts"]["ledger_events"], 125)
        self.assertEqual(report["final_counts"]["compacted_events"], 1)

    def test_02_interrupted_pending_batch_is_recovered_before_new_build(self):
        state = {
            "ledger_events": 125,
            "sealed_events": 124,
            "compacted_events": 1,
            "detailed_selection_events": 132,
            "pending_unsealed_events": 8,
            "compactable_events": 0,
        }
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(
                Path(td), selection_progress=0, state=state
            )
            report = controller.run(batch_events=8, max_cycles=1)

        self.assertIsNotNone(report["recovery"])
        self.assertEqual(report["recovery"]["before"]["pending_unsealed_events"], 8)
        self.assertEqual(report["final_counts"]["ledger_events"], 133)
        self.assertEqual(report["final_counts"]["detailed_selection_events"], 124)
        self.assertEqual(report["final_counts"]["pending_unsealed_events"], 0)

    def test_03_selection_delta_above_proven_batch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(Path(td), selection_progress=9)
            with self.assertRaisesRegex(
                ResearchCatchupError, "NBOT_V383_SELECTION_DELTA_INVALID"
            ):
                controller.run(batch_events=8, max_cycles=1)

    def test_04_batch_and_cycle_limits_cannot_be_weakened_from_cli_contract(self):
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(Path(td), selection_progress=0)
            with self.assertRaisesRegex(ValueError, "BATCH_EVENTS_MUST_BE_1_TO_8"):
                controller.run(batch_events=9, max_cycles=1)
            with self.assertRaisesRegex(ValueError, "MAX_CYCLES_OUT_OF_RANGE"):
                controller.run(batch_events=8, max_cycles=33)


    def test_05_interrupted_compaction_backlog_is_recovered_before_build(self):
        state = {
            "ledger_events": 133,
            "sealed_events": 129,
            "compacted_events": 4,
            "detailed_selection_events": 129,
            "pending_unsealed_events": 0,
            "compactable_events": 5,
        }
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(
                Path(td), selection_progress=0, state=state
            )
            report = controller.run(batch_events=8, max_cycles=1)

        self.assertIsNotNone(report["recovery"])
        self.assertEqual(report["recovery"]["before"]["compactable_events"], 5)
        self.assertEqual(report["final_counts"]["detailed_selection_events"], 124)
        self.assertEqual(report["final_counts"]["compacted_events"], 9)
        self.assertEqual(report["final_counts"]["compactable_events"], 0)


    def test_06_admin_cli_exposes_only_bounded_catchup_controls(self):
        parser = nbot_admin.build_parser()
        args = parser.parse_args([
            "research-catchup", "--batch-events", "8", "--max-cycles", "3"
        ])
        self.assertEqual(args.command, "research-catchup")
        self.assertEqual(args.batch_events, 8)
        self.assertEqual(args.max_cycles, 3)
        defaults = parser.parse_args(["research-catchup"])
        self.assertEqual(defaults.batch_events, 8)
        self.assertEqual(defaults.max_cycles, 1)


    def test_07_build_failure_is_wrapped_with_component_identity(self):
        with tempfile.TemporaryDirectory() as td:
            controller = _HarnessController(
                Path(td), selection_progress=0, fail_component="outcomes"
            )
            with self.assertRaises(ResearchCatchupError) as cm:
                controller.run(batch_events=8, max_cycles=1)
        self.assertEqual(cm.exception.code, "NBOT_V383_BUILD_FAILED")
        self.assertEqual(cm.exception.report["component"], "outcomes")
        self.assertEqual(cm.exception.report["error_type"], "RuntimeError")

    def test_05_collector_health_requires_live_runtime_lock_and_fresh_capture(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            try:
                os.chdir(td)
                cfg = observation_config_for_profile(get_profile("live-paper"))
                db = EvidenceDatabase(cfg)
                store_live(db, 1)
                with db.connection() as conn:
                    captured = int(conn.execute(
                        "SELECT MAX(captured_at_ms) FROM market_events"
                    ).fetchone()[0])
                controller = BoundedResearchCatchupController(
                    db,
                    Path(td),
                    now_ms=lambda: captured + 1_000,
                )
                self.assertFalse(controller._collector_health()["healthy"])
                lock = ObservationRuntimeLock(
                    observation_runtime_lock_path(Path(td), "LIVE")
                )
                with lock:
                    health = controller._collector_health()
                    self.assertTrue(health["healthy"], health)
                    self.assertTrue(health["runtime_lock_held"])
                    self.assertEqual(health["capture_age_ms"], 1_000)
            finally:
                os.chdir(prior)


if __name__ == "__main__":
    unittest.main()
