"""Adversarial outcome perturbations must not change an earlier choice."""
import json
import sqlite3
import unittest
from nbot_v7.lab import SCHEMA, generate_symbol, outcome, HORIZON_BARS
from nbot_v7.data import Bar, Contract, BAR_MS
from nbot_v7.experiment import replay, month_start
from nbot_v7.features import proposals, market_features
from nbot_v7.science import block_bootstrap_uplift


class PositiveBrain:
    version = "TEST_ONLY"
    def score(self, rows, kind):
        # Any future field reaching a model is a contract failure.
        for row in rows:
            assert not set(row.keys()) & {"net", "quality", "label_available_ms", "exit_ms", "target_net"}
        return [(.01, 1.0) for _ in rows]


class CausalReplay(unittest.TestCase):
    def connection(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.executescript(SCHEMA)
        self.addCleanup(c.close)
        return c

    def fixture(self):
        c = self.connection()
        t = month_start("2026-01")
        for symbol in ("AAAUSDT", "ZZZUSDT"):
            c.execute("INSERT INTO watch_candidate VALUES(?,?,?,?,?)", (t,symbol,"up","{}","f"*64))
            c.execute("INSERT INTO candidate VALUES(?,?,?,?,?,?,?)",(t,symbol,"LONG","neutral_grid","up","{}","f"*64))
            c.execute("INSERT INTO opportunity VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (t,t+BAR_MS,symbol,"LONG","neutral_grid","up","{}",-.02,0,-.02,t+BAR_MS,"STOP","AMBIGUOUS_5M_STOP_FIRST","f"*64))
        return c,t

    def test_future_ambiguity_never_removes_selected_candidate(self):
        c,t = self.fixture()
        events=[]
        report=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS,event_sink=events.append)
        self.assertEqual(report["trades"][0]["symbol"],"ZZZUSDT")
        c.execute("UPDATE opportunity SET quality='COARSE_5M_OHLC_PATH_PROXY',net=.03")
        changed=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS)
        self.assertEqual(changed["trades"][0]["symbol"],report["trades"][0]["symbol"])
        self.assertNotEqual(changed["net_pnl_usdt"],report["net_pnl_usdt"])
        self.assertTrue(any(e.get("reason")=="SELECTED" for e in events))

    def test_known_evaluation_boundary_blocks_new_trade_without_future_outcomes(self):
        c,t=self.fixture()
        events=[]
        report=replay(c,PositiveBrain(),t,t+(HORIZON_BARS-1)*BAR_MS,event_sink=events.append)
        self.assertEqual(report["selected_trades"],0)
        self.assertEqual(report["unresolved_selected_paths"],0)
        self.assertTrue(report["account_complete"])
        self.assertEqual(report["stats"]["entry_horizon_exceeds_period"],1)
        self.assertTrue(any(e.get("reason")=="EVALUATION_END_ENTRY_HORIZON" for e in events))
        # Entry exactly one full maximum policy horizon before the end is allowed.
        enough=replay(c,PositiveBrain(),t,t+HORIZON_BARS*BAR_MS)
        self.assertEqual(enough["selected_trades"],1)

    def test_missing_label_locks_capital_and_reports_incomplete(self):
        c,t=self.fixture()
        c.execute("DELETE FROM opportunity WHERE symbol='ZZZUSDT'")
        report=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS)
        self.assertEqual(report["unresolved_selected_paths"],1)
        self.assertFalse(report["account_complete"])
        self.assertEqual(report["selected_trades"],0)

    def test_future_gap_keeps_causal_candidates(self):
        c=self.connection()
        t=month_start("2026-01")
        bars=[Bar(t+j*BAR_MS,100,100.1,99.9,100,100) for j in range(120)]
        contract=Contract("BTCUSDT",t,t+200*BAR_MS,"f"*64)
        generate_symbol(c,"BTCUSDT",bars,bars,contract,"f"*64,t,t+120*BAR_MS)
        before={tuple(r) for r in c.execute("SELECT * FROM candidate WHERE decision_ms<=?",(t+100*BAR_MS,))}
        self.assertTrue(before)  # Neutral grid exists even on perfectly flat bars.
        other=self.connection()
        damaged=bars[:101]+bars[103:]
        generate_symbol(other,"BTCUSDT",damaged,bars,contract,"f"*64,t,t+120*BAR_MS)
        after={tuple(r) for r in other.execute("SELECT * FROM candidate WHERE decision_ms<=?",(t+100*BAR_MS,))}
        self.assertEqual(before,after)

    def test_incomplete_wallet_cannot_claim_bootstrap_improvement(self):
        c,t=self.fixture()
        complete=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS)
        c.execute("DELETE FROM opportunity WHERE symbol='ZZZUSDT'")
        incomplete=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS)
        self.assertFalse(incomplete["account_complete"])
        verdict=block_bootstrap_uplift(incomplete,complete)
        self.assertEqual(verdict["status"],"INCOMPLETE_ACCOUNTS_NO_UPLIFT")
        self.assertNotIn("bootstrap_95pct_interval_pct",verdict)

    def test_stale_watch_expires_without_a_future_review(self):
        c,t=self.fixture()
        c.execute("DELETE FROM candidate")
        c.execute("INSERT INTO candidate VALUES(?,?,?,?,?,?,?)",(t+9*3600000,"ZZZUSDT","LONG","neutral_grid","up","{}","f"*64))
        report=replay(c,PositiveBrain(),t,t+10*3600000)
        self.assertEqual(report["selected_trades"],0)
        self.assertEqual(report["stats"]["no_candidate_at_decision"],1)

    def test_gap_stop_fills_at_worse_open(self):
        bars=[Bar(j*BAR_MS,100,100.1,99.9,100,100) for j in range(20)]
        bars[2]=Bar(2*BAR_MS,90,91,89,90,100)
        self.assertLess(outcome(bars,0,"LONG")[0],-.101)

    def test_insolvency_prevents_new_entry(self):
        c,t=self.fixture()
        c.execute("UPDATE opportunity SET net=-1")
        c.execute("INSERT INTO candidate VALUES(?,?,?,?,?,?,?)",(t+BAR_MS,"ZZZUSDT","LONG","neutral_grid","up","{}","f"*64))
        report=replay(c,PositiveBrain(),t,t+(HORIZON_BARS+2)*BAR_MS,stake_usdt=1000,sleeve_usdt=1000)
        self.assertEqual(report["stats"]["insufficient_capital"],1)

if __name__ == "__main__":
    unittest.main()
