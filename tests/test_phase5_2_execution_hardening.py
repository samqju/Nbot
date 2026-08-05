import unittest

from utils.telegram_notifier import format_trade_close_panel


class Phase52ExecutionHardeningTests(unittest.TestCase):
    def test_close_panel_is_null_safe(self):
        panel = format_trade_close_panel(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=100.0,
            initial_stop_loss=None,
            final_stop_loss=None,
            qty=1.0,
            risk_usd=None,
            exit_price=101.0,
            realized_pnl=None,
            r_multiple=None,
        )
        self.assertIn("Initial Stop: 0.00000000", panel)
        self.assertIn("Final Stop: 0.00000000", panel)
        self.assertIn("PnL: +0.00 USD", panel)
        self.assertIn("Result: +0.00R", panel)

    def test_position_lifecycle_has_no_mid_trade_panel_edit(self):
        from pathlib import Path
        source = Path("engine/position_lifecycle.py").read_text()
        marker = "Update Telegram panel (Locked R emphasis)"
        self.assertNotIn(marker, source)
        self.assertEqual(source.count("edit_message("), 1)

    def test_reconciliation_receives_emergency_handler(self):
        from pathlib import Path
        source = Path("engine/core.py").read_text()
        block = source[source.index("ReconciliationLifecycle("):source.index("# Position Lifecycle")]
        self.assertIn("emergency=self.emergency", block)


if __name__ == "__main__":
    unittest.main()
