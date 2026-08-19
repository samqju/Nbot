from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nbot.execution.entry import EntryRejected
from tests.test_v3110_execution_worker import WorkerHarness, proposal, seed_open


class V35ExecutionBoundaryTests(unittest.TestCase):
    def test_rejected_remote_proposal_emits_local_veto_feedback_hook(self):
        with tempfile.TemporaryDirectory() as td:
            harness = WorkerHarness(Path(td))
            harness.durable.state.set_entries_enabled(True)
            item = proposal(proposal_id="P-VETO")
            harness.proposals.value = item
            harness.entry.error = EntryRejected("SPREAD_TOO_WIDE")
            vetoes = []

            def record_veto(**kwargs):
                vetoes.append(kwargs)

            harness.proposals.record_veto = record_veto
            result = harness.worker.process_flat_cycle()
            self.assertEqual(result, "PROPOSAL_REJECTED:SPREAD_TOO_WIDE")
            self.assertEqual(
                vetoes,
                [
                    {
                        "proposal_id": "P-VETO",
                        "reason": "SPREAD_TOO_WIDE",
                        "rejected_at_ms": 1_800_000_000_000,
                    }
                ],
            )

    def test_veto_feedback_failure_never_turns_rejection_into_entry(self):
        with tempfile.TemporaryDirectory() as td:
            harness = WorkerHarness(Path(td))
            harness.durable.state.set_entries_enabled(True)
            harness.proposals.value = proposal(proposal_id="P-VETO-FAIL")
            harness.entry.error = EntryRejected("QUOTE_STALE")

            def broken(**_kwargs):
                raise OSError("disk unavailable")

            harness.proposals.record_veto = broken
            result = harness.worker.process_flat_cycle()
            self.assertEqual(result, "PROPOSAL_REJECTED:QUOTE_STALE")
            self.assertIsNone(harness.durable.state.open_position)
            self.assertEqual(
                harness.durable.state.health.last_event,
                "PROPOSAL_VETO_FEEDBACK_FAILED",
            )

    def test_open_position_path_never_invokes_proposal_veto_or_outcome_clients(self):
        with tempfile.TemporaryDirectory() as td:
            harness = WorkerHarness(Path(td))
            seed_open(harness.durable.state)
            calls = []
            harness.proposals.record_veto = lambda **kwargs: calls.append(("veto", kwargs))
            # Existing worker invariant: open quote path manages capital only.
            quote = __import__("nbot.exchange.contracts", fromlist=["Quote"]).Quote(
                "BTCUSDT",
                100.0,
                100.1,
                1_800_000_000_000,
            )
            harness.worker.process_open_quote(quote)
            self.assertEqual(calls, [])
            self.assertFalse(any(event.startswith("outcome:") for event in harness.events))
            self.assertNotIn("proposal", harness.events)
