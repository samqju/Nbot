from pathlib import Path
import json
import tempfile
import unittest

from nbot.common.atomic_io import atomic_write_json, atomic_write_text
from nbot.common.ids import is_valid_id, new_id
from nbot.config.loader import parse_env_file


class FoundationCommonTests(unittest.TestCase):
    def test_ids_are_namespaced_and_valid(self):
        value = new_id("REQUEST")
        self.assertTrue(is_valid_id(value))
        self.assertTrue(value.startswith("REQUEST-"))

    def test_atomic_text_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_write_text(root / "a.txt", "hello\n")
            self.assertEqual((root / "a.txt").read_text(), "hello\n")
            atomic_write_json(root / "b.json", {"b": 2, "a": 1})
            self.assertEqual(json.loads((root / "b.json").read_text()), {"a": 1, "b": 2})

    def test_env_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.env"
            path.write_text("A=1\n# comment\nB='two'\n", encoding="utf-8")
            self.assertEqual(parse_env_file(path), {"A": "1", "B": "two"})


if __name__ == "__main__":
    unittest.main()
