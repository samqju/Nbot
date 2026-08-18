from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from nbot.config.profiles import PROFILES, get_profile
from nbot.config.validation import MachineRole, detect_role, profile_is_armed, validate_role_profile


class FoundationProfileTests(unittest.TestCase):
    def test_three_profiles_are_frozen(self):
        self.assertEqual(set(PROFILES), {"testnet-trade", "live-paper", "live-trade"})
        for profile in PROFILES.values():
            profile.validate()

    def test_live_paper_can_never_write_binance_orders(self):
        profile = get_profile("live-paper")
        self.assertFalse(profile.binance_order_writes)
        with self.assertRaises(ValueError):
            replace(profile, binance_order_writes=True).validate()

    def test_live_trade_requires_arm_gate(self):
        profile = get_profile("live-trade")
        self.assertTrue(profile.requires_arm_gate)
        with self.assertRaises(ValueError):
            replace(profile, requires_arm_gate=False).validate()

    def test_testnet_and_live_state_paths_do_not_overlap(self):
        testnet = get_profile("testnet-trade")
        paper = get_profile("live-paper")
        real = get_profile("live-trade")
        self.assertNotEqual(testnet.execution_state_dir, paper.execution_state_dir)
        self.assertNotEqual(testnet.execution_state_dir, real.execution_state_dir)
        self.assertEqual(paper.observation_db, real.observation_db)
        self.assertNotEqual(testnet.observation_db, paper.observation_db)

    def test_role_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".nbot-role").write_text("EXECUTION\n", encoding="utf-8")
            self.assertIs(detect_role(root), MachineRole.EXECUTION)
            (root / ".nbot-role").write_text("OBSERVATION\n", encoding="utf-8")
            self.assertIs(detect_role(root), MachineRole.OBSERVATION)

    def test_observation_rejects_private_order_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "NBOT_OBSERVATION_PRIVATE_CREDENTIAL_FORBIDDEN"):
                validate_role_profile(
                    repo_root=tmp,
                    role=MachineRole.OBSERVATION,
                    profile=get_profile("live-paper"),
                    environment={"BINANCE_API_SECRET": "secret"},
                )

    def test_execution_testnet_doctor_fails_while_disarmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_role_profile(
                repo_root=tmp,
                role=MachineRole.EXECUTION,
                profile=get_profile("testnet-trade"),
                environment={},
            )
            self.assertFalse(result.ok)
            self.assertIn("PROFILE_DISARMED", result.warnings)

    def test_observation_does_not_require_execution_arm_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_role_profile(
                repo_root=tmp,
                role=MachineRole.OBSERVATION,
                profile=get_profile("testnet-trade"),
                environment={},
            )
            self.assertTrue(result.ok)

    def test_testnet_arm_is_initially_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(profile_is_armed(tmp, get_profile("testnet-trade")))


if __name__ == "__main__":
    unittest.main()
