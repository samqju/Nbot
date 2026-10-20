"""Stop-loss target must remain bound to the trained model's provenance."""
import unittest

from nbot_v7.freqai_research_bridge import (
    NetForecast, FreqAINetResearchBrain,TARGET
)
from nbot_v7.lab import LABEL_POLICY
from nbot_v7.data import BAR_MS

STOP1="V7_5M_PAPER_BROKER_1STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_CF_V1"


def record(policy):
    ms=1780000000000
    return {
        "decision_ms":ms,"symbol":"BTCUSDT","side":"LONG",
        "family":"momentum_3","source_hash":"a"*64,
        "feature_bar_open_ms":ms,"features_ready_ms":ms+BAR_MS,
        "training_labels_available_before_ms":ms-86400000,
        "model_sha256":"b"*64,
        "target":TARGET,
        "label_policy":policy,
        "expected_net":0.002,
        "uncertainty_net":0.004,
    }


class StopPolicyModelContracts(unittest.TestCase):
    def test_prior_2pct_stays_default(self):
        p=NetForecast.from_mapping(record(LABEL_POLICY))
        self.assertEqual(p.label_policy,LABEL_POLICY)
        with self.assertRaises(ValueError):
            NetForecast.from_mapping(record(STOP1))

    def test_explicit_1pct_target_accepted_only_when_authorized(self):
        p=NetForecast.from_mapping(record(STOP1),required_label_policy=STOP1)
        self.assertEqual(p.label_policy,STOP1)
        b=FreqAINetResearchBrain([record(STOP1)],cutoff_ms=1780000000000,
                                   label_policy=STOP1,uncertainty_weight=0)
        scores=b.score([{
            "decision_ms":p.decision_ms,"symbol":p.symbol,"side":p.side,
            "family":p.family,"source_hash":p.source_hash
        }],"opportunity")
        self.assertAlmostEqual(scores[0][0],0.002)

    def test_never_treat_2pct_forecast_as_fitted_on_1pct_labels(self):
        with self.assertRaises(ValueError):
            FreqAINetResearchBrain([record(LABEL_POLICY)],
                                   cutoff_ms=1780000000000,
                                   label_policy=STOP1)
        with self.assertRaises(ValueError):
            FreqAINetResearchBrain([record(STOP1)],
                                   cutoff_ms=1780000000000,
                                   label_policy=LABEL_POLICY)
        with self.assertRaises(ValueError):
            FreqAINetResearchBrain([record(STOP1)],
                                   cutoff_ms=1780000000000,
                                   label_policy="MADE_UP_STOP_TARGET")


if __name__=="__main__":
    unittest.main()
