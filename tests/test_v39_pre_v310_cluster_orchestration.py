from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.operator.cluster import (
    ClusterOperatorError,
    cluster_profile_units,
    execution_cluster_start_guard,
    execution_stop_guard,
    parse_tunnel_unit,
    privileged_systemctl_argv,
)


REPO = Path(__file__).resolve().parents[1]


def _unit(*, profile: str = "live-paper", strict: bool = True, forward: str | None = None) -> str:
    units = cluster_profile_units(profile)
    local = units.expected_local_port
    remote = units.expected_observation_port
    strict_value = "yes" if strict else "no"
    forward_value = forward or f"127.0.0.1:{local}:127.0.0.1:{remote}"
    return (
        "[Service]\n"
        "User=ubuntu\n"
        "ExecStart=/usr/bin/ssh -NT "
        "-o BatchMode=yes "
        "-o ExitOnForwardFailure=yes "
        "-o ServerAliveInterval=15 "
        "-o ServerAliveCountMax=3 "
        f"-o StrictHostKeyChecking={strict_value} "
        "-i /home/ubuntu/.ssh/nbot-observation "
        f"-L {forward_value} root@observation.example\n"
    )


class V39PreV310ClusterOrchestrationTests(unittest.TestCase):
    def test_live_trade_cluster_is_hard_blocked_before_v310(self):
        with self.assertRaisesRegex(
            ClusterOperatorError,
            "NBOT_CLUSTER_LIVE_TRADE_FORBIDDEN_BEFORE_V3_10",
        ):
            cluster_profile_units("live-trade")

    def test_live_paper_tunnel_definition_parses_strict_pinned_transport(self):
        units = cluster_profile_units("live-paper")
        transport = parse_tunnel_unit(_unit(), units=units)
        self.assertEqual(transport.service_user, "ubuntu")
        self.assertEqual(transport.identity_file, "/home/ubuntu/.ssh/nbot-observation")
        self.assertEqual(transport.target, "root@observation.example")
        self.assertEqual(transport.local_port, 18765)
        self.assertEqual(transport.observation_port, 8765)

    def test_tunnel_requires_strict_host_key_checking(self):
        units = cluster_profile_units("live-paper")
        with self.assertRaisesRegex(
            ClusterOperatorError,
            "NBOT_CLUSTER_TUNNEL_REQUIRED_OPTION:StrictHostKeyChecking=yes",
        ):
            parse_tunnel_unit(_unit(strict=False), units=units)

    def test_tunnel_rejects_wrong_profile_forward(self):
        units = cluster_profile_units("live-paper")
        with self.assertRaisesRegex(
            ClusterOperatorError,
            "NBOT_CLUSTER_TUNNEL_LOCAL_PORT_MISMATCH",
        ):
            parse_tunnel_unit(
                _unit(forward="127.0.0.1:18766:127.0.0.1:8765"),
                units=units,
            )

    def test_cluster_stop_refuses_every_capital_unsafe_state(self):
        safe = {
            "state": "VALID",
            "entries_enabled": False,
            "open_position": None,
            "entry_inflight": None,
            "pending_outcomes": 0,
            "recovery_critical": False,
        }
        self.assertEqual(execution_stop_guard(safe), (True, "SAFE_FLAT"))

        cases = (
            ({**safe, "open_position": "BTCUSDT"}, "OPEN_POSITION"),
            ({**safe, "entry_inflight": "PROP-1"}, "ENTRY_INFLIGHT"),
            ({**safe, "pending_outcomes": 1}, "PENDING_OUTCOME"),
            ({**safe, "recovery_critical": True}, "RECOVERY_CRITICAL"),
            ({**safe, "entries_enabled": True}, "ENTRIES_ENABLED"),
        )
        for payload, reason in cases:
            self.assertEqual(execution_stop_guard(payload), (False, reason))

    def test_cluster_start_refuses_remote_dependency_for_local_recovery_state(self):
        base = {
            "state": "VALID",
            "entries_enabled": False,
            "open_position": None,
            "entry_inflight": None,
            "pending_outcomes": 0,
            "recovery_critical": False,
        }
        self.assertEqual(
            execution_cluster_start_guard(base, runtime_active=False),
            (True, "SAFE_TO_ORCHESTRATE"),
        )
        self.assertEqual(
            execution_cluster_start_guard(
                {**base, "open_position": "BTCUSDT"},
                runtime_active=False,
            ),
            (False, "OPEN_POSITION_REQUIRES_LOCAL_RECOVERY"),
        )
        self.assertEqual(
            execution_cluster_start_guard(
                {**base, "pending_outcomes": 1},
                runtime_active=False,
            ),
            (False, "PENDING_OUTCOME_REQUIRES_LOCAL_RECOVERY"),
        )

    def test_privileged_systemctl_is_narrowly_scoped(self):
        with mock.patch("nbot.operator.cluster.os.geteuid", return_value=0):
            self.assertEqual(
                privileged_systemctl_argv(
                    "restart",
                    "nbot-observation-live-paper-control.service",
                ),
                [
                    "systemctl",
                    "restart",
                    "nbot-observation-live-paper-control.service",
                ],
            )
        with self.assertRaisesRegex(
            ClusterOperatorError,
            "NBOT_CLUSTER_SYSTEMCTL_ACTION_FORBIDDEN",
        ):
            privileged_systemctl_argv("enable", "nbot-observation-live.service")
        with self.assertRaisesRegex(
            ClusterOperatorError,
            "NBOT_CLUSTER_SYSTEMCTL_UNIT_INVALID",
        ):
            privileged_systemctl_argv("stop", "ssh.service")

    def test_cluster_cli_is_implemented_and_worker_does_not_import_it(self):
        nbotctl = (REPO / "nbotctl").read_text(encoding="utf-8")
        worker = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertIn("cluster.set_defaults(func=cmd_cluster)", nbotctl)
        self.assertNotIn("cluster.set_defaults(func=cmd_not_implemented)", nbotctl)
        self.assertNotIn("def cmd_not_implemented", nbotctl)
        self.assertNotIn("nbot.operator.cluster", worker)

    def test_cluster_start_never_enables_entries(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        start = text[text.index("def _cluster_start("):text.index("def _cluster_resolve_stop_profile(")]
        self.assertIn("set_operator_entry_block(ROOT, profile_name, blocked=True)", start)
        self.assertNotIn("blocked=False", start)
        self.assertNotIn("enable_new_entries", start)
        self.assertIn('"entry_authority_created"] = False', start)

    def test_cluster_stop_guards_before_remote_or_systemd_mutation(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        stop = text[text.index("def _cluster_stop("):text.index("def _cluster_status(")]
        guard = stop.index("execution_stop_guard(summary)")
        transport = stop.index("installed_tunnel_transport(profile_name)")
        remote = stop.index("remote_systemctl(")
        local = stop.index('local_systemctl("stop"')
        self.assertLess(guard, transport)
        self.assertLess(guard, remote)
        self.assertLess(guard, local)

    def test_docs_close_cluster_debt_without_authorizing_v310(self):
        ledger = (REPO / "docs/PRE_V310_GAP_LEDGER.md").read_text(encoding="utf-8")
        operations = (REPO / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("[x] Implement `nbotctl cluster doctor/start/stop/status`", ledger)
        self.assertIn("V3.10 remains hard-blocked", ledger)
        self.assertIn("Execution VPS is the cluster control point", operations)
        self.assertIn("must never be used to recover an OPEN position", operations)


if __name__ == "__main__":
    unittest.main()
