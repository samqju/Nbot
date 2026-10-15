"""G1-02: safe configuration, evidence vocabulary, and veto-only guardian."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from nbot_v5_1.core import (
    FiveMinuteEvent, SourceEvidence, ObservationAuthority,
    ObservationDisposition, canonical_digest,
)
from nbot_v5_1.foundation import (
    FOUNDATION_SCHEMA_VERSION, RunMode, RunConfig, EvidenceGrade, ProposalSide,
    ProposalEnvelope, GuardianVerdict, inspect_proposal,
)

ROOT = Path(__file__).resolve().parents[1]


class FoundationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = FiveMinuteEvent(900_000, 1_200_000)
        self.ident = canonical_digest("intent", {"t": 900_000})

    def proposal(self, **kw):
        values = dict(event=self.event, symbol="BTCUSDT", side=ProposalSide.LONG,
                      proposal_id=self.ident, proposed_at_ms=1_200_000,
                      expires_at_ms=1_200_100)
        values.update(kw)
        return ProposalEnvelope(**values)

    def evidence(self, **kw):
        values = dict(last_closed_bar_open_ms=900_000,
                      source_max_bar_open_ms=900_000,
                      observed_at_ms=1_200_000,
                      source_digest="a" * 64, source_epoch=0,
                      route_state="HEALTHY", quality_issues=())
        values.update(kw)
        return SourceEvidence(**values)

    def test_F01_default_config_is_no_network_no_order(self):
        cfg = RunConfig()
        self.assertEqual(cfg.mode, RunMode.OFFLINE)
        self.assertFalse(cfg.network_enabled)
        self.assertFalse(cfg.order_enabled)
        self.assertEqual(FOUNDATION_SCHEMA_VERSION, "NBOT_V5_1_FOUNDATION_V1")
        with self.assertRaises(FrozenInstanceError):
            cfg.mode = RunMode.REAL

    def test_F02_future_modes_are_vocabulary_only_and_locked(self):
        for mode in (RunMode.VIRTUAL_RESEARCH, RunMode.CHAMPION_PAPER,
                     RunMode.CHALLENGER_PAPER, RunMode.REAL):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                RunConfig(mode=mode)
        self.assertEqual(RunConfig(mode=RunMode.OBSERVATION).mode,
                         RunMode.OBSERVATION)

    def test_F03_config_rejects_raw_modes_and_capability_bypass(self):
        for values in (dict(mode="OFFLINE"), dict(mode=None),
                       dict(mode=RunMode.REAL), dict(network_enabled=True),
                       dict(order_enabled=True), dict(order_enabled=1),
                       dict(network_enabled=0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                RunConfig(**values)

    def test_F04_envelope_is_frozen_and_nonexecuting(self):
        prop = self.proposal()
        self.assertEqual(prop.side, ProposalSide.LONG)
        with self.assertRaises(FrozenInstanceError):
            prop.side = ProposalSide.SHORT
        self.assertIsNone(prop.model_digest)

    def test_F05_invalid_symbol_side_or_identifier_rejected(self):
        for bad in (dict(symbol="btcUSDT"), dict(symbol="BTC-USDT"),
                    dict(symbol="BTCUSDT\n"), dict(side="LONG"),
                    dict(proposal_id="a"*63), dict(proposal_id="A"*64),
                    dict(proposal_id=None), dict(event="not_event")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.proposal(**bad)

    def test_F06_proposal_clock_rejects_preclose_future_bool_and_expiry(self):
        for bad in (dict(proposed_at_ms=1_199_999),
                    dict(proposed_at_ms=1_200_001),
                    dict(proposed_at_ms=True),
                    dict(expires_at_ms=1_199_999),
                    dict(expires_at_ms=1_200_100.0)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.proposal(**bad)

    def test_F07_grade_metadata_cannot_assert_original_or_profit(self):
        for grade in (EvidenceGrade.ORIGINAL_VERIFIED,
                      EvidenceGrade.AFTER_COST_QUALIFIED, "METADATA_ONLY", None):
            with self.subTest(grade=grade), self.assertRaises(ValueError):
                self.proposal(evidence_grade=grade)
        for grade in (EvidenceGrade.UNKNOWN, EvidenceGrade.SYNTHETIC,
                      EvidenceGrade.METADATA_ONLY):
            self.assertEqual(self.proposal(evidence_grade=grade).evidence_grade, grade)

    def test_F08_model_fingerprint_is_not_an_authorization(self):
        for bad in ("g"*64, "A"*64, "a"*63, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.proposal(model_digest=bad)
        v = inspect_proposal(RunConfig(), self.proposal(model_digest="b"*64),
                             btc=self.evidence(), symbol=self.evidence())
        self.assertIn("MODEL_ATTESTATION_UNAVAILABLE", v.reasons)
        self.assertEqual(v.authority, ObservationAuthority.NONE)
        self.assertEqual(v.disposition, ObservationDisposition.NO_TRADE)

    def test_F09_missing_proposal_never_allows_an_order(self):
        for proposal in (None, "not_proposal"):
            verdict = inspect_proposal(RunConfig(), proposal)
            self.assertEqual(verdict.authority, ObservationAuthority.NONE)
            self.assertEqual(verdict.disposition, ObservationDisposition.NO_TRADE)
            self.assertTrue("PROPOSAL_MISSING" in verdict.reasons
                            or "PROPOSAL_INVALID" in verdict.reasons)
        with self.assertRaises(ValueError):
            inspect_proposal("OFFLINE", self.proposal())

    def test_F10_btc_and_symbol_missing_or_late_sources_veto(self):
        verdict = inspect_proposal(RunConfig(), self.proposal())
        self.assertIn("BTC_MISSING", verdict.reasons)
        self.assertIn("SYMBOL_MISSING", verdict.reasons)
        stale = inspect_proposal(RunConfig(), self.proposal(),
                                 btc=self.evidence(route_state="GAP"),
                                 symbol=self.evidence(observed_at_ms=1_200_001))
        self.assertIn("BTC_ROUTE_UNHEALTHY", stale.reasons)
        self.assertIn("SYMBOL_OBSERVATION_TIME_INVALID", stale.reasons)
        self.assertEqual(stale.disposition, ObservationDisposition.NO_TRADE)

    def test_F11_expired_proposal_and_trading_directions_veto(self):
        for side in (ProposalSide.LONG, ProposalSide.SHORT, ProposalSide.NO_TRADE):
            verdict = inspect_proposal(RunConfig(), self.proposal(side=side,
                    expires_at_ms=1_200_000), btc=self.evidence(), symbol=self.evidence())
            self.assertEqual(verdict.authority, ObservationAuthority.NONE)
            self.assertIn("G1_NONTRADING_ONLY", verdict.reasons)
            if side is not ProposalSide.NO_TRADE:
                self.assertIn("TRADE_PROPOSAL_VETOED", verdict.reasons)
        # An intent created at close may already be expired by the decision clock.
        e = FiveMinuteEvent(900_000, 1_200_100)
        verdict = inspect_proposal(RunConfig(), self.proposal(event=e,
                    proposed_at_ms=1_200_000, expires_at_ms=1_200_001),
                    btc=self.evidence(), symbol=self.evidence())
        self.assertIn("PROPOSAL_EXPIRED", verdict.reasons)

    def test_F12_synthetic_or_metadata_grade_never_proves_original(self):
        for grade in (EvidenceGrade.SYNTHETIC, EvidenceGrade.METADATA_ONLY):
            result = inspect_proposal(RunConfig(), self.proposal(evidence_grade=grade),
                    btc=self.evidence(), symbol=self.evidence())
            self.assertTrue(any("ORIGINAL" in s for s in result.reasons))
            self.assertEqual(result.authority, ObservationAuthority.NONE)

    def test_F13_guardian_verdict_cannot_be_positive(self):
        for bad in (dict(authority="LIVE"), dict(disposition="BUY"),
                    dict(reasons=()), dict(reasons=("B", "A")),
                    dict(reasons=("A", "A"))):
            fields = dict(authority=ObservationAuthority.NONE,
                          disposition=ObservationDisposition.NO_TRADE,
                          reasons=("G1_NONTRADING_ONLY",))
            fields.update(bad)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                GuardianVerdict(**fields)

    def test_F15_malformed_source_object_is_vetoed_not_crashed(self):
        result = inspect_proposal(RunConfig(), self.proposal(), btc="bad-input",
                                  symbol=self.evidence())
        self.assertIn("BTC_EVIDENCE_INVALID", result.reasons)
        self.assertEqual(result.authority, ObservationAuthority.NONE)
        self.assertEqual(result.disposition, ObservationDisposition.NO_TRADE)

    def test_F14_foundation_imports_stdlib_or_relative_core_only(self):
        path = ROOT / "nbot_v5_1" / "foundation.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"__future__", "dataclasses", "enum", "re"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name in allowed for alias in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertTrue((node.level == 1 and node.module == "core")
                                or node.module in allowed)
        for forbidden in ("import binance", "import sqlite3", "subprocess",
                          "MAX_SYMBOLS", "requests", "socket", "send_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
