"""Safety regressions for the PR39-derived G1 source recovery patch.

Pure offline fixtures. No database resets, network calls, paper or real orders.
"""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from nbot.v5.g1f_runner import ObservationOnlyRunner, MAX_FRAMES_PER_5M
from nbot.v5.reconnect_policy import ReconnectPolicy, FeedRecoveryHold


class G1SourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app=ObservationOnlyRunner(
            top=2,path=Path(self.temp.name)/"g1.sqlite",max_seconds=60)
        self.app.policy=ReconnectPolicy()
        for route in ("market","public"):
            self.app.policy.on_connect(route)
        self.app.interrupted=True
        self.event=300_000_000
        self.session=SimpleNamespace(generations={"market":3,"public":4})

    def test_held_coin_must_not_clear_global_source_interruption(self):
        with patch("nbot.v5.g1f_runner.feed_holds",return_value={
            "BTCUSDT":(),"ETHUSDT":("TRADE_NOT_FRESH",)
        }):
            self.assertFalse(self.app._source_epoch_candidate(
                self.session,("BTCUSDT","ETHUSDT"),self.event))
        self.assertTrue(self.app.interrupted)
        self.assertEqual(self.app.stats["reverified_epochs"],0)
        self.assertTrue(self.app.policy.routes["market"].reconciliation_required)

    def test_every_coin_must_have_independent_fresh_source(self):
        with patch("nbot.v5.g1f_runner.feed_holds",return_value={
            "BTCUSDT":()
        }):
            self.assertFalse(self.app._source_epoch_candidate(
                self.session,("BTCUSDT","ETHUSDT"),self.event))
        self.assertTrue(self.app.interrupted)

    def test_only_clean_future_event_resets_interruption_and_retry_budget(self):
        for route in ("market","public"):
            self.app.policy.on_disconnect(route)
            self.app.policy.retry_delay(route)
            self.app.policy.on_connect(route)
        with patch("nbot.v5.g1f_runner.feed_holds",return_value={
            "BTCUSDT":(),"ETHUSDT":()
        }):
            self.assertTrue(self.app._source_epoch_candidate(
                self.session,("BTCUSDT","ETHUSDT"),self.event))
        # A candidate alone is insufficient. Wait for genuine REST 3-stage
        # success and a complete accepted, committed event.
        self.assertTrue(self.app.interrupted)
        self.assertTrue(self.app._accept_source_epoch(
            self.session,self.event))
        self.assertFalse(self.app.interrupted)
        self.assertEqual(self.app.stats["reverified_epochs"],1)
        for route in ("market","public"):
            state=self.app.policy.routes[route]
            self.assertEqual(state.retry_attempts,0)
            self.assertFalse(state.reconciliation_required)

    def test_unaccepted_event_cannot_clear_source_hold(self):
        with patch("nbot.v5.g1f_runner.feed_holds",return_value={
            "BTCUSDT":(),"ETHUSDT":()
        }):
            candidate=self.app._source_epoch_candidate(
                self.session,("BTCUSDT","ETHUSDT"),self.event)
        self.assertTrue(candidate)
        # The caller is deliberately required to wait for the 3 REST
        # checks and a journaled OBSERVE_ONLY status before confirming.
        self.assertTrue(self.app.interrupted)
        self.assertEqual(self.app.stats["reverified_epochs"],0)

    def test_refuse_to_reverify_disconnected_route(self):
        self.app.policy.on_disconnect("public")
        with self.assertRaisesRegex(FeedRecoveryHold,"REVERIFY_DISCONNECTED"):
            self.app.policy.accept_reverified("public")

    def test_frame_budget_remains_bounded_and_has_250k_headroom(self):
        self.assertGreater(MAX_FRAMES_PER_5M,250000)
        self.assertLessEqual(MAX_FRAMES_PER_5M,1000000)

    def test_socket_disconnect_is_accounted_once_before_backoff(self):
        class BrokenSocket:
            async def __aenter__(self):
                return self
            async def __aexit__(self,*unused):
                return False
            async def recv(self):
                raise OSError("simulated close")
        entered=[]
        exited=[]
        session=SimpleNamespace(
            connect=lambda r:entered.append(r),
            disconnect=lambda r:exited.append(r))
        async def fast_sleep(_delay):
            return None
        self.app.policy=ReconnectPolicy()
        self.app.interrupted=False
        with patch("websockets.asyncio.client.connect",return_value=BrokenSocket()), \
             patch("nbot.v5.g1f_runner.asyncio.sleep",side_effect=fast_sleep):
            asyncio.run(self.app._route(
                "public","wss://example.invalid",session,float("inf")))
        self.assertTrue(self.app.stop.is_set())
        self.assertIn("RETRY_BUDGET_EXHAUSTED",self.app.failed_reason)
        self.assertEqual(len(entered),4)
        self.assertEqual(entered,exited)
        self.assertEqual(self.app.policy.global_incidents,4)
        self.assertEqual(self.app.stats["reconnect_attempts"],4)


if __name__=="__main__":
    unittest.main()
