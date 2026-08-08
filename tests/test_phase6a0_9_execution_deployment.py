import tempfile
import unittest
from pathlib import Path

from deploy.execution.install_services import render_units


class Phase6A09ExecutionDeploymentTests(unittest.TestCase):
    def _render(self, root: Path):
        repo = root / "repo"
        repo.mkdir()

        bin_dir = root / "venv" / "bin"
        bin_dir.mkdir(parents=True)
        real_python = bin_dir / "python3.12"
        real_python.write_text("#!/bin/sh\n")
        python = bin_dir / "python"
        python.symlink_to(real_python.name)

        ssh_bin = root / "ssh"
        ssh_bin.write_text("#!/bin/sh\n")
        identity = root / "identity"
        identity.write_text("PRIVATE TEST KEY\n")
        known_hosts = root / "known_hosts"
        known_hosts.write_text(
            "203.0.113.10 ssh-ed25519 TEST\n"
        )
        destination = root / "units"

        written = render_units(
            repo=repo,
            python=python,
            user="nbot-user",
            ssh_bin=ssh_bin,
            identity_file=identity,
            known_hosts_file=known_hosts,
            observer_host="203.0.113.10",
            observer_ssh_user="nbot-tunnel",
            destination=destination,
        )
        return (
            repo,
            python,
            ssh_bin,
            identity,
            known_hosts,
            destination,
            written,
        )

    def test_renderer_writes_two_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._render(Path(tmp))
            destination, written = result[-2], result[-1]
            self.assertEqual(len(written), 2)
            self.assertTrue(
                (destination / "nbot-execution.service").exists()
            )
            self.assertTrue(
                (
                    destination
                    / "nbot-observation-tunnel.service"
                ).exists()
            )

    def test_execution_uses_venv_and_does_not_require_tunnel(self):
        with tempfile.TemporaryDirectory() as tmp:
            (
                repo,
                python,
                _,
                _,
                _,
                destination,
                _,
            ) = self._render(Path(tmp))
            text = (
                destination / "nbot-execution.service"
            ).read_text()
            self.assertIn(
                f"WorkingDirectory={repo.resolve()}",
                text,
            )
            self.assertIn(
                f"ExecStart={python} run_execution.py --yes",
                text,
            )
            self.assertIn(
                "Wants=network-online.target "
                "nbot-observation-tunnel.service",
                text,
            )
            self.assertNotIn(
                "Requires=nbot-observation-tunnel.service",
                text,
            )
            self.assertNotIn("BindsTo=", text)
            self.assertIn("KillSignal=SIGINT", text)

    def test_tunnel_is_loopback_pinned_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            (
                _,
                _,
                ssh_bin,
                identity,
                known_hosts,
                destination,
                _,
            ) = self._render(Path(tmp))
            text = (
                destination
                / "nbot-observation-tunnel.service"
            ).read_text()
            self.assertIn(f"ExecStart={ssh_bin.resolve()} -NT", text)
            self.assertIn(f"-i {identity.resolve()}", text)
            self.assertIn(
                f"-o UserKnownHostsFile={known_hosts.resolve()}",
                text,
            )
            self.assertIn("-o IdentitiesOnly=yes", text)
            self.assertIn("-o StrictHostKeyChecking=yes", text)
            self.assertIn("-o ExitOnForwardFailure=yes", text)
            self.assertIn(
                "-L 127.0.0.1:8765:127.0.0.1:8765",
                text,
            )
            self.assertIn(
                "nbot-tunnel@203.0.113.10",
                text,
            )

    def test_templates_have_no_machine_specific_execution_paths(self):
        for path in Path("deploy/execution").glob("*.service.in"):
            text = path.read_text()
            self.assertNotIn("/home/ubuntu", text)
            self.assertNotIn("/root/Nbot", text)
            self.assertNotIn("169.58.145.154", text)
            self.assertNotIn("132.145.50.220", text)

    def test_invalid_port_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            python = root / "python"
            python.write_text("")
            ssh_bin = root / "ssh"
            ssh_bin.write_text("")
            identity = root / "identity"
            identity.write_text("")
            known_hosts = root / "known_hosts"
            known_hosts.write_text("")

            with self.assertRaisesRegex(
                ValueError,
                "NBOT_LOCAL_PORT_INVALID",
            ):
                render_units(
                    repo=repo,
                    python=python,
                    user="nbot-user",
                    ssh_bin=ssh_bin,
                    identity_file=identity,
                    known_hosts_file=known_hosts,
                    observer_host="203.0.113.10",
                    observer_ssh_user="nbot-tunnel",
                    destination=root / "units",
                    local_port=0,
                )


if __name__ == "__main__":
    unittest.main()
