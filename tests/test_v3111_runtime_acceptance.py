from __future__ import annotations

import contextlib
import fcntl
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from nbot.config.bootstrap import bootstrap_layout
from nbot.config.profiles import get_profile
from nbot.config.validation import (
    MachineRole,
    validate_execution_v31,
    validate_host_foundation,
    validate_role_profile,
)
from nbot.execution.outcomes import ExecutionHistoryStore, PendingOutcomeOutbox
from nbot.execution.state import ExecutionStatePaths, ExecutionStateStore


REPO = Path(__file__).resolve().parents[1]


def load_run_execution():
    spec = importlib.util.spec_from_file_location("nbot_v3111_run_execution", REPO / "run_execution.py")
    if spec is None or spec.loader is None:
        raise AssertionError("run_execution import spec missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_nbotctl():
    loader = SourceFileLoader("nbot_v3111_nbotctl", str(REPO / "nbotctl"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise AssertionError("nbotctl import spec missing")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class V3111RuntimeAcceptanceTests(unittest.TestCase):
    def test_runtime_entrypoint_is_implemented(self):
        text = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertNotIn("NBOT_V3_EXECUTION_NOT_IMPLEMENTED", text)
        self.assertIn("run_testnet_runtime", text)
        self.assertIn("worker.prepare()", text)
        self.assertIn("worker.disable_new_entries()", text)

    def test_execution_runtime_has_no_observation_research_import(self):
        forbidden = ("nbot.observation", "nbot.research", "nbot.learning", "nbot.strategy")
        files = list((REPO / "nbot/execution").glob("*.py")) + [REPO / "run_execution.py"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path}: {token}")

    def test_all_v31_capital_components_exist(self):
        required = (
            "models.py", "state.py", "risk.py", "entry.py", "position.py",
            "reconciliation.py", "emergency.py", "outcomes.py", "execution.py",
        )
        for name in required:
            self.assertTrue((REPO / "nbot/execution" / name).is_file(), name)
        self.assertTrue((REPO / "nbot/exchange/paper.py").is_file())
        self.assertTrue((REPO / "nbot/exchange/binance_testnet.py").is_file())

    def test_nbotctl_reports_current_v3_release_family(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        self.assertIn('PHASE = "V3"', text)
        self.assertIn('PHASE_STATUS = "CURRENT_RESEARCH_BUILD_ECONOMIC_WAIT"', text)
        self.assertNotIn('PHASE = "V3.0"', text)

    def test_local_operator_commands_are_implemented(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        for function in ("cmd_start", "cmd_stop", "cmd_restart", "cmd_logs"):
            self.assertIn(f"def {function}", text)
        self.assertIn("_start_execution", text)

    def test_nbotctl_help_exposes_runtime_commands(self):
        result = subprocess.run(
            [str(REPO / "nbotctl"), "--help"], cwd=REPO, text=True,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("start", "stop", "restart", "logs", "doctor", "status"):
            self.assertIn(command, result.stdout)

    def test_run_execution_help_requires_no_machine_role(self):
        result = subprocess.run(
            [str(REPO / "run_execution.py"), "--help"], cwd=REPO, text=True,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--profile", result.stdout)
        self.assertIn("--preflight-only", result.stdout)

    def test_pid_control_rejects_unrelated_process_identity(self):
        module = load_nbotctl()
        self.assertFalse(module._pid_matches_execution_runtime(os.getpid(), "testnet-trade"))

    def test_runtime_profile_is_explicit_not_defaulted_to_testnet(self):
        text = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertIn('parser.error("--profile or NBOT_PROFILE is required")', text)
        self.assertNotIn('os.environ.get("NBOT_PROFILE", "testnet-trade")', text)

    def test_systemd_template_requires_explicit_profile(self):
        text = (REPO / "deploy/systemd/nbot-execution.service.in").read_text(encoding="utf-8")
        self.assertIn("Environment=NBOT_PROFILE=@NBOT_PROFILE@", text)
        self.assertIn("--profile @NBOT_PROFILE@", text)

    def test_live_paper_runtime_is_v38_operational_canary(self):
        text = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertIn("run_live_paper_runtime", text)
        self.assertIn("LIVE_PAPER_OPERATIONAL_CANARY", text)
        self.assertNotIn("NBOT_LIVE_PAPER_RUNTIME_DEFERRED_UNTIL_V3_8", text)

    def test_live_trade_runtime_requires_explicit_trial_permission(self):
        text = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertIn("LIVE_EXPLICIT_TRIAL_ARM_REQUIRED", text)

    def test_testnet_runtime_authority_is_mechanical_only(self):
        module = load_run_execution()
        self.assertEqual(module.TESTNET_MECHANICAL_AUTHORITY, "TESTNET_MECHANICAL_ONLY")

    def test_runtime_leafs_are_profile_separated(self):
        module = load_run_execution()
        self.assertEqual(module.runtime_leaf("testnet-trade"), "testnet")
        self.assertEqual(module.runtime_leaf("live-paper"), "paper")
        self.assertEqual(module.runtime_leaf("live-trade"), "real")

    def test_testnet_build_refuses_missing_credentials(self):
        module = load_run_execution()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "TESTNET_CREDENTIALS_MISSING"):
                module.build_testnet_exchange(Path(tmp), {})

    def test_testnet_build_refuses_live_rest_host(self):
        module = load_run_execution()
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "TESTNET_API_KEY": "k",
                "TESTNET_API_SECRET": "s",
                "TESTNET_BASE_URL": "https://fapi.binance.com",
            }
            with self.assertRaisesRegex(ValueError, "TESTNET_REST_HOST_INVALID"):
                module.build_testnet_exchange(Path(tmp), env)

    def test_testnet_build_refuses_live_websocket_host(self):
        module = load_run_execution()
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "TESTNET_API_KEY": "k",
                "TESTNET_API_SECRET": "s",
                "TESTNET_WS_BASE_URL": "wss://fstream.binance.com",
            }
            with self.assertRaisesRegex(ValueError, "TESTNET_WS_HOST_INVALID"):
                module.build_testnet_exchange(Path(tmp), env)

    def test_secret_file_does_not_override_exported_environment(self):
        module = load_run_execution()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / "secret.env"
            secret.write_text("TESTNET_API_KEY=file-key\nTESTNET_API_SECRET=file-secret\n", encoding="utf-8")
            with mock.patch.dict(
                "os.environ",
                {"TESTNET_API_KEY": "export-key", "TESTNET_API_SECRET": "export-secret"},
                clear=False,
            ):
                env = module.runtime_environment(root, "testnet-trade", secret_file=secret)
            self.assertEqual(env["TESTNET_API_KEY"], "export-key")
            self.assertEqual(env["TESTNET_API_SECRET"], "export-secret")

    def test_self_check_has_no_order_authority(self):
        module = load_run_execution()
        with tempfile.TemporaryDirectory() as tmp, io.StringIO() as stream:
            with contextlib.redirect_stdout(stream):
                code = module.self_check(Path(tmp), "testnet-trade")
            self.assertEqual(code, 0)
            body = stream.getvalue()
            self.assertIn("NONE_V3_1_FAIL_CLOSED", body)
            self.assertIn("V3_1_EXECUTION_RUNTIME_READY_FOR_V3_2_TESTNET", body)

    def test_live_paper_doctor_contract_passes_clean_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_execution_v31(
                repo_root=tmp, profile=get_profile("live-paper"), environment={}
            )
            self.assertTrue(result.ok, result.warnings)
            self.assertIn("EXECUTION_PAPER_EXCHANGE_AVAILABLE", result.checks)
            self.assertIn("EXECUTION_STATE_CLEAN_START_READY", result.checks)
            self.assertIn("EXECUTION_PENDING_OUTCOMES:0", result.checks)
            self.assertIn("EXECUTION_SINGLE_INSTANCE_LOCK_AVAILABLE", result.checks)

    def test_live_paper_doctor_reports_operational_canary_no_economic_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_execution_v31(
                repo_root=tmp, profile=get_profile("live-paper"), environment={}
            )
            self.assertIn("EXECUTION_LIVE_PUBLIC_MARKET_ADAPTER_AVAILABLE", result.checks)
            self.assertIn("EXECUTION_LIVE_PUBLIC_BINANCE_HOST_PINNED", result.checks)
            self.assertIn(
                "LIVE_PAPER_OPERATIONAL_CANARY_HAS_NO_ECONOMIC_AUTHORITY",
                result.warnings,
            )

    def test_testnet_doctor_contract_checks_pinned_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_execution_v31(
                repo_root=tmp, profile=get_profile("testnet-trade"), environment={}
            )
            self.assertTrue(result.ok, result.warnings)
            self.assertIn("EXECUTION_TESTNET_ENDPOINTS_PINNED", result.checks)
            self.assertIn("EXECUTION_TESTNET_CREDENTIALS_REQUIRED_FOR_V3_2_RUNTIME", result.warnings)

    def test_testnet_doctor_contract_rejects_live_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_execution_v31(
                repo_root=tmp,
                profile=get_profile("testnet-trade"),
                environment={"TESTNET_BASE_URL": "https://fapi.binance.com"},
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("TESTNET_REST_HOST_INVALID" in item for item in result.warnings))

    def test_live_trade_doctor_contract_fails_before_v310(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_execution_v31(
                repo_root=tmp, profile=get_profile("live-trade"), environment={}
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("LIVE_CREDENTIALS_MISSING" in w for w in result.warnings))

    def test_corrupt_execution_state_fails_doctor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ExecutionStatePaths.for_profile(root, "live-paper")
            paths.state_file.parent.mkdir(parents=True, exist_ok=True)
            paths.state_file.write_text("{not-json", encoding="utf-8")
            result = validate_execution_v31(
                repo_root=root, profile=get_profile("live-paper"), environment={}
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("EXECUTION_DURABLE_STATE_INVALID" in item for item in result.warnings))

    def test_valid_execution_state_passes_integrity_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ExecutionStatePaths.for_profile(root, "live-paper")
            ExecutionStateStore(
                paths.state_file, profile="live-paper", market_environment="LIVE"
            )
            result = validate_execution_v31(
                repo_root=root, profile=get_profile("live-paper"), environment={}
            )
            self.assertTrue(result.ok, result.warnings)
            self.assertIn("EXECUTION_STATE_INTEGRITY_VALID", result.checks)

    def test_history_without_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ExecutionStatePaths.for_profile(root, "live-paper")
            ExecutionHistoryStore(paths.history_file).append("OUT-1", {"value": 1})
            result = validate_execution_v31(
                repo_root=root, profile=get_profile("live-paper"), environment={}
            )
            self.assertFalse(result.ok)
            self.assertIn("EXECUTION_STATE_MISSING_WITH_DURABLE_EVIDENCE", result.warnings)

    def test_pending_without_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ExecutionStatePaths.for_profile(root, "live-paper")
            PendingOutcomeOutbox(paths.pending_outcomes_dir).enqueue("OUT-1", {"value": 1})
            result = validate_execution_v31(
                repo_root=root, profile=get_profile("live-paper"), environment={}
            )
            self.assertFalse(result.ok)
            self.assertIn("EXECUTION_STATE_MISSING_WITH_DURABLE_EVIDENCE", result.warnings)

    def test_pending_outcome_is_visible_as_entry_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ExecutionStatePaths.for_profile(root, "live-paper")
            ExecutionStateStore(paths.state_file, profile="live-paper", market_environment="LIVE")
            PendingOutcomeOutbox(paths.pending_outcomes_dir).enqueue("OUT-1", {"value": 1})
            result = validate_execution_v31(
                repo_root=root, profile=get_profile("live-paper"), environment={}
            )
            self.assertTrue(result.ok, result.warnings)
            self.assertIn("EXECUTION_PENDING_OUTCOMES:1", result.checks)
            self.assertIn("EXECUTION_PENDING_OUTCOMES_BLOCK_NEW_REQUEST:1", result.warnings)

    def test_held_execution_lock_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / "runtime/execution/paper/execution.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            with lock.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = validate_execution_v31(
                    repo_root=root, profile=get_profile("live-paper"), environment={}
                )
                self.assertIn("EXECUTION_SINGLE_INSTANCE_LOCK_HELD", result.warnings)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def test_foundation_doctor_no_longer_defers_v31_execution_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bootstrap_layout(root, MachineRole.EXECUTION)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").write_text("", encoding="utf-8")
            (root / "requirements.txt").write_text("", encoding="utf-8")
            with mock.patch("nbot.config.validation._clock_synchronized", return_value=True), \
                 mock.patch("nbot.config.validation._git_worktree_clean", return_value=True):
                result = validate_host_foundation(repo_root=root, role=MachineRole.EXECUTION)
            self.assertFalse(any("DEFERRED_UNTIL_V3_1" in item for item in result.warnings))
            self.assertNotIn(
                "OPERATOR_TOOLING_DEBT:CROSS_VPS_PROTOCOL_COMPATIBILITY_NOT_IN_FOUNDATION_DOCTOR",
                result.warnings,
            )

    def test_role_profile_no_longer_uses_exchange_phase_credential_deferral(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_role_profile(
                repo_root=tmp,
                role=MachineRole.EXECUTION,
                profile=get_profile("testnet-trade"),
                environment={},
            )
            self.assertNotIn("EXECUTION_ORDER_CREDENTIAL_CHECK_DEFERRED_UNTIL_EXCHANGE_PHASE", result.warnings)
            self.assertIn("PROFILE_DISARMED", result.warnings)

    def test_canonical_roadmap_records_v3110_and_v3111_closure(self):
        text = (REPO / "docs/NBOT_V3_ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("## V3.1.10 Execution Worker integration", text)
        self.assertIn("## V3.1.11 Runtime and acceptance closure", text)
        self.assertIn("final V3.1 acceptance audit passes", text)

    def test_readme_declares_v31_acceptance_closure(self):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("V3.1 EXECUTION CORE", text)
        self.assertNotIn("Trading/research workers are intentionally not implemented yet", text)

    def test_execution_safety_contract_is_no_longer_placeholder(self):
        text = (REPO / "docs/EXECUTION_SAFETY_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("Permanent capital invariants", text)
        self.assertNotIn("Status: V3.0 placeholder", text)

    def test_operations_document_preserves_v32_history_and_current_transition(self):
        text = (REPO / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("## V3.2 standalone Testnet mechanical canary", text)
        self.assertIn("V3.7-A Normal LONG is physically proven", text)
        self.assertIn("V3.7-B Normal SHORT is physically proven end-to-end", text)


if __name__ == "__main__":
    unittest.main()
