import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nbot_v7.data import Bar,BAR_MS
from nbot_v7.runtime import TradingEngine,Memory,RiskPolicy,GuardedLiveBroker


class Brain:
    version="FIXTURE_FROZEN"
    def score(self,rows,kind):return [(.02,1) for _ in rows]


class RuntimeContracts(unittest.TestCase):
    def fixture(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        memory=Memory(Path(tmp.name)/"state.sqlite")
        self.addCleanup(memory.close)
        engine=TradingEngine(memory,Brain())
        watch={"review_ms":0,"symbol":"BTCUSDT","regime":"up","features":"{}","source_hash":"f"*64}
        engine.review([watch],0,0)
        row={"decision_ms":0,"symbol":"BTCUSDT","side":"LONG","family":"neutral_grid",
             "regime":"up","features":"{}","source_hash":"f"*64}
        return engine,memory,row

    def test_paper_one_slot_persistent_exit_and_matured_memory(self):
        e,m,r=self.fixture()
        self.assertEqual(e.decide([r],0,0,{"BTCUSDT":100}),"ENTERED")
        self.assertEqual(e.decide([r],0,0,{"BTCUSDT":100}),"DUPLICATE_DECISION")
        nextrow={**r,"decision_ms":BAR_MS}
        self.assertEqual(e.decide([nextrow],BAR_MS,BAR_MS,{"BTCUSDT":100}),"ONE_SLOT_OCCUPIED")
        result=e.on_bar("BTCUSDT",Bar(0,100,104,99,103,10),BAR_MS)
        self.assertEqual(result["reason"],"TARGET")
        self.assertGreater(result["net_usdt"],0)
        self.assertEqual(m.matured(BAR_MS),[])
        self.assertEqual(len(m.matured(BAR_MS+1)),1)
        self.assertIsNone(m.read()["position"])
        m.verify()

    def test_restart_preserves_open_position_and_duplicate_bar_is_idempotent(self):
        e,m,r=self.fixture()
        e.decide([r],0,0,{"BTCUSDT":100})
        restarted=TradingEngine(m,Brain())
        self.assertIsNotNone(m.read()["position"])
        bar=Bar(0,100,100.1,99.9,100,10)
        restarted.on_bar("BTCUSDT",bar,BAR_MS,funding_rate=.001)
        before=m.read()["position"]["funding_net"]
        restarted.on_bar("BTCUSDT",bar,BAR_MS,funding_rate=.001)
        self.assertEqual(m.read()["position"]["funding_net"],before)

    def test_live_adapter_disabled_and_unresolved_intent_blocks_recovery(self):
        e,m,r=self.fixture()
        live=TradingEngine(m,Brain(),GuardedLiveBroker())
        with self.assertRaisesRegex(PermissionError,"DISABLED"):
            live.decide([r],0,0,{"BTCUSDT":100})
        self.assertTrue(m.read()["kill"])
        self.assertIsNotNone(m.read()["pending"])

    def test_stale_source_and_kill_switch_abstain(self):
        e,m,r=self.fixture()
        self.assertEqual(e.decide([r],0,0,{"BTCUSDT":100},source_ready=False),"SOURCE_HOLD")
        e.kill("TEST")
        self.assertEqual(e.decide([{**r,"decision_ms":BAR_MS}],BAR_MS,BAR_MS,{"BTCUSDT":100}),"KILL_SWITCH")

    def test_journal_corruption_fails_closed(self):
        e,m,r=self.fixture()
        m.conn.execute("UPDATE event SET body='{}' WHERE seq=0")
        with self.assertRaisesRegex(ValueError,"CORRUPT"):
            m.verify()

    def test_risk_change_on_restart_rejected(self):
        e,m,r=self.fixture()
        with self.assertRaisesRegex(ValueError,"RISK_POLICY_CHANGED"):
            TradingEngine(m,Brain(),policy=RiskPolicy(notional_usdt=2000))

    def test_outcome_conflict_does_not_mutate_account(self):
        e,m,r=self.fixture()
        e.decide([r],0,0,{"BTCUSDT":100})
        identity=m.read()["position"]["id"]
        m.record_outcome(identity,1,{"corrupt_fixture":True})
        equity=m.read()["equity"]
        with self.assertRaisesRegex(ValueError,"CONFLICT"):
            e.on_bar("BTCUSDT",Bar(0,100,104,99,103,10),BAR_MS)
        self.assertEqual(m.read()["equity"],equity)
        self.assertIsNotNone(m.read()["position"])

if __name__=="__main__":unittest.main()
