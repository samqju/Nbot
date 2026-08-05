import json
import tempfile
import unittest
from pathlib import Path

from execution.paper_account import PaperAccount


class Phase12PaperAccountTests(unittest.TestCase):
    def make_account(self, root: Path, source: str = "PAPER_LIVE"):
        return PaperAccount(
            starting_balance_usd=10000.0,
            state_path=str(root / "paper_state.json"),
            trades_path=str(root / "paper_trades.jsonl"),
            source=source,
        )

    def test_creates_and_recovers_account_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = self.make_account(root)
            account.load_or_create()
            self.assertEqual(account.get_balance_usd(), 10000.0)

            account.open_position(
                symbol="BTCUSDT",
                side="LONG",
                qty=0.01,
                entry_price=50000.0,
                stop_loss=49000.0,
                opened_at_ms=1_000,
                initial_risk_usd=10.0,
                entry_fee_usd=0.25,
            )

            recovered = self.make_account(root)
            recovered.load_or_create()
            position = recovered.get_open_position()
            self.assertIsNotNone(position)
            self.assertEqual(position.symbol, "BTCUSDT")
            self.assertEqual(recovered.get_balance_usd(), 9999.75)

    def test_rejects_second_open_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self.make_account(Path(tmp))
            account.load_or_create()
            account.open_position(
                symbol="ETHUSDT",
                side="SHORT",
                qty=1.0,
                entry_price=3000.0,
                stop_loss=3010.0,
                opened_at_ms=1_000,
                initial_risk_usd=10.0,
                entry_fee_usd=1.5,
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "PAPER_POSITION_ALREADY_OPEN",
            ):
                account.open_position(
                    symbol="BTCUSDT",
                    side="LONG",
                    qty=0.01,
                    entry_price=50000.0,
                    stop_loss=49000.0,
                    opened_at_ms=2_000,
                    initial_risk_usd=10.0,
                    entry_fee_usd=0.25,
                )

    def test_closes_long_and_writes_immutable_trade_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = self.make_account(root)
            account.load_or_create()
            account.open_position(
                symbol="BTCUSDT",
                side="LONG",
                qty=0.01,
                entry_price=50000.0,
                stop_loss=49000.0,
                opened_at_ms=1_000,
                initial_risk_usd=10.0,
                entry_fee_usd=0.25,
            )
            account.update_position_market_extremes(50500.0)
            trade = account.close_position(
                exit_price=50200.0,
                closed_at_ms=2_000,
                exit_fee_usd=0.251,
                exit_reason="MANUAL_TEST",
            )

            self.assertAlmostEqual(trade.gross_pnl_usd, 2.0)
            self.assertAlmostEqual(trade.net_pnl_usd, 1.499)
            self.assertAlmostEqual(account.get_balance_usd(), 10001.499)
            self.assertIsNone(account.get_open_position())

            rows = (root / "paper_trades.jsonl").read_text().splitlines()
            self.assertEqual(len(rows), 1)
            stored = json.loads(rows[0])
            self.assertEqual(stored["trade_id"], trade.trade_id)
            self.assertEqual(stored["source"], "PAPER_LIVE")

    def test_closes_short_with_correct_pnl_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self.make_account(Path(tmp), source="PAPER_TESTNET")
            account.load_or_create()
            account.open_position(
                symbol="ETHUSDT",
                side="SHORT",
                qty=2.0,
                entry_price=3000.0,
                stop_loss=3005.0,
                opened_at_ms=1_000,
                initial_risk_usd=10.0,
                entry_fee_usd=3.0,
            )
            trade = account.close_position(
                exit_price=2995.0,
                closed_at_ms=2_000,
                exit_fee_usd=2.995,
                exit_reason="MANUAL_TEST",
            )
            self.assertAlmostEqual(trade.gross_pnl_usd, 10.0)
            self.assertAlmostEqual(trade.net_pnl_usd, 4.005)
            self.assertAlmostEqual(trade.net_r, 0.4005)

    def test_corrupted_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "paper_state.json"
            state_path.write_text('{"version": 1, "balance_usd": -5}')
            account = self.make_account(root)
            with self.assertRaisesRegex(
                (RuntimeError, ValueError),
                "PAPER_STATE",
            ):
                account.load_or_create()

    def test_source_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_account(root, source="PAPER_TESTNET")
            first.load_or_create()
            second = self.make_account(root, source="PAPER_LIVE")
            with self.assertRaisesRegex(
                RuntimeError,
                "PAPER_STATE_SOURCE_MISMATCH",
            ):
                second.load_or_create()


if __name__ == "__main__":
    unittest.main()
