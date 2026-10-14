"""Strict G1 SQLite location contract for the single-Nbot deployment."""
from pathlib import Path
import unittest

from nbot.v5.candle_ledger import _is_protected_legacy_db_target


class G1DatabaseLayoutTests(unittest.TestCase):
    def test_only_approved_in_tree_g1_file_is_allowed(self):
        allowed=Path("/home/ubuntu/Nbot/runtime/observation/g1g2g3.sqlite")
        self.assertFalse(_is_protected_legacy_db_target(allowed))

    def test_legacy_in_tree_databases_remain_blocked(self):
        for path in (
            "/home/ubuntu/Nbot/runtime/observation/live/account.sqlite",
            "/home/ubuntu/Nbot/runtime/observation/testnet/state.sqlite",
            "/home/ubuntu/Nbot/old_v4.sqlite",
            "/home/ubuntu/Nbot/runtime/observation/other.sqlite",
        ):
            with self.subTest(path=path):
                self.assertTrue(_is_protected_legacy_db_target(Path(path)))

    def test_old_named_live_and_v4_roots_are_denied(self):
        for path in (
            "/home/ubuntu/nbot_v4_data/history.db",
            "/var/lib/nbot/live/order.sqlite",
        ):
            self.assertTrue(_is_protected_legacy_db_target(Path(path)))


if __name__=="__main__":
    unittest.main()
