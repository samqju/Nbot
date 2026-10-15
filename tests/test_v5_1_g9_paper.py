"""G9 Champion-first PAPER authority locked, only local hypothetical LAB."""
import tempfile
from pathlib import Path
from dataclasses import replace
from decimal import Decimal
import unittest

from nbot_v5_1.paper_contract import (
    PaperPolicy,SignedLabProposal,PaperQuote,PaperCosts,PaperHold,
    proposal_body,sign_lab_proposal,assess_lab_proposal,authorize_real_paper_release)
from nbot_v5_1.paper_lab import ChampionLabPaperBook,real_paper_entry
from nbot_v5_1.research_journal import ResearchJournal,JournalHold

H="a"*64;MODEL="b"*64;KEY=b"G9 offline non-production lab key "*2
AT=1792030000000

def policy(**changes):
    base=PaperPolicy()
    return replace(base,**changes)

def proposal(*,i=1,side="LONG",stop=None,target=None,at=AT,model=MODEL,source=H,pol=None,
             key=KEY,book="CHAMPION_LAB_ONLY",grade="SYNTHETIC_OFFLINE_TEST_ONLY",authority="NONE"):
    pol=pol or policy()
    fields=dict(decision_id=f"{i:064x}",model_sha256=model,at_ms=at,
        expires_ms=at+4000,symbol="BTCUSDT",side=side,
        stop=stop or ("95" if side=="LONG" else "105"),
        target=target or ("105" if side=="LONG" else "95"),
        lower_net_r="0.8",source_sha256=source,policy_sha256=pol.digest(),
        idempotency_sha256=f"{i+1000:064x}",book=book,grade=grade,
        authority=authority)
    signed=sign_lab_proposal(fields,key) if grade=="SYNTHETIC_OFFLINE_TEST_ONLY" and book=="CHAMPION_LAB_ONLY" and authority=="NONE" else "z"*64
    return SignedLabProposal(signature=signed,**fields)

def quote(at=AT,side="LONG",bid=None,ask=None):
    return PaperQuote("BTCUSDT",at,bid or "100",ask or "100.1",H)

def costs(at=AT,**changes):
    return replace(PaperCosts("0.0004","0.0005","0.01",at,H,H,H,
                  funding_from_ms=AT-1000000),**changes)


class G9Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g9-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/"paper-lab.jsonl"
        self.p=policy()
        self.b=ChampionLabPaperBook(ResearchJournal(self.path),
                         policy=self.p,model_sha256=MODEL,lab_key=KEY)
    def admit(self,i=1,side="LONG",**kw):
        q=quote()
        return self.b.simulate_entry(proposal(i=i,side=side,pol=self.p,**kw),
                q,costs(),now_ms=AT)
    def test_P01_legacy_two_model_conflict_resolved_champion_only_lab(self):
        r=self.admit()
        self.assertEqual(r["status"],"SYNTHETIC_LAB_OPEN_NOT_PAPER")
        self.assertTrue(self.b.state.occupied)
        self.assertEqual(self.b.state.exchange_orders,0)

    def test_P02_explicit_true_owner_paper_release_not_available(self):
        with self.assertRaises(PaperHold):authorize_real_paper_release()
        with self.assertRaises(PaperHold):real_paper_entry()

    def test_P03_no_challenger_required_for_lab_while_no_real_release(self):
        self.assertNotIn("CHALLENGER",self.b.state.status)
        self.assertEqual(self.admit()["status"],"SYNTHETIC_LAB_OPEN_NOT_PAPER")

    def test_P04_unsigned_or_wrong_key_veto(self):
        q=quote();p=proposal(key=b"other secret separate key"*3)
        r=assess_lab_proposal(proposal=p,quote=q,costs=costs(),
           policy=self.p,known_model_sha256=MODEL,lab_key=KEY,now_ms=AT)
        self.assertIn("PROPOSAL_SIGNATURE_INVALID",r.reasons)

    def test_P05_tampered_proposal_signature_veto(self):
        p=replace(proposal(),stop="94")
        r=self.b.simulate_entry(p,quote(),costs(),now_ms=AT)
        self.assertEqual(r["status"],"LAB_VETO_NO_PAPER")

    def test_P06_forged_paper_or_real_authority_refused(self):
        for auth in ("PAPER","REAL"):
            with self.subTest(auth=auth):
                p=proposal(authority=auth)
                r=self.b.simulate_entry(p,quote(),costs(),now_ms=AT)
                self.assertIn("PAPER_OR_REAL_AUTHORITY_UNAVAILABLE",r["reasons"])

    def test_P07_lab_signer_refuses_real_keys_release(self):
        with self.assertRaises(PaperHold):
            sign_lab_proposal({"authority":"PAPER","grade":"SYNTHETIC_OFFLINE_TEST_ONLY","book":"CHAMPION_LAB_ONLY"},KEY)

    def test_P08_model_change_veto(self):
        r=self.b.simulate_entry(proposal(model="c"*64),quote(),costs(),now_ms=AT)
        self.assertIn("UNAPPROVED_OR_CHANGED_MODEL",r["reasons"])

    def test_P09_expired_clock_veto(self):
        r=self.b.simulate_entry(proposal(),quote(),costs(),now_ms=AT+6000)
        self.assertIn("PROPOSAL_STALE_OR_EXPIRED",r["reasons"])

    def test_P10_stale_quote_veto(self):
        r=self.b.simulate_entry(proposal(),quote(at=AT-1001),costs(),now_ms=AT)
        self.assertIn("QUOTE_STALE_OR_UNVERIFIED",r["reasons"])

    def test_P11_wide_crossed_spread_veto(self):
        r=self.b.simulate_entry(proposal(),quote(bid="105",ask="100"),costs(),now_ms=AT)
        self.assertIn("QUOTE_CROSSED_OR_WIDE",r["reasons"])

    def test_P12_missing_funding_cost_veto(self):
        r=self.b.simulate_entry(proposal(),quote(),
           costs(settled_through_ms=AT-1),now_ms=AT)
        self.assertIn("FEE_SLIPPAGE_FUNDING_UNVERIFIED",r["reasons"])

    def test_P13_nan_fees_and_zero_economic_default_rejected(self):
        r=self.b.simulate_entry(proposal(),quote(),
           costs(fee_rate="NaN"),now_ms=AT)
        self.assertIn("COST_NUMERIC_INVALID",r["reasons"])

    def test_P14_stop_target_geometry_veto(self):
        r=self.b.simulate_entry(proposal(stop="110"),quote(),costs(),now_ms=AT)
        self.assertIn("STOP_TARGET_RISK_GEOMETRY",r["reasons"])

    def test_P15_one_position_only_even_other_coin_side(self):
        self.admit()
        r=self.b.simulate_entry(proposal(i=2,side="SHORT"),
                                quote(),costs(),now_ms=AT)
        self.assertIn("ONE_POSITION_ALREADY_OCCUPIED",r["reasons"])

    def test_P16_duplicate_decision_after_settlement_rejected(self):
        self.admit()
        self.b.simulate_mark_or_exit(quote(at=AT+500,bid="105.2",ask="105.3"),
                    costs(at=AT+500),now_ms=AT+500)
        r=self.admit()
        self.assertIn("DECISION_REPLAY",r["reasons"])

    def test_P17_long_win_economics_bid_ask_fee_slip_funding(self):
        self.admit()
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="105.2",ask="105.3"),
              costs(at=AT+500),now_ms=AT+500)
        self.assertEqual(r["reason"],"TARGET")
        self.assertGreater(Decimal(r["net_quote"]),0)
        self.assertFalse(self.b.state.occupied)
        self.assertEqual(self.b.state.settled,1)
        self.assertEqual(Decimal(self.b.state.cash),
                         Decimal(self.p.capital)+Decimal(self.b.state.realized_net))

    def test_P18_short_target_correct_bid_ask_and_funding(self):
        self.admit(side="SHORT")
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="94.7",ask="94.8"),
                     costs(at=AT+500,funding_cash_quote="-0.02"),now_ms=AT+500)
        self.assertEqual(r["reason"],"TARGET")
        self.assertGreater(Decimal(r["net_quote"]),0)

    def test_P19_stop_loss_cash_and_fee_reconciliation(self):
        self.admit()
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="94.8",ask="94.9"),
                                costs(at=AT+500),now_ms=AT+500)
        self.assertEqual(r["reason"],"STOP")
        self.assertLess(Decimal(self.b.state.realized_net),0)
        self.assertGreater(Decimal(self.b.state.fees),0)

    def test_P20_no_touch_returns_occupied_without_extra_writes(self):
        self.admit()
        n=len(self.b._rows)
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="101",ask="101.1"),
              costs(at=AT+500),now_ms=AT+500)
        self.assertEqual(r["status"],"LAB_STILL_OCCUPIED")
        self.assertEqual(len(self.b._rows),n)

    def test_P21_trailing_long_only_tightens(self):
        self.admit()
        self.b.simulate_mark_or_exit(quote(at=AT+500,bid="101",ask="101.1"),
                costs(at=AT+500),now_ms=AT+500,trailing_stop="96")
        self.assertEqual(Decimal(self.b.state.position["stop"]),96)
        with self.assertRaises(PaperHold):
            self.b.simulate_mark_or_exit(quote(at=AT+600,bid="101",ask="101.1"),
                costs(at=AT+600),now_ms=AT+600,trailing_stop="95")

    def test_P22_trailing_short_only_tightens(self):
        self.admit(side="SHORT")
        self.b.simulate_mark_or_exit(quote(at=AT+500,bid="99",ask="99.1"),
                costs(at=AT+500),now_ms=AT+500,trailing_stop="104")
        self.assertEqual(Decimal(self.b.state.position["stop"]),104)
        with self.assertRaises(PaperHold):
            self.b.simulate_mark_or_exit(quote(at=AT+600,bid="99",ask="99.1"),
                costs(at=AT+600),now_ms=AT+600,trailing_stop="106")

    def test_P23_exit_checks_stop_before_same_tick_trailing(self):
        self.admit()
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="94.8",ask="94.9"),
            costs(at=AT+500),now_ms=AT+500,trailing_stop="99")
        self.assertEqual(r["reason"],"STOP")

    def test_P24_reopen_restart_holds_open_slot(self):
        self.admit()
        reboot=ChampionLabPaperBook(ResearchJournal(self.path),
               policy=self.p,model_sha256=MODEL,lab_key=KEY)
        self.assertTrue(reboot.restart_hold)
        self.assertTrue(reboot.state.occupied)
        with self.assertRaises(PaperHold):reboot.simulate_entry(proposal(i=2),quote(),costs(),now_ms=AT+2)
        with self.assertRaises(PaperHold):reboot.simulate_mark_or_exit(quote(),costs(),now_ms=AT+2)

    def test_P25_audited_restart_censor_no_fake_profit(self):
        self.admit()
        reboot=ChampionLabPaperBook(ResearchJournal(self.path),
                    policy=self.p,model_sha256=MODEL,lab_key=KEY)
        out=reboot.censor_held_lab(now_ms=AT+50,reason="UNCLEAN_RESTART")
        self.assertEqual(out["status"],"LAB_CENSORED_UNQUALIFIED")
        self.assertEqual(reboot.state.censored,1)
        self.assertEqual(reboot.state.settled,0)
        self.assertFalse(reboot.state.occupied)

    def test_P26_missing_exit_cost_holds_occupied(self):
        self.admit()
        r=self.b.simulate_mark_or_exit(quote(at=AT+500,bid="105.5",ask="105.6"),
              costs(at=AT+400),now_ms=AT+500)
        self.assertEqual(r["status"],"SOURCE_OR_COST_HOLD")
        self.assertTrue(self.b.state.occupied)
        self.assertEqual(self.b.state.settled,0)

    def test_P27_insecure_parent_permissions_journal_holds(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g9-insecure-") as tmp:
            p=Path(tmp)
            p.chmod(0o777)
            try:
                with self.assertRaises(JournalHold):ResearchJournal(p/"bad.jsonl").replay()
            finally:p.chmod(0o700)

    def test_P28_torn_journal_line_replay_fails_closed(self):
        self.admit()
        with self.path.open("ab") as f:f.write(b'{"bad":')
        with self.assertRaises(JournalHold):
            ChampionLabPaperBook(ResearchJournal(self.path),
                 policy=self.p,model_sha256=MODEL,lab_key=KEY)

    def test_P29_changed_source_model_policy_cannot_replay(self):
        self.admit()
        with self.assertRaises(PaperHold):
            ChampionLabPaperBook(ResearchJournal(self.path),
                policy=policy(capital="2000"),model_sha256=MODEL,lab_key=KEY)
        with self.assertRaises(PaperHold):
            ChampionLabPaperBook(ResearchJournal(self.path),
                policy=self.p,model_sha256="c"*64,lab_key=KEY)

    def test_P30_journal_concurrent_writer_fail_closed(self):
        self.admit()
        other=ChampionLabPaperBook(ResearchJournal(self.path),
                policy=self.p,model_sha256=MODEL,lab_key=KEY)
        self.b.simulate_mark_or_exit(quote(at=AT+100,bid="101",ask="101.1"),
                costs(at=AT+100),now_ms=AT+100,trailing_stop="96")
        with self.assertRaises((JournalHold,PaperHold)):
            other.censor_held_lab(now_ms=AT+200,reason="UNCLEAN_RESTART")

    def test_P31_policy_no_leverage_and_risk_relaxation(self):
        for p in (policy(max_positions=2),policy(max_exposure_multiple="2"),
                  policy(risk_fraction="0.05"),policy(max_drawdown_fraction="0.2"),
                  policy(mode="PAPER")):
            with self.subTest(p=p),self.assertRaises(PaperHold):p.validate()

    def test_P32_recovered_settled_lab_book_stays_locked(self):
        self.admit()
        self.b.simulate_mark_or_exit(quote(at=AT+100,bid="105.1",ask="105.2"),
                  costs(at=AT+100),now_ms=AT+100)
        again=ChampionLabPaperBook(ResearchJournal(self.path),
                    policy=self.p,model_sha256=MODEL,lab_key=KEY)
        self.assertEqual(again.state.settled,1)
        self.assertFalse(again.state.occupied)
        self.assertEqual(again.state.paper_authority,"NONE")

    def test_P33_quote_future_timestamp_never_accepted(self):
        r=self.b.simulate_entry(proposal(),quote(at=AT+1),costs(),now_ms=AT)
        self.assertIn("QUOTE_STALE_OR_UNVERIFIED",r["reasons"])

    def test_P35_missing_funding_start_date_veto(self):
        r=self.b.simulate_entry(proposal(),quote(),
                costs(funding_from_ms=None),now_ms=AT)
        self.assertIn("FEE_SLIPPAGE_FUNDING_UNVERIFIED",r["reasons"])

    def test_P36_late_funding_start_holds_exit_and_occupied(self):
        self.admit()
        r=self.b.simulate_mark_or_exit(
               quote(at=AT+500,bid="105.3",ask="105.4"),
               costs(at=AT+500,funding_from_ms=AT+1),now_ms=AT+500)
        self.assertEqual(r["status"],"SOURCE_OR_COST_HOLD")
        self.assertTrue(self.b.state.occupied)
        self.assertEqual(self.b.state.settled,0)
        self.assertTrue(self.b.restart_hold)

    def test_P34_no_automatic_champion_promotion_from_lab_model(self):
        self.assertEqual(self.b.state.status,"LAB_LOCKED_NO_PAPER_RELEASE")
        self.assertEqual(self.b.state.paper_authority,"NONE")
        self.assertEqual(self.b.state.financial_authority,"NONE")

if __name__=="__main__":unittest.main()
