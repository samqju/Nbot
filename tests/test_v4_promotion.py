import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot.observation.decision_ledger import DecisionLedger, FrozenDecision, MaturedOutcome
from nbot.observation.v4_generation import V4GenerationStore
from nbot.observation.v4_paper_contest import V4PaperReviewAdmin, V4PaperContest
from nbot.observation.v4_promotion import connect, digest

START = 1_790_000_000_000
HOUR = 3_600_000
NOW = START + 120 * HOUR


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.admin = V4PaperReviewAdmin(generation_path=root/'generations.db',
                                       contest_path=root/'contest.db', ledger_path=root/'ledger.db')
        self.store = self.admin.store
        self.generations = self.admin.generations
        self.ledger = DecisionLedger(root/'ledger.db')
        self.ledger.initialize()

    def generation(self, n):
        body = {'order_authority': 'NONE', 'trained_at_ms': START-1, 'generation': n}
        artifact = {**body, 'model_digest': digest(body)}
        qualification = 'BASELINE_READY' if n == 1 else 'CHALLENGER_READY'
        self.generations.save_generation(batch_no=n, artifact=artifact, training_rows=1000,
            training_events=40, validation_events=10, validation_mean=.2,
            validation_positive=.6, qualification=qualification, now_ms=START-1)
        return type('Model', (), {'model_digest': artifact['model_digest'], 'qualification': qualification})()

    def contest(self, head_to_head=False, generation=1):
        models = {1: self.generation(1)}
        if head_to_head or generation == 2:
            models[2] = self.generation(2)
        champ = 1 if head_to_head else None
        challenger = 2 if head_to_head else generation
        self.generations.set_state('champion_generation', champ)
        self.generations.set_state('challenger_generation', challenger)
        selected = {g: m for g, m in models.items() if g in {champ, challenger}}
        return self.store.ensure_contest(champion_generation=champ, challenger_generation=challenger,
                                         models=selected, now_ms=START), models

    def trades(self, contest_id, model, generation=1, *, count=100, returns=None,
               spacing=HOUR, sides=None, regimes=None, evidence=True):
        # Seed immutable production-shaped evidence in one transaction per DB.
        # Store lifecycle/counter behavior is tested separately in test_v4_paper_contest.
        with connect(self.store.path) as book, connect(self.ledger.path) as ledger:
            realized = peak = drawdown = 0.
            positive = 0
            for i in range(count):
                self._trade_fixture(book, ledger, contest_id, model, generation, i,
                                    returns, spacing, sides, regimes, evidence)
                net = returns(i) if returns else (-.2 if i % 4 == 0 else .4)
                realized += net
                peak = max(peak, realized)
                drawdown = max(drawdown, peak-realized)
                positive += net > 0
            book.execute("UPDATE contest_models SET completed_trades=?,positive_trades=?,realized_r=?,peak_realized_r=?,max_drawdown_r=?,status=? WHERE contest_id=? AND generation=?",
                         (count, positive, realized, peak, drawdown,
                          'REVIEW_REQUIRED' if count >= 100 else 'EXAMINING', contest_id, generation))
            if not book.execute('SELECT 1 FROM contest_models WHERE contest_id=? AND completed_trades<100', (contest_id,)).fetchone():
                book.execute("UPDATE contests SET status='REVIEW_REQUIRED' WHERE contest_id=?", (contest_id,))

    def _trade_fixture(self, book, ledger, contest_id, model, generation, i,
                       returns, spacing, sides, regimes, evidence):
        entry = START + i * spacing
        side = sides(i) if sides else ('LONG' if i % 2 == 0 else 'SHORT')
        vol = regimes(i) if regimes else (.1 if (i//2) % 2 == 0 else .9)
        vector = {'volatility_percentile': vol}
        net = returns(i) if returns else (-.2 if i % 4 == 0 else .4)
        key = f'{contest_id}-{generation}-{i}'
        extra = {'contest_id': contest_id, 'generation': generation, 'model_digest': model.model_digest,
                 'order_authority': 'NONE', 'feature_vector': vector,
                 'v4_paper_contract': 'NBOT_V4_PAPER_CONTEST_V1'}
        if evidence:
            decision = FrozenDecision(
                decision_id=key, event_id=f'event-{entry}', decision_time_ms=entry,
                symbol='BTCUSDT', side=side, setup_id='MODEL_ONLY', release_sha='test',
                model_id=f'V4_MODEL_GEN_{generation:03d}', feature_digest=digest(vector),
                ridge_score_r=None, ml_mean_r=1., ml_lower_r=None, conservative_score_r=1.,
                rank=1, runner_up_score_r=None, edge_gap_r=None, approved=True,
                reason='V4_PAPER_TOP1', bid=99., ask=100., quote_source='WSS_BOOK',
                policy_id='TICK_INTEGER_R_V1', sampling_probability=1., capacity_available=True)
            dp = {**asdict(decision), 'authority': 'RESEARCH_ONLY_NO_EXECUTION', 'extras': extra}
            ledger.execute('INSERT INTO frozen_decisions VALUES(?,?,?,?,?,?,?,?,?,?)',
                (key, decision.event_id, entry, 'BTCUSDT', side, 1, decision.reason,
                 decision.policy_id, json.dumps(dp, sort_keys=True, separators=(',', ':')), digest(dp)))
            outcome = MaturedOutcome(key, 'TICK_INTEGER_R_V1', entry+60_000,
                'AGGTRADE_RESOLVED', 'STOP', net, 1., -.2, f'source-{key}',
                evidence={'exit_time_ms': entry+60_000})
            op = {**asdict(outcome), 'authority': 'RESEARCH_ONLY_NO_EXECUTION'}
            ledger.execute('INSERT INTO matured_outcomes VALUES(?,?,?,?,?,?,?)',
                (key, outcome.policy_id, entry+60_000, outcome.quality, 0,
                 json.dumps(op, sort_keys=True, separators=(',', ':')), digest(op)))
        book.execute('INSERT INTO paper_trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                     (key, contest_id, generation, entry, 'BTCUSDT', side, entry,
                      100., 1., 'CLOSED', entry+60_000, net, 1., -.2, 'STOP', f'source-{key}'))

    def blocked(self, reason):
        before = self.generations.state()
        report = self.admin.promotion_status(now_ms=NOW)
        self.assertFalse(report['eligible'], report)
        self.assertTrue(any(reason in r for r in report['failed_checks']), report)
        with self.assertRaisesRegex(ValueError, 'GATES_FAILED|NOT_REVIEW_READY'):
            self.admin.promote_challenger(now_ms=NOW)
        self.assertEqual(self.generations.state(), before)
        self.assertIsNotNone(self.store.active_contest())
        return report

    def test_good_baseline_requires_explicit_promotion_and_audits_proof(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        self.assertTrue(self.admin.promotion_status(now_ms=NOW)['eligible'])
        self.assertIsNone(self.generations.state()['champion_generation'])
        result = self.admin.promote_challenger(now_ms=NOW)
        self.assertEqual(result['champion_generation'], 1)
        self.assertEqual(result['order_authority'], 'NONE')
        self.assertIsNone(self.store.active_contest())
        with connect(self.generations.path) as c:
            row = c.execute('SELECT report_json,applied FROM paper_review_outbox').fetchone()
        self.assertTrue(json.loads(row[0])['eligible'])
        self.assertEqual(row[1], 1)

    def test_profitable_gen2_can_be_first_champion(self):
        cid, models = self.contest(generation=2)
        self.trades(cid, models[2], 2)
        self.assertEqual(self.admin.promote_challenger(now_ms=NOW)['champion_generation'], 2)

    def test_losing_baseline_is_blocked_and_can_be_rejected(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: -.1)
        self.blocked('POSITIVE_EXPECTANCY')
        self.admin.reject_challenger(now_ms=NOW)
        self.assertIsNone(self.generations.state()['champion_generation'])
        self.assertIsNone(self.generations.state()['challenger_generation'])

    def test_99_trades_cannot_promote(self):
        cid, models = self.contest()
        self.trades(cid, models[1], count=99)
        self.blocked('NEEDS_100')

    def test_elapsed_time_cannot_be_manufactured_by_waiting_after_exam(self):
        cid, models = self.contest()
        self.trades(cid, models[1], spacing=300_000)
        self.blocked('FUTURE_TIME_COVERAGE')

    def test_long_only_is_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], sides=lambda i: 'LONG')
        self.blocked('SIDE_SUPPORT')

    def test_one_regime_is_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], regimes=lambda i: .5)
        self.blocked('REGIME_SUPPORT')

    def test_positive_but_too_small_edge_is_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: .09)
        self.blocked('POSITIVE_EXPECTANCY')

    def test_exact_mean_threshold_tolerates_floating_point_summation(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: .1)
        self.assertTrue(self.admin.promotion_status(now_ms=NOW)['eligible'])

    def test_low_positive_rate_is_blocked_despite_high_mean(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: 2. if i % 3 == 0 else -.1)
        self.blocked('POSITIVE_RATE')

    def test_second_half_losses_are_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: .5 if i < 50 else -.05)
        self.blocked('BOTH_HALVES_POSITIVE')

    def test_excessive_unscorable_paths_are_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        with connect(self.store.path) as c:
            for i in range(26):
                c.execute("INSERT INTO paper_trades(decision_id,contest_id,generation,event_open_ms,symbol,side,entry_time_ms,entry_price,one_r_price,status) VALUES(?,?,?,?,?,?,?,?,?,'UNSCORABLE')",
                          (f'gap-{i}', cid, 1, START, 'BTCUSDT', 'LONG', START, 100., 1.))
        self.blocked('CONTINUITY_SUPPORT')

    def test_open_position_prevents_review(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        self.store.open_trade(decision_id='open', contest_id=cid, generation=1,
            event_open_ms=START+101*HOUR, symbol='BTCUSDT', side='LONG',
            entry_time_ms=START+101*HOUR, entry_price=100., one_r_price=1.)
        self.assertIn('OPEN_PAPER_POSITIONS', self.admin.promotion_status(now_ms=NOW)['failed_checks'])
        with self.assertRaisesRegex(ValueError, 'OPEN_POSITIONS'):
            self.admin.promote_challenger(now_ms=NOW)

    def test_no_champion_waiting_queue_advances_after_rejection(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: -.1)
        self.generation(2)
        self.admin.reject_challenger(now_ms=NOW)
        runtime = V4PaperContest.__new__(V4PaperContest)
        runtime.generations, runtime.store = self.generations, self.store
        runtime._assign_waiting_challenger()
        self.assertEqual(self.generations.state(), {'champion_generation': None, 'challenger_generation': 2})

    def test_one_lucky_block_is_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: 20. if i == 50 else -.1)
        self.blocked('NOT_ONE_LUCKY_BLOCK')

    def test_tail_loss_is_blocked_even_with_positive_mean(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: -4. if i == 50 else .5)
        self.blocked('TAIL_LOSS_LIMIT')

    def test_drawdown_is_blocked(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: -.9 if 40 <= i < 55 else .6)
        self.blocked('DRAWDOWN_LIMIT')

    def test_losing_side_is_blocked_despite_total_profit(self):
        cid, models = self.contest()
        self.trades(cid, models[1], returns=lambda i: -.1 if i % 2 else .5)
        self.blocked('SIDE_SUPPORT')

    def test_missing_immutable_evidence_cannot_promote(self):
        cid, models = self.contest()
        self.trades(cid, models[1], evidence=False)
        self.blocked('EVIDENCE_INVALID')

    def test_status_is_recomputed_and_cannot_be_reused_after_tampering(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        self.assertTrue(self.admin.promotion_status(now_ms=NOW)['eligible'])
        with connect(self.store.path) as c:
            c.execute('UPDATE paper_trades SET net_r=100 WHERE decision_id=?', (f'{cid}-1-0',))
        self.blocked('EVIDENCE_INVALID')

    def test_artifact_or_incumbent_changes_fail_closed(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        with connect(self.generations.path) as c:
            c.execute("UPDATE generations SET artifact_digest='changed'")
        self.blocked('EVIDENCE_INVALID')

    def test_counter_only_checkpoint_cannot_promote(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        with connect(self.store.path) as c:
            c.execute('UPDATE contest_models SET realized_r=999')
        self.blocked('CACHED_COUNTERS_MISMATCH')

    def test_better_head_to_head_can_replace_champion(self):
        cid, models = self.contest(head_to_head=True)
        self.trades(cid, models[1], 1)
        self.trades(cid, models[2], 2, returns=lambda i: -.2 if i % 4 == 0 else .8)
        self.assertEqual(self.admin.promote_challenger(now_ms=NOW)['champion_generation'], 2)

    def test_tie_does_not_replace_champion(self):
        cid, models = self.contest(head_to_head=True)
        self.trades(cid, models[1], 1)
        self.trades(cid, models[2], 2)
        self.blocked('INSUFFICIENT_LIFT')

    def test_losing_less_than_champion_is_not_enough(self):
        cid, models = self.contest(head_to_head=True)
        self.trades(cid, models[1], 1, returns=lambda i: -.2)
        self.trades(cid, models[2], 2, returns=lambda i: -.1)
        self.blocked('POSITIVE_EXPECTANCY')

    def test_higher_average_with_worse_tail_does_not_replace_champion(self):
        cid, models = self.contest(head_to_head=True)
        self.trades(cid, models[1], 1)
        self.trades(cid, models[2], 2, returns=lambda i: -.3 if i % 4 == 0 else .8)
        self.blocked('RISK_WORSE_THAN_CHAMPION')

    def test_changed_generation_state_blocks_even_a_previously_good_report(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        self.generations.set_state('champion_generation', 9)
        with self.assertRaisesRegex(ValueError, 'GENERATION_STATE_CHANGED'):
            self.admin.promote_challenger(now_ms=NOW)
        self.assertEqual(self.generations.state()['champion_generation'], 9)

    def test_low_level_store_cannot_bypass_promotion_gates(self):
        cid, _ = self.contest()
        with self.assertRaisesRegex(ValueError, 'GATED_REVIEW_ADMIN'):
            self.store.finish_review(cid, decision='PROMOTE', now_ms=NOW)

    def test_review_crash_recovers_before_queue_and_blocks_training_slot(self):
        cid, models = self.contest()
        self.trades(cid, models[1])
        # Fail the acknowledgement after the authoritative state/audit commit.
        original = self.admin.recover_reviews
        with patch.object(self.admin, 'recover_reviews', side_effect=[None, RuntimeError('crash')]):
            with self.assertRaisesRegex(RuntimeError, 'crash'):
                self.admin.promote_challenger(now_ms=NOW)
        self.assertEqual(self.generations.state()['champion_generation'], 1)
        self.assertFalse(self.generations.assign_challenger_if_empty(2))
        # Simulate the earlier crash boundary, before the contest DB closure.
        with connect(self.store.path) as c:
            c.execute("UPDATE contests SET status='REVIEW_REQUIRED',review_decision=NULL,closed_at_ms=NULL")
        original()
        original()
        self.assertIsNone(self.store.active_contest())
        self.assertTrue(self.generations.assign_challenger_if_empty(2))

    def test_failure_between_database_commits_is_recovered(self):
        cid, models = self.contest()
        self.trades(cid, models[1])

        class FailedContestCommit(sqlite3.Connection):
            def commit(self):
                raise RuntimeError('contest commit interrupted')

        def fault_connect(path, **kwargs):
            if path == self.store.path:
                kwargs['factory'] = FailedContestCommit
            return connect(path, **kwargs)

        with patch('nbot.observation.v4_paper_contest.connect', side_effect=fault_connect):
            with self.assertRaisesRegex(RuntimeError, 'contest commit interrupted'):
                self.admin.promote_challenger(now_ms=NOW)
        self.assertEqual(self.generations.state()['champion_generation'], 1)
        self.assertEqual(self.store.active_contest()['status'], 'REVIEW_REQUIRED')
        self.assertFalse(self.generations.assign_challenger_if_empty(2))
        self.admin.recover_reviews()
        self.assertIsNone(self.store.active_contest())


if __name__ == '__main__':
    unittest.main()
