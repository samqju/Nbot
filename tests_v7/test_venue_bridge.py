import os
from pathlib import Path
import tempfile
import unittest
from nbot_v7.runtime.risk import RiskPolicy


@unittest.skipUnless(os.name=="posix","Audited legacy durable/venue engine targets Linux POSIX")
class VenueBridge(unittest.TestCase):
    def test_v7_intent_to_audited_paper_protection_target_and_durable_close(self):
        from nbot.config.profiles import get_profile
        from nbot.exchange.contracts import Quote
        from nbot.exchange.paper import PaperExchange,PaperExchangeConfig
        from nbot_v7.runtime.venue import AuditedVenueTransport
        now=[1800000000000]
        class Market:
            def connect(self):pass
            def is_healthy(self):return True
            def quote(self,symbol):return Quote(symbol,price[0]-.01,price[0]+.01,now[0])
        price=[100.0]
        with tempfile.TemporaryDirectory() as tmp:
            exchange=PaperExchange(repo_root=Path(tmp),profile=get_profile("live-paper"),market_data=Market(),
                                   config=PaperExchangeConfig(entry_slippage_pct=.01,exit_slippage_pct=.01))
            policy=RiskPolicy()
            venue=AuditedVenueTransport(exchange,Path(tmp),"live-paper",policy,lambda:now[0])
            venue.enable_after_review("OFFLINE_TEST_ONLY")
            intent={"id":"V7-TEST-PROPOSAL","time_ms":now[0],"symbol":"BTCUSDT","side":"LONG","quote":100}
            position=venue.submit_protected_idempotent(intent,policy)
            self.assertTrue(position["protective_stop_id"])
            self.assertIsNotNone(venue.durable.state.open_position)
            price[0]=105;now[0]+=1000
            report=venue.poll()
            self.assertIsNone(report["position"])
            self.assertEqual(len(report["pending_outcomes"]),1)
            payload=report["pending_outcomes"][0]["payload"]
            self.assertGreater(payload["realized_pnl_usd"],0)
            venue.acknowledge(report["pending_outcomes"][0]["record_id"])

    def test_brain_runtime_venue_bridge_reconciles_account_exactly_once(self):
        from nbot.config.profiles import get_profile
        from nbot.exchange.contracts import Quote
        from nbot.exchange.paper import PaperExchange,PaperExchangeConfig
        from nbot_v7.runtime.venue import AuditedVenueTransport
        from nbot_v7.runtime import Memory,TradingEngine,GuardedLiveBroker
        from nbot_v7.runtime.broker import LivePermit
        now=[1800000000000];price=[100.0]
        class Market:
            def connect(self):pass
            def is_healthy(self):return True
            def quote(self,symbol):return Quote(symbol,price[0]-.01,price[0]+.01,now[0])
        class Brain:
            version="TEST_PAPER_BRIDGE"
            def score(self,rows,kind):return [(.02,1) for _ in rows]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);policy=RiskPolicy()
            exchange=PaperExchange(repo_root=root,profile=get_profile("live-paper"),market_data=Market(),
                                   config=PaperExchangeConfig(entry_slippage_pct=.01,exit_slippage_pct=.01))
            transport=AuditedVenueTransport(exchange,root,"live-paper",policy,lambda:now[0])
            transport.enable_after_review("OFFLINE_MOCK_ONLY")
            broker=GuardedLiveBroker(transport,LivePermit(True,now[0]+86400000,1000,"MOCK_ONLY_NO_REAL_VENUE"))
            memory=Memory(root/"v7.sqlite")
            try:
                engine=TradingEngine(memory,Brain(),broker,policy)
                base={"symbol":"BTCUSDT","regime":"up","features":"{}","source_hash":"f"*64}
                engine.review([{**base,"review_ms":now[0]}],now[0],now[0])
                engine.decide([{**base,"decision_ms":now[0],"side":"LONG","family":"neutral_grid"}],now[0],now[0],{"BTCUSDT":100})
                price[0]=105;now[0]+=1000
                engine.reconcile_venue()
                equity=memory.read()["equity"]
                self.assertGreater(equity,10000)
                engine.reconcile_venue()
                self.assertEqual(memory.read()["equity"],equity)
                self.assertIsNone(memory.read()["position"])
            finally:memory.close()

if __name__=="__main__":unittest.main()
