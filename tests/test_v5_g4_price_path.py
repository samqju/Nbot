"""Synthetic-only G4 genuine-format aggTrade path tests. No exchange and NO fills."""
from hashlib import sha256
import json
import unittest

from nbot.v5.g4_price_path import replay_aggtrade_price_path

EVENT = 1_800_000_000_000
DECISION = EVENT + 301_000
MATURITY = DECISION + 600_000
H = "a" * 64


def make(side="LONG"):
    prices = ["99","100","100","105","110","111","110"]
    times=[DECISION-1,DECISION,DECISION+10,DECISION+100,
           DECISION+200,DECISION+300,MATURITY+1]
    rows = [
        {"a":i+100,"f":2*i+1000,"l":2*i+1001,"T":t,"p":p,"q":"0.10","m":i%2==0}
        for i,(t,p) in enumerate(zip(times,prices))
    ]
    policy = {
        "horizon_ms":600_000, "declared_at_ms":DECISION,
        "policy_sha256":"b"*64,
        "entry_reference_price":"100",
        "stop_price":"95" if side=="LONG" else "115",
        "target_price":"110" if side=="LONG" else "95",
    }
    candidate={"decision_id":H,"symbol":"BTCUSDT","side":side,
               "decision_at_ms":DECISION,"status":"OBSERVED"}
    manifest={"archive_sha256":"c"*64,"symbol":"BTCUSDT",
              "source_grade":"ORIGINAL_BINANCE_PUBLIC_AGGTRADES",
              "original_archive_verified":True,
              "first_agg_id":100,"last_agg_id":106}
    manifest["rows_sha256"]=sha256(json.dumps(rows,sort_keys=True,
        separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
    return candidate, policy, rows, manifest


def run(modifier=None, at=MATURITY+10):
    c,p,r,m=make()
    if modifier: modifier(c,p,r,m)
    return replay_aggtrade_price_path(candidate=c,policy=p,
                                     original_rows=r,source_manifest=m,audit_at_ms=at)


class G4PricePathTests(unittest.TestCase):
    def test_original_tick_path_produces_price_only_not_net_fills(self):
        x=run()
        self.assertEqual(x.state,"PATH_REPLAYED")
        self.assertEqual(x.exit_reason,"TARGET_PRICE_CROSSED")
        self.assertEqual(x.exit_trade_price,"110")
        self.assertEqual(x.gross_path_r,"2")
        self.assertIsNone(x.net_r)
        self.assertEqual(x.scored_outcomes,0)
        self.assertEqual(x.financial_authority,"NONE")
        self.assertEqual(x.path_trade_count,7)

    def test_determinism(self):
        self.assertEqual(run(),run())

    def test_pre_maturity_is_pending(self):
        self.assertEqual(run(at=MATURITY-1).state,"PENDING")

    def test_source_row_digest_tamper_cannot_replay(self):
        x=run(lambda c,p,r,m:r[3].update(p="10000"))
        self.assertEqual(x.state,"HOLD")
        self.assertIn("ORIGINAL_ROWS_SHA_MISMATCH",x.reasons)

    def test_agg_id_gap_blocks_replay(self):
        def gap(c,p,r,m):
            r[2]["a"]+=1
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        x=run(gap)
        self.assertIn("AGGTRADE_SEQUENCE_GAP_OR_REORDER",x.reasons)

    def test_original_underlying_trade_id_gap_blocks_replay(self):
        def gap(c,p,r,m):
            r[4]["f"]+=2
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        x=run(gap)
        self.assertIn("AGGTRADE_SEQUENCE_GAP_OR_REORDER",x.reasons)

    def test_out_of_order_time_blocks_replay(self):
        def bad(c,p,r,m):
            r[3]["T"]=DECISION-500
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertIn("TRADE_TIME_REORDER",run(bad).reasons)

    def test_missing_end_coverage_never_synthesizes_horizon(self):
        def bad(c,p,r,m):
            r[-1]["T"]=MATURITY-1
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertIn("ORIGINAL_PATH_BOUNDS_INCOMPLETE",run(bad).reasons)

    def test_missing_start_coverage_never_synthesizes_price(self):
        def bad(c,p,r,m):
            r[0]["T"]=DECISION+1
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertIn("ORIGINAL_PATH_BOUNDS_INCOMPLETE",run(bad).reasons)

    def test_fake_source_grade_rejected(self):
        self.assertIn("ORIGINAL_SOURCE_GRADE_UNVERIFIED",
                      run(lambda c,p,r,m:m.update(source_grade="SYNTHETIC")).reasons)

    def test_authenticity_verification_mandatory(self):
        self.assertIn("ORIGINAL_ARCHIVE_AUTHENTICITY_UNVERIFIED",
                      run(lambda c,p,r,m:m.update(original_archive_verified=False)).reasons)

    def test_other_symbol_rejected(self):
        self.assertIn("ORIGINAL_SYMBOL_MISMATCH",
                      run(lambda c,p,r,m:m.update(symbol="ETHUSDT")).reasons)

    def test_future_declared_stop_invalid(self):
        self.assertIn("POLICY_OR_DECISION_CLOCK_INVALID",
                      run(lambda c,p,r,m:p.update(declared_at_ms=DECISION+1)).reasons)

    def test_long_stop_geometry_invalid(self):
        self.assertIn("LONG_RISK_GEOMETRY_INVALID",
                      run(lambda c,p,r,m:p.update(stop_price="120")).reasons)

    def test_short_path_stop_first(self):
        c,p,r,m=make("SHORT")
        x=replay_aggtrade_price_path(candidate=c,policy=p,original_rows=r,
            source_manifest=m,audit_at_ms=MATURITY+10)
        self.assertEqual(x.state,"PATH_REPLAYED")
        self.assertEqual(x.exit_reason,"HORIZON_LAST_TRADE")
        self.assertEqual(x.gross_path_r,"-0.6666666666666666666666666666666667")

    def test_short_stop_exact_tick(self):
        def stop(c,p,r,m):
            c["side"]="SHORT"
            p["stop_price"]="105"
            p["target_price"]="95"
        x=run(stop)
        self.assertEqual(x.exit_reason,"STOP_PRICE_CROSSED")
        self.assertEqual(x.gross_path_r,"-1")

    def test_short_first_trade_valid(self):
        def rev(c,p,r,m):
            c["side"]="SHORT"
            p["stop_price"]="115"
            p["target_price"]="95"
            r[1]["p"]="90"
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        x=run(rev)
        self.assertEqual(x.gross_path_r,"0.6666666666666666666666666666666667")

    def test_unknown_source_negative_price_is_not_replay(self):
        def bad(c,p,r,m):
            r[2]["p"]="-5"
            m["rows_sha256"]=sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertIn("ORIGINAL_ROW_INVALID",run(bad).reasons)

    def test_missing_archive_sha_is_hold(self):
        self.assertIn("ORIGINAL_ARCHIVE_MANIFEST_MISSING",
                      run(lambda c,p,r,m:m.update(archive_sha256=None)).reasons)


if __name__=="__main__":
    unittest.main()
