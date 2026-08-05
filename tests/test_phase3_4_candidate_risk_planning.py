import unittest
from strategy.candidate import StrategyCandidate
from strategy.candidate_risk import CandidateRiskPlanner
from strategy.features import CandidateFeatures

class Phase34CandidateRiskPlanningTests(unittest.TestCase):
    def _candidate(self,direction="LONG",price=100.0,short_range=0.01):
        f=CandidateFeatures(short_range,0.01,7,0.4,0.6,1.0,-0.005,0.03,4)
        return StrategyCandidate("BTCUSDT",direction,0.7,"STRUCTURE_5M",1,f,reference_price=price)

    def test_long_plan_math(self):
        p=CandidateRiskPlanner(risk_budget_usd=10,max_notional_usd=1000,leverage=5,min_stop_pct=0.5,max_stop_pct=2.0).plan(self._candidate()).risk_plan
        self.assertAlmostEqual(p.stop_distance_pct,1.0); self.assertAlmostEqual(p.suggested_quantity,10.0)
        self.assertAlmostEqual(p.suggested_notional_usd,1000.0); self.assertAlmostEqual(p.suggested_stop_price,99.0)
        self.assertAlmostEqual(p.required_margin_usd,200.0); self.assertEqual(p.capped_by,"NOTIONAL")

    def test_short_stop_above_price(self):
        c=CandidateRiskPlanner().plan(self._candidate(direction="SHORT"))
        self.assertGreater(c.risk_plan.suggested_stop_price,c.reference_price)

    def test_stop_distance_clamped(self):
        r=CandidateRiskPlanner(min_stop_pct=0.5,max_stop_pct=2.0)
        self.assertAlmostEqual(r.plan(self._candidate(short_range=0.0001)).risk_plan.stop_distance_pct,0.5)
        self.assertAlmostEqual(r.plan(self._candidate(short_range=0.10)).risk_plan.stop_distance_pct,2.0)

    def test_wider_stop_reduces_quantity(self):
        r=CandidateRiskPlanner(risk_budget_usd=10,max_notional_usd=1000,min_stop_pct=0.5,max_stop_pct=2.0)
        narrow=r.plan(self._candidate(short_range=0.005)); wide=r.plan(self._candidate(short_range=0.02))
        self.assertGreater(narrow.risk_plan.suggested_quantity,wide.risk_plan.suggested_quantity)
        self.assertEqual(wide.risk_plan.capped_by,"RISK")

    def test_missing_reference_price_rejected(self):
        f=CandidateFeatures(0.01,0.01,7,0.4,0.6,1.0,-0.005,0.03,4)
        c=StrategyCandidate("BTCUSDT","LONG",0.7,"STRUCTURE_5M",1,f)
        with self.assertRaisesRegex(ValueError,"CANDIDATE_RISK_REFERENCE_PRICE_INVALID"):
            CandidateRiskPlanner().plan(c)

if __name__=="__main__": unittest.main()
