"""Second-audit counterexamples. Real production thresholds, isolated DBs.

Clock=0 explicitly models accelerated local time; receipt/decision watermarks
are still checked. No network, account access, or production validation patch.
"""
import asyncio
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from nbot.observation.v5_live_evidence import LiveEvidenceBridge, FUNDING_GRACE_MS
from nbot.observation.v5_live_transport import run_session
from nbot.observation.v5_foundation import V5EvidenceStore
from nbot.observation.v5_evidence_trust import CONTRACT, require_certified_sample
from tests.test_v5_live_evidence import T, END, trade, depth, quote, entry


def make_bridge(path, *, snapshot_receipt=T-70, clock=lambda: 0, admit=True):
    b = LiveEvidenceBridge(path, symbols=['BTCUSDT'], clock=clock)
    b.initialize()
    b.connected('BTCUSDT')
    b.ingest(trade(), T-80)
    b.ingest(depth(), T-80)
    b.ingest(quote(u=100, t=T-100, bid='99.9', ask='100'), T-60)
    b.snapshot('BTCUSDT', {'lastUpdateId':100, 'T':T-100,
                          'bids':[['99.9','2']], 'asks':[['100','2']]}, snapshot_receipt)
    if admit:
        b.add(entry())
    return b


def observed_horizon(b, *, crossing=False):
    if crossing:
        b.ingest(quote(u=101,t=T+50), T+55)
    b.ingest(quote(u=103,t=T+100,bid='99.9',ask='100'), T+110)
    b.ingest(depth(u=103,U=101,pu=100,t=T+100), T+115)
    b.ingest(trade(11,T+100), T+120)
    last_u, agg = 103, 11
    for timestamp in list(range(T+20_000, END, 20_000)) + [END]:
        bid, ask = ('100.5','100.6') if timestamp == END else ('99.9','100')
        update = last_u + 1
        b.ingest(quote(u=update,t=timestamp,bid=bid,ask=ask), timestamp+10)
        d=depth(u=update,pu=last_u,t=timestamp,bid=bid,ask=ask)
        if timestamp == END:
            d['b'].append(['99.9','0']); d['a'].append(['100','0'])
        b.ingest(d,timestamp+15)
        agg += 1
        b.ingest(trade(agg,timestamp),timestamp+20)
        b.check_source_coverage(timestamp+25)
        last_u=update
    return last_u, agg


def ledger(path):
    store=V5EvidenceStore(path)
    store.initialize()
    store.record_decision(decision_id='d1',event_open_ms=300_000,symbol='BTCUSDT',side='LONG',
                          setup_id='TEST',qualified=True,reason='TEST',feature_digest='test',
                          selection_policy_id='TEST')
    return store


class TrustRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'v5'/'live.db'
    def tearDown(self):
        self.temp.cleanup()

    def test_h1_delivered_and_omitted_crossing_have_different_observed_results_neither_certified(self):
        results=[]
        for crossing in (False, True):
            b=make_bridge(self.path.with_name(str(crossing)+'.db'))
            observed_horizon(b,crossing=crossing)
            key=b.reconcile_funding('BTCUSDT',T,END,lambda *a:[],now_ms=END+FUNDING_GRACE_MS)
            rows=b.finalize('d1',now_ms=END+FUNDING_GRACE_MS,funding_key=key)
            self.assertEqual({r.status for r in rows},{'OBSERVED_STREAM'})
            self.assertEqual({r.evidence_contract for r in rows},{CONTRACT})
            self.assertTrue(all(r.accounting is None and r.proof is None for r in rows))
            self.assertTrue(all(r.observed_accounting['net_r'] is None for r in rows))
            self.assertEqual(len({r.evidence_digest for r in rows}),1)
            store=ledger(self.path.with_name('ledger'+str(crossing)+'.db'))
            b.persist_results(store,'d1')
            self.assertEqual(store.status()['scored'],0)
            self.assertEqual(len(store.observed_pairs(authority=b)),1)
            for purpose in ('TRAINING','CHAMPION','PROMOTION','PERFORMANCE'):
                with self.assertRaisesRegex(ValueError,'VALIDATOR_UNAVAILABLE'):
                    store.certified_pairs(purpose=purpose)
            results.append(rows)
        self.assertTrue(all(r.observed_accounting['gross_r']==.5 for r in results[0]))
        self.assertTrue(all(r.observed_accounting['gross_r']==-1.5 for r in results[1]))
        self.assertTrue(all(r.exit_time_ms==T+50 for r in results[1]))

    def test_h2_snapshot_after_decision_rejected(self):
        b=make_bridge(self.path,snapshot_receipt=T+500,admit=False)
        with self.assertRaisesRegex(ValueError,'ANCHOR_UNPROVEN'):
            b.add(entry())
        self.assertEqual(b.lab.active_count,0)

    def test_h2_actual_processing_completion_blocks_backdating(self):
        now=[0]
        b=make_bridge(self.path,clock=lambda:now[0],admit=False)
        now[0]=T+500
        b.ingest(quote(u=101,t=T-50,bid='99.9',ask='100'),T-40)
        with self.assertRaisesRegex(ValueError,'ANCHOR_UNPROVEN'):
            b.add(replace(entry(),entry_quote_time_ms=T-50))

    def test_h2_later_depth_receipt_and_stale_depth_rejected(self):
        b=make_bridge(self.path,admit=False)
        b.ingest(depth(u=101,pu=100,t=T-50),T+500)
        b.ingest(quote(u=101,t=T-50,bid='99.9',ask='100'),T+501)
        with self.assertRaisesRegex(ValueError,'ANCHOR_UNPROVEN'):
            b.add(replace(entry(),entry_quote_time_ms=T-50))
        b.ingest(quote(u=102,t=T+500,bid='99.9',ask='100'),T+510)
        with self.assertRaisesRegex(ValueError,'ANCHOR_UNPROVEN'):
            b.add(replace(entry(),entry_time_ms=T+2200,entry_quote_time_ms=T+500))

    def test_h3_conflict_revokes_pending_persisted_and_restart(self):
        b=make_bridge(self.path)
        observed_horizon(b)
        key=b.reconcile_funding('BTCUSDT',T,END,lambda *a:[],now_ms=END+FUNDING_GRACE_MS)
        rows=b.finalize('d1',now_ms=END+FUNDING_GRACE_MS,funding_key=key)
        store=ledger(self.path.with_name('ledger.db'))
        b.persist_results(store,'d1')
        settlement={'symbol':'BTCUSDT','fundingTime':T+5000,'fundingRate':'.001','markPrice':'105'}
        with self.assertRaisesRegex(ValueError,'CONFLICT'):
            b.reconcile_funding('BTCUSDT',T,END,lambda *a:[settlement],now_ms=END+FUNDING_GRACE_MS+1)
        self.assertEqual(b.funding[key]['state'],'REVOKED')
        self.assertEqual(store.observed_pairs(authority=b)[0]['effective_class'],'REVOKED')
        restored=LiveEvidenceBridge(self.path,symbols=['BTCUSDT'],clock=lambda:0)
        restored.initialize()
        self.assertEqual(restored.funding[key]['state'],'REVOKED')
        self.assertEqual(store.observed_pairs(authority=restored)[0]['effective_class'],'REVOKED')
        self.assertEqual(rows[0].status,'OBSERVED_STREAM')  # history not rewritten
        with self.assertRaises(ValueError): store.certified_pairs()

    def test_h3_failed_revocation_write_latches_until_invalidating_recovery(self):
        b=make_bridge(self.path)
        key=b.reconcile_funding('BTCUSDT',T,END,lambda *a:[],now_ms=END+FUNDING_GRACE_MS)
        settlement={'symbol':'BTCUSDT','fundingTime':T+5000,'fundingRate':'.001','markPrice':'105'}
        with patch.object(b,'_connect',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):
                b.reconcile_funding('BTCUSDT',T,END,lambda *a:[settlement],now_ms=END+FUNDING_GRACE_MS)
        with self.assertRaisesRegex(RuntimeError,'INTEGRITY_FAULT'):
            b.finalize('d1',now_ms=END,funding_key=key)
        b.recover_integrity()
        self.assertTrue(b.revocations('d1'))

    def test_h4_same_time_conflict_after_horizon_before_publication(self):
        b=make_bridge(self.path)
        update,_=observed_horizon(b)
        self.assertTrue(b.lab._paths['d1'].horizon_witnessed)
        b.ingest(quote(u=update+1,t=END),END+30)
        self.assertEqual(b.lab._paths['d1'].gap_reason,'JOINT_QUOTE_ORDER_AMBIGUOUS')
        self.assertTrue(all(r.status=='UNSCORABLE' for r in b.finalize('d1',now_ms=END+30)))

    def test_h4_late_contradiction_revokes_after_ledger_ack(self):
        b=make_bridge(self.path)
        update,_=observed_horizon(b)
        b.finalize('d1',now_ms=END+20)
        store=ledger(self.path.with_name('ledger.db'))
        b.persist_results(store,'d1')
        b.ingest(quote(u=update+1,t=END),END+30)
        pair=store.observed_pairs(authority=b)[0]
        self.assertEqual(pair['effective_class'],'REVOKED')
        self.assertEqual({a['status'] for a in pair['arms']},{'OBSERVED_STREAM'})

    def test_h5_failed_stop_and_failed_invalidation_cannot_be_bypassed(self):
        b=make_bridge(self.path)
        with patch.object(b,'_connect',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError): b.ingest(quote(t=T+50),T+55)
            with self.assertRaisesRegex(RuntimeError,'INTEGRITY_FAULT'): b.disconnect('BTCUSDT')
            with self.assertRaises(sqlite3.OperationalError): b.recover_integrity()
        self.assertEqual(b.integrity_fault['event']['payload']['b'],'98.5')
        for operation in (lambda:b.ingest(quote(u=103,t=T+100,bid='99.9',ask='100'),T+110),
                          lambda:b.connected('BTCUSDT'),lambda:b.add(entry(decision='new')),
                          lambda:b.finalize('d1',now_ms=END)):
            with self.assertRaisesRegex(RuntimeError,'INTEGRITY_FAULT'): operation()
        b.recover_integrity()
        self.assertIsNone(b.integrity_fault)
        self.assertFalse(b.feeds['BTCUSDT']['connected'])
        self.assertTrue(all(r.status=='UNSCORABLE' for r in b.finalize('d1',now_ms=END)))

    def test_h5_restart_after_failed_stop_cannot_resume_eligibility(self):
        b=make_bridge(self.path)
        with patch.object(b,'_connect',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError): b.ingest(quote(t=T+50),T+55)
        restored=LiveEvidenceBridge(self.path,symbols=['BTCUSDT'],clock=lambda:0)
        restored.initialize()
        self.assertFalse(restored.feeds['BTCUSDT']['connected'])
        self.assertTrue(restored.revocations('d1'))
        self.assertTrue(all(r.status=='UNSCORABLE' for r in restored.finalize('d1',now_ms=END)))

    def test_m2_barrier_disconnect_between_call_and_locked_admission(self):
        b=make_bridge(self.path,admit=False)
        reached, release=threading.Event(),threading.Event()
        original=b._change
        def barrier(event, action):
            if event['kind']=='ENTRY':
                reached.set(); self.assertTrue(release.wait(3))
            return original(event,action)
        failures=[]
        def admit():
            try:b.add(entry())
            except Exception as e:failures.append(e)
        with patch.object(b,'_change',side_effect=barrier):
            worker=threading.Thread(target=admit)
            worker.start(); self.assertTrue(reached.wait(3))
            b.disconnect('BTCUSDT'); release.set(); worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(b.lab.active_count,0)
        self.assertEqual(len(failures),1)
        self.assertIn('ANCHOR_UNPROVEN',str(failures[0]))

    def test_event_tail_replay_preserves_stop_digest_before_invalidating_restart(self):
        b=make_bridge(self.path)
        b.ingest(quote(t=T+50),T+55)
        before=b.lab._paths['d1'].digest.hexdigest()
        with b._connect() as c:
            checkpoint=c.execute('SELECT seq FROM checkpoint').fetchone()[0]
        self.assertLess(checkpoint,b.seq)
        restored=LiveEvidenceBridge(self.path,symbols=['BTCUSDT'],clock=lambda:0)
        restored.initialize()
        p=restored.lab._paths['d1']
        self.assertEqual(p.digest.hexdigest(),before)
        self.assertEqual(p.arms['TIME_EXIT_V1'].exit_price,98.5)
        self.assertEqual(p.gap_reason,'PROCESS_RESTART')

    def test_journal_truncation_detected_even_when_checkpoint_is_older(self):
        b=make_bridge(self.path)
        b.ingest(quote(),T+110)
        with b._connect() as c:
            c.execute('DROP TRIGGER journal_no_delete')
            c.execute('DELETE FROM journal WHERE seq=?',(b.seq,))
        with self.assertRaisesRegex(ValueError,'JOURNAL_HEAD_MISMATCH'):
            LiveEvidenceBridge(self.path,symbols=['BTCUSDT'],clock=lambda:0).initialize()

    def test_checkpoint_failure_poisoned_and_old_state_recoverable(self):
        b=make_bridge(self.path,admit=False)
        with b._connect() as c:
            c.execute("CREATE TRIGGER fail_checkpoint BEFORE INSERT ON checkpoint BEGIN SELECT RAISE(ABORT,'disk full'); END")
        with self.assertRaises(sqlite3.DatabaseError): b.add(entry())
        self.assertIsNotNone(b.integrity_fault)
        with b._connect() as c:c.execute('DROP TRIGGER fail_checkpoint')
        b.recover_integrity()
        self.assertEqual(b.lab.active_count,0)

    def test_empty_funding_and_forged_certification_never_train(self):
        for classification in ('RECEIVED_EVIDENCE','OBSERVED_STREAM','SCORED','CERTIFIED_PATH','REVOKED','UNSCORABLE'):
            for purpose in ('TRAINING','CHAMPION','PROMOTION','PERFORMANCE'):
                with self.assertRaisesRegex(ValueError,'VALIDATOR_UNAVAILABLE'):
                    require_certified_sample({'evidence_class':classification,'proof':{'valid':True}},purpose=purpose)

    def test_independent_review_fabricated_pair_cannot_bypass_source_provenance(self):
        b=make_bridge(self.path)
        b.disconnect('BTCUSDT')
        rows=b.finalize('d1',now_ms=T+100)
        store=ledger(self.path.with_name('ledger.db'))
        fabricated=tuple(replace(r,status='OBSERVED_STREAM',evidence_class='OBSERVED_STREAM',
                                 observed_accounting={'gross_r':999,'net_r':999}) for r in rows)
        with self.assertRaisesRegex(ValueError,'NOT_CURRENT_FINALIZED'):
            store.record_observed_pair(fabricated,authority=b)
        self.assertEqual(store.observed_pairs(authority=b),[])
        b.persist_results(store,'d1')
        self.assertEqual(store.observed_pairs(authority=b)[0]['effective_class'],'REVOKED')

    def test_stale_authority_cannot_publish_or_read_diagnostics(self):
        b=make_bridge(self.path)
        b.disconnect('BTCUSDT')
        rows=b.finalize('d1',now_ms=T+100)
        store=ledger(self.path.with_name('ledger.db'))
        second=LiveEvidenceBridge(self.path,symbols=['BTCUSDT'],clock=lambda:0)
        second.initialize()
        with self.assertRaisesRegex(RuntimeError,'AUTHORITY_STALE'):
            store.record_observed_pair(rows,authority=b)

    def test_legacy_partial_pair_write_rolls_back_every_arm(self):
        from nbot.observation.v5_paired_exits import PairedExitLab, persist_to_v5_ledger
        from tests.test_v5_paired_exits import tick, DEADLINE
        store=ledger(self.path.with_name('ledger.db'))
        lab=PairedExitLab(); lab.add(entry())
        lab.invalidate_symbol('BTCUSDT',reason='WSS_GAP')
        rows=lab.finalize('d1',now_ms=END)
        with store._connect() as c:
            c.execute("CREATE TRIGGER fail_second BEFORE INSERT ON v5_outcomes WHEN NEW.exit_policy_id='TIME_EXIT_V1' BEGIN SELECT RAISE(ABORT,'disk full'); END")
        with self.assertRaises(sqlite3.DatabaseError):persist_to_v5_ledger(store,rows)
        self.assertEqual(store.status()['unscorable'],0)
        with store._connect() as c:c.execute('DROP TRIGGER fail_second')
        persist_to_v5_ledger(store,rows)
        self.assertEqual(store.status()['unscorable'],3)

    def test_derived_window_and_identity_corruption_rejected_on_restart(self):
        for table in ('published_windows','decision_ids'):
            path=self.path.with_name(table+'.db')
            b=make_bridge(path); b.disconnect('BTCUSDT'); b.finalize('d1',now_ms=T)
            with b._connect() as c:
                c.execute(f'DROP TRIGGER {table}_no_update')
                if table=='published_windows':c.execute("UPDATE published_windows SET end_ms=0")
                else:c.execute("UPDATE decision_ids SET entry='{}'")
            with self.assertRaisesRegex(ValueError,'JOURNAL_MISMATCH'):
                LiveEvidenceBridge(path,symbols=['BTCUSDT'],clock=lambda:0).initialize()

    def test_randomized_duplicate_quote_repeatability_and_fault_state_machine(self):
        digests=[]
        for repeat in range(2):
            b=make_bridge(self.path.with_name(f'{repeat}.db'))
            rng=random.Random(3813)
            for i in range(1,40):
                px=rng.choice(['99.9','100.1','100.2'])
                q=quote(u=100+i,t=T+i*10,bid=px,ask=str(float(px)+.1))
                b.ingest(q,T+i*10+1)
                if rng.choice([True,False]):b.ingest(q,T+i*10+1)
            digests.append(b.lab._paths['d1'].digest.hexdigest())
            with patch.object(b,'_connect',side_effect=sqlite3.OperationalError('disk full')):
                with self.assertRaises(sqlite3.OperationalError):b.ingest(quote(u=200,t=T+500),T+501)
            for _ in range(10):
                with self.assertRaisesRegex(RuntimeError,'INTEGRITY_FAULT'):
                    b.ingest(quote(u=rng.randrange(201,300),t=T+600),T+601)
        self.assertEqual(digests[0],digests[1])


class SupervisionTests(unittest.TestCase):
    def run_fault(self, *, rest=None, messages=None, tweaks=None):
        class Socket:
            def __init__(self,url): self.market='/market/' in url
            async def __aenter__(self):return self
            async def __aexit__(self,*a):pass
            def __aiter__(self):return self.rows()
            async def rows(self):
                if not self.market:
                    for row in messages or [depth()]:yield json.dumps(row)
                await asyncio.Event().wait()
        with tempfile.TemporaryDirectory() as td:
            b=LiveEvidenceBridge(Path(td)/'v5'/'transport.db',symbols=['BTCUSDT'],clock=lambda:0)
            b.initialize()
            async def execute():
                await asyncio.wait_for(run_session(b,rest=rest,connect=lambda url,**kw:Socket(url),clock=lambda:T),2)
            with tweaks or patch('nbot.observation.v5_live_transport.SYNC_TIMEOUT',.3):
                asyncio.run(execute())

    def test_m1_immediate_snapshot_exception_propagates_no_unretrieved_task(self):
        def rest(*a):raise OSError('synthetic REST failure')
        with self.assertRaisesRegex(OSError,'synthetic REST failure'):
            self.run_fault(rest=rest)

    def test_sync_deadline_while_sockets_stay_open(self):
        def rest(*a):return {'lastUpdateId':100,'T':T-100,'bids':[['99.9','2']],'asks':[['100','2']]}
        with self.assertRaisesRegex(TimeoutError,'BOOK_SYNC_DEADLINE'):
            self.run_fault(rest=rest,messages=[quote(t=T)])

    def test_byte_overflow_is_prompt(self):
        before=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'BYTE_BUFFER_OVERFLOW'):
            self.run_fault(messages=[{**depth(),'unused':'x'*70000}])
        self.assertLess(time.monotonic()-before,2)

    def test_count_overflow_is_prompt_and_does_not_process_two_thousand_sqlite_writes(self):
        before=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'BUFFER_OVERFLOW'):
            self.run_fault(messages=[depth()]*2001,
                           tweaks=patch('nbot.observation.v5_live_transport.MAX_QUEUE_ITEMS',2))
        self.assertLess(time.monotonic()-before,2)


if __name__=='__main__':unittest.main()
