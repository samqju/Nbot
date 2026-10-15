"""G1-01: T01–T12 offline safety contract; no market/account access."""

from __future__ import annotations

import ast
import builtins
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from nbot_v5_1 import __version__
from nbot_v5_1 import core
from nbot_v5_1.core import (
    CORE_SCHEMA_VERSION, INTERVAL_MS, FiveMinuteEvent, SourceEvidence,
    ObservationAuthority, ObservationDisposition, canonical_digest,
    evidence_hold_reasons,
)

ROOT = Path(__file__).resolve().parents[1]


def valid_evidence(event: FiveMinuteEvent, **overrides: object) -> SourceEvidence:
    values = dict(
        last_closed_bar_open_ms=event.event_open_ms,
        source_max_bar_open_ms=event.event_open_ms,
        observed_at_ms=event.event_close_ms,
        source_digest="a" * 64,
        source_epoch=0,
        route_state="HEALTHY",
        quality_issues=(),
    )
    values.update(overrides)
    return SourceEvidence(**values)


class CoreOfflineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.event = FiveMinuteEvent(900_000, 1_200_000)

    def test_T01_import_has_no_application_io_or_order_side_effects(self) -> None:
        """Imports must not open files for writing, use network, SQL or spawn."""
        real_open = builtins.open

        def no_writes(file: object, mode: str = "r", *args: object, **kwargs: object):
            if any(flag in mode for flag in "wax+"):
                raise AssertionError("application write attempted during import")
            return real_open(file, mode, *args, **kwargs)

        with (patch.object(builtins, "open", side_effect=no_writes),
              patch.object(socket, "socket", side_effect=AssertionError("socket")),
              patch.object(sqlite3, "connect", side_effect=AssertionError("sqlite")),
              patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")),
              patch.object(os, "system", side_effect=AssertionError("os.system"))):
            importlib.reload(core)
            self.assertEqual(core.ObservationAuthority.NONE.value, "NONE")
        # reload() creates fresh class objects; keep later tests on those types.
        globals().update({name: getattr(core, name) for name in (
            "FiveMinuteEvent", "SourceEvidence", "ObservationAuthority",
            "ObservationDisposition", "evidence_hold_reasons", "canonical_digest",
        )})
        self.assertNotIn("nbot", sys.modules)

    def test_T02_version_identity_and_no_startup(self) -> None:
        self.assertEqual(__version__, "5.1.0")
        self.assertEqual(CORE_SCHEMA_VERSION, "NBOT_V5_1_CORE_V1")
        self.assertEqual(INTERVAL_MS, 300_000)
        self.assertEqual(FiveMinuteEvent.__module__, "nbot_v5_1.core")
        self.assertNotIn("nbot", sys.modules)
        self.assertFalse(hasattr(core, "start"))
        self.assertFalse(hasattr(core, "run"))

    def test_T03_closed_candle_and_exact_decision_boundary(self) -> None:
        exact = FiveMinuteEvent(0, 300_000)
        self.assertEqual(exact.event_close_ms, 300_000)
        delayed = FiveMinuteEvent(300_000, 900_001)
        self.assertEqual(delayed.event_close_ms, 600_000)
        self.assertEqual(self.event.event_close_ms, 1_200_000)
        with self.assertRaises(FrozenInstanceError):
            exact.event_open_ms = 300_000

    def test_T04_reject_invalid_clocks_and_future_metadata(self) -> None:
        bad_events = [
            (True, 300_000), (0.0, 300_000), (-300_000, 0),
            (1, 300_001), (0, True), (0, 300_000.0),
            (0, 299_999), (0, -1), (None, 300_000),
        ]
        for opening, decision in bad_events:
            with self.subTest(opening=opening, decision=decision):
                with self.assertRaises(ValueError):
                    FiveMinuteEvent(opening, decision)
        future = valid_evidence(self.event, observed_at_ms=1_200_001)
        self.assertIn("BTC_OBSERVATION_TIME_INVALID",
                      evidence_hold_reasons(self.event, future, prefix="BTC"))
        malformed = valid_evidence(self.event, observed_at_ms=True)
        self.assertIn("BTC_INVALID_TIMESTAMPS",
                      evidence_hold_reasons(self.event, malformed, prefix="BTC"))
        misaligned = valid_evidence(self.event, source_max_bar_open_ms=900_001)
        self.assertIn("BTC_INVALID_TIMESTAMPS",
                      evidence_hold_reasons(self.event, misaligned, prefix="BTC"))

    def test_T05_missing_stale_future_unknown_source_fail_closed(self) -> None:
        self.assertEqual(evidence_hold_reasons(self.event, None, prefix="BTC"),
                         ("BTC_MISSING",))
        self.assertEqual(evidence_hold_reasons(self.event, None, prefix="SYMBOL"),
                         ("SYMBOL_MISSING",))
        cases = (
            (dict(route_state="GAP"), "BTC_ROUTE_UNHEALTHY"),
            (dict(route_state="UNKNOWN"), "BTC_ROUTE_UNHEALTHY"),
            (dict(route_state="CONNECTED"), "BTC_ROUTE_INVALID"),
            (dict(source_epoch=None), "BTC_SOURCE_EPOCH_INVALID"),
            (dict(source_epoch=-1), "BTC_SOURCE_EPOCH_INVALID"),
            (dict(source_epoch=True), "BTC_SOURCE_EPOCH_INVALID"),
            (dict(last_closed_bar_open_ms=600_000), "BTC_CANDLE_MISSING_OR_STALE"),
            (dict(source_max_bar_open_ms=600_000), "BTC_SOURCE_NOT_ASOF_EVENT"),
            (dict(source_max_bar_open_ms=1_200_000), "BTC_SOURCE_FUTURE"),
            (dict(last_closed_bar_open_ms=1_200_000), "BTC_CANDLE_FUTURE"),
            (dict(source_digest=None), "BTC_SOURCE_DIGEST_MISSING"),
        )
        for overrides, code in cases:
            with self.subTest(issue=code, source=overrides):
                reasons = evidence_hold_reasons(
                    self.event, valid_evidence(self.event, **overrides), prefix="BTC"
                )
                self.assertIn(code, reasons)
        self.assertEqual(evidence_hold_reasons(
            self.event, valid_evidence(self.event), prefix="BTC"), ())

    def test_T06_digest_never_proves_original_market_custody(self) -> None:
        evidence = valid_evidence(self.event, source_digest=None)
        self.assertIn("BTC_SOURCE_DIGEST_MISSING",
                      evidence_hold_reasons(self.event, evidence, prefix="BTC"))
        for invalid in ("A" * 64, "deadbeef", "x" * 64, False, 123):
            with self.subTest(invalid=invalid):
                self.assertIn("SYMBOL_SOURCE_DIGEST_INVALID", evidence_hold_reasons(
                    self.event, valid_evidence(self.event, source_digest=invalid),
                    prefix="SYMBOL"))
        valid = valid_evidence(self.event)
        self.assertFalse(hasattr(valid, "verified_original"))
        self.assertFalse(hasattr(valid, "qualified_after_cost"))
        self.assertFalse(hasattr(core, "qualify_economic_outcome"))
        self.assertEqual(ObservationAuthority.NONE.value, "NONE")

    def test_T07_versioned_domain_separated_deterministic_ids(self) -> None:
        first = {"b": ["BTCUSDT", "ETHUSDT"], "a": 900_000}
        reordered = {"a": 900_000, "b": ["BTCUSDT", "ETHUSDT"]}
        one = canonical_digest("event", first)
        self.assertEqual(one, canonical_digest("event", reordered))
        self.assertRegex(one, r"\A[0-9a-f]{64}\Z")
        self.assertNotEqual(one, canonical_digest("evidence", first))
        self.assertNotEqual(one, canonical_digest("event", {"a": 1}))
        canonical = json.dumps(
            {"schema": CORE_SCHEMA_VERSION, "domain": "event", "payload": first},
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        self.assertEqual(one, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        self.assertNotEqual(one, hashlib.sha256(json.dumps(
            first, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")).hexdigest())
        for invalid_domain in ("", "trade", "LIVE", 1, None):
            with self.subTest(domain=invalid_domain):
                with self.assertRaises(ValueError):
                    canonical_digest(invalid_domain, first)

    def test_T08_no_float_nan_coercion_or_unserializable_payload(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf"), 1.0,
                      {"x": 0.1}, object(), ("tuple",), {1: "key"}):
            with self.subTest(payload=str(type(value))):
                with self.assertRaises(ValueError):
                    canonical_digest("intent", value)
        recursive: list[object] = []
        recursive.append(recursive)
        with self.assertRaises(ValueError):
            canonical_digest("event", recursive)
        self.assertEqual(len(canonical_digest("intent", {"valid": [None, True, 1]})), 64)

    def test_T09_reasons_are_sorted_unique_and_checked(self) -> None:
        ev = valid_evidence(
            self.event, route_state="GAP",
            quality_issues=("QUOTE_GAP", "CANDLE_GAP", "QUOTE_GAP"),
        )
        expected = ("SYMBOL_CANDLE_GAP", "SYMBOL_QUOTE_GAP",
                    "SYMBOL_ROUTE_UNHEALTHY")
        self.assertEqual(evidence_hold_reasons(self.event, ev, prefix="SYMBOL"), expected)
        self.assertEqual(evidence_hold_reasons(self.event, ev, prefix="SYMBOL"), expected)
        for bad_prefix in ("", "btc", "BTC-EXAMPLE", "FOO\n", True):
            with self.subTest(prefix=bad_prefix):
                with self.assertRaises(ValueError):
                    evidence_hold_reasons(self.event, ev, prefix=bad_prefix)
        malformed = valid_evidence(self.event, quality_issues=("bad input",))
        self.assertIn("BTC_QUALITY_ISSUES_INVALID",
                      evidence_hold_reasons(self.event, malformed, prefix="BTC"))

    def test_T10_nontrading_default_and_no_order_interface(self) -> None:
        self.assertEqual({x.value for x in ObservationAuthority}, {"NONE"})
        self.assertEqual({x.value for x in ObservationDisposition},
                         {"OBSERVE_ONLY", "HOLD", "NO_TRADE"})
        for name in ("buy", "sell", "submit_order", "place_order", "execute_trade",
                     "binance_client", "approve_paper", "send_order", "unlock_live"):
            self.assertFalse(hasattr(core, name), name)
        self.assertNotIn("LIVE", ObservationAuthority.__members__)
        self.assertNotIn("PAPER", ObservationAuthority.__members__)

    def test_T11_static_stdlib_imports_without_legacy_schema_or_sql(self) -> None:
        source = (ROOT / "nbot_v5_1" / "core.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"__future__", "dataclasses", "enum", "hashlib", "json", "re"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name in allowed for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
        for forbidden in ("MAX_SYMBOLS", "NBOT_V5_CANDIDATE_OBSERVATION_V2",
                          "CREATE TABLE", "sqlite3", "source_epochs", "ws_contract"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("nbot", sys.modules)
        self.assertFalse(hasattr(core, "initialize_candidate_ledger"))
        self.assertFalse(hasattr(core, "append_candidate_records"))

    def test_T12_synthetic_offline_repeatability_without_file_writes(self) -> None:
        self.assertTrue(sys.dont_write_bytecode)
        before = tuple(sorted(p.name for p in ROOT.iterdir()))
        ev = FiveMinuteEvent(0, INTERVAL_MS)
        healthy = valid_evidence(ev)
        for _ in range(50):
            self.assertEqual(evidence_hold_reasons(ev, healthy, prefix="BTC"), ())
            self.assertEqual(canonical_digest("event", {"t": 0}),
                             canonical_digest("event", {"t": 0}))
        after = tuple(sorted(p.name for p in ROOT.iterdir()))
        self.assertEqual(before, after)
        self.assertFalse(hasattr(core, "open"))
        self.assertFalse(hasattr(core, "connect"))


if __name__ == "__main__":
    unittest.main()
