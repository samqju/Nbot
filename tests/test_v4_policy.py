from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot.observation.v4_policy import training_schedule
from nbot.observation.v4_generation import V4GenerationTrainer
from nbot.observation.v4_paper_contest import V4PaperContestStore
from nbot.observation.v4_promotion import connect
from tests import test_v4_promotion as fixture


class CadenceTests(unittest.TestCase):
    def test_generation_four_needs_five_thousand_additional_outcomes(self):
        self.assertEqual(training_schedule(2,2)['next_training_at'],3000)
        self.assertEqual(training_schedule(3,3,resolved=7999)['remaining_outcomes'],1)
        self.assertEqual(training_schedule(3,3,resolved=8000)['remaining_outcomes'],0)
        self.assertEqual(training_schedule(3,3)['next_training_at'],8000)
        self.assertEqual(training_schedule(4,8)['next_training_at'],13000)
        self.assertEqual(training_schedule(5,13)['next_training_at'],18000)

    def test_no_catchup_training_at_intermediate_old_batch_windows(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            trainer=V4GenerationTrainer(ledger_path=root/'absent.db',
                research_meta_path=root/'meta.db',generation_path=root/'generations.db')
            for n in (1,2,3):
                trainer.store.save_generation(batch_no=n,artifact={'n':n},training_rows=100,
                    training_events=40,validation_events=10,validation_mean=.2,
                    validation_positive=.6,qualification='CHALLENGER_READY',now_ms=n)
            with connect(root/'meta.db') as c:
                c.execute('CREATE TABLE v4_batches(batch_no INTEGER,status TEXT)')
                c.executemany('INSERT INTO v4_batches VALUES(?,?)',[(n,'READY_FOR_TRAINING') for n in range(1,8)])
            self.assertEqual(trainer.ready_batches(),[])
            self.assertEqual(trainer.train_next()['next_training_at'],8000)
            with connect(root/'meta.db') as c:
                c.executemany('INSERT INTO v4_batches VALUES(?,?)',[(n,'READY_FOR_TRAINING') for n in (8,9,10,11,12)])
            self.assertEqual(trainer.ready_batches(),[8])
            with patch('nbot.observation.v4_generation.load_rows',return_value=[]) as loader:
                trainer.train_next()
                loader.assert_called_once_with(root/'absent.db',through_outcome=8000)
            trainer.store.save_generation(batch_no=8,artifact={'n':4},training_rows=100,
                training_events=40,validation_events=10,validation_mean=.2,
                validation_positive=.6,qualification='CHALLENGER_READY',now_ms=4)
            self.assertEqual(trainer.ready_batches(),[])
            self.assertEqual(trainer.status()['next_training_at'],13000)

    def test_existing_generation_history_is_not_rewritten(self):
        # If Gen-4 already existed at activation, wait 5,000 beyond its actual cutoff.
        self.assertEqual(training_schedule(4,4)['next_training_at'],9000)


class ContestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.PromotionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_new_head_to_head_defaults_to_fifty_baseline_remains_hundred(self):
        models={1:self.fixture.generation(1),2:self.fixture.generation(2)}
        cid=self.fixture.store.ensure_contest(champion_generation=1,challenger_generation=2,
            models=models,now_ms=fixture.START)
        self.assertEqual(self.fixture.store.active_contest()['checkpoint_trades'],50)
        self.assertEqual(self.fixture.store.status()['models'][0]['remaining_to_checkpoint'],50)

    def test_legacy_migration_preserves_one_hundred_checkpoint(self):
        cid,_=self.fixture.contest(head_to_head=True)
        with connect(self.fixture.store.path) as c:
            c.execute('ALTER TABLE contests DROP COLUMN checkpoint_trades')
        self.fixture.store.initialize()
        self.assertEqual(self.fixture.store.active_contest()['checkpoint_trades'],100)
        self.fixture.store.initialize()
        self.assertEqual(self.fixture.store.active_contest()['checkpoint_trades'],100)

    def test_real_book_reaches_review_only_when_both_models_close_fifty(self):
        cid,_=self.fixture.contest(head_to_head=True,checkpoint=50)
        for generation in (1,2):
            for i in range(50):
                key=f'book-{generation}-{i}'
                self.fixture.store.open_trade(decision_id=key,contest_id=cid,generation=generation,
                    event_open_ms=i*300000,symbol='BTCUSDT',side='LONG',entry_time_ms=i*300000+1,
                    entry_price=100.,one_r_price=1.)
                self.fixture.store.close_trade(key,net_r=.2,mfe_r=.3,mae_r=-.1,
                    exit_time_ms=i*300000+2,exit_reason='STOP',source_digest=key)
            expected='ACTIVE' if generation==1 else 'REVIEW_REQUIRED'
            self.assertEqual(self.fixture.store.active_contest()['status'],expected)
        self.assertEqual([m['completed_trades'] for m in self.fixture.store.status()['models']],[50,50])

    def test_fifty_fresh_trades_each_can_pass_unweakened_economic_gates(self):
        cid,models=self.fixture.contest(head_to_head=True,checkpoint=50)
        self.fixture.trades(cid,models[1],count=50,returns=lambda _: .1,spacing=2*fixture.HOUR)
        self.fixture.trades(cid,models[2],generation=2,count=50,returns=lambda _: .4,spacing=2*fixture.HOUR)
        result=self.fixture.admin.promotion_status(now_ms=fixture.NOW)
        self.assertTrue(result['eligible'],result['failed_checks'])
        self.assertEqual(result['policy']['checkpoint_trades'],50)
        self.assertEqual(self.fixture.admin.promote_challenger(now_ms=fixture.NOW)['champion_generation'],2)

    def test_49_trades_cannot_promote_new_head_to_head(self):
        cid,models=self.fixture.contest(head_to_head=True,checkpoint=50)
        self.fixture.trades(cid,models[1],count=50,returns=lambda _: .1,spacing=2*fixture.HOUR)
        self.fixture.trades(cid,models[2],generation=2,count=49,returns=lambda _: .4,spacing=2*fixture.HOUR)
        result=self.fixture.admin.promotion_status(now_ms=fixture.NOW)
        self.assertFalse(result['eligible'])
        self.assertIn('CHALLENGER:NEEDS_50_SCORED_TRADES',result['failed_checks'])
