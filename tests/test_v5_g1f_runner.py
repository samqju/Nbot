"""G1f runner startup, resource, and public-only REST contracts."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from nbot.v5.g1f_runner import (
    ObservationOnlyRunner, resource_guard, db_size_mib, rest_seed,
)
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.observation_contract import INTERVAL_MS
from tests.test_v5_public_market import klines


class G1fRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"g1f_data.sqlite"

    def test_invalid_runtime_limits_refuse_before_opening_database(self):
        for top,max_seconds in ((0,60),(51,60),(2,10),
                                (2,3601),(2,-1),(True,60)):
            with self.subTest(args=(top,max_seconds)),self.assertRaises(ValueError):
                ObservationOnlyRunner(top=top,path=self.db,
                                      max_seconds=max_seconds)
        self.assertFalse(self.db.exists())

    def test_isolated_db_path_must_have_existing_parent(self):
        with self.assertRaisesRegex(EvidenceHold,"DB_PARENT_MISSING"):
            ObservationOnlyRunner(
                top=2,path=self.db.parent/"missing"/"g1f.sqlite",
                max_seconds=60)

    def test_runtime_metrics_and_file_size_are_bounded(self):
        app=ObservationOnlyRunner(top=2,path=self.db,max_seconds=60)
        self.assertFalse(app.stop.is_set())
        self.assertEqual(db_size_mib(self.db),0)
        result=resource_guard(self.db)
        self.assertLess(result["peak_rss_mib"],192)
        self.assertEqual(result["db_mib"],0)

    def test_rest_seed_uses_only_96_closed_bars_for_each_coin(self):
        event=(int(time.time()*1000)//INTERVAL_MS-1)*INTERVAL_MS
        queried=[]
        def getter(path,params=None):
            self.assertEqual(path,"/fapi/v1/klines")
            queried.append(params["symbol"])
            self.assertEqual(params["interval"],"5m")
            self.assertEqual(params["limit"],"96")
            self.assertEqual(int(params["endTime"]),event+INTERVAL_MS-1)
            return klines(event)
        with ObservationContinuity(("BTCUSDT","ETHUSDT"),self.db) as collector:
            result=asyncio.run(rest_seed(collector,collector.symbols,
                                         event,getter=getter))
            self.assertEqual(len(result),2)
            self.assertTrue(all(x["inserted"]==96 for x in result.values()))
            self.assertCountEqual(queried,collector.symbols)
            self.assertFalse(collector.store.health.cohort_valid)
        with ObservationContinuity(("BTCUSDT","ETHUSDT"),self.db) as reopened:
            self.assertEqual(reopened.ledger.inspect("BTCUSDT")["closed_bar_count"],96)
            self.assertEqual(reopened.ledger.inspect("ETHUSDT")["closed_bar_count"],96)
            self.assertFalse(reopened.ledger.inspect("BTCUSDT")["research_ready"])

    def test_REST_failure_does_not_create_fake_market_bars(self):
        event=(int(time.time()*1000)//INTERVAL_MS-1)*INTERVAL_MS
        def getter(path,params=None):
            if params["symbol"]=="ETHUSDT":
                raise OSError("SIMULATED_PUBLIC_NETWORK_LOSS")
            return klines(event)
        with ObservationContinuity(("BTCUSDT","ETHUSDT"),self.db) as collector:
            with self.assertRaisesRegex(EvidenceHold,"REST_SEED_ETHUSDT"):
                asyncio.run(rest_seed(
                    collector,collector.symbols,event,getter=getter))
            self.assertEqual(collector.ledger.inspect("ETHUSDT")["closed_bar_count"],0)


if __name__=="__main__":
    unittest.main()
