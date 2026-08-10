import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DEPLOY_DOCS = (
    ROOT / "deploy" / "README.md",
    ROOT / "deploy" / "FRESH_INSTALL.md",
    ROOT / "deploy" / "execution" / "README.md",
    ROOT / "deploy" / "observation" / "README.md",
)


class Phase6PlanAuditDocsHygieneTests(unittest.TestCase):
    def test_gitignore_has_no_duplicate_active_rules(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        rules = [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(rules), len(set(rules)))
        self.assertIn("nbot_*_audit.txt", rules)
        self.assertIn("data/", rules)
        self.assertIn("logs/", rules)
        self.assertIn("runtime/", rules)

    def test_current_deployment_docs_do_not_use_phase6a0_final(self):
        for path in CURRENT_DEPLOY_DOCS:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("phase6a0-final", text)

    def test_current_release_and_rollback_anchor_are_documented(self):
        readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
        fresh = (ROOT / "deploy" / "FRESH_INSTALL.md").read_text(
            encoding="utf-8"
        )
        for text in (readme, fresh):
            self.assertIn("pre-phase6b-clean", text)
            self.assertIn("phase6a-final", text)

    def test_role_env_ownership_and_switching_are_documented(self):
        readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
        fresh = (ROOT / "deploy" / "FRESH_INSTALL.md").read_text(
            encoding="utf-8"
        )
        combined = readme + "\n" + fresh
        self.assertIn("deploy/examples/execution.env.example", combined)
        self.assertIn("deploy/examples/observation.env.example", combined)
        self.assertIn("TESTNET+TRADE", combined)
        self.assertIn("LIVE+TRADE", combined)
        self.assertIn("private Binance", combined)

    def test_execution_log_policy_lists_lifecycle_events(self):
        operations = (ROOT / "deploy" / "OPERATIONS.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "POSITION_OPENED",
            "SL_UPDATE_ATTEMPT",
            "SL_UPDATE_VERIFIED",
            "POSITION_CLOSED_CONFIRMED",
            "POSITION_CLOSE_DETAILS",
        ):
            self.assertIn(marker, operations)
        self.assertIn("## Emergency Exit Validation", operations)


if __name__ == "__main__":
    unittest.main()
