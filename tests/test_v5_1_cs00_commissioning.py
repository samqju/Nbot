"""CS-00 source-only offline foundation, 30d planning/alerts/permission negatives."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot_v5_1.cs00_commissioning import (
    CommissioningPolicy, ArchivePlan, CommissioningHold,
    OfflineObservationRunner, write_immutable_offline_report,
    verify_immutable_offline_report)
from nbot_v5_1.core import FiveMinuteEvent,INTERVAL_MS
from nbot_v5_1.observation import ObservationBook
from test_v5_1_g2 import manifest,history,bar,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW


class CS00OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-cs00-offline-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.universe=manifest()
        self.book=ObservationBook(self.universe)
        self.runner=OfflineObservationRunner(self.book)

    def prepare(self):
        for sym in self.universe.symbols:
            self.assertTrue(self.book.bootstrap(sym,history(sym),
                                                 as_of_ms=END_DECISION))
        return self.runner.on_five_minute(
            FiveMinuteEvent(END_OPEN,END_DECISION))

    def source_dir(self):
        raw=self.root/"raw"
        raw.mkdir(mode=0o700)
        return raw

    def test_CS01_default_has_no_possible_network_or_orders(self):
        p=CommissioningPolicy().validate()
        s=self.runner.status()
        self.assertEqual((p.broad_count,p.deep_count,p.retention_planning_days),
                         (100,20,30))
        self.assertFalse(s["public_network"])
        self.assertFalse(s["running"])
        self.assertEqual(s["financial_authority"],"NONE")
        self.assertEqual(s["actual_exchange_orders"],0)
        self.assertFalse(s["deletion_allowed"])

    def test_CS02_disable_all_modes_even_if_settings_tampered(self):
        for key in ("public_network_enabled","production_service_enabled",
                    "autostart_enabled","virtual_research_enabled",
                    "paper_enabled","testnet_enabled",
                    "real_trading_enabled","model_promotion_enabled",
                    "archive_deletion_enabled","external_alerts_enabled"):
            with self.subTest(key=key):
                with self.assertRaises(CommissioningHold):
                    OfflineObservationRunner(self.book,
                                             replace(CommissioningPolicy(),
                                                     **{key:True}))

    def test_CS03_30day_target_cannot_turn_into_auto_delete(self):
        with self.assertRaises(CommissioningHold):
            ArchivePlan(retention_days_target=7).validate()
        with self.assertRaises(CommissioningHold):
            ArchivePlan(deletion_permission=True).validate()
        with self.assertRaises(CommissioningHold):
            CommissioningPolicy(retention_planning_days=90).validate()

    def test_CS04_archive_provider_unspecified_is_explicit_HOLD(self):
        x=ArchivePlan().planning_status()
        self.assertEqual(x["retention_target_days"],30)
        self.assertFalse(x["actual_offhost_archival_verified"])
        self.assertIsNone(x["illustrative_30day_bytes"])
        self.assertEqual(x["state"],
            "CS00_PROVIDER_CONFIGURATION_AND_LIVE_CAPACITY_HOLD")

    def test_CS05_nonsecret_existing_provider_profile_no_contact(self):
        x=ArchivePlan(provider_label="Existing Provider",
                      destination_type="S3_COMPATIBLE",
                      bytes_per_day_observed=123456,
                      budget_bytes=9000000).planning_status()
        self.assertEqual(x["illustrative_30day_bytes"],3703680)
        self.assertFalse(x["actual_provider_contacted"])
        self.assertFalse(x["actual_offhost_archival_verified"])

    def test_CS06_provider_profile_must_not_contain_credentials(self):
        for k,v in (("provider_label","user:password@service"),
                    ("credential_attached",True),
                    ("destination_verified",True)):
            with self.subTest(k=k),self.assertRaises(CommissioningHold):
                ArchivePlan(**{k:v}).validate()

    def test_CS07_100_market_200_direction_20deep_exact(self):
        result=self.prepare()
        self.assertEqual((result.broad,result.directions,result.deep),
                         (100,200,20))
        self.assertEqual(result.metadata_ready,100)
        self.assertEqual(result.source_held,0)
        self.assertEqual(result.action,"NO_TRADE")
        self.assertFalse(result.original_grade_witnessed)
        self.assertIn("BTCUSDT",self.runner.deep.symbols)
        self.assertEqual(self.runner.status()["event_count"],1)

    def test_CS08_genuine_source_missing_never_waived(self):
        result=self.runner.on_five_minute(
            FiveMinuteEvent(END_OPEN,END_DECISION))
        self.assertEqual(result.source_held,100)
        self.assertIn("PUBLIC_CANDLE_METADATA_SOURCE_HOLD",
                      self.runner.status()["alerts"])
        self.assertFalse(self.runner.status()["original_source_verified"])

    def test_CS09_repeated_five_minute_event_is_denied(self):
        self.prepare()
        with self.assertRaises(CommissioningHold):
            self.runner.on_five_minute(
                FiveMinuteEvent(END_OPEN,END_DECISION))
        self.assertEqual(len(self.runner.proofs),1)

    def test_CS10_smaller_than_100_never_claims_CS00_ready(self):
        with self.assertRaises(CommissioningHold):
            OfflineObservationRunner(ObservationBook(manifest(20)))

    def test_CS11_do_not_ingest_stale_bar_after_processed_event(self):
        self.prepare()
        with self.assertRaises(CommissioningHold):
            self.runner.on_closed_bar(bar("BTCUSDT",END_OPEN),
                                      decision_at_ms=END_DECISION)
        self.assertIn("STALE_CANDLE_AFTER_BOUNDARY",
                      self.runner.status()["alerts"])

    def test_CS12_gapped_new_closed_bar_sets_HOLD(self):
        self.prepare()
        t=END_DECISION+2*INTERVAL_MS
        self.assertFalse(self.runner.on_closed_bar(
            bar("BTCUSDT",END_OPEN+2*INTERVAL_MS,received=t),
            decision_at_ms=t))
        self.assertIn("BAR_GAP_OR_UNQUALIFIED",
                      self.runner.status()["alerts"])

    def test_CS13_synthetic_20x3_frames_seal_and_verify(self):
        self.prepare()
        raw=self.source_dir()
        self.runner.bind_synthetic_raw_recorder(raw)
        for sym in self.runner.deep.symbols:
            for kind in ("TRADE","QUOTE","MARK"):
                self.assertTrue(self.runner.accept_synthetic_raw(
                    kind=kind,raw=frame(kind,symbol=sym,id=8,received=NOW),
                    received_at_ms=NOW,epoch=1))
        archive=self.root/"archive"
        archive.mkdir(mode=0o700)
        evidence=self.runner.archive_locally_for_offline_test(archive)
        self.assertEqual(evidence["frames"],60)
        self.assertEqual(self.runner.status()["synthetic_frames"],60)
        self.assertFalse(self.runner.status()["archive_offhost_verified"])

    def test_CS14_raw_frame_must_follow_frozen_cohort(self):
        with self.assertRaises(CommissioningHold):
            self.runner.accept_synthetic_raw(
                kind="TRADE",raw=frame(),received_at_ms=NOW,epoch=1)
        with self.assertRaises(CommissioningHold):
            self.runner.bind_synthetic_raw_recorder(self.source_dir())

    def test_CS15_bad_original_shaped_frame_stays_HOLD(self):
        self.prepare()
        self.runner.bind_synthetic_raw_recorder(self.source_dir())
        self.assertFalse(self.runner.accept_synthetic_raw(
            kind="TRADE",raw=frame(symbol="NOTSELECTEDUSDT"),
            received_at_ms=NOW,epoch=1))
        self.assertIn("ORIGINAL_SHAPED_SYNTHETIC_SOURCE_GAP",
                      self.runner.status()["alerts"])
        self.assertFalse(self.runner.status()["original_source_verified"])

    def test_CS16_monitoring_rss_disk_queue_hold(self):
        s=self.runner.status(rss_kib=300000,
                 free_disk_bytes=2*1024*1024,source_queue_depth=5000)
        self.assertEqual(s["decision"],"HOLD")
        self.assertIn("RAM_HIGH_HOLD",s["alerts"])
        self.assertIn("FREE_DISK_RESERVE_HOLD",s["alerts"])
        self.assertIn("SOURCE_BACKPRESSURE_HOLD",s["alerts"])

    def test_CS17_monitor_does_not_push_external_notification(self):
        with patch("socket.socket",side_effect=AssertionError("SOCKET_FORBIDDEN")):
            s=self.runner.status(rss_kib=999999)
        self.assertIn("RAM_HIGH_HOLD",s["alerts"])
        self.assertFalse(self.runner.policy.external_alerts_enabled)

    def test_CS18_private_immutable_report_create_verify_no_overwrite(self):
        payload=self.runner.status()
        d=write_immutable_offline_report(
            self.root,"cs00-proof.json",payload)
        self.assertEqual(d["payload"]["mode"],
                         "OFFLINE_SYNTHETIC_FIXTURE_ONLY")
        self.assertEqual(d,verify_immutable_offline_report(
            self.root/"cs00-proof.json"))
        self.assertEqual((self.root/"cs00-proof.json").stat().st_mode&0o777,
                         0o600)
        with self.assertRaises(CommissioningHold):
            write_immutable_offline_report(
                self.root,"cs00-proof.json",payload)

    def test_CS19_modified_report_detected_not_repaired(self):
        payload=self.runner.status()
        write_immutable_offline_report(self.root,"cs00-tamper.json",payload)
        p=self.root/"cs00-tamper.json"
        content=p.read_text().replace("NO_TRADE","REAL_TRADING")
        p.write_text(content)
        with self.assertRaises(CommissioningHold):
            verify_immutable_offline_report(p)

    def test_CS20_symlink_or_world_readable_is_denied(self):
        public=self.root/"public"
        public.mkdir(mode=0o755)
        with self.assertRaises(CommissioningHold):
            write_immutable_offline_report(public,"x.json",
                                           self.runner.status())
        origin=self.root/"destination.json"
        origin.write_text("{}")
        (self.root/"linked.json").symlink_to(origin)
        with self.assertRaises(CommissioningHold):
            verify_immutable_offline_report(self.root/"linked.json")

    def test_CS21_no_false_new_paper_authority_from_report(self):
        fake=self.runner.status()
        fake["financial_authority"]="PAPER"
        with self.assertRaises(CommissioningHold):
            write_immutable_offline_report(self.root,"authority.json",fake)

    def test_CS22_policy_digest_deterministic(self):
        p=CommissioningPolicy()
        self.assertEqual(p.digest(),CommissioningPolicy().digest())
        self.assertEqual(len(p.digest()),64)

    def test_CS23_cannot_claim_live_offhost_recovery(self):
        with self.assertRaises(CommissioningHold):
            ArchivePlan(destination_verified=True).validate()

    def test_CS24_stop_instructions_present_no_launcher_method(self):
        self.assertFalse(hasattr(self.runner,"start"))
        self.assertFalse(hasattr(self.runner,"place_order"))
        self.assertFalse(hasattr(self.runner,"fetch_market"))
        self.assertFalse(hasattr(self.runner,"stop_production"))


if __name__=="__main__":
    unittest.main()
