"""Generated CSV archives -> causal dataset -> frozen brains -> verified artifacts."""
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import nbot_v7.lab as lab
from nbot_v7.archive import months_after
from nbot_v7.artifacts import verify_run
from nbot_v7.data import BAR_MS,contract_registry,Bar
from nbot_v7.experiment import month_start,nine_month_bounds,experiment
from nbot_v7.lab import build_archive_database,con,outcome
from nbot_v7.registry import observed_registry
from nbot_v7.runtime.broker import PaperBroker
from nbot_v7.runtime.risk import RiskPolicy


class ArchiveSystem(unittest.TestCase):
    def test_csv_through_models_replays_deterministically_and_reports_source_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/"archive";archive.mkdir()
            months=months_after("2026-01")
            for month in months:
                t=month_start(month)
                for index,symbol in enumerate(("BTCUSDT","ETHUSDT","SOLUSDT")):
                    with (archive/f"{symbol}-5m-{month}.csv").open("w",newline="") as stream:
                        writer=csv.writer(stream)
                        for j in range(3*288):
                            price=100+index*10+2*math.sin(j/31+index)+.003*j
                            writer.writerow((t+j*BAR_MS,price,price*1.002,price*.998,price*(1+.001*math.sin(j/7)),100+j%23))
            registry=root/"registry.csv"
            report=observed_registry(archive,"2026-01",registry)
            self.assertEqual(report["symbols"],3)
            with self.assertRaisesRegex(ValueError,"UNATTESTED"):
                contract_registry(registry)
            a,_,_,end=nine_month_bounds("2026-01")
            db=root/"dataset.sqlite"
            build_archive_database(archive,registry,db,a,end,set(months),allow_archive_observed=True)
            c=con(db)
            coverage=json.loads(c.execute("SELECT v FROM meta WHERE k='coverage'").fetchone()[0])
            self.assertFalse(coverage["historical_exchange_universe_verified"])
            self.assertGreater(coverage["symbols"]["BTCUSDT"]["missing_eligible_bars"],0)
            c.close()
            first=experiment(db,"2026-01",root/"run1")
            second=experiment(db,"2026-01",root/"run2")
            self.assertEqual(first["dataset_sha256"],second["dataset_sha256"])
            self.assertEqual(first["stage_c"],second["stage_c"])
            for name in ("B_A","C_A","C_B1","C_B"):
                self.assertEqual((root/"run1"/(name+"_decisions.jsonl")).read_bytes(),(root/"run2"/(name+"_decisions.jsonl")).read_bytes())
            verify_run(root/"run1")
            (root/"run1"/"C_B_trades.jsonl").write_text("TAMPERED")
            with self.assertRaisesRegex(ValueError,"HASH_MISMATCH"):verify_run(root/"run1")

    def test_checkpoint_resume_and_source_scope_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); archive=root/"source"; archive.mkdir()
            start=month_start("2026-01")
            for symbol in ("BTCUSDT","ETHUSDT"):
                with (archive/(symbol+"-5m-2026-01.csv")).open("w",newline="") as stream:
                    writer=csv.writer(stream)
                    for i in range(125):
                        price=100+i*.01
                        writer.writerow((start+i*BAR_MS,price,price*1.002,price*.998,price,100))
            registry=root/"registry.csv"
            observed_registry(archive,"2026-01",registry)
            db=root/"partial.sqlite"
            params=dict(allow_archive_observed=True,max_db_gib=.01,min_free_gib=0)
            actual=lab.generate_symbol
            calls=0
            def fail_after_first(*args,**kwargs):
                nonlocal calls
                calls+=1
                if calls==2:
                    raise RuntimeError("SIMULATED_INTERRUPTION")
                return actual(*args,**kwargs)
            with patch.object(lab,"generate_symbol",side_effect=fail_after_first):
                with self.assertRaisesRegex(RuntimeError,"SIMULATED_INTERRUPTION"):
                    build_archive_database(archive,registry,db,start,start+125*BAR_MS,{"2026-01"},**params)
            c=con(db)
            self.assertEqual(c.execute("SELECT v FROM meta WHERE k='build_complete'").fetchone()[0],"false")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM build_progress").fetchone()[0],1)
            labels_before=c.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
            c.close()
            with self.assertRaisesRegex(FileExistsError,"EXISTING_DATABASE"):
                build_archive_database(archive,registry,db,start,start+125*BAR_MS,{"2026-01"},**params)
            report=build_archive_database(archive,registry,db,start,start+125*BAR_MS,{"2026-01"},
                                          resume=True,**params)
            self.assertEqual(report["symbols_reused_after_checkpoint"],1)
            self.assertEqual(report["symbols_scanned"],2)
            c=con(db)
            self.assertEqual(c.execute("SELECT v FROM meta WHERE k='build_complete'").fetchone()[0],"true")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM build_progress").fetchone()[0],2)
            self.assertGreaterEqual(c.execute("SELECT COUNT(*) FROM candidate").fetchone()[0],labels_before)
            c.close()
            with self.assertRaisesRegex(ValueError,"PARTIAL_DATASET_SCOPE"):
                build_archive_database(archive,registry,db,start,start+125*BAR_MS,{"2026-01"},resume=True,**params)

    def test_database_budget_leaves_explicit_incomplete_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"source";source.mkdir()
            start=month_start("2026-01")
            with (source/"BTCUSDT-5m-2026-01.csv").open("w",newline="") as f:
                writer=csv.writer(f)
                for i in range(100):
                    writer.writerow((start+i*BAR_MS,100,101,99,100,100))
            registry=root/"registry.csv"
            observed_registry(source,"2026-01",registry)
            db=root/"too-small.sqlite"
            with self.assertRaisesRegex(RuntimeError,"DATASET_DB_BUDGET_EXCEEDED_INCOMPLETE"):
                build_archive_database(source,registry,db,start,start+100*BAR_MS,{"2026-01"},
                                       allow_archive_observed=True,max_db_gib=1e-8,min_free_gib=0)
            c=con(db)
            self.assertEqual(c.execute("SELECT v FROM meta WHERE k='build_complete'").fetchone()[0],"false")
            c.close()

    def test_historical_label_and_incremental_paper_broker_use_identical_fills(self):
        bars=[Bar(i*BAR_MS,100,100.3,99.7,100,10) for i in range(20)]
        bars[5]=Bar(5*BAR_MS,100,105,95,100,10)
        for side in ("LONG","SHORT"):
            broker=PaperBroker();policy=RiskPolicy()
            position=broker.submit({"id":"PARITY","symbol":"TEST","time_ms":BAR_MS,"side":side,"quote":100},policy)
            for b in bars[1:13]:
                result,position=broker.on_bar(position,b,b.t+BAR_MS,policy)
                if result is not None:break
            label=outcome(bars,0,side)
            self.assertAlmostEqual(label[0],result["net_usdt"]/policy.notional_usdt)
            self.assertEqual(label[3],result["available_ms"])

if __name__=="__main__":unittest.main()
