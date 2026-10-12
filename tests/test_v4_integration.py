import json
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from nbot.observation.v4_operator import V4PaperOperator
from nbot.observation.v4_paper_contest import V4PaperContestStore
from nbot.observation.v4_recommendation import V4ChampionSource
from nbot.observation.v4_promotion import connect, digest
from nbot.communication.server import ObservationControlServer
from nbot.communication.client import RemoteObservationClient
from nbot.operator.execution import ExecutionOperatorSurface
from nbot.operator.telegram import TelegramClient, TelegramConfig
from tests import test_v4_promotion as fixtures
from tests.communication.test_v35_control_target import database, seed_event, NOW, SHA
from tests.test_v386_operator_observability import FakeWorker


class V4IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PromotionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.temp.name)
        self.operator = V4PaperOperator(self.root)
        self.operator.base = self.root

    def passing(self):
        contest, models = self.fixture.contest()
        self.fixture.trades(contest, models[1])
        # Production default filenames.
        self.operator.base = self.root/'data/observation/v4'
        self.operator.base.mkdir(parents=True)
        for old, new in [('contest.db','paper_contest.db'), ('ledger.db','paper_ledger.db'), ('generations.db','generations.db')]:
            with connect(self.root/old) as source, connect(self.operator.base/new) as dest:
                source.backup(dest)
        return contest

    def stage_unfinished_exam(self, *, head_to_head=False):
        contest, _ = self.fixture.contest(head_to_head=head_to_head)
        self.operator.base = self.root / 'data/observation/v4'
        self.operator.base.mkdir(parents=True)
        for old, new in [('contest.db', 'paper_contest.db'),
                         ('ledger.db', 'paper_ledger.db'),
                         ('generations.db', 'generations.db')]:
            with connect(self.root / old) as source, connect(self.operator.base / new) as dest:
                source.backup(dest)
        return contest, V4PaperContestStore(self.operator.base / 'paper_contest.db')

    def test_champion_status_shows_open_next_paper_trade_and_elapsed(self):
        contest, store = self.stage_unfinished_exam()
        entry_ms = fixtures.NOW - (75 * 60_000)
        store.open_trade(decision_id='unsettled-13', contest_id=contest,
            generation=1, event_open_ms=entry_ms - 1,
            symbol='CFXUSDT', side='LONG', entry_time_ms=entry_ms,
            entry_price=0.1, one_r_price=0.001)
        with patch('nbot.observation.v4_operator.time.time',
                   return_value=fixtures.NOW / 1000):
            result = self.operator.status()
        body = result['telegram_body']
        self.assertIn('Gen-1 CHALLENGER: 0/100 scored', body)
        self.assertIn('CFXUSDT LONG OPEN', body)
        self.assertIn('elapsed 1h 15m', body)
        self.assertIn('entry ', body)
        self.assertEqual(result['document']['open_positions'][0]['symbol'], 'CFXUSDT')
        self.assertEqual(result['order_authority'], 'NONE')
        self.assertEqual(store.contest_model_status(contest, 1)['completed_trades'], 0)

    def test_champion_status_says_none_when_no_paper_position(self):
        self.stage_unfinished_exam()
        result = self.operator.status()
        self.assertIn('Gen-1 CHALLENGER: none open', result['telegram_body'])
        self.assertEqual(result['document']['open_positions'], [])

    def test_champion_status_lists_both_open_head_to_head_models(self):
        contest, store = self.stage_unfinished_exam(head_to_head=True)
        for generation, symbol, side in (
            (1, 'BTCUSDT', 'SHORT'), (2, 'ETHUSDT', 'LONG')
        ):
            store.open_trade(decision_id=f'open-{generation}',
                contest_id=contest, generation=generation, event_open_ms=300_000,
                symbol=symbol, side=side, entry_time_ms=fixtures.NOW-90_000,
                entry_price=100, one_r_price=1)
        with patch('nbot.observation.v4_operator.time.time',
                   return_value=fixtures.NOW / 1000):
            result = self.operator.status()
        self.assertIn('Gen-1 CHAMPION: BTCUSDT SHORT OPEN', result['telegram_body'])
        self.assertIn('Gen-2 CHALLENGER: ETHUSDT LONG OPEN', result['telegram_body'])
        self.assertEqual(len(result['document']['open_positions']), 2)

    def test_status_is_read_only_and_gives_exact_commands(self):
        contest = self.passing()
        result = self.operator.status()
        self.assertTrue(result['document']['review_ready'])
        self.assertIn(f'/champion approve {contest} 1', result['telegram_body'])
        self.assertIn(f'/champion reject {contest} 1', result['telegram_body'])
        self.assertEqual(self.operator.status()['document']['contest']['status'], 'REVIEW_REQUIRED')

    def test_stale_approval_does_not_promote(self):
        contest = self.passing()
        with self.assertRaisesRegex(ValueError, 'STALE_APPROVAL'):
            self.operator.review({'action':'approve', 'contest_id':contest+1, 'generation':1})
        self.assertEqual(self.operator.status()['document']['contest']['status'], 'REVIEW_REQUIRED')

    def test_telegram_approval_rechecks_gates(self):
        contest = self.passing()
        with connect(self.operator.base/'paper_contest.db') as c:
            c.execute("UPDATE contest_models SET completed_trades=101")
        with self.assertRaisesRegex(ValueError, 'GATES_FAILED'):
            self.operator.review({'action':'approve', 'contest_id':contest, 'generation':1})

    def test_duplicate_approval_cannot_affect_next_contest(self):
        contest = self.passing()
        command = {'action':'approve', 'contest_id':contest, 'generation':1}
        self.assertEqual(self.operator.review(command)['champion_generation'], 1)
        with self.assertRaisesRegex(ValueError, 'NOT_REVIEW_READY'):
            self.operator.review(command)

    def source(self):
        db = database(self.root, 'live-paper')
        seed_event(db)
        return V4ChampionSource(db, release_sha=SHA, repo_root=self.root), db

    def test_no_champion_never_falls_back_to_legacy(self):
        source, _ = self.source()
        result = source.refresh(now_ms=NOW, ttl_ms=30000)
        self.assertIsNone(result.proposal)
        self.assertEqual(result.reason, 'V4_WAIT_FOR_APPROVED_PAPER_CHAMPION')

    def test_v4_cannot_run_in_real_money_profile(self):
        db = database(self.root, 'live-paper')
        with self.assertRaisesRegex(ValueError, 'PAPER_ONLY'):
            V4ChampionSource(db, release_sha=SHA, repo_root=self.root, profile_name='live-trade')

    def test_approved_champion_proposal_frozen_once_per_event_and_expires(self):
        contest = self.passing()
        self.operator.review({'action':'approve','contest_id':contest,'generation':1})
        source, db = self.source()
        candidate = SimpleNamespace(symbol='BTCUSDT', side='LONG', vector={'x':1})
        source.scanner.scan = Mock(return_value=[candidate])
        fake_model = Mock()
        fake_model.score.return_value = .25
        with patch('nbot.observation.v4_paper_contest.FrozenGenerationModel', return_value=fake_model):
            first = source.refresh(now_ms=NOW, ttl_ms=30000)
            second = source.refresh(now_ms=NOW+5000, ttl_ms=30000)
        self.assertIsNotNone(first.proposal)
        self.assertEqual(first.proposal.to_dict(), second.proposal.to_dict())
        source.scanner.scan.assert_called_once()
        self.assertEqual(first.proposal.experiment_context['v4_generation'], 1)
        self.assertEqual(first.proposal.profile, 'live-paper')
        self.assertIsNone(source.refresh(now_ms=NOW+30001, ttl_ms=30000).proposal)

    def test_negative_v4_rank_score_still_proposes_and_is_not_expected_r(self):
        contest = self.passing()
        self.operator.review({'action':'approve','contest_id':contest,'generation':1})
        source, _ = self.source()
        candidate = SimpleNamespace(symbol='BTCUSDT', side='LONG', vector={'x':1})
        source.scanner.scan = Mock(return_value=[candidate])
        fake_model = Mock()
        fake_model.score.return_value = -.25
        with patch('nbot.observation.v4_paper_contest.FrozenGenerationModel', return_value=fake_model):
            result = source.refresh(now_ms=NOW, ttl_ms=30000)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(result.proposal.selection_score, -.25)
        self.assertIsNone(result.proposal.expected_after_cost_net_r)
        self.assertEqual(result.proposal.experiment_context['selection_score_kind'],
                         'LIGHTGBM_LAMBDARANK_UNCALIBRATED')
        self.assertFalse(result.proposal.experiment_context['expected_r_calibrated'])

    def test_tampered_approved_model_fails_closed(self):
        contest = self.passing()
        self.operator.review({'action':'approve','contest_id':contest,'generation':1})
        source, _ = self.source()
        with connect(self.operator.base/'generations.db') as c:
            c.execute("UPDATE generations SET artifact_digest='tampered'")
        with self.assertRaisesRegex(ValueError, 'CORRUPT'):
            source.refresh(now_ms=NOW, ttl_ms=30000)

    def test_telegram_notifies_once_and_never_auto_promotes(self):
        contest = self.passing()
        telegram = TelegramClient(TelegramConfig('test', '123', '456', 1))
        telegram.send_info = Mock(return_value=42)
        writer = Mock()
        worker = FakeWorker()
        surface = ExecutionOperatorSurface(repo_root=self.root, profile='live-paper',worker=worker,
            telegram=telegram,system_log=logging.getLogger('v4'),trade_log=logging.getLogger('v4'),
            enable_policy=lambda:(False,'test'), observation_status_reader=self.operator.status,
            paper_review_writer=writer)
        surface._notify_paper_review()
        surface._notify_paper_review()
        telegram.send_info.assert_called_once()
        writer.assert_not_called()
        surface.command_dispatcher.send_info = Mock()
        writer.return_value = {'order_authority':'NONE','contest_id':contest,'decision':'PROMOTE','champion_generation':1}
        surface.handle_command(f'/champion approve {contest} 1')
        writer.assert_called_once_with({'action':'approve','contest_id':contest,'generation':1})

    def test_unauthenticated_or_real_profile_review_is_rejected(self):
        import urllib.request, urllib.error
        token = 'test-token-'+'x'*32
        provider = Mock(return_value={'order_authority':'NONE'})
        target = SimpleNamespace(profile=SimpleNamespace(name='live-trade'))
        server = ObservationControlServer(target=target,auth_token=token,port=0,paper_review_provider=provider)
        host, port = server.start()
        self.addCleanup(server.stop)
        for auth, expected in [(None,401), (token,403)]:
            request = urllib.request.Request(f'http://{host}:{port}/v4-paper-review',data=b'{}',headers={'Authorization':'Bearer '+auth} if auth else {})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request,timeout=2)
            self.assertEqual(caught.exception.code, expected)
        provider.assert_not_called()

    def test_authenticated_paper_review_roundtrip(self):
        contest = self.passing()
        token = 'test-token-'+'x'*32
        target = SimpleNamespace(profile=SimpleNamespace(name='live-paper'))
        server = ObservationControlServer(target=target, auth_token=token, port=0,
            paper_review_provider=self.operator.review)
        host, port = server.start()
        self.addCleanup(server.stop)
        client = RemoteObservationClient(base_url=f'http://{host}:{port}', auth_token=token,
            profile='live-paper', execution_release_sha=SHA, receipt_directory=self.root/'receipts')
        result = client.paper_review({'action':'approve','contest_id':contest,'generation':1})
        self.assertEqual(result['champion_generation'], 1)
        self.assertEqual(result['order_authority'], 'NONE')

    def test_wss_diagnosis_records_stream_duration_and_queue(self):
        import asyncio
        from nbot.observation.wss_transport import CombinedStreamRunner
        async def run():
            state = Mock()
            runner = CombinedStreamRunner(url='wss://example/market/stream?streams=btcusdt@aggTrade',
                state=state, symbols=('BTCUSDT',))
            class Socket:
                close_code = 1006
                async def recv(self):
                    runner._stop = True
                    raise RuntimeError('test disconnect')
            class Context:
                async def __aenter__(self): return Socket()
                async def __aexit__(self, *args): pass
            async def connect_factory(_url): return Context()
            runner.connect_factory = connect_factory
            with self.assertLogs('nbot.observation.wss_transport', level='ERROR') as logs:
                await runner.run()
            output = '\n'.join(logs.output)
            for field in ('stream=aggTrade', 'connected_seconds=', 'messages=0', 'queue_depth=0', 'close_code=1006', 'exception=RuntimeError', 'retry_seconds='):
                self.assertIn(field, output)
        asyncio.run(run())

    def test_journal_diagnosis_distinguishes_old_and_new_without_exposing_logs(self):
        from nbot.operator.wss_diagnosis import summarize
        result = summarize(['WSS_RUNNER_RECONNECT attempt=0 reason=no close frame received or sent',
            'WSS_RUNNER_RECONNECT stream=aggTrade messages=10 close_code=1006 reason=keepalive ping timeout credential=secret',
            'WSS_MARKET_DATA_GAP symbol=BTCUSDT reason=gap'])
        self.assertEqual(result['stream_counts'], {'unlabelled':1, 'aggTrade':1})
        self.assertEqual(result['symbol_gap_events'], 1)
        self.assertEqual(result['categories']['keepalive_timeout'], 1)
        self.assertNotIn('secret', json.dumps(result))
