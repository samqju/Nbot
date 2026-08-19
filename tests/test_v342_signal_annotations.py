from __future__ import annotations

from dataclasses import replace
import json
import unittest
from unittest import mock

from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.signals import (
    ResearchSignalConfig,
    ResearchSignalError,
    ResearchSignalStore,
    SIGNAL_ANNOTATION_FIELDS,
    SIGNAL_VERSIONS,
)

from test_v341_feature_calculation import (
    INTERVAL,
    SYMBOLS,
    isolated_live_db,
    store_live,
)


EXPECTED_SIGNAL_HASHES = {
    "CSM_RANK_1H_4H_V1": "2c78dba096961624d056f06e97093691f4fb0c701ed71fd4f119a7fbba074139",
    "TSMOM_4H_VOL_ADJ_V1": "d9a3268f7807d3ae43fc08fc3b2384d553b840bd6b89175060d11d045e25bab3",
    "INTRADAY_CONDITIONAL_MOM_REV_V1": "1d7b9134cd3e89d8ece4282170bb74fe821a9f483c131e70015fc4541553367f",
}


def by_symbol_version(rows, symbol: str, signal_version: str):
    return next(
        row
        for row in rows
        if row["symbol"] == symbol and row["signal_version"] == signal_version
    )


class V342SignalDefinitionTests(unittest.TestCase):
    def test_definitions_are_frozen_v2_equivalent_and_schema_is_raw_read_only(self):
        with isolated_live_db() as db:
            target = store_live(db, 0)
            feature_store = CanonicalFeatureStore(db)
            feature_store.build(max_events=1)
            before = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            store = ResearchSignalStore(db)

            store.initialize()

            after = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            self.assertEqual(before, after)
            self.assertEqual(SIGNAL_VERSIONS, tuple(store.signal_definitions()))
            self.assertEqual(store.definition_hashes, EXPECTED_SIGNAL_HASHES)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM signal_sets").fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM signal_annotations").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM signal_builds").fetchone()[0], 0)

            with self.assertRaisesRegex(ValueError, "SIGNAL_DEFINITION_IMMUTABLE"):
                replace(ResearchSignalConfig(), csm_active_abs_score=0.70).validate()

    def test_every_feature_row_gets_all_three_annotations_even_when_inactive(self):
        with isolated_live_db() as db:
            store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            rows = ResearchSignalStore(db).compute_event_annotations(
                0,
                computed_at_ms=123_456,
            )

            self.assertEqual(len(rows), len(SYMBOLS) * len(SIGNAL_VERSIONS))
            for row in rows:
                self.assertEqual(tuple(row), SIGNAL_ANNOTATION_FIELDS)
                self.assertEqual(row["computed_at_ms"], 123_456)
                self.assertEqual(row["active"], 0)
                self.assertEqual(row["direction"], "NONE")
                self.assertEqual(row["reason"], "INSUFFICIENT_HISTORY")
            for symbol in SYMBOLS:
                self.assertEqual(
                    {row["signal_version"] for row in rows if row["symbol"] == symbol},
                    set(SIGNAL_VERSIONS),
                )


class V342SignalFormulaTests(unittest.TestCase):
    def test_v2_equivalent_signal_formulas_and_thresholds(self):
        with isolated_live_db() as db:
            for index in range(49):
                store_live(db, index)
            CanonicalFeatureStore(db).build(max_events=0)
            rows = ResearchSignalStore(db).compute_event_annotations(
                48 * INTERVAL,
                computed_at_ms=999_999,
            )

            aaa_csm = by_symbol_version(rows, "AAAUSDT", SIGNAL_VERSIONS[0])
            self.assertAlmostEqual(aaa_csm["score"], 1.0, places=12)
            self.assertEqual((aaa_csm["active"], aaa_csm["direction"]), (1, "LONG"))
            self.assertEqual(aaa_csm["reason"], "EXTREME_RANK")

            bbb_csm = by_symbol_version(rows, "BBBUSDT", SIGNAL_VERSIONS[0])
            self.assertAlmostEqual(bbb_csm["score"], -1.0, places=12)
            self.assertEqual((bbb_csm["active"], bbb_csm["direction"]), (1, "SHORT"))

            btc_csm = by_symbol_version(rows, "BTCUSDT", SIGNAL_VERSIONS[0])
            self.assertAlmostEqual(btc_csm["score"], 0.0, places=12)
            self.assertEqual((btc_csm["active"], btc_csm["direction"]), (0, "NONE"))
            self.assertEqual(btc_csm["reason"], "MIDDLE_RANK")

            aaa_tsmom = by_symbol_version(rows, "AAAUSDT", SIGNAL_VERSIONS[1])
            self.assertGreater(aaa_tsmom["score"], 0.50)
            self.assertEqual((aaa_tsmom["active"], aaa_tsmom["direction"]), (1, "LONG"))
            self.assertEqual(aaa_tsmom["reason"], "VOL_ADJUSTED_TREND")

            bbb_tsmom = by_symbol_version(rows, "BBBUSDT", SIGNAL_VERSIONS[1])
            self.assertLess(bbb_tsmom["score"], -0.50)
            self.assertEqual((bbb_tsmom["active"], bbb_tsmom["direction"]), (1, "SHORT"))

            aaa_intraday = by_symbol_version(rows, "AAAUSDT", SIGNAL_VERSIONS[2])
            self.assertEqual(
                (aaa_intraday["active"], aaa_intraday["direction"], aaa_intraday["reason"]),
                (1, "LONG", "BROAD_UP_AND_LEADER"),
            )
            self.assertEqual(json.loads(aaa_intraday["metadata_json"])["mode"], "MOMENTUM")

            bbb_intraday = by_symbol_version(rows, "BBBUSDT", SIGNAL_VERSIONS[2])
            self.assertEqual(
                (bbb_intraday["active"], bbb_intraday["direction"], bbb_intraday["reason"]),
                (0, "NONE", "NO_CONDITION"),
            )


class V342SignalBuildAuditTests(unittest.TestCase):
    def test_build_is_atomic_raw_read_only_and_rebuild_digest_stable(self):
        with isolated_live_db() as db:
            for index in range(3):
                store_live(db, index)
            feature_store = CanonicalFeatureStore(db)
            feature_store.build(max_events=0)
            store = ResearchSignalStore(db)
            before_raw = db.audit(now_ms=4 * INTERVAL, record=False)["evidence_digest"]
            with db.connection() as conn:
                feature_rows_before = conn.execute(
                    "SELECT COUNT(*) FROM canonical_features"
                ).fetchone()[0]
                feature_builds_before = conn.execute(
                    "SELECT COUNT(*) FROM feature_builds"
                ).fetchone()[0]

            first = store.build(max_events=1)

            after_raw = db.audit(now_ms=4 * INTERVAL, record=False)["evidence_digest"]
            self.assertEqual(before_raw, after_raw)
            self.assertEqual(first.feature_events, 3)
            self.assertEqual(first.pending_before, 3)
            self.assertEqual(first.built_events, 1)
            self.assertEqual(first.signal_annotations, len(SYMBOLS) * len(SIGNAL_VERSIONS))
            with db.connection() as conn:
                build_before = conn.execute(
                    """
                    SELECT built_at_ms, source_digest, signal_digest
                    FROM signal_builds WHERE event_open_ms=0
                    """
                ).fetchone()
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM canonical_features").fetchone()[0], feature_rows_before)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM feature_builds").fetchone()[0], feature_builds_before)
                computed_before = conn.execute(
                    "SELECT computed_at_ms FROM signal_annotations ORDER BY symbol, signal_version LIMIT 1"
                ).fetchone()[0]

            second = store.build(max_events=1)
            self.assertEqual(second.built_events, 1)
            self.assertEqual(second.pending_before, 2)

            with mock.patch(
                "nbot.observation.signals.time.time",
                return_value=(computed_before + 10_000) / 1000,
            ):
                rebuilt = store.build(max_events=1, rebuild=True)
            self.assertEqual(rebuilt.built_events, 1)
            with db.connection() as conn:
                build_after = conn.execute(
                    """
                    SELECT built_at_ms, source_digest, signal_digest
                    FROM signal_builds WHERE event_open_ms=0
                    """
                ).fetchone()
                computed_after = conn.execute(
                    """
                    SELECT computed_at_ms FROM signal_annotations
                    WHERE event_open_ms=0 ORDER BY symbol, signal_version LIMIT 1
                    """
                ).fetchone()[0]
            self.assertEqual(build_before[1:], build_after[1:])
            self.assertNotEqual(computed_before, computed_after)

            audit = store.audit()
            self.assertTrue(audit["healthy"])
            self.assertEqual(audit["built_events"], 2)
            self.assertEqual(audit["unbuilt_events"], 1)

    def test_audit_detects_feature_source_mutation(self):
        with isolated_live_db() as db:
            target = store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            store = ResearchSignalStore(db)
            store.build(max_events=1)

            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE canonical_features
                    SET close_price=close_price + 1.0
                    WHERE event_open_ms=? AND symbol='AAAUSDT'
                    """,
                    (target,),
                )

            audit = store.audit()
            self.assertFalse(audit["healthy"])
            self.assertFalse(audit["feature_audit_healthy"])
            self.assertEqual(audit["source_digest_mismatches"], 1)

    def test_audit_detects_signal_annotation_tampering(self):
        with isolated_live_db() as db:
            target = store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            store = ResearchSignalStore(db)
            store.build(max_events=1)

            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE signal_annotations
                    SET reason='TAMPERED'
                    WHERE event_open_ms=? AND symbol='AAAUSDT'
                      AND signal_version=?
                    """,
                    (target, SIGNAL_VERSIONS[0]),
                )

            audit = store.audit()
            self.assertFalse(audit["healthy"])
            self.assertEqual(audit["signal_digest_mismatches"], 1)
            self.assertEqual(audit["source_digest_mismatches"], 0)

    def test_audit_detects_signal_definition_tampering_without_repair(self):
        with isolated_live_db() as db:
            store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            store = ResearchSignalStore(db)
            store.build(max_events=1)

            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE signal_sets SET definition_hash=?
                    WHERE signal_version=?
                    """,
                    ("0" * 64, SIGNAL_VERSIONS[0]),
                )

            audit = store.audit()
            self.assertFalse(audit["healthy"])
            self.assertEqual(audit["signal_definition_mismatches"], 1)
            with self.assertRaisesRegex(
                ResearchSignalError,
                "SIGNAL_DEFINITION_HASH_MISMATCH",
            ):
                store.initialize()
            with db.connection() as conn:
                stored = conn.execute(
                    """
                    SELECT definition_hash FROM signal_sets
                    WHERE signal_version=?
                    """,
                    (SIGNAL_VERSIONS[0],),
                ).fetchone()[0]
            self.assertEqual(stored, "0" * 64)


if __name__ == "__main__":
    unittest.main()
