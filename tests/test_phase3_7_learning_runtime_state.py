import json
import tempfile
import unittest
from pathlib import Path

from strategy.learning_runtime_state import (
    LearningRuntimeStateStore,
)


class Phase37LearningRuntimeStateTests(unittest.TestCase):
    def test_atomic_section_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "learning_state.json"
            store = LearningRuntimeStateStore(str(path))
            rows = [{"candidate_observation_id": "abc"}]

            store.replace_section("pending_simulations", rows)

            reloaded = LearningRuntimeStateStore(str(path))
            self.assertEqual(
                reloaded.get_section("pending_simulations"),
                rows,
            )
            self.assertEqual(
                json.loads(path.read_text())["version"],
                1,
            )
            self.assertFalse(
                list(path.parent.glob("*.tmp"))
            )

    def test_returned_sections_are_defensive_copies(self):
        with tempfile.TemporaryDirectory() as root:
            store = LearningRuntimeStateStore(
                str(Path(root) / "state.json")
            )
            store.replace_section(
                "pending_simulations",
                [{"value": 1}],
            )
            rows = store.get_section("pending_simulations")
            rows[0]["value"] = 999

            self.assertEqual(
                store.get_section("pending_simulations"),
                [{"value": 1}],
            )

    def test_invalid_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            path.write_text(
                json.dumps({
                    "version": 1,
                    "pending_simulations": {},
                    "active_virtual_trades": [],
                })
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "LEARNING_RUNTIME_STATE_SECTION_INVALID",
            ):
                LearningRuntimeStateStore(str(path))


if __name__ == "__main__":
    unittest.main()
