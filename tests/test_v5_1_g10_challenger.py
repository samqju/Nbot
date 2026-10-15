"""G10 two independent frozen LAB paper books, fair comparison, NO promotion."""
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot_v5_1.paper_contract import (
    PaperPolicy,PaperHold,PaperQuote,PaperCosts,SignedLabProposal,
    sign_lab_proposal,proposal_body)
from nbot_v5_1.paper_lab import ChampionLabPaperBook
from nbot_v5_1.research_journal import ResearchJournal,JournalHold
from nbot_v5_1.challenger_lab import (
    LabChallengerCohort,CompetitionProtocol,SharedLabEvent,
    DualBookCompetition,CHAMPION,CHALLENGER,
    authorize_challenger_paper,approve_model_promotion)
from test_v5_1_g9_paper import policy as base_policy,quote,costs,AT,H,KEY,MODEL

# Deliberately distinct frozen LAB model and HMAC keys, never production keys.
OTHER="c"*64
K2=b"isolated G10 challenger laboratory signer "*2
T=AT+20000000

def identity(i):return hashlib.sha256(f"g10-event-{i}".encode()).hexdigest()


def cohort(**kw):
    params=dict(sample_count=2000,effective_btc_blocks=100,
        first_ms=T-30000000,last_ms=T-4000000,
        evidence_sha256="d"*64)
    params.update(kw)
    return LabChallengerCohort(**params)


def protocol(p=None,co=None,**kw):
    p=p or base_policy();co=co or cohort()
    params=dict(champion_sha256=MODEL,challenger_sha256=OTHER,
        policy_sha256=p.digest(),cohort_sha256=co.evidence_sha256,
        frozen_at_ms=T-2000000,start_ms=T,end_ms=T+150000000)
    params.update(kw)
    return CompetitionProtocol(**params)


def signed(book,idx,when,*,p=None,key=None,model=None,source=H,side="LONG"):
    p=p or base_policy()
    key=KEY if book==CHAMPION else K2 if key is None else key
    model=(MODEL if book==CHAMPION else OTHER) if model is None else model
    body=dict(decision_id=identity(idx*7+(0 if book==CHAMPION else 1)),
        model_sha256=model,at_ms=when,expires_ms=when+4000,
        symbol="BTCUSDT",side=side,
        stop="95" if side=="LONG" else "105",
        target="105" if side=="LONG" else "95",
        lower_net_r=".8",source_sha256=source,
        policy_sha256=p.digest(),
        idempotency_sha256=identity(idx*7+2),
        book=book,grade="SYNTHETIC_OFFLINE_TEST_ONLY",authority="NONE")
    return SignedLabProposal(**body,signature=sign_lab_proposal(body,key))


def market(i,*,champ=True,chall=True,source=H,quote_change=None,p=None):
    p=p or base_policy()
    when=T+i*300000
    opening=i%2==0
    q=(quote(at=when) if opening
       else quote(at=when,bid="105.2",ask="105.3"))
    if quote_change:q=quote_change(q)
    return SharedLabEvent(identity(i),when,
          "UP" if i%4 else "DOWN",
          "RANGE" if i%3 else "TRANSITION",
          q,costs(at=when),
          signed(CHAMPION,i,when,p=p,source=source) if opening and champ else None,
          signed(CHALLENGER,i,when,p=p,source=source) if opening and chall else None)


class G10Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="nbot-g10-test-")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.p=base_policy()
        self.co=cohort()
        self.pt=protocol(self.p,self.co)
        self.j1=ResearchJournal(self.base/"champion.jsonl")
        self.j2=ResearchJournal(self.base/"challenger.jsonl")
        self.j3=ResearchJournal(self.base/"common.jsonl")
        self.engine=DualBookCompetition(champion_journal=self.j1,
              challenger_journal=self.j2,review_journal=self.j3,
              policy=self.p,cohort=self.co,protocol=self.pt,
              champion_key=KEY,challenger_key=K2)

    def test_C01_two_isolated_books_one_shared_market_event(self):
        x=self.engine.step(market(0))
        self.assertTrue(x.champion_occupied)
        self.assertTrue(x.challenger_occupied)
        self.assertNotEqual(self.engine.books[CHAMPION].journal.path,
                            self.engine.books[CHALLENGER].journal.path)
        self.assertEqual(self.engine.books[CHAMPION].state.paper_authority,"NONE")

    def test_C02_distinct_signed_id_and_model_per_book(self):
        x=self.engine.step(market(0))
        a=self.engine.books[CHAMPION].state.position
        b=self.engine.books[CHALLENGER].state.position
        self.assertNotEqual(a["model_sha256"],b["model_sha256"])
        self.assertNotEqual(a["decision_id"],b["decision_id"])

    def test_C03_challenger_cannot_use_champion_key(self):
        candidate=signed(CHALLENGER,0,T,key=KEY)
        x=replace(market(0),challenger=candidate)
        out=self.engine.step(x)
        self.assertEqual(out.challenger_result,"LAB_VETO_NO_PAPER")
        self.assertEqual(out.champion_result,"SYNTHETIC_LAB_OPEN_NOT_PAPER")

    def test_C04_no_paper_release_or_champion_promotion(self):
        with self.assertRaises(PaperHold):authorize_challenger_paper()
        with self.assertRaises(PaperHold):approve_model_promotion()

    def test_C05_original_grade_cohort_claim_is_denied(self):
        with self.assertRaises(PaperHold):
            cohort(source_grade="ORIGINAL_VERIFIED").validate()

    def test_C06_forged_independent_new_2000_rejected(self):
        with self.assertRaises(PaperHold):
            cohort(independently_original_qualified=2000).validate()

    def test_C07_insufficient_further_lab_cohort_denied(self):
        with self.assertRaises(PaperHold):cohort(sample_count=1999).validate()

    def test_C08_100_btc_dependence_not_2000_independent(self):
        self.assertEqual(self.co.sample_count,2000)
        self.assertEqual(self.co.effective_btc_blocks,100)
        self.assertEqual(self.co.independently_original_qualified,0)

    def test_C09_model_same_sha_for_champion_challenger_denied(self):
        with self.assertRaises(PaperHold):
            protocol(challenger_sha256=MODEL).validate(self.p,self.co)

    def test_C10_source_digest_swap_denied(self):
        with self.assertRaises(PaperHold):
            protocol(cohort_sha256="e"*64).validate(self.p,self.co)

    def test_C11_predeclared_after_cohort_and_before_paper_window(self):
        with self.assertRaises(PaperHold):
            protocol(frozen_at_ms=T-5000000).validate(self.p,self.co)
        with self.assertRaises(PaperHold):
            protocol(frozen_at_ms=T+1).validate(self.p,self.co)

    def test_C12_two_independent_keys_required(self):
        with self.assertRaises(PaperHold):
            DualBookCompetition(champion_journal=self.j1,challenger_journal=self.j2,
                review_journal=self.j3,policy=self.p,cohort=self.co,protocol=self.pt,
                champion_key=KEY,challenger_key=KEY)

    def test_C13_one_paper_file_cannot_back_two_books(self):
        with self.assertRaises(PaperHold):
            DualBookCompetition(champion_journal=self.j1,challenger_journal=self.j1,
                review_journal=self.j3,policy=self.p,cohort=self.co,protocol=self.pt,
                champion_key=KEY,challenger_key=K2)

    def test_C14_different_equity_ledger_after_abstention(self):
        self.engine.step(market(0,chall=False))
        self.engine.step(market(1,champ=False,chall=False))
        self.assertGreater(
           float(self.engine.books[CHAMPION].state.cash),
           float(self.engine.books[CHALLENGER].state.cash))
        self.assertEqual(self.engine.books[CHALLENGER].state.settled,0)

    def test_C15_common_feed_same_quote_cost_for_both(self):
        self.engine.step(market(0))
        a=self.engine.books[CHAMPION].state.position
        b=self.engine.books[CHALLENGER].state.position
        self.assertEqual(a["quote_sha256"],b["quote_sha256"])
        self.assertEqual(a["cost_sha256"],b["cost_sha256"])

    def test_C16_abstentions_not_forced_into_fake_fill(self):
        self.engine.step(market(0,champ=False,chall=False))
        q=self.engine.review()
        self.assertEqual(q.champion_abstained,1)
        self.assertEqual(q.challenger_abstained,1)
        self.assertEqual(q.action,"HOLD")

    def test_C17_bad_challenger_model_source_denied(self):
        x=market(0)
        bad=replace(x.challenger,source_sha256="f"*64)
        with self.assertRaises(PaperHold):
            self.engine.step(replace(x,challenger=bad))

    def test_C18_nonmonotone_common_clock_denied(self):
        self.engine.step(market(0))
        with self.assertRaises(PaperHold):self.engine.step(market(0))

    def test_C19_outside_fixed_window_denied(self):
        x=market(0)
        with self.assertRaises(PaperHold):
            self.engine.step(replace(x,at_ms=self.pt.end_ms))

    def test_C20_malformed_original_quote_claim_denied(self):
        x=market(0)
        with self.assertRaises(PaperHold):
            self.engine.step(replace(x,quote=replace(x.quote,original_verified=True)))

    def test_C21_partial_source_funding_time_denied(self):
        x=market(0)
        with self.assertRaises(PaperHold):
            self.engine.step(replace(x,costs=replace(x.costs,funding_from_ms=T+1)))

    def test_C22_paper_release_permission_denied_by_protocol(self):
        with self.assertRaises(PaperHold):
            protocol(paper_release_authority="PAPER").validate(self.p,self.co)
        with self.assertRaises(PaperHold):
            protocol(route_change_authority="REAL").validate(self.p,self.co)

    def test_C23_no_scientific_promotion_even_good_lab_stats(self):
        for i in range(12):
            self.engine.step(market(i))
        review=self.engine.review()
        self.assertEqual(review.action,"HOLD")
        self.assertFalse(review.scientific_challenger_approved)
        self.assertEqual(review.independent_original_outcomes,0)
        self.assertEqual(review.genuine_paper_settlements,0)

    def test_C24_review_matches_actual_frozen_champion_identity(self):
        self.engine.step(market(0))
        self.assertEqual(self.engine.review().active_champion_sha256,MODEL)

    def test_C25_restart_with_active_both_is_locked(self):
        self.engine.step(market(0))
        reboot=DualBookCompetition(champion_journal=ResearchJournal(self.j1.path),
                challenger_journal=ResearchJournal(self.j2.path),
                review_journal=ResearchJournal(self.j3.path),policy=self.p,
                cohort=self.co,protocol=self.pt,champion_key=KEY,challenger_key=K2)
        self.assertTrue(reboot.restarted)
        self.assertTrue(reboot.books[CHAMPION].state.occupied)
        self.assertTrue(reboot.books[CHALLENGER].state.occupied)
        with self.assertRaises(PaperHold):reboot.step(market(1))

    def test_C26_restart_after_closed_books_still_no_automatic_contest(self):
        self.engine.step(market(0))
        self.engine.step(market(1))
        reboot=DualBookCompetition(champion_journal=ResearchJournal(self.j1.path),
                challenger_journal=ResearchJournal(self.j2.path),
                review_journal=ResearchJournal(self.j3.path),policy=self.p,
                cohort=self.co,protocol=self.pt,champion_key=KEY,challenger_key=K2)
        self.assertTrue(reboot.restarted)
        self.assertEqual(reboot.books[CHAMPION].state.settled,1)
        self.assertEqual(reboot.books[CHALLENGER].state.settled,1)

    def test_C27_shared_receipt_torn_record_fails_closed(self):
        self.engine.step(market(0))
        with self.j3.path.open("ab") as f:f.write(b"{bad")
        with self.assertRaises(JournalHold):
            DualBookCompetition(champion_journal=ResearchJournal(self.j1.path),
              challenger_journal=ResearchJournal(self.j2.path),
              review_journal=ResearchJournal(self.j3.path),policy=self.p,
              cohort=self.co,protocol=self.pt,champion_key=KEY,challenger_key=K2)

    def test_C28_sidebook_wrong_model_replay_deny(self):
        self.engine.step(market(0))
        p=replace(self.pt,champion_sha256="e"*64)
        with self.assertRaises(PaperHold):
            DualBookCompetition(champion_journal=ResearchJournal(self.j1.path),
              challenger_journal=ResearchJournal(self.j2.path),
              review_journal=ResearchJournal(self.j3.path),policy=self.p,
              cohort=self.co,protocol=p,champion_key=KEY,challenger_key=K2)

    def test_C29_guardian_second_entry_veto_per_book(self):
        self.engine.step(market(0))
        # shared event with positions still occupied; new attempts must be vetoed.
        x=market(1)
        # quote unchanged so neither stop nor target can be hit
        q=quote(at=x.at_ms)
        x=replace(x,quote=q,champion=signed(CHAMPION,1,x.at_ms),
                         challenger=signed(CHALLENGER,1,x.at_ms))
        out=self.engine.step(x)
        self.assertEqual(out.champion_result,"LAB_VETO_NO_PAPER")
        self.assertEqual(out.challenger_result,"LAB_VETO_NO_PAPER")

    def test_C30_missing_models_do_not_force_competition(self):
        x=market(0,champ=False,chall=False)
        self.engine.step(x)
        self.assertEqual(self.engine.review().common_events,1)
        self.assertEqual(self.engine.review().laboratory_diagnostic,"LAB_HOLD")

    def test_C31_policy_separate_risk_mismatch_refused(self):
        with self.assertRaises(PaperHold):
            protocol(policy_sha256="f"*64).validate(self.p,self.co)

    def test_C32_paper_settlement_100_target_not_lab_qualification(self):
        self.assertEqual(self.pt.minimum_paper_settled_per_model,100)
        self.assertEqual(self.engine.review().genuine_paper_settlements,0)

    def test_C33_comparison_cannot_require_forced_loser_entries(self):
        for i in range(14):
            self.engine.step(market(i,chall=False))
        r=self.engine.review()
        self.assertGreater(r.challenger_abstained,0)
        self.assertEqual(r.action,"HOLD")

    def test_C34_fault_in_one_book_does_not_mix_balances(self):
        self.engine.step(market(0))
        a=self.engine.books[CHAMPION].state.cash
        b=self.engine.books[CHALLENGER].state.cash
        self.assertEqual(a,b)
        with self.assertRaises(JournalHold):
            self.engine.books[CHALLENGER].journal.append(
                 "ADMIT",T+1,{},expected_head="f"*64)
        self.assertEqual(self.engine.books[CHAMPION].state.cash,a)

    def test_C35_deceptive_unapproved_favorable_lab_challenger_still_HOLD(self):
        for i in range(18):
            self.engine.step(market(i,champ=(i%4!=0),chall=True))
        r=self.engine.review()
        self.assertEqual(r.action,"HOLD")
        self.assertEqual(r.financial_authority,"NONE")
        self.assertFalse(r.fair_real_paper_comparison)

    def test_C36_wrong_context_window_or_cohort_time_holds(self):
        with self.assertRaises(PaperHold):
            protocol(minimum_common_market_events=10).validate(self.p,self.co)
        with self.assertRaises(PaperHold):
            cohort(first_ms=T,last_ms=T-1).validate()

if __name__=="__main__":
    unittest.main()
