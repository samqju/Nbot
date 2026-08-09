import tempfile
import unittest
from pathlib import Path

from deploy.execution.install_services import render_units as render_execution
from deploy.observation.install_services import render_units as render_observation


class Phase6A09RoleTargetTests(unittest.TestCase):
    def test_observation_renderer_writes_role_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\n")
            dest = root / "units"

            written = render_observation(
                repo=repo,
                python=python,
                user="nbot-user",
                destination=dest,
            )
            self.assertEqual(len(written), 4)
            target = (dest / "nbot-observer.target").read_text()
            self.assertIn("Wants=nbot-observation.service", target)
            self.assertIn("Wants=nbot-auto-training.service", target)
            self.assertIn("Wants=nbot-promotion-controller.service", target)
            self.assertIn("Wants=nbot-paper-canary-controller.service", target)

            for name in (
                "nbot-observation.service",
                "nbot-auto-training.service",
                "nbot-promotion-controller.service",
                "nbot-paper-canary-controller.service",
            ):
                self.assertIn(
                    "PartOf=nbot-observer.target",
                    (dest / name).read_text(),
                )

    def test_execution_renderer_writes_safe_role_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            python = root / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\n")
            ssh = root / "ssh"
            ssh.write_text("#!/bin/sh\n")
            identity = root / "identity"
            identity.write_text("TEST\n")
            known_hosts = root / "known_hosts"
            known_hosts.write_text("observer ssh-ed25519 TEST\n")
            dest = root / "units"

            written = render_execution(
                repo=repo,
                python=python,
                user="nbot-user",
                ssh_bin=ssh,
                identity_file=identity,
                known_hosts_file=known_hosts,
                observer_host="203.0.113.10",
                observer_ssh_user="nbot-tunnel",
                destination=dest,
            )
            self.assertEqual(len(written), 2)
            target = (dest / "nbot-execution.target").read_text()
            self.assertIn("Wants=nbot-observation-tunnel.service", target)
            self.assertIn("Wants=nbot-execution.service", target)

            execution = (dest / "nbot-execution.service").read_text()
            tunnel = (dest / "nbot-observation-tunnel.service").read_text()
            self.assertIn("PartOf=nbot-execution.target", execution)
            self.assertIn("PartOf=nbot-execution.target", tunnel)
            self.assertIn("Wants=network-online.target nbot-observation-tunnel.service", execution)
            self.assertNotIn("Requires=nbot-observation-tunnel.service", execution)
            self.assertNotIn("BindsTo=", execution)

    def test_role_target_templates_have_no_current_vps_paths_or_ips(self):
        for root in (Path("deploy/observation"), Path("deploy/execution")):
            for path in root.glob("*.target.in"):
                text = path.read_text()
                self.assertNotIn("/root/Nbot", text)
                self.assertNotIn("/home/ubuntu", text)
                self.assertNotIn("169.58.145.154", text)
                self.assertNotIn("132.145.50.220", text)


if __name__ == "__main__":
    unittest.main()
