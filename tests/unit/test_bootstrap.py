from pathlib import Path
import tempfile
import unittest

from nbot.config.bootstrap import DIRECTORY_MODE, bootstrap_layout, required_directories, validate_layout
from nbot.config.validation import MachineRole


class BootstrapLayoutTests(unittest.TestCase):
    def test_execution_bootstrap_creates_only_execution_role_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.EXECUTION)
            self.assertTrue((root / "data/execution/testnet/pending_outcomes").is_dir())
            self.assertTrue((root / "runtime/execution/real").is_dir())
            self.assertFalse((root / "data/observation").exists())
            self.assertFalse((root / "runtime/observation").exists())

    def test_observation_bootstrap_creates_only_observation_role_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.OBSERVATION)
            self.assertTrue((root / "data/observation/live/backups").is_dir())
            self.assertTrue((root / "runtime/observation/testnet").is_dir())
            self.assertFalse((root / "data/execution").exists())
            self.assertFalse((root / "runtime/execution").exists())

    def test_bootstrap_enforces_0700_on_all_required_mutable_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.EXECUTION)
            for relative in required_directories(MachineRole.EXECUTION):
                mode = (root / relative).stat().st_mode & 0o777
                self.assertEqual(mode, DIRECTORY_MODE, relative)

    def test_bootstrap_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = bootstrap_layout(root, MachineRole.OBSERVATION)
            second = bootstrap_layout(root, MachineRole.OBSERVATION)
            self.assertEqual(first, second)
            self.assertEqual(validate_layout(root, MachineRole.OBSERVATION), ())

    def test_validate_layout_reports_missing_directories_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = validate_layout(tmp, MachineRole.EXECUTION)
            self.assertTrue(any(item.startswith("MISSING:") for item in problems))

    def test_validate_layout_rejects_opposite_role_mutable_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.EXECUTION)
            (root / "data/observation/live").mkdir(parents=True)
            problems = validate_layout(root, MachineRole.EXECUTION)
            self.assertIn("FORBIDDEN_ROLE_PATH:data/observation", problems)

    def test_bootstrap_creates_no_credentials_state_database_or_arm_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.EXECUTION)
            forbidden_names = {
                "execution_state.json",
                "observer.db",
                "TESTNET_TRADING_ARMED",
                "LIVE_TRADING_ARMED",
                ".env",
            }
            present = {path.name for path in root.rglob("*") if path.is_file()}
            self.assertTrue(forbidden_names.isdisjoint(present))
            self.assertEqual(present, set())


if __name__ == "__main__":
    unittest.main()
