"""Pinned integrated service templates must remain explicit owner-release HOLD.

Tests are static: never touch systemd, network, order APIs, or production data.
"""
from pathlib import Path
import unittest


TOP=Path(__file__).resolve().parents[1]
G1=TOP/"deploy/v5/nbot-v5-g1g2g3-observation.service"
G4=TOP/"deploy/v5/nbot-v5-continuous-research.service"
G7=TOP/"deploy/v5/nbot-v5-g7-locked.service"


class IntegratedStoppedServicesTests(unittest.TestCase):
    def test_all_three_use_one_canonical_directory_and_no_auto_restart(self):
        for file in (G1,G4,G7):
            with self.subTest(unit=file.name):
                content=file.read_text()
                self.assertIn("WorkingDirectory=/home/ubuntu/Nbot",content)
                self.assertIn("Restart=no",content)
                self.assertNotIn("Restart=on-failure",content)
                self.assertNotIn("Restart=always",content)
                self.assertNotIn("/home/ubuntu/nbot_v5_",content)
                self.assertNotIn("/home/ubuntu/nbot-backups",content)
                self.assertNotIn("/home/ubuntu/nbot_v5_integrated_",content)
                self.assertIn("NoNewPrivileges=true",content)
                self.assertIn("ProtectSystem=strict",content)

    def test_g4_and_g7_cannot_be_enabled_or_started_without_owner_marker(self):
        for file,marker in (
            (G4,"runtime/research/OWNER_APPROVED_G4_RESEARCH_RELEASE"),
            (G7,"runtime/paper/OWNER_APPROVED_LOCKED_HEALTH"),
        ):
            with self.subTest(unit=file.name):
                body=file.read_text()
                self.assertIn("ConditionPathExists=/home/ubuntu/Nbot/"+marker,body)
                self.assertNotIn("\n[Install]",body)
                self.assertNotIn("WantedBy=",body)

    def test_g4_research_cannot_use_execution_or_old_frozen_db(self):
        spec=G4.read_text()
        self.assertIn("runtime/observation/g1g2g3.sqlite",spec)
        self.assertIn("runtime/source/g4-forward-cohort/segments",spec)
        self.assertIn("runtime/research/protocol.json",spec)
        self.assertIn("${NBOT_V5_START_EVENT_MS}",spec)
        self.assertIn("RestrictAddressFamilies=AF_UNIX",spec)
        self.assertNotIn("--enable-network",spec)
        self.assertNotIn("--sustained-source",spec)

    def test_research_unit_requires_G1_and_G4_and_frozen_registered_policy(self):
        spec=G4.read_text()
        self.assertIn("Requisite=nbot-v5-g1g2g3-observation.service nbot-v5-g4-source-capture.service",spec)
        self.assertIn("runtime/source/g4-forward-cohort/g4_research_template.json",spec)
        self.assertNotIn("approved.env",spec)
        self.assertNotIn("NBOT_V5_START_EVENT_MS",spec)
        self.assertNotIn("--start-event-ms",spec)
        self.assertIn("Restart=no",spec)
        self.assertNotIn("\n[Install]",spec)

    def test_g7_is_local_locked_health_not_order_worker(self):
        spec=G7.read_text()
        self.assertIn("nbot.v5.paper_health_runner",spec)
        self.assertIn("RestrictAddressFamilies=AF_UNIX",spec)
        for banned in ("binance", "api_key", "api_secret", "execution_engine",
                       "websockets","--enable-orders"):
            self.assertNotIn(banned,spec.lower())


if __name__=="__main__":
    unittest.main()
