"""G1-03: source, audit recovery, fail-closed integrations; synthetic only."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from nbot_v5_1.bootstrap import BOOTSTRAP_SCHEMA_VERSION, RecoveryAssessment, inspect_restart, record_restart_hold
from nbot_v5_1.core import FiveMinuteEvent, ObservationAuthority, ObservationDisposition, SourceEvidence, canonical_digest
from nbot_v5_1.foundation import RunConfig, RunMode, ProposalEnvelope, ProposalSide, inspect_proposal
from nbot_v5_1.journal import AppendOnlyJournal, JournalEvent, JournalKind, JournalIntegrityError
from nbot_v5_1.source_contract import SOURCE_CONTRACT_VERSION, RouteHealth, SourceCursor, source_hold_reasons

ROOT = Path(__file__).resolve().parents[1]

class G1Integration(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="nbot-g1-")
        self.addCleanup(t.cleanup)
        self.path = Path(t.name) / "audit.jsonl"
        self.journal = AppendOnlyJournal(self.path)
        self.event = FiveMinuteEvent(900_000, 1_200_000)
        self.ident = canonical_digest("intent", {"t": 900_000})

    def cursor(self, **kw):
        data = dict(symbol="BTCUSDT", route="public_wss", source_epoch=0,
                    sequence=5, last_bar_open_ms=900_000, received_at_ms=1_200_000,
                    origin_digest="a"*64, health=RouteHealth.HEALTHY)
        data.update(kw)
        return SourceCursor(**data)

    def audit(self):
        return record_restart_hold(self.journal, observed_at_ms=1_200_000)

    def test_G01_version_and_immutable_source(self):
        c = self.cursor()
        self.assertEqual(SOURCE_CONTRACT_VERSION, "NBOT_V5_1_SOURCE_V1")
        with self.assertRaises(FrozenInstanceError): c.sequence = 9

    def test_G02_invalid_source_fields(self):
        bad = (dict(symbol="btc"), dict(route="INVALID!"), dict(source_epoch=True),
               dict(sequence=-1), dict(last_bar_open_ms=1),
               dict(received_at_ms=1.0), dict(origin_digest="A"*64),
               dict(health="HEALTHY"), dict(has_gap=1))
        for kw in bad:
            with self.subTest(kw=kw), self.assertRaises(ValueError): self.cursor(**kw)

    def test_G03_healthy_metadata_cannot_authenticate(self):
        self.assertEqual(source_hold_reasons(self.event, self.cursor(), expected_symbol="BTCUSDT"),
                         ("SOURCE_UNAUTHENTICATED_G1",))

    def test_G04_source_invalidity_and_gaps_hold(self):
        cases = ((None, "SOURCE_MISSING"), ("bad", "SOURCE_INVALID"),
                 (self.cursor(symbol="ETHUSDT"), "SOURCE_SYMBOL_MISMATCH"),
                 (self.cursor(health=RouteHealth.GAP), "SOURCE_ROUTE_HOLD"),
                 (self.cursor(has_gap=True), "SOURCE_ROUTE_HOLD"),
                 (self.cursor(origin_digest=None), "SOURCE_ORIGIN_DIGEST_MISSING"))
        for cur, reason in cases:
            codes = source_hold_reasons(self.event, cur, expected_symbol="BTCUSDT")
            self.assertIn(reason, codes)
            self.assertIn("SOURCE_UNAUTHENTICATED_G1", codes)

    def test_G05_time_mismatch_never_admitted(self):
        for kw, expected in ((dict(received_at_ms=1_199_999), "SOURCE_RECEIPT_TIME_INVALID"),
                             (dict(received_at_ms=1_200_001), "SOURCE_RECEIPT_TIME_INVALID"),
                             (dict(last_bar_open_ms=600_000), "SOURCE_NOT_ASOF_EVENT")):
            self.assertIn(expected, source_hold_reasons(self.event, self.cursor(**kw), expected_symbol="BTCUSDT"))

    def test_G06_new_restart_never_enables_trading(self):
        result = inspect_restart(self.journal)
        self.assertEqual(result.mode, RunMode.OFFLINE)
        self.assertIs(result.authority, ObservationAuthority.NONE)
        self.assertIs(result.disposition, ObservationDisposition.HOLD)
        self.assertIn("NEW_SOURCE_REQUIRED", result.reasons)
        self.assertFalse(self.path.exists())

    def test_G07_restart_receipt_is_idempotent(self):
        self.assertEqual(BOOTSTRAP_SCHEMA_VERSION, "NBOT_V5_1_BOOT_V1")
        first = self.audit()
        self.assertEqual(first.event.kind, JournalKind.RESTART_HOLD)
        self.assertEqual(first, self.audit())
        self.assertEqual(len(self.journal.replay()), 1)
        self.assertEqual(inspect_restart(self.journal).journal_head_digest, first.digest)

    def test_G08_corrupt_journal_boots_hold(self):
        self.audit()
        with self.path.open('ab') as stream: stream.write(b'BAD_TAIL')
        result = inspect_restart(self.journal)
        self.assertFalse(result.journal_verified)
        self.assertEqual(result.authority, ObservationAuthority.NONE)
        with self.assertRaises(JournalIntegrityError): self.audit()

    def test_G09_open_permission_never_auto_repaired(self):
        self.audit(); self.path.chmod(0o666)
        self.assertFalse(inspect_restart(self.journal).journal_verified)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o666)

    def test_G10_new_file_syncs_data_and_parent(self):
        true_sync, calls = os.fsync, []
        def track(fd):
            calls.append(stat.S_IFMT(os.fstat(fd).st_mode)); return true_sync(fd)
        with patch('nbot_v5_1.journal.os.fsync', side_effect=track): self.audit()
        self.assertIn(stat.S_IFREG, calls)
        self.assertIn(stat.S_IFDIR, calls)

    def test_G11_sync_failure_retry_reissues_directory_sync(self):
        true_sync, failed = os.fsync, []
        def fail_once(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
                failed.append(True); raise OSError('injected directory sync failure')
            return true_sync(fd)
        with patch('nbot_v5_1.journal.os.fsync', side_effect=fail_once):
            with self.assertRaises(OSError): self.audit()
        self.assertEqual(len(self.journal.replay()), 1)
        with patch('nbot_v5_1.journal.os.fsync', wraps=true_sync) as spy:
            self.assertEqual(self.audit().sequence, 1)
        self.assertGreaterEqual(spy.call_count, 2)

    def test_G12_partial_write_stays_torn_on_replay(self):
        true_write, attempts = os.write, []
        def break_write(fd, data):
            if not attempts:
                attempts.append(True); return true_write(fd, data[:8])
            raise OSError('injected interrupted write')
        ev = JournalEvent(JournalKind.SOURCE_HOLD, self.ident, 1, ('SOURCE_UNAVAILABLE',))
        with patch('nbot_v5_1.journal.os.write', side_effect=break_write):
            with self.assertRaises(OSError): self.journal.append(ev)
        damaged = self.path.read_bytes()
        with self.assertRaises(JournalIntegrityError): self.journal.append(ev)
        self.assertEqual(damaged, self.path.read_bytes())

    def test_G13_tampered_bytes_break_hash(self):
        self.audit(); self.path.write_bytes(self.path.read_bytes().replace(b'RESTART_HOLD', b'SOURCE_HOLD'))
        self.assertFalse(inspect_restart(self.journal).journal_verified)

    def test_G14_unknown_old_schema_is_not_migrated(self):
        self.audit()
        self.path.write_bytes(self.path.read_bytes().replace(b'NBOT_V5_1_JOURNAL_V1', b'NBOT_V5_1_JOURNAL_V2'))
        self.assertFalse(inspect_restart(self.journal).journal_verified)
        self.assertFalse(hasattr(self.journal, 'migrate_legacy'))

    def test_G15_full_quota_does_not_rotate(self):
        bounded = AppendOnlyJournal(self.path, max_bytes=4096)
        for n in range(80):
            try: bounded.append(JournalEvent(JournalKind.SOURCE_HOLD,
                  canonical_digest('event', {'n':n}), n, ('SOURCE_UNAVAILABLE',)))
            except JournalIntegrityError as err:
                self.assertIn('BUDGET_EXCEEDED', str(err)); break
        else: self.fail('quota bypass')
        self.assertLessEqual(self.path.stat().st_size, 4096)
        self.assertTrue(bounded.replay())

    def test_G16_invalid_restart_args_not_releasable(self):
        for bad in (True, 1.0, -1, None):
            with self.assertRaises(ValueError): record_restart_hold(self.journal, observed_at_ms=bad)
        with self.assertRaises(ValueError): inspect_restart('not journal')
        s = inspect_restart(self.journal)
        with self.assertRaises(ValueError):
            RecoveryAssessment(RunMode.REAL,s.authority,s.disposition,True,0,None,s.reasons)

    def test_G17_guardian_source_journal_integration(self):
        p = ProposalEnvelope(self.event,'BTCUSDT',ProposalSide.LONG,self.ident,1_200_000,1_200_100)
        e = SourceEvidence(900_000,900_000,1_200_000,'a'*64,0,'HEALTHY')
        verdict = inspect_proposal(RunConfig(),p,btc=e,symbol=e)
        self.assertIs(verdict.authority,ObservationAuthority.NONE)
        self.assertIs(verdict.disposition,ObservationDisposition.NO_TRADE)
        self.assertIn('SOURCE_UNAUTHENTICATED_G1',source_hold_reasons(self.event,self.cursor(),expected_symbol='BTCUSDT'))
        row = self.journal.append(JournalEvent(JournalKind.GUARDIAN_VETO,self.ident,1_200_000,verdict.reasons))
        self.assertEqual(self.journal.replay()[0],row)

    def test_G18_abrupt_child_exit_then_parent_reopens(self):
        code = '''import os,sys
from nbot_v5_1.core import canonical_digest
from nbot_v5_1.journal import AppendOnlyJournal,JournalEvent,JournalKind
AppendOnlyJournal(sys.argv[1]).append(JournalEvent(JournalKind.SOURCE_HOLD,
 canonical_digest("event", {"n":1}),1,("SOURCE_UNAVAILABLE",)))
os._exit(0)'''
        done = subprocess.run([sys.executable,'-B','-c',code,str(self.path)],cwd=ROOT,
               env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=15)
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(inspect_restart(self.journal).journal_sequence,1)
        self.assertEqual(inspect_restart(self.journal).authority,ObservationAuthority.NONE)

    def test_G19_no_old_or_exchange_imports(self):
        for filename in ('source_contract.py','bootstrap.py'):
            ast.parse((ROOT/'nbot_v5_1'/filename).read_text())
        from nbot_v5_1 import bootstrap, source_contract
        self.assertFalse(hasattr(bootstrap,'submit_order'))
        self.assertFalse(hasattr(source_contract,'connect'))

    def test_G20_future_modes_cannot_start(self):
        self.assertIs(RunConfig().mode,RunMode.OFFLINE)
        for mode in (RunMode.VIRTUAL_RESEARCH,RunMode.CHAMPION_PAPER,RunMode.CHALLENGER_PAPER,RunMode.REAL):
            with self.assertRaises(ValueError): RunConfig(mode=mode)

    def test_G21_world_writable_parent_rejected(self):
        p = self.path.parent/'shared';p.mkdir(mode=0o700);p.chmod(0o777)
        try:
            with self.assertRaisesRegex(JournalIntegrityError,'UNSAFE_PARENT'):
                AppendOnlyJournal(p/'audit.jsonl').append(JournalEvent(JournalKind.SOURCE_HOLD,self.ident,1,('SOURCE_UNAVAILABLE',)))
            self.assertFalse((p/'audit.jsonl').exists())
        finally: p.chmod(0o700)

    def test_G22_no_source_grade_or_account_claim(self):
        c = self.cursor()
        self.assertFalse(hasattr(c,'original_verified'))
        self.assertFalse(hasattr(c,'place_order'))
        self.assertIn('SOURCE_UNAUTHENTICATED_G1',source_hold_reasons(self.event,c,expected_symbol='BTCUSDT'))

if __name__ == '__main__': unittest.main()
