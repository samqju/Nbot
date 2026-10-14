"""Fresh G1 ranked selection and restart G3 cohort equivalence."""
import unittest
from nbot.v5.g1f_runner import g3_frozen_cohort
from nbot.v5.candle_ledger import EvidenceHold


class FreshG3CohortTests(unittest.TestCase):
    def test_original_volume_rank_normalizes_without_changing_membership(self):
        ranked=("BTCUSDT","SOLUSDT","ETHUSDT","ADAUSDT")
        frozen=g3_frozen_cohort(ranked)
        self.assertEqual(frozen,("ADAUSDT","BTCUSDT","ETHUSDT","SOLUSDT"))
        self.assertEqual(set(frozen),set(ranked))
        self.assertEqual(g3_frozen_cohort(frozen),frozen)

    def test_duplicate_or_missing_btc_cannot_become_valid_cohort(self):
        for bad in (
            ("ETHUSDT","SOLUSDT"),
            ("BTCUSDT","BTCUSDT"),
            ("BTCUSDT",),
        ):
            with self.subTest(bad=bad), self.assertRaises(EvidenceHold):
                g3_frozen_cohort(bad)


if __name__=="__main__":
    unittest.main()
