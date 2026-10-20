"""Tests only offline calculations. Never access an exchange or the user's VPS."""
from __future__ import annotations
import json
import sqlite3
import tempfile
import unittest
import math
from pathlib import Path
from datetime import datetime,timezone
from nbot_v7.data import Bar,contract_registry,load_bars,load_funding,BAR_MS
from nbot_v7.features import market_features,proposals,btc_regime
from nbot_v7.lab import con,outcome,generate_symbol,path_outcome_context
from nbot_v7.experiment import nine_month_bounds,month_start,replay
from nbot.observation import decision_ledger, research_replay, v5_paired_exits
from nbot_v5_1 import learning_science

class OfflineContracts(unittest.TestCase):
    def _bars(self,n=230,scale=1.0):
        start=month_start("2026-01")
        return [Bar(start+i*BAR_MS,scale*(100+i*.08),scale*(101+i*.08),
                    scale*(99+i*.08),scale*(100+i*.08),100*(1+(i%11)/10)) for i in range(n)]

    def test_legacy_modules_import_without_orders(self):
        self.assertTrue(hasattr(decision_ledger,"DecisionLedger"))
        self.assertTrue(hasattr(research_replay,"ResearchReplayBook"))
        self.assertTrue(hasattr(v5_paired_exits,"PairedExitLab"))
        self.assertTrue(hasattr(learning_science,"QualityReport"))

    def test_5m_simulation_stop_first_when_target_and_stop_touch(self):
        b=self._bars(90)
        i=65
        entry=b[i+1].o
        b[i+1]=Bar(b[i+1].t,entry,entry*1.05,entry*.95,entry,100)
        net,mfe,mae,exit_ms,why,quality=outcome(b,i,"LONG")
        self.assertEqual(why,"STOP")
        self.assertEqual(quality,"AMBIGUOUS_5M_STOP_FIRST")
        self.assertAlmostEqual(net,-.02-.0012,places=7)
        self.assertLessEqual(mfe,0)
        self.assertLess(mae,0)

    def test_funding_rate_archive_column_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"BTCUSDT-fundingRate-2026-01.csv"
            p.write_text("calc_time,funding_interval_hours,last_funding_rate\n"
                         "1767225600000,8,0.0001\n1767254400000,8,-0.0003\n")
            funding, hashes=load_funding([p],1767225600000,1767283200000)
            self.assertEqual(len(funding),2)
            self.assertAlmostEqual(funding[0][1],0.0001)
            self.assertIn(str(p),hashes)

    def test_source_gated_registry_rejects_unattested_contract(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.csv"
            p.write_text("symbol,from_ms,to_ms,evidence_sha256,source_grade\n"+
                f"BTCUSDT,1,9999999999999,{'0'*64},UNVERIFIED\n")
            with self.assertRaisesRegex(ValueError,"UNATTESTED"):
                contract_registry(p)
            p.write_text("symbol,from_ms,to_ms,evidence_sha256,source_grade\n"+
                f"BTCUSDT,1,9999999999999,{'0'*64},SOURCE_ATTESTED\n")
            self.assertTrue(contract_registry(p)["BTCUSDT"].eligible(1000))

    def test_train_features_only_past_btc(self):
        bars=self._bars()
        x=market_features(bars,100,bars,[r.t for r in bars])
        self.assertIn("btc_r48",x)
        self.assertEqual(btc_regime(x),"up")
        found=proposals(bars,100,x)
        self.assertTrue(isinstance(found,list))

    def test_frozen_future_context_is_recorded_separately(self):
        bars=self._bars()
        i=100
        _,_,_,exit_ms,_,_=outcome(bars,i,"LONG")
        details=path_outcome_context(bars,i,"LONG",exit_ms,bars,[x.t for x in bars],bars[i].t+BAR_MS)
        self.assertEqual(details[4],"FUNDING_UNVERIFIED_NOT_COUNTED")
        self.assertIsNotNone(details[2])
        self.assertGreaterEqual(details[0],bars[i+1].t)
        self.assertIn(details[3],("BTC_UP","BTC_RANGE","BTC_DOWN"))

    def test_nine_month_periods_are_disjoint(self):
        a,b,c,d=nine_month_bounds("2026-01")
        self.assertEqual(datetime.fromtimestamp(b/1000,timezone.utc).strftime("%Y-%m"),"2026-04")
        self.assertEqual(datetime.fromtimestamp(c/1000,timezone.utc).strftime("%Y-%m"),"2026-07")
        self.assertEqual(datetime.fromtimestamp(d/1000,timezone.utc).strftime("%Y-%m"),"2026-10")
        self.assertTrue(a<b<c<d)

    def test_one_slot_replay_never_double_books(self):
        class YesBrain:
            version="FIXTURE"
            def score(self,rows,kind):
                return [(.01,float(len(rows)-i)) for i in range(len(rows))]
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/"lab.sqlite"
            c=con(db)
            t=month_start("2026-01")
            f=json.dumps({x:0.1 for x in
             ("r3","r12","r48","atr","volume_ratio","range_12","body",
             "btc_r3","btc_r12","btc_r48","btc_atr","vs_btc","utc_hour")})
            for symbol in ("BTCUSDT","ETHUSDT"):
                c.execute("INSERT INTO watch VALUES(?,?,?,?,?,?,?,?)",(t,t+REVIEW,symbol,"up",f,.01,2,"0"*64))
                for j in range(4):
                    decision=t+j*BAR_MS
                    exit_ms=decision+3*BAR_MS
                    c.execute("INSERT INTO opportunity VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (decision,exit_ms,symbol,"LONG","structure_generic","up",f,.02,.03,-.01,
                     exit_ms,"HORIZON","COARSE_5M_OHLC_PATH_PROXY","0"*64))
            c.commit()
            s=replay(c,YesBrain(),t,t+6*BAR_MS)
            self.assertEqual(s["selected_trades"],2)
            self.assertGreater(s["stats"]["occupied_slot_decisions"],0)
            self.assertEqual(s["stats"]["universe_excluded"],0)
            c.close()

REVIEW=8*60*60*1000
if __name__=="__main__":
    unittest.main()
