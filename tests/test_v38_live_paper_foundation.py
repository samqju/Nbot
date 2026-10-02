from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.config.profiles import get_profile
from nbot.exchange.binance_public import (
    LIVE_PUBLIC_REST_BASE_URL,
    BinanceLivePublicMarketConfig,
    BinanceLivePublicMarketData,
    BinanceLivePublicMarketError,
)
from nbot.exchange.contracts import Quote
from nbot.exchange.paper import PaperExchange


REPO = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000_000


class FakeHTTPResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.raw


class FakeUrlopen:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        url = request.full_url
        if url.endswith("/fapi/v1/time"):
            return FakeHTTPResponse({"serverTime": NOW})
        if "/fapi/v1/ticker/bookTicker?symbol=BTCUSDT" in url:
            return FakeHTTPResponse(
                {
                    "symbol": "BTCUSDT",
                    "bidPrice": "100.0",
                    "askPrice": "100.1",
                    "time": NOW,
                }
            )
        raise AssertionError(url)


class FakeMarket:
    def __init__(self):
        self.connected = False

    def connect(self):
        self.connected = True

    def is_healthy(self):
        return self.connected

    def quote(self, symbol):
        return Quote(symbol=symbol, bid=100.0, ask=100.1, timestamp_ms=NOW)


class V38LivePaperFoundationTests(unittest.TestCase):
    def test_public_host_is_hard_pinned(self):
        BinanceLivePublicMarketConfig().validate()
        with self.assertRaisesRegex(ValueError, "LIVE_PUBLIC_BINANCE_HOST_NOT_PINNED"):
            BinanceLivePublicMarketConfig(base_url="https://example.com").validate()

    def test_public_adapter_uses_only_public_no_auth_requests(self):
        transport = FakeUrlopen()
        client = BinanceLivePublicMarketData(
            urlopen_fn=transport,
            now_ms_fn=lambda: NOW,
        )
        client.connect()
        quote = client.quote("BTCUSDT")
        self.assertEqual(quote.symbol, "BTCUSDT")
        self.assertEqual(quote.bid, 100.0)
        self.assertEqual(quote.ask, 100.1)
        self.assertTrue(client.is_healthy())
        self.assertTrue(all(req.full_url.startswith(LIVE_PUBLIC_REST_BASE_URL) for req, _ in transport.requests))
        for request, _timeout in transport.requests:
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertNotIn("authorization", headers)
            self.assertNotIn("x-mbx-apikey", headers)

    def test_public_adapter_has_no_private_or_order_surface(self):
        client = BinanceLivePublicMarketData(urlopen_fn=FakeUrlopen(), now_ms_fn=lambda: NOW)
        for name in (
            "api_key",
            "api_secret",
            "open_market",
            "close_position",
            "set_leverage",
            "ensure_protective_stop",
            "replace_protective_stop",
        ):
            self.assertFalse(hasattr(client, name), name)

    def test_public_adapter_rejects_unapproved_path(self):
        client = BinanceLivePublicMarketData(urlopen_fn=FakeUrlopen(), now_ms_fn=lambda: NOW)
        with self.assertRaisesRegex(BinanceLivePublicMarketError, "LIVE_PUBLIC_PATH_FORBIDDEN"):
            client._get("/fapi/v2/account")

    def test_live_paper_execution_worker_can_be_composed_without_binance_order_adapter(self):
        import run_execution

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            market = FakeMarket()
            exchange = PaperExchange(
                repo_root=root,
                profile=get_profile("live-paper"),
                market_data=market,
            )
            worker = run_execution.build_execution_worker(
                repo_root=root,
                profile_name="live-paper",
                exchange=exchange,
            )
            self.assertEqual(worker.state.snapshot.profile, "live-paper")
            self.assertEqual(
                worker.entry.config.allowed_entry_authorities,
                frozenset({run_execution.LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY}),
            )
            self.assertFalse(get_profile("live-paper").binance_order_writes)

    def test_live_paper_runner_is_operational_only_and_live_trade_stays_forbidden(self):
        text = (REPO / "run_execution.py").read_text(encoding="utf-8")
        self.assertIn("mode=LIVE_PAPER_OPERATIONAL_CANARY", text)
        self.assertIn("worker.disable_new_entries()", text)
        self.assertIn("LIVE_EXPLICIT_TRIAL_ARM_REQUIRED", text)
        self.assertNotIn("NBOT_LIVE_PAPER_RUNTIME_DEFERRED_UNTIL_V3_8", text)

    def test_control_only_runner_does_not_create_observation_worker(self):
        text = (REPO / "run_observation_control.py").read_text(encoding="utf-8")
        self.assertNotIn("from nbot.observation.worker", text)
        self.assertNotIn("ObservationRuntimeLock(", text)
        self.assertIn("ObservationControlTarget", text)
        self.assertIn("ObservationReadOnlyStatusProvider", text)
        self.assertNotIn("ObservationOperatorSurface", text)
        self.assertNotIn('prefix="OBSERVATION"', text)
        self.assertIn("LIVE_PAPER_OPERATIONAL_CANARY", text)

    def test_live_paper_service_uses_separate_control_only_process(self):
        text = (
            REPO / "deploy/systemd/nbot-observation-live-paper-control.service.in"
        ).read_text(encoding="utf-8")
        self.assertIn("run_observation_control.py", text)
        self.assertIn("--profile live-paper", text)
        self.assertNotIn("run_observation.py", text)
        self.assertNotIn("observation-live.env", text)

    def test_live_paper_tunnel_has_distinct_ports_from_testnet(self):
        live = (REPO / "deploy/systemd/nbot-control-tunnel-live-paper.service.in").read_text()
        testnet = (REPO / "deploy/systemd/nbot-control-tunnel-testnet.service.in").read_text()
        self.assertIn("127.0.0.1:18765:127.0.0.1:8765", live)
        self.assertIn("127.0.0.1:18766:127.0.0.1:8766", testnet)

    def test_nbotctl_live_paper_start_blocker_is_removed_and_cluster_is_implemented(self):
        text = (REPO / "nbotctl").read_text(encoding="utf-8")
        self.assertNotIn("NBOT_LIVE_PAPER_RUNTIME_DEFERRED_UNTIL_V3_8", text)
        self.assertIn("def _start_execution", text)
        self.assertIn("cluster.set_defaults(func=cmd_cluster)", text)
        self.assertNotIn("def cmd_not_implemented", text)
        self.assertIn("LIVE_ENABLE_REQUIRES_CURRENT_EXPLICIT_TRIAL_ARM", text)


if __name__ == "__main__":
    unittest.main()
