from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys


REPO = Path(__file__).resolve().parents[1]


def load_installer():
    path = REPO / "deploy/observation/install_services.py"
    spec = importlib.util.spec_from_file_location("v385_observation_installer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class V385ObservationOperationsTests(unittest.TestCase):
    def test_live_collector_is_explicit_continuous_live_paper_service(self):
        text = (REPO / "deploy/systemd/nbot-observation-live.service.in").read_text()
        self.assertIn("run_observation.py --profile live-paper", text)
        self.assertIn("Restart=always", text)
        self.assertIn("PartOf=nbot-observer.target", text)
        self.assertIn("User=@NBOT_USER@", text)

    def test_epoch_is_low_priority_oneshot_with_pruning(self):
        text = (REPO / "deploy/systemd/nbot-research-epoch.service.in").read_text()
        self.assertIn("Type=oneshot", text)
        self.assertIn("research-epoch-run --prune-raw", text)
        self.assertIn("Nice=15", text)
        self.assertIn("CPUWeight=20", text)
        self.assertIn("IOWeight=20", text)
        self.assertIn("IOSchedulingClass=idle", text)
        self.assertNotIn("Restart=always", text)

    def test_epoch_timer_is_persistent_and_base_target_starts_only_base_work(self):
        timer = (REPO / "deploy/systemd/nbot-research-epoch.timer.in").read_text()
        target = (REPO / "deploy/systemd/nbot-observer.target.in").read_text()
        self.assertIn("Persistent=true", timer)
        self.assertIn("OnUnitInactiveSec=15min", timer)
        self.assertIn("nbot-observation-live.service", target)
        self.assertIn("nbot-research-epoch.timer", target)
        self.assertNotIn("live-paper-control", target)
        self.assertNotIn("testnet", target.lower())

    def test_v39_challenger_is_epoch_triggered_and_daily_timer_is_removed(self):
        self.assertFalse((REPO / "deploy/systemd/nbot-challenger-cycle.timer.in").exists())
        service = (REPO / "deploy/systemd/nbot-challenger-cycle.service.in").read_text()
        epoch_service = (REPO / "deploy/systemd/nbot-research-epoch.service.in").read_text()
        installer = (REPO / "deploy/observation/install_services.py").read_text()
        self.assertIn("Epoch Challenger Transition Recovery", service)
        self.assertIn("challenger-cycle", service)
        self.assertNotIn("nbot-research-epoch.service", service)
        self.assertIn("Nice=18", service)
        self.assertIn("CPUWeight=10", service)
        self.assertIn("IOWeight=10", service)
        self.assertNotIn("Restart=always", service)
        self.assertIn("TimeoutStartSec=4h30min", epoch_service)
        self.assertNotIn("enable-challenger-cycle", installer)
        self.assertNotIn("start-challenger-cycle", installer)
        self.assertNotIn("nbot-challenger-cycle.timer", installer)

    def test_live_paper_control_is_optional_but_restartable(self):
        text = (
            REPO / "deploy/systemd/nbot-observation-live-paper-control.service.in"
        ).read_text()
        self.assertIn("Restart=always", text)
        self.assertIn("User=@NBOT_USER@", text)

    def test_installer_renders_portable_units_without_starting(self):
        module = load_installer()
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td)
            written = module.render_units(
                repo=REPO,
                python=Path(sys.executable),
                user="root",
                destination=destination,
            )
            names = {path.name for path in written}
            self.assertEqual(
                names,
                set(module.BASE_UNIT_NAMES + module.OPTIONAL_UNIT_NAMES),
            )
            collector = (destination / "nbot-observation-live.service").read_text()
            self.assertIn(str(REPO), collector)
            self.assertIn(str(Path(sys.executable)), collector)
            self.assertNotIn("@NBOT_", collector)

    def test_admin_epoch_and_prune_share_process_lock(self):
        text = (REPO / "nbot_admin.py").read_text()
        self.assertIn('V384_EPOCH_LOCK_PATH = Path("runtime/observation/live/research_epoch.lock")', text)
        self.assertIn("NBOT_V384_EPOCH_COMMAND_LOCK_HELD", text)
        epoch_body = text.split("def cmd_research_epoch_run", 1)[1].split("def cmd_research_raw_prune", 1)[0]
        prune_body = text.split("def cmd_research_raw_prune", 1)[1].split("def cmd_research_generation_cutover", 1)[0]
        self.assertIn("with _research_epoch_command_lock()", epoch_body)
        self.assertIn("pending_challenger_transition", epoch_body)
        self.assertIn("_run_epoch_challenger_transition()", epoch_body)
        self.assertIn("with _research_epoch_command_lock()", prune_body)

    def test_generic_ambiguous_observation_template_is_removed(self):
        self.assertFalse((REPO / "deploy/systemd/nbot-observation.service.in").exists())


if __name__ == "__main__":
    unittest.main()
