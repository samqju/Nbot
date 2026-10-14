"""No-hindsight synthetic prospective policy freeze artifact tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nbot.v5.g4_policy_registry import register_prospective_policy
from nbot.v5.g4_prospective_policy import freeze_template
from nbot.v5.observation_contract import INTERVAL_MS

NOW=1800000000000


class FrozenProspectiveRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.folder=Path(self.tmp.name)/"g4-forward-registry-test"
        self.folder.mkdir(mode=0o700)
        self.file=self.folder/"g4_research_template.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_policy_is_frozen_ahead_of_future_event_without_source_hindsight(self):
        report=register_prospective_policy(output=self.file,declared_at_ms=NOW+3000)
        data=json.loads(self.file.read_text())
        self.assertEqual(report["policy_sha256"],
                         freeze_template(data["spec"]).policy_sha256)
        self.assertGreaterEqual(report["min_lead_ms"],600000)
        self.assertEqual(report["activation_at_ms"]%INTERVAL_MS,0)
        self.assertEqual(report["scored_outcomes"],0)
        self.assertFalse(report["source_quality_accepted"])
        self.assertEqual(data["financial_authority"],"NONE")
        self.assertEqual(data["spec"]["target_r_multiple"],"2.0")
        self.assertEqual(data["spec"]["atr_risk_multiple"],"1.5")

    def test_exact_file_sha_and_private_mode(self):
        report=register_prospective_policy(output=self.file,declared_at_ms=NOW)
        self.assertEqual(report["file_sha256"],
                         hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(self.file.stat().st_mode & 0o077,0)

    def test_reject_implicit_policy_retroactive_mutation(self):
        register_prospective_policy(output=self.file,declared_at_ms=NOW)
        with self.assertRaisesRegex(ValueError,"G4_POLICY_ISOLATION_OR_EXISTENCE_INVALID"):
            register_prospective_policy(output=self.file,declared_at_ms=NOW+1)

    def test_wrong_directory_refused(self):
        x=Path(self.tmp.name)/"other"/"g4_research_template.json"
        x.parent.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError,"G4_POLICY_ISOLATION_OR_EXISTENCE_INVALID"):
            register_prospective_policy(output=x,declared_at_ms=NOW)

    def test_invalid_clock_refused(self):
        with self.assertRaisesRegex(ValueError,"G4_PROSPECTIVE_DECLARATION_CLOCK_INVALID"):
            register_prospective_policy(output=self.file,declared_at_ms=True)

if __name__=="__main__":
    unittest.main()
