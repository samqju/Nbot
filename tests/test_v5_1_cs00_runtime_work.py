"""CS-00 nontrading source transport, recovery scheduler, backup/supervisor tests."""
import hashlib
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.cs00_public_ws import (
    validate_route,client_frame,PublicTlsSocket,PublicSocketHold)
from nbot_v5_1.cs00_source_runtime import (
    public_routes,SourceOnlyIntake,CollectorHold)
from nbot_v5_1.cs00_history_recovery import HistoricalAggTradeRecovery
from nbot_v5_1.cs00_recovery_worker import (
    BudgetedPublicRest,RecoveryScheduler,RecoveryTransportHold)
from nbot_v5_1.cs00_compact_backup import (
    create_compact_backup,verify_compact_backup,CompactBackupHold)
from nbot_v5_1.cs00_supervisor import SourceOnlySupervisor,Heartbeat,SupervisorHold
from test_v5_1_g4_source import frame,NOW
from test_v5_1_cs00_history_recovery import trade,body,T

SYMBOLS=("BTCUSDT",)+tuple("COIN%02dUSDT"%i for i in range(19))
SHA="a"*64


class PublicOnlyTests(unittest.TestCase):
    def test_CSRT01_all_routes_are_20_public_only_and_disabled(self):
        routes=public_routes(SYMBOLS)
        self.assertEqual({x.kind for x in routes},{"TRADE","QUOTE","MARK"})
        self.assertTrue(all(x.uri.startswith("wss://fstream.binance.com/")
                            and not x.enabled and x.financial_authority=="NONE"
                            for x in routes))
        for r in routes:
            self.assertIn("/stream?streams=",validate_route(r.uri))

    def test_CSRT02_wrong_route_credentials_and_account_endpoints_blocked(self):
        for uri in ("wss://evil.example/market/stream?streams=btcusdt@aggTrade",
                    "wss://api.binance.com/market/stream?streams=btcusdt@aggTrade",
                    "wss://fstream.binance.com/private/stream?streams=btcusdt@aggTrade",
                    "wss://user:password@fstream.binance.com/market/stream?streams=btcusdt@aggTrade",
                    "wss://fstream.binance.com/market/stream?streams=btcusdt@bookTicker"):
            with self.subTest(uri=uri),self.assertRaises(PublicSocketHold):
                validate_route(uri)

    def test_CSRT03_public_socket_cannot_connect_without_owner_cs01(self):
        p=PublicTlsSocket(public_routes(SYMBOLS)[0].uri)
        with self.assertRaisesRegex(PublicSocketHold,"OWNER_CS01_APPROVAL_MISSING"):
            p.connect()
        self.assertTrue(p.closed)
        self.assertIsNone(p.sock)

    def test_CSRT04_masked_frames_and_opcode_restrictions(self):
        p=client_frame(b"hi",mask=b"abcd")
        self.assertEqual(p[:2],bytes((0x82,0x82)))
        self.assertEqual(p[2:6],b"abcd")
        self.assertEqual(bytes(p[6+i]^b"abcd"[i] for i in range(2)),b"hi")
        with self.assertRaises(PublicSocketHold):
            client_frame(b"x",opcode=3)

    def test_CSRT05_accept_synthetic_frames_but_never_grade_original(self):
        x=SourceOnlyIntake(SYMBOLS)
        for kind in ("TRADE","QUOTE","MARK"):
            r=x.observe(kind=kind,raw=frame(kind,id=8),epoch=1,
                        received_ms=NOW)
            self.assertEqual(r.state,"LOCAL_FRAME_NOT_INDEPENDENTLY_QUALIFIED")
            self.assertFalse(r.source_qualified)
        self.assertEqual(x.status()["frames_processed"],3)
        self.assertEqual(x.status()["source_qualified"],0)

    def test_CSRT06_duplicate_or_gap_holds_symbol_and_never_auto_heals(self):
        x=SourceOnlyIntake(SYMBOLS)
        x.observe(kind="TRADE",raw=frame(id=8),epoch=1,received_ms=NOW)
        r=x.observe(kind="TRADE",raw=frame(id=10,received=NOW+1000),
                    epoch=1,received_ms=NOW+1000)
        self.assertEqual(r.state,"SOURCE_HOLD")
        r=x.observe(kind="TRADE",raw=frame(id=11,received=NOW+2000),
                    epoch=1,received_ms=NOW+2000)
        self.assertEqual(r.state,"SOURCE_HOLD")
        self.assertEqual(x.status()["quarantined_pairs"],1)

    def test_CSRT07_disconnect_quarantines_20_no_seamless_epoch(self):
        x=SourceOnlyIntake(SYMBOLS)
        x.observe(kind="QUOTE",raw=frame("QUOTE"),epoch=1,
                  received_ms=NOW)
        x.mark_disconnect(kind="QUOTE",at_ms=NOW+500)
        self.assertEqual(x.status()["quarantined_pairs"],20)
        r=x.observe(kind="QUOTE",raw=frame("QUOTE",received=NOW+1000),
                    epoch=2,received_ms=NOW+1000)
        self.assertEqual(r.state,"SOURCE_HOLD")

    def test_CSRT08_outside_cohort_and_wrong_type_denied(self):
        x=SourceOnlyIntake(SYMBOLS)
        with self.assertRaises(CollectorHold):
            x.observe(kind="TRADE",raw=frame(symbol="XRPUSDT"),
                      epoch=1,received_ms=NOW)
        with self.assertRaises(CollectorHold):
            x.observe(kind="ORDER",raw=frame(),epoch=1,received_ms=NOW)


class SchedulerTests(unittest.TestCase):
    def rec(self,ident="a"*64,first=10,count=2):
        return HistoricalAggTradeRecovery(
            experiment_id=ident,symbol="BTCUSDT",first_agg_id=first,
            last_agg_id=first+count-1,
            gap_start_ms=T,gap_end_ms=T+10000,now_ms=T+20000,
            side="LONG",stop="99",target="102")

    def test_CSRW01_network_is_disabled_by_default(self):
        c=BudgetedPublicRest()
        with self.assertRaisesRegex(RecoveryTransportHold,"NO_NETWORK_PERMISSION"):
            c.get_page("/fapi/v1/aggTrades?symbol=BTCUSDT&fromId=10&limit=2",
                       now_ms=T+21000)

    def test_CSRW02_mock_transport_paginates_and_finishes(self):
        visited=[]
        def fake(url,timeout):
            visited.append(url)
            if "fromId=10" in url:
                return body([trade(10,T+1000),trade(11,T+2000,"98")])
            raise RuntimeError("UNEXPECTED_RETRY")
        c=BudgetedPublicRest(allow_public_network=True,transport=fake)
        sch=RecoveryScheduler(c)
        sch.admit(self.rec(),now_ms=T+20000)
        x=sch.step(now_ms=T+20000)
        self.assertEqual(x.status,"TRADE_PATH_RECOVERED_ONLY")
        self.assertEqual(x.pages,1)
        self.assertEqual(len(visited),1)
        self.assertEqual(c.requests,1)

    def test_CSRW03_backoff_and_nonrecoverable_never_auto_censors(self):
        def broken(url,timeout):
            raise TimeoutError("OFFLINE_SIMULATED")
        c=BudgetedPublicRest(allow_public_network=True,transport=broken)
        s=RecoveryScheduler(c);s.admit(self.rec(),now_ms=T+20000)
        for n in range(4):
            now=T+20000+(3000 if n==1 else 10000 if n==2 else 30000 if n==3 else 0)
            x=s.step(now_ms=now)
        self.assertEqual(x.status,"RECOVERY_HOLD")
        self.assertIn("RETRIES_EXHAUSTED",x.reason)
        self.assertEqual(s.tasks["a"*64].proof().trade_count,0)
        self.assertFalse(s.tasks["a"*64].proof().qualifies_scientific_training)

    def test_CSRW04_global_weight_budget_and_no_private_paths(self):
        c=BudgetedPublicRest(allow_public_network=True,
                             transport=lambda uri,timeout:body([trade(10,T+1000)]),
                             weight_budget=20)
        path="/fapi/v1/aggTrades?symbol=BTCUSDT&fromId=10&limit=1"
        c.get_page(path,now_ms=T+20000)
        with self.assertRaisesRegex(RecoveryTransportHold,"GLOBAL_WEIGHT"):
            c.get_page(path,now_ms=T+20001)
        for bad in ("/fapi/v1/order?symbol=BTCUSDT",
                    "/fapi/v1/aggTrades?symbol=BTCUSDT&limit=1",
                    "/fapi/v1/aggTrades?symbol=BTCUSDT&fromId=10&limit=1001"):
            with self.assertRaises(RecoveryTransportHold):
                c.get_page(bad,now_ms=T+20000)

    def test_CSRW06_rate_limit_defers_not_recovery_failure(self):
        def page(url,timeout):
            return body([trade(10,T+1000)])
        c=BudgetedPublicRest(allow_public_network=True,
                             transport=page,weight_budget=20)
        s=RecoveryScheduler(c)
        s.admit(self.rec(),now_ms=T+20000)
        first=s.step(now_ms=T+20000)
        self.assertEqual(first.pages,1)
        second=s.step(now_ms=T+21000)
        self.assertEqual(second.attempts,0)
        self.assertEqual(second.status,"RECOVERY_PENDING")
        self.assertIsNone(second.reason)
        self.assertGreater(second.next_attempt_ms,T+21000)

    def test_CSRW05_tasks_older_than_48h_become_archive_pending(self):
        s=RecoveryScheduler(BudgetedPublicRest(allow_public_network=True,
                    transport=lambda u,t:b"[]"))
        s.admit(self.rec(),now_ms=T+20000)
        self.assertIsNone(s.step(now_ms=T+50*3600*1000))
        self.assertEqual(s.status("a"*64).status,"ARCHIVE_PENDING")


class CompactBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="cs00-ledger-backup-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"source";self.dest=self.root/"backup"
        self.source.mkdir(mode=0o700);self.dest.mkdir(mode=0o700)
        (self.source/"research.jsonl").write_text('{"state":"CENSORED"}\n')
        (self.source/"research.jsonl").chmod(0o600)

    def test_CSBU01_immutable_journal_backup_and_restore_verification(self):
        m=create_compact_backup(source=self.source,destination=self.dest,
                                filenames=("research.jsonl",))
        self.assertEqual(m["files"],1)
        self.assertFalse(m["offhost_independently_verified"])
        self.assertEqual(verify_compact_backup(self.dest),m)

    def test_CSBU02_corrupt_receipt_never_accepted(self):
        create_compact_backup(source=self.source,destination=self.dest,
                              filenames=("research.jsonl",))
        (self.dest/"research.jsonl").write_text("hacked")
        with self.assertRaises(CompactBackupHold):
            verify_compact_backup(self.dest)

    def test_CSBU03_no_overwrite_and_extra_files_rejected(self):
        create_compact_backup(source=self.source,destination=self.dest,
                              filenames=("research.jsonl",))
        with self.assertRaises(CompactBackupHold):
            create_compact_backup(source=self.source,destination=self.dest,
                                  filenames=("research.jsonl",))
        (self.dest/"extra.txt").write_text("extra")
        (self.dest/"extra.txt").chmod(0o600)
        with self.assertRaises(CompactBackupHold):
            verify_compact_backup(self.dest)

    def test_CSBU04_coherent_sqlite_wal_checkpoint_copy(self):
        p=self.source/"science.sqlite"
        db=sqlite3.connect(p);db.execute("pragma journal_mode=WAL")
        db.execute("create table events(id integer primary key, state text)")
        db.execute("insert into events values (1,'UNRECOVERABLE_EXCLUDED')")
        db.commit();p.chmod(0o600)
        m=create_compact_backup(source=self.source,destination=self.dest,
                                filenames=("research.jsonl","science.sqlite"))
        self.assertEqual(m["files"],2)
        independent=sqlite3.connect(self.dest/"science.sqlite")
        try:
            self.assertEqual(independent.execute("select state from events").fetchone()[0],
                             "UNRECOVERABLE_EXCLUDED")
        finally:independent.close();db.close()

    def test_CSBU05_symlinks_and_world_readable_source_blocked(self):
        (self.source/"research.jsonl").chmod(0o644)
        with self.assertRaises(CompactBackupHold):
            create_compact_backup(source=self.source,destination=self.dest,
                                  filenames=("research.jsonl",))


class SupervisorCS00(unittest.TestCase):
    def h(self,now=1000,**kwargs):
        v=dict(at_ms=now,source_frames=20,source_gaps=0,queue_depth=0,
               rss_kib=50000,free_disk_bytes=1024*1024*1024,
               last_five_minute_lag_ms=100)
        v.update(kwargs);return Heartbeat(**v)
    def test_CSSU01_health_is_not_startup_approval(self):
        x=SourceOnlySupervisor()
        self.assertEqual(x.assess(self.h())["state"],"STOPPED_OFFLINE_PRESTART_HOLD")
        self.assertFalse(x.prestart_review()["production_started"])
        self.assertFalse(x.prestart_review()["auto_restart_permitted"])
    def test_CSSU02_resource_and_new_gap_hard_hold(self):
        x=SourceOnlySupervisor();x.assess(self.h())
        z=x.assess(self.h(2000,source_frames=21,source_gaps=1,
                            queue_depth=5000,rss_kib=260000,free_disk_bytes=1))
        self.assertEqual(z["state"],"EMERGENCY_SOURCE_HOLD")
        self.assertGreaterEqual(len(z["alerts"]),4)
        self.assertFalse(z["new_virtual_admissions_allowed"])
    def test_CSSU03_emergency_stop_requires_explicit_epoch_review(self):
        x=SourceOnlySupervisor()
        y=x.emergency_stop(at_ms=100,reason="NETWORK_UNKNOWN")
        self.assertTrue(y["must_stop_source_only_intake"])
        self.assertFalse(y["restart_without_epoch_audit"])
        self.assertEqual(x.prestart_review()["state"],"EMERGENCY_SOURCE_HOLD")


if __name__=="__main__":unittest.main()
