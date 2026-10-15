"""G1-02: bounded audit journal durability, tampering, permissions and replay."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.core import canonical_digest
from nbot_v5_1.journal import (
    JOURNAL_SCHEMA_VERSION, AppendOnlyJournal, JournalEvent, JournalKind,
    JournalIntegrityError, DEFAULT_MAX_BYTES,
)

ROOT = Path(__file__).resolve().parents[1]


class JournalContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nbot-g1-journal-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "audit.jsonl"
        self.log = AppendOnlyJournal(self.path)

    def ev(self, n=1, **overrides):
        values = dict(kind=JournalKind.SOURCE_HOLD,
                      event_id=canonical_digest("event", {"n": n}),
                      recorded_at_ms=1_000_000 + n,
                      reason_codes=("BTC_MISSING",))
        values.update(overrides)
        return JournalEvent(**values)

    def test_J01_constructor_and_replay_dont_create_a_file(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(self.log.replay(), ())
        self.assertFalse(self.path.exists())
        self.assertEqual(JOURNAL_SCHEMA_VERSION, "NBOT_V5_1_JOURNAL_V1")
        self.assertEqual(DEFAULT_MAX_BYTES, 4*1024*1024)

    def test_J02_append_fsync_and_replay_exact_receipts(self):
        a = self.log.append(self.ev())
        b = self.log.append(self.ev(2, kind=JournalKind.GUARDIAN_VETO))
        self.assertEqual((a.sequence, b.sequence), (1, 2))
        self.assertNotEqual(a.digest, b.digest)
        self.assertEqual(self.log.replay(), (a, b))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        contents = self.path.read_bytes()
        self.assertEqual(contents.count(b"\n"), 2)
        self.assertNotIn(b"private_key", contents)

    def test_J03_retry_same_event_is_idempotent_without_new_line(self):
        first = self.log.append(self.ev())
        original = self.path.read_bytes()
        self.assertEqual(self.log.append(self.ev()), first)
        self.assertEqual(self.path.read_bytes(), original)

    def test_J04_same_event_id_altered_body_conflicts(self):
        self.log.append(self.ev())
        with self.assertRaisesRegex(JournalIntegrityError, "REPLAY_CONFLICT"):
            self.log.append(self.ev(reason_codes=("BTC_SOURCE_FUTURE",)))
        self.assertEqual(len(self.log.replay()), 1)

    def test_J05_torn_last_record_fails_closed_without_repair(self):
        self.log.append(self.ev())
        with self.path.open("ab") as w:
            w.write(b'{"broken":')
        old = self.path.read_bytes()
        with self.assertRaisesRegex(JournalIntegrityError, "TORN_TAIL"):
            self.log.replay()
        with self.assertRaises(JournalIntegrityError):
            self.log.append(self.ev(2))
        self.assertEqual(self.path.read_bytes(), old)

    def test_J06_integrity_fails_when_first_record_bytes_change(self):
        self.log.append(self.ev())
        before = self.path.read_bytes()
        self.path.write_bytes(before.replace(b"BTC_MISSING", b"BTC_UNKNOWN"))
        with self.assertRaisesRegex(JournalIntegrityError, "HASH_MISMATCH"):
            self.log.replay()

    def test_J07_chain_link_and_sequence_corruption_rejected(self):
        self.log.append(self.ev())
        self.log.append(self.ev(2))
        saved = self.path.read_text()
        for field, newvalue in (("p", "f"*64), ("n", 300)):
            parts = [json.loads(line) for line in saved.splitlines()]
            parts[1][field] = newvalue
            self.path.write_text("\n".join(json.dumps(x, sort_keys=True,
                      separators=(",", ":")) for x in parts) + "\n")
            with self.subTest(field=field), self.assertRaises(JournalIntegrityError):
                self.log.replay()
        self.path.write_text(saved)
        self.assertEqual(len(self.log.replay()), 2)

    def test_J08_schema_and_duplicate_fields_fail_closed(self):
        self.log.append(self.ev())
        saved = self.path.read_bytes()
        self.path.write_bytes(saved.replace(b"NBOT_V5_1_JOURNAL_V1", b"NBOT_V5_1_JOURNAL_V2"))
        with self.assertRaises(JournalIntegrityError):
            self.log.replay()
        self.path.write_bytes(saved)
        self.path.write_bytes(saved.replace(b'"at":', b'"at":1,"at":'))
        with self.assertRaisesRegex(JournalIntegrityError, "DUPLICATE_KEY"):
            self.log.replay()

    def test_J09_validation_rejects_bad_input_and_credentials(self):
        for attrs in (dict(kind="SOURCE_HOLD"), dict(event_id="foo"),
                      dict(recorded_at_ms=True), dict(recorded_at_ms=-1),
                      dict(reason_codes=["BTC_MISSING"]),
                      dict(reason_codes=("password=TOPSECRET",)),
                      dict(reason_codes=("BTC_MISSING", "BTC_MISSING")),
                      dict(reason_codes=("ZZ", "AA"))):
            with self.subTest(attrs=attrs), self.assertRaises(ValueError):
                self.ev(**attrs)
        self.assertFalse(self.path.exists())

    def test_J10_symlink_file_and_permissive_permissions_rejected(self):
        target = Path(self.temp.name) / "other.txt"
        target.write_text("keep me")
        self.path.symlink_to(target)
        with self.assertRaises(OSError):
            self.log.append(self.ev())
        self.assertEqual(target.read_text(), "keep me")
        self.path.unlink()
        self.log.append(self.ev())
        self.path.chmod(0o644)
        with self.assertRaisesRegex(JournalIntegrityError, "UNSAFE_FILE"):
            self.log.replay()
        with self.assertRaisesRegex(JournalIntegrityError, "UNSAFE_FILE"):
            self.log.append(self.ev(2))

    def test_J11_hardlinks_and_untrusted_directory_links_rejected(self):
        self.log.append(self.ev())
        hard = Path(self.temp.name) / "audit-copy.jsonl"
        os.link(self.path, hard)
        with self.assertRaises(JournalIntegrityError):
            self.log.append(self.ev(2))
        hard.unlink()
        linked = Path(self.temp.name) / "link"
        linked.symlink_to(Path(self.temp.name), target_is_directory=True)
        with self.assertRaises(ValueError):
            AppendOnlyJournal(linked / "audit2.jsonl")

    def test_J12_bounded_journal_refuses_growth_and_never_truncates(self):
        bounded = AppendOnlyJournal(self.path, max_bytes=4096)
        first = bounded.append(self.ev())
        for i in range(2, 50):
            try:
                bounded.append(self.ev(i))
            except JournalIntegrityError as e:
                self.assertIn("BUDGET_EXCEEDED", str(e))
                break
        else:
            self.fail("bounded journal accepted excessive entries")
        self.assertLessEqual(self.path.stat().st_size, 4096)
        self.assertEqual(bounded.replay()[0], first)

    def test_J13_empty_parent_invalid_path_and_budget_fail_closed(self):
        for bad in ("relative.jsonl", Path(self.temp.name)/"missing"/"log"):
            j = AppendOnlyJournal(bad) if str(bad).startswith("/") else None
            if j is None:
                with self.assertRaises(ValueError):
                    AppendOnlyJournal(bad)
            else:
                with self.assertRaises(JournalIntegrityError):
                    j.append(self.ev())
        for invalid in (4095, True, 65*1024*1024):
            with self.assertRaises(ValueError):
                AppendOnlyJournal(self.path, max_bytes=invalid)

    def test_J14_static_imports_only_explicit_local_file_io(self):
        path = ROOT / "nbot_v5_1" / "journal.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"__future__", "dataclasses", "enum", "fcntl", "hashlib",
                   "json", "os", "pathlib", "re", "stat"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(n.name in allowed for n in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
        for forbidden in ("sqlite3", "binance", "subprocess", "requests",
                          "socket", "MAX_SYMBOLS", "PRIVATE_KEY"):
            self.assertNotIn(forbidden, source)

    def test_J16_guardian_veto_can_be_recorded_without_trade_interface(self):
        from nbot_v5_1.core import FiveMinuteEvent
        from nbot_v5_1.foundation import (RunConfig, ProposalEnvelope, ProposalSide,
                                           inspect_proposal)
        clock = FiveMinuteEvent(900_000, 1_200_000)
        ident = canonical_digest("intent", {"symbol": "BTCUSDT", "t": 900_000})
        proposal = ProposalEnvelope(clock, "BTCUSDT", ProposalSide.LONG, ident,
                                    1_200_000, 1_200_100)
        verdict = inspect_proposal(RunConfig(), proposal)
        event = JournalEvent(JournalKind.GUARDIAN_VETO, ident, 1_200_000,
                             verdict.reasons)
        self.assertEqual(verdict.authority.value, "NONE")
        self.assertEqual(self.log.append(event).event, event)
        self.assertEqual(self.log.replay()[0].event, event)

    def test_J17_two_distinct_appenders_share_ordered_chain(self):
        another = AppendOnlyJournal(self.path)
        a = self.log.append(self.ev(1))
        b = another.append(self.ev(2))
        c = self.log.append(self.ev(3))
        self.assertEqual([r.sequence for r in self.log.replay()], [1, 2, 3])
        self.assertEqual(another.replay(), (a, b, c))

    def test_J18_parallel_process_append_uses_one_integrity_chain(self):
        import subprocess
        import sys
        code = r'''from nbot_v5_1.journal import AppendOnlyJournal, JournalEvent, JournalKind
from nbot_v5_1.core import canonical_digest
import sys
j = AppendOnlyJournal(sys.argv[1])
base = int(sys.argv[2])
for n in range(base, base + 6):
    j.append(JournalEvent(JournalKind.SOURCE_HOLD,
             canonical_digest("event", {"p": n}), n, ("BTC_MISSING",)))
'''
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        children = [subprocess.Popen([sys.executable, "-B", "-c", code,
                     str(self.path), str(n)], cwd=ROOT, env=env,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for n in (100, 200, 300)]
        for child in children:
            _, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr.decode(errors="replace"))
        records = self.log.replay()
        self.assertEqual(len(records), 18)
        self.assertEqual([r.sequence for r in records], list(range(1, 19)))
        self.assertEqual(len({r.event.event_id for r in records}), 18)

    def test_J15_reopen_existing_journal_after_restart(self):
        first = self.log.append(self.ev())
        reopened = AppendOnlyJournal(self.path)
        self.assertEqual(reopened.replay(), (first,))
        self.assertEqual(reopened.append(self.ev()), first)
        second = reopened.append(self.ev(2))
        self.assertEqual(self.log.replay(), (first, second))


if __name__ == "__main__":
    unittest.main()
