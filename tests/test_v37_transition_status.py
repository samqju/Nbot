from __future__ import annotations

from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]


class V37TransitionStatusTests(unittest.TestCase):
    def test_roadmap_preserves_exception_history_and_records_v37_closure(self):
        text = (REPO / "docs/NBOT_V3_ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("Implementation sequencing exception — 2026-08-21", text)
        self.assertIn("V3.7-B Normal SHORT: **DEFERRED**", text)
        self.assertIn("canonical V3.7 gate is **not fully passed**", text)
        self.assertIn("does not retroactively convert V3.7-B into a Testnet PASS", text)
        self.assertIn("V3.7-B closure — 2026-08-23", text)
        self.assertIn("PROP-33b8005daa79db45b237a3c449ec677c3d2d4db6", text)
        self.assertIn("OUT-9b671e52f3e35e5ca9138358a96df3ae", text)
        self.assertIn(
            "canonical V3.7 operational acceptance gate is now **PASSED**",
            text,
        )

    def test_protocol_no_longer_claims_v346_is_deferred(self):
        text = (REPO / "docs/PROTOCOL_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("V3.4.6 Research Champion evaluation", text)
        self.assertIn("V3.4.7", text)
        self.assertIn("RESEARCH_ONLY_NO_EXECUTION", text)
        self.assertNotIn("Because V3.4.6 Research Champion evaluation is deferred", text)

    def test_obsolete_doctor_phase_deferral_labels_are_removed(self):
        text = (REPO / "nbot/config/validation.py").read_text(encoding="utf-8")
        self.assertNotIn("OBSERVATION_DATABASE_INTEGRITY_CHECK_DEFERRED_UNTIL_V3_3", text)
        self.assertNotIn("CROSS_VPS_PROTOCOL_CHECK_DEFERRED_UNTIL_V3_6", text)
        self.assertIn("OPERATOR_TOOLING_DEBT:OBSERVATION_DATABASE_INTEGRITY_NOT_IN_FOUNDATION_DOCTOR", text)
        self.assertIn("OPERATOR_TOOLING_DEBT:CROSS_VPS_PROTOCOL_COMPATIBILITY_NOT_IN_FOUNDATION_DOCTOR", text)

    def test_cluster_debt_is_not_falsely_claimed_complete(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        self.assertIn("cluster.set_defaults(func=cmd_not_implemented)", text)
        operations = (REPO / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("cluster doctor/start/stop/status` remains unimplemented", operations)


if __name__ == "__main__":
    unittest.main()
