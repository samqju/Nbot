import unittest
from strategy.candidate import StrategyCandidate, rank_candidates
from strategy.candidate_scorer import CandidateScorer
from strategy.features import CandidateFeatures
class Phase33CandidateScoringTests(unittest.TestCase):
    def _candidate(self,**kw):
        d=dict(symbol="BTCUSDT",direction="LONG",rule_score=0.6,trend=7,short_range=0.01,acceleration=1.0,body=0.6,dist_high=-0.005,dist_low=0.03,consistency=4); d.update(kw); f=CandidateFeatures(d["short_range"],0.01,d["trend"],1.0-d["body"],d["body"],d["acceleration"],d["dist_high"],d["dist_low"],d["consistency"]); return StrategyCandidate(d["symbol"],d["direction"],d["rule_score"],"STRUCTURE_5M",123,f)
    def test_score_is_bounded_and_explained(self):
        s=CandidateScorer().score(self._candidate()); self.assertGreaterEqual(s.score,0); self.assertLessEqual(s.score,1); self.assertEqual(s.score,s.score_breakdown.final_score); self.assertEqual(s.score_breakdown.rule_score,0.6)
    def test_stronger_features_score_higher(self):
        sc=CandidateScorer(); weak=sc.score(self._candidate(trend=2,short_range=0.0025,acceleration=3.5,body=0.2,dist_high=-0.03,consistency=1)); strong=sc.score(self._candidate(trend=9,short_range=0.012,acceleration=1.2,body=0.8,dist_high=-0.001,consistency=5)); self.assertGreater(strong.score,weak.score)
    def test_short_location_uses_low_distance(self):
        sc=CandidateScorer(); near=sc.score(self._candidate(direction="SHORT",dist_low=0.001,dist_high=-0.04)); far=sc.score(self._candidate(direction="SHORT",dist_low=0.04,dist_high=-0.001)); self.assertGreater(near.score_breakdown.location_quality,far.score_breakdown.location_quality)
    def test_ranking_uses_final_score(self):
        sc=CandidateScorer(); ranked=rank_candidates(sc.score_all([self._candidate(symbol="WEAKUSDT",trend=2,body=0.2,consistency=1),self._candidate(symbol="STRONGUSDT",trend=9,body=0.8,consistency=5)])); self.assertEqual(ranked[0].symbol,"STRONGUSDT")
    def test_invalid_weight_sum_rejected(self):
        with self.assertRaisesRegex(ValueError,"CANDIDATE_SCORER_WEIGHTS_SUM"): CandidateScorer(rule_weight=1,trend_weight=1,volatility_weight=0,candle_weight=0,location_weight=0,consistency_weight=0)
if __name__=="__main__": unittest.main()
