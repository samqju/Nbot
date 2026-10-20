"""Contract tests for FreqAI after-cost candidate export and V7 ranking."""
import unittest
from nbot_v7.data import BAR_MS
from nbot_v7.lab import LABEL_POLICY
from nbot_v7.decision import choose
from nbot_v7.freqai_research_bridge import (
    FreqAINetResearchBrain, NetForecast, TARGET
)


def forecast(symbol="BTCUSDT", family="momentum_3", side="LONG",
             decision_ms=1800000000000, expected_net=.004, uncertainty_net=.001):
    return {
        "decision_ms":decision_ms, "symbol":symbol, "side":side,
        "family":family, "source_hash":"a"*64,
        "feature_bar_open_ms":decision_ms,
        "features_ready_ms":decision_ms+BAR_MS,
        "training_labels_available_before_ms":decision_ms-3600000,
        "model_sha256":"b"*64,
        "target":TARGET, "label_policy":LABEL_POLICY,
        "expected_net":expected_net,"uncertainty_net":uncertainty_net,
    }


def candidate(r):
    # The real V7 entry path whitelists these causal fields before scoring.
    # Test the same strict route rather than calling our adapter directly.
    return {
        **{k:r[k] for k in
           ("decision_ms", "symbol", "side", "family", "source_hash")},
        "regime":"range", "features":"{}",
    }


class FreqAIThreeCoinResearchContracts(unittest.TestCase):
    def test_chooses_highest_confidence_adjusted_aftercost_opportunity(self):
        a=forecast(expected_net=.006,uncertainty_net=.005)
        b=forecast(symbol="ETHUSDT",side="SHORT",family="reversal_3",
                   expected_net=.004,uncertainty_net=.001)
        c=forecast(symbol="SOLUSDT",family="breakout_12",
                   expected_net=.003,uncertainty_net=.004)
        model=FreqAINetResearchBrain([a,b,c],cutoff_ms=a["decision_ms"]-86400000)
        selected,predictions=choose(model,[candidate(a),candidate(b),candidate(c)])
        self.assertEqual(selected[0]["symbol"],"ETHUSDT")
        self.assertAlmostEqual(selected[1][0],.003)
        self.assertEqual(len(predictions),3)

    def test_no_trade_if_all_lower_bound_net_nonpositive(self):
        a=forecast(expected_net=.001,uncertainty_net=.003)
        b=forecast(symbol="SOLUSDT",expected_net=.002,uncertainty_net=.004)
        brain=FreqAINetResearchBrain([a,b],cutoff_ms=a["decision_ms"]-86400000)
        selected,_=choose(brain,[candidate(a),candidate(b)])
        self.assertIsNone(selected)

    def test_price_only_standard_freqai_prediction_cannot_pass_as_net(self):
        a=forecast()
        a["target"]="&-s_close"
        with self.assertRaisesRegex(ValueError,"NON_NET_TARGET"):
            FreqAINetResearchBrain([a],cutoff_ms=a["decision_ms"]-86400000)

    def test_future_label_or_future_feature_fails_closed(self):
        a=forecast()
        a["training_labels_available_before_ms"]=a["decision_ms"]+1
        with self.assertRaises(ValueError):
            NetForecast.from_mapping(a)
        b=forecast()
        b["features_ready_ms"]+=BAR_MS
        with self.assertRaises(ValueError):
            NetForecast.from_mapping(b)

    def test_refuses_mismatched_source_and_duplicate_candidate_forecast(self):
        a=forecast()
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            FreqAINetResearchBrain([a,a],cutoff_ms=a["decision_ms"]-86400000)
        brain=FreqAINetResearchBrain([a],cutoff_ms=a["decision_ms"]-86400000)
        bad=candidate(a)
        bad["source_hash"]="c"*64
        with self.assertRaisesRegex(ValueError,"SOURCE_OR_ASOF"):
            brain.score([bad],"opportunity")

    def test_unknown_signals_fail_to_abstention_not_hindsight(self):
        a=forecast()
        model=FreqAINetResearchBrain([a],cutoff_ms=a["decision_ms"]-86400000)
        nonlisted=forecast(symbol="ETHUSDT",family="breakout_48")
        selected,_=choose(model,[candidate(nonlisted)])
        self.assertIsNone(selected)

    def test_forbids_future_outcome_columns_in_prediction_contract(self):
        a=forecast()
        a["realized_net_after_cost"]=.23
        with self.assertRaisesRegex(ValueError,"FUTURE_OUTCOME_COLUMN"):
            NetForecast.from_mapping(a)


if __name__=="__main__":
    unittest.main()
