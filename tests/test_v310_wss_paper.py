import tempfile
import unittest
from pathlib import Path

from nbot.config.profiles import get_profile
from nbot.exchange.contracts import Quote
from nbot.exchange.paper import PaperExchange
from nbot.exchange.binance_stream import QuoteUpdate


class _StreamingMarket:
    def __init__(self):
        self.connected = False
        self.seq = 0

    def connect(self):
        self.connected = True

    def is_healthy(self):
        return self.connected

    def quote(self, symbol):
        return Quote(symbol, 100.0, 100.1, 1_000)

    def wait_quote(self, symbol, *, after_sequence=0, timeout_seconds=None):
        self.seq = max(self.seq + 1, after_sequence + 1)
        return QuoteUpdate(
            self.seq,
            Quote(symbol, 100.0, 100.1, 1_000 + self.seq),
            1_000 + self.seq,
        )

    def recovery_quote(self, symbol):
        return Quote(symbol, 99.9, 100.2, 2_000)


class PaperStreamingMarketTests(unittest.TestCase):
    def test_paper_delegates_wss_wait_and_explicit_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            market = _StreamingMarket()
            exchange = PaperExchange(
                repo_root=Path(tmp),
                profile=get_profile("live-paper"),
                market_data=market,
            )
            exchange.connect()
            update = exchange.wait_quote("BTCUSDT", after_sequence=0, timeout_seconds=.1)
            self.assertEqual(update.sequence, 1)
            recovered = exchange.recovery_quote("BTCUSDT")
            self.assertEqual(recovered.bid, 99.9)


if __name__ == "__main__":
    unittest.main()
