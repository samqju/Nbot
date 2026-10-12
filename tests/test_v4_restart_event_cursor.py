"""A restarted V4 worker waits for a new complete event, never replaying the old one."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nbot.config.validation import MachineRole
from deploy.observation import run_v4_paper_contest, run_v4_research


class _StopAfterTwoPolls:
    def __init__(self):
        self.calls = 0

    def wait(self, _timeout):
        self.calls += 1
        return self.calls > 2


class V4RestartEventCursorTests(unittest.TestCase):
    def _run_runner(self, module, class_name, event_sequence, expected_event):
        worker = Mock()
        worker.last_event_open_ms = None
        worker.status.return_value = {"order_authority": "NONE"}

        def process_event(*, event_open_ms):
            worker.last_event_open_ms = event_open_ms
            return {"event_open_ms": event_open_ms, "order_authority": "NONE"}

        worker.on_five_minute_event.side_effect = process_event
        stop = _StopAfterTwoPolls()

        with patch.object(module, "detect_role", return_value=MachineRole.OBSERVATION), \
             patch.object(module, "get_profile", return_value=SimpleNamespace(name="live-paper")), \
             patch.object(module, "validate_role_profile"), \
             patch.object(module, "observation_config_for_profile", return_value=object()), \
             patch.object(module, "EvidenceDatabase", return_value=object()), \
             patch.object(module, "_git_sha", return_value="a" * 40), \
             patch.object(module, class_name, return_value=worker), \
             patch.object(module, "_latest_complete_event", side_effect=event_sequence) as latest, \
             patch.object(module.threading, "Event", return_value=stop), \
             patch.object(module.signal, "signal"), \
             patch.object(module.os, "chdir"), \
             patch("builtins.print"):
            self.assertEqual(module.main(), 0)

        self.assertEqual(latest.call_count, len(event_sequence))
        worker.on_five_minute_event.assert_called_once_with(
            event_open_ms=expected_event
        )
        self.assertEqual(worker.last_event_open_ms, expected_event)
        worker.stop.assert_called_once()

    def test_research_skips_preexisting_completed_event(self):
        self._run_runner(
            run_v4_research, "V4ResearchFactory",
            [300_000, 300_000, 600_000], 600_000
        )

    def test_paper_contest_skips_preexisting_completed_event(self):
        self._run_runner(
            run_v4_paper_contest, "V4PaperContest",
            [300_000, 300_000, 600_000], 600_000
        )

    def test_initial_research_run_with_no_existing_event_still_starts(self):
        self._run_runner(
            run_v4_research, "V4ResearchFactory",
            [None, None, 300_000], 300_000
        )

    def test_initial_paper_run_with_no_existing_event_still_starts(self):
        self._run_runner(
            run_v4_paper_contest, "V4PaperContest",
            [None, None, 300_000], 300_000
        )


if __name__ == "__main__":
    unittest.main()
