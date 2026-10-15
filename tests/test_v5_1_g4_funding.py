"""Settled funding public REST receipt only; absolutely no account-cost claim."""
import json
import unittest
from dataclasses import replace

from nbot_v5_1.settled_funding import verify_settled,FundingHold

NOW=1792051084925
PATH="/fapi/v1/fundingRate?symbol=BTCUSDT&limit=2"

def sample():
    return json.dumps([
      {"symbol":"BTCUSDT","fundingRate":"0.0001","fundingTime":NOW-57600000},
      {"symbol":"BTCUSDT","fundingRate":"-0.0002","fundingTime":NOW-28800000},
    ],separators=(",",":")).encode()

class SettledFundingTests(unittest.TestCase):
    def test_T01_previous_settlements_are_real_public_not_position_fills(self):
        a=verify_settled(symbol="BTCUSDT",raw=sample(),
                          received_at_ms=NOW,path=PATH)
        self.assertEqual(len(a.settlements),2)
        self.assertEqual(a.financial_authority,"NONE")
        self.assertEqual(a.qualified_virtual_costs,0)
        self.assertEqual(a.grade,"PUBLIC_REST_SETTLED_HISTORY_NOT_POSITION_COST")
        self.assertEqual(len(a.source_sha256),64)

    def test_T02_future_funding_never_called_settled(self):
        rows=json.loads(sample())
        rows[-1]["fundingTime"]=NOW+1000
        with self.assertRaises(FundingHold):
            verify_settled(symbol="BTCUSDT",raw=json.dumps(rows).encode(),
                           received_at_ms=NOW,path=PATH)

    def test_T03_missing_or_duplicate_times_block(self):
        rows=json.loads(sample())
        rows[-1]["fundingTime"]=rows[0]["fundingTime"]
        with self.assertRaises(FundingHold):
            verify_settled(symbol="BTCUSDT",raw=json.dumps(rows).encode(),
                           received_at_ms=NOW,path=PATH)

    def test_T04_private_route_and_wrong_symbol_denied(self):
        with self.assertRaises(FundingHold):
            verify_settled(symbol="BTCUSDT",raw=sample(),
                          received_at_ms=NOW,path="/fapi/v1/account")
        with self.assertRaises(FundingHold):
            verify_settled(symbol="ETHUSDT",raw=sample(),received_at_ms=NOW,
                          path="/fapi/v1/fundingRate?symbol=ETHUSDT&limit=2")

    def test_T05_nan_infinite_negative_boolean_clock_fail_closed(self):
        for rate in ("NaN","Infinity","0.50","zz"):
            rows=json.loads(sample());rows[0]["fundingRate"]=rate
            with self.subTest(rate=rate),self.assertRaises(FundingHold):
                verify_settled(symbol="BTCUSDT",raw=json.dumps(rows).encode(),
                               received_at_ms=NOW,path=PATH)
        with self.assertRaises(FundingHold):
            verify_settled(symbol="BTCUSDT",raw=sample(),
                           received_at_ms=True,path=PATH)

if __name__=="__main__":unittest.main()
