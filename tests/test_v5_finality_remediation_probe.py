"""No-network exercise of G1e remediation two-window one-shot probe."""
import asyncio
import time
import unittest
from unittest.mock import patch

from nbot.v5.live_finality_remediation_probe import run_probe
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.finality_quarantine import STAGES
from tests.test_v5_public_market import exchange, ticker


class FinalityRemediationProbeTests(unittest.TestCase):
    def test_invalid_bounds_do_not_call_exchange(self):
        for top,windows,seconds in ((0,2,338),(51,2,338),(50,3,338),
                                    (50,2,20),(True,2,338)):
            with self.subTest(params=(top,windows,seconds)):
                with self.assertRaises(ValueError):
                    asyncio.run(run_probe(
                        top=top,windows=windows,seconds=seconds,
                        getter=lambda *a: self.fail("No public network allowed"),
                    ))

    def _synthetic(self, *, conflict=False, btc_conflict=False):
        now=int(time.time()*1000)
        selections=["BTCUSDT"]+[f"COIN{i:02}USDT" for i in range(49)]
        event_opens=[]
        def fake_get(path,params=None):
            if path=="/fapi/v1/time":
                return {"serverTime":now}
            if path=="/fapi/v1/exchangeInfo":
                return exchange()
            if path=="/fapi/v1/ticker/24hr":
                return ticker()
            self.fail("Unexpected REST endpoint")
        async def fake_collect(symbols,target,seconds):
            event_opens.append(target)
            return ({
                s: {"symbol":s,"candle":(target,100.,101.,99.,100.,10.),
                    "received_ms":target+INTERVAL_MS+1000}
                for s in symbols
            },{"frames":5000,"trades":500})
        async def fake_rest_stage(audit,live,event,stage,getter):
            results=[]
            for s,row in live.items():
                bar=row["candle"]
                if stage=="FIRST_REST" and (
                    (conflict and s=="COIN00USDT") or
                    (btc_conflict and s=="BTCUSDT")
                ):
                    rest=(event,100.,101.,99.,100.7,10.5)
                else:
                    rest=bar
                result=audit.check(
                    s,event,stage,
                    observed_ms=event+INTERVAL_MS+2000+STAGES.index(stage)*9000,
                    wss_candle=bar,rest_candle=rest,
                )
                results.append(result)
            return results
        async def fast_sleep(seconds):
            return None
        with (
            patch("nbot.v5.live_finality_remediation_probe.collect",
                  side_effect=fake_collect),
            patch("nbot.v5.live_finality_remediation_probe.rest_stage",
                  side_effect=fake_rest_stage),
            patch("nbot.v5.live_finality_remediation_probe.asyncio.sleep",
                  side_effect=fast_sleep),
        ):
            report=asyncio.run(run_probe(
                top=50,windows=2,seconds=338,getter=fake_get,
            ))
        self.assertEqual(len(event_opens),2)
        self.assertEqual(event_opens[1]-event_opens[0],INTERVAL_MS)
        return report

    def test_two_50_coin_windows_zero_conflicts_are_observe_only(self):
        result=self._synthetic()
        self.assertEqual(result["result"],"PASS_WITH_QUARANTINE")
        self.assertEqual(result["reopen"]["wss_proofs"],100)
        self.assertEqual(result["reopen"]["rest_checks"],300)
        self.assertEqual(result["reopen"]["directional_observations"],200)
        self.assertTrue(result["reopen"]["temporary_db_removed"])
        self.assertEqual([len(x["evidence"]["verified_symbols"])
                          for x in result["windows"]],[50,50])
        self.assertFalse(result["research_ready"])
        self.assertEqual(result["training_labels_created"],0)
        self.assertEqual(result["order_authority"],"NONE")

    def test_initial_disputed_coins_stay_quarantined_after_later_match(self):
        result=self._synthetic(conflict=True)
        self.assertEqual(result["result"],"PASS_WITH_QUARANTINE")
        for window in result["windows"]:
            self.assertEqual(len(window["evidence"]["verified_symbols"]),49)
            self.assertEqual(len(window["evidence"]["quarantined_symbols"]),1)
            self.assertEqual(window["evidence"]["directional_observation_states"]
                             ["quarantined_unscorable"],2)
            self.assertTrue(window["evidence"]["btc_verified"])
            self.assertEqual(window["rest_stages"][0]["matched"],49)
            self.assertEqual(window["rest_stages"][2]["matched"],50)
        self.assertEqual(result["reopen"]["directional_observations"],200)

    def test_btc_dispute_never_permits_other_coin_evidence(self):
        report=self._synthetic(btc_conflict=True)
        self.assertEqual(report["result"],"HOLD")
        for window in report["windows"]:
            self.assertFalse(window["evidence"]["btc_verified"])
            self.assertEqual(window["evidence"]["recorded_directional_observations"],100)
            self.assertFalse(window["evidence"]["research_ready"])
            self.assertFalse(window["evidence"]["evidence_cohort_eligible_for_future_review"])
        self.assertEqual(report["order_authority"],"NONE")


if __name__=="__main__":
    unittest.main()
