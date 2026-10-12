"""Public Binance market-quality parser fixtures: no network access."""
from dataclasses import replace
import copy
import unittest

from nbot.observation.models import SourceCapture
from nbot.observation.v5_market_quality import (
    parse_exchange_info, parse_depth, capture_public_quality, submit_order,
)
from nbot.observation.v5_selection import evaluate, DepthSnapshot
from tests.test_v5_selection import observations, NOW


def info_row():
    return {
        "symbol": "BTCUSDT", "quoteAsset": "USDT",
        "contractType": "PERPETUAL", "status": "TRADING",
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "stepSize": "0.001",
             "minQty": "0.001", "maxQty": "100.0"},
            {"filterType": "MIN_NOTIONAL", "notional": "5.0"},
        ],
    }


class QualityBridgeTests(unittest.TestCase):
    def test_exchange_rules_parse_and_provenance(self):
        payload = {"symbols": [info_row()]}
        c = SourceCapture("v5_exchange_info", NOW-5000, NOW-4000)
        x = parse_exchange_info(payload, c, symbols=("BTCUSDT",))
        inst = x["BTCUSDT"]
        self.assertTrue(inst.trading)
        self.assertEqual(inst.tick_size, .01)
        self.assertEqual(inst.quantity_step, .001)
        self.assertEqual(inst.min_notional, 5)
        self.assertEqual(inst.min_qty, .001)
        self.assertEqual(inst.max_qty, 100)
        self.assertEqual(len(inst.source_digest), 64)
        self.assertEqual(x, parse_exchange_info(payload,c,symbols=("BTCUSDT",)))

    def test_invalid_exchange_filter_and_contract_fail_closed(self):
        c=SourceCapture("v5_exchange_info", NOW-5000, NOW-4000)
        row=info_row()
        bad=copy.deepcopy(row)
        bad["filters"]=[f for f in bad["filters"] if f["filterType"] != "MIN_NOTIONAL"]
        with self.assertRaisesRegex(ValueError,"FILTERS_MISSING"):
            parse_exchange_info({"symbols":[bad]},c,symbols=("BTCUSDT",))
        bad=copy.deepcopy(row)
        bad["quoteAsset"]="USDC"
        with self.assertRaisesRegex(ValueError,"CONTRACT_INVALID"):
            parse_exchange_info({"symbols":[bad]},c,symbols=("BTCUSDT",))
        with self.assertRaisesRegex(ValueError,"SYMBOL_MISSING"):
            parse_exchange_info({"symbols":[]},c,symbols=("BTCUSDT",))
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            parse_exchange_info({"symbols":[row,row]},c,symbols=("BTCUSDT",))
        bad=copy.deepcopy(row)
        bad["filters"][0]["tickSize"]="0"
        with self.assertRaisesRegex(ValueError,"INVALID_TICK"):
            parse_exchange_info({"symbols":[bad]},c,symbols=("BTCUSDT",))

    def test_depth_sweep_quote_and_timestamp(self):
        m=observations()
        payload={"lastUpdateId":42,"bids":[[str(m.bid),"10"]],
                 "asks":[[str(m.ask),"10"]]}
        depth=parse_depth(payload,SourceCapture("v5_depth",NOW-2500,NOW-1500),
                          symbol=m.symbol)
        self.assertEqual(depth.bids[0],(m.bid,10))
        self.assertEqual(len(depth.source_digest),64)
        self.assertTrue(evaluate(replace(m,depth=depth),"LONG",now_ms=NOW).qualified)
        bad=copy.deepcopy(payload)
        bad["asks"][0][1]="NaN"
        with self.assertRaisesRegex(ValueError,"PAYLOAD_INVALID"):
            parse_depth(bad,SourceCapture("v5_depth",NOW-2500,NOW-1500),symbol=m.symbol)

    def test_no_arbitrary_client_or_orders(self):
        with self.assertRaisesRegex(ValueError,"PUBLIC_CLIENT_REQUIRED"):
            capture_public_quality(object(),("BTCUSDT",))
        with self.assertRaisesRegex(RuntimeError,"NO_ORDER_AUTHORITY"):
            submit_order()


if __name__=="__main__":
    unittest.main()
