from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.observation.challengers import AUTHORITY, ContinuousChallengerCycle
from nbot.observation.governance import ModelGovernanceRegistry
from nbot.observation.market_regimes import (
    CONFIG,
    CONTRACT_KEY,
    REPORT_PREFIX,
    MarketRegimeEvidence,
    classify_context,
)
from nbot.observation.research_memory import LEDGER_COLUMNS, RIDGE_COLUMNS, ResearchMemoryStore
from nbot.observation.retention import ARCHIVE_VERSION, _encode_training_rows
from nbot.observation.selection import FEATURE_VECTOR_NAMES, RidgeSufficientStatistics, SELECTION_CONFIG, _digest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class V394MarketRegimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.memory = ResearchMemoryStore(root / "research_memory.db")
        self.memory.initialize(generation="TEST_V394", generation_floor_ms=0)
        self.governance = ModelGovernanceRegistry(self.memory, root / "model_artifacts")
        self.regimes = MarketRegimeEvidence(self.memory)
        self.release_sha = "c" * 40
        self.state = RidgeSufficientStatistics.empty()
        self.next_event = CONFIG.calibration_cutoff_event_ms - (CONFIG.calibration_event_count - 1) * 300_000

    def tearDown(self):
        self.tmp.cleanup()

    def _feature_vector(self, side: str) -> str:
        vector = {name: 0.0 for name in FEATURE_VECTOR_NAMES}
        sign = 1.0 if side == "LONG" else -1.0
        vector["side_sign"] = sign
        vector["atr14_frac"] = 0.01
        vector["realized_vol_1h"] = 0.012
        vector["log_quote_volume_24h"] = math.log1p(16_500_000.0)
        vector["spread_pct"] = 0.027
        vector["funding_rate_side"] = 0.00005 * sign
        vector["btc_ret_5m_side"] = 0.0
        vector["btc_ret_1h_side"] = 0.0
        vector["btc_ret_4h_side"] = 0.0
        vector["breadth_5m_side"] = 0.0
        vector["breadth_1h_side"] = 0.0
        vector["median_ret_5m_side"] = 0.0
        vector["median_ret_1h_side"] = 0.0
        return canonical(vector)

    def _event_rows(self, event: int, *, target: float = -1.0):
        rows = []
        for symbol, side in (("AAAUSDT", "LONG"), ("ZZZUSDT", "SHORT")):
            rows.append({
                "event_open_ms": event,
                "symbol": symbol,
                "side": side,
                "feature_vector_json": self._feature_vector(side),
                "target_net_r": target,
                "target_net_return_frac": target * 0.01,
                "target_mfe_r": max(0.5, target if target > 0 else 0.5),
                "target_mae_r": 1.0,
                "source_policy_result_digest": f"policy-{event}-{symbol}-{side}",
                "source_feature_digest": f"feature-{event}",
                "source_signal_digest": f"signal-{event}",
                "example_digest": f"example-{event}-{symbol}-{side}",
            })
        return rows

    def _append_events(self, count: int, *, target: float = -1.0):
        ledger = []
        for _ in range(count):
            event = self.next_event
            self.next_event += 300_000
            rows = self._event_rows(event, target=target)
            blob, training_digest, raw_bytes = _encode_training_rows(rows)
            selector_summary = {}
            policy_summary = {}
            build_manifest = {}
            archive_digest = digest_text(canonical({
                "archive_version": ARCHIVE_VERSION,
                "event_open_ms": event,
                "selector_summary": selector_summary,
                "policy_summary": policy_summary,
                "build_manifest": build_manifest,
                "training_digest": training_digest,
                "example_row_count": len(rows),
            }))
            row = (
                event, ARCHIVE_VERSION, event + 1, len(rows),
                "ZLIB_CANONICAL_JSON_V1", blob, training_digest, raw_bytes,
                len(blob), canonical(selector_summary), canonical(policy_summary),
                canonical(build_manifest), archive_digest, AUTHORITY,
            )
            self.assertEqual(len(row), len(LEDGER_COLUMNS))
            ledger.append(row)
            self.state.add_event(event, rows)
        self.memory.import_ledger_rows(ledger, source_generation="TEST_V394")
        payload = self.state.to_payload()
        ridge_row = (
            SELECTION_CONFIG.lab_version,
            SELECTION_CONFIG.learned_selector_version,
            self.state.through_event_ms,
            self.state.event_count,
            self.state.row_count,
            canonical(payload),
            _digest(payload),
            self.next_event,
        )
        self.assertEqual(len(ridge_row), len(RIDGE_COLUMNS))
        self.memory.replace_ridge_state(ridge_row)

    def test_taxonomy_classifies_required_extremes(self):
        bullish = classify_context({
            "btc_ret_1h": 0.01,
            "median_market_ret_1h": 0.01,
            "breadth_positive_1h": 0.9,
            "median_realized_vol_1h": 0.02,
            "median_market_ret_5m": 0.005,
            "median_funding_rate": 0.0002,
            "median_quote_volume_24h_usd": 30_000_000.0,
            "median_spread_pct": 0.02,
        })
        self.assertEqual(bullish, {
            "trend": "BULLISH_TREND",
            "volatility": "SHOCK",
            "breadth": "RISK_ON",
            "funding": "HIGH",
            "liquidity": "HIGH",
        })
        bearish = classify_context({
            "btc_ret_1h": -0.01,
            "median_market_ret_1h": -0.01,
            "breadth_positive_1h": 0.1,
            "median_realized_vol_1h": 0.009,
            "median_market_ret_5m": -0.001,
            "median_funding_rate": -0.00001,
            "median_quote_volume_24h_usd": 10_000_000.0,
            "median_spread_pct": 0.04,
        })
        self.assertEqual(bearish, {
            "trend": "BEARISH_TREND",
            "volatility": "LOW",
            "breadth": "RISK_OFF",
            "funding": "LOW",
            "liquidity": "LOW",
        })

    def test_contract_requires_exact_pre_cutoff_480_event_calibration(self):
        self._append_events(CONFIG.calibration_event_count)
        contract = self.regimes.contract()
        calibration = contract["calibration"]
        self.assertEqual(calibration["calibration_event_count"], 480)
        self.assertEqual(calibration["calibration_cutoff_event_ms"], CONFIG.calibration_cutoff_event_ms)
        self.assertEqual(calibration["funding_unique_event_medians"], 1)
        self.assertEqual(calibration["funding_variation_status"], "INSUFFICIENT_VARIATION")
        self.assertEqual(contract["active_window_visibility"], "HIDDEN_UNTIL_FINAL_EVALUATION")
        self.assertFalse(contract["automatic_promotion"])

    def test_pre_governance_final_gets_companion_but_is_excluded_from_eligibility(self):
        # First challenger freezes 40 events before the V3.9.4 calibration cutoff.
        self._append_events(440, target=-1.0)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        first = cycle.cycle()
        self.assertEqual(first["action"], "TRAIN")
        self._append_events(40, target=-1.0)
        final = cycle.cycle()
        self.assertEqual(final["action"], "EVALUATE_FINAL_AND_TRAIN_NEXT")
        self.assertEqual(final["next_challenger"]["training_cutoff_event_ms"], CONFIG.calibration_cutoff_event_ms)

        # Governance starts only after the first final, matching production history.
        self.governance.sync()
        synced = self.regimes.sync()
        self.assertEqual(synced["final_window_reports_synced"], 1)
        status = self.regimes.status()
        self.assertEqual(status["final_window_reports"], 1)
        report = status["latest_final_window_regime_report"]
        self.assertFalse(report["eligibility_counting_window"])
        self.assertFalse(report["historical_final_test_mutable"])
        self.assertEqual(report["coverage"]["funding"]["observed_categories"], ["NORMAL"])
        self.assertIn("LOW", report["coverage"]["funding"]["missing_categories"])
        self.assertIn("HIGH", report["coverage"]["funding"]["missing_categories"])
        self.assertEqual(status["coverage"]["eligibility_counting_final_windows"], 0)
        self.assertFalse(status["coverage"]["all_required_market_regimes_observed"])
        self.assertEqual(status["active_window_regime_distribution"], "HIDDEN_UNTIL_FINAL_EVALUATION")
        self.assertTrue(self.regimes.audit()["healthy"])
        self.assertIsNotNone(self.memory.artifact(CONTRACT_KEY))
        self.assertIsNotNone(self.memory.artifact(REPORT_PREFIX + final["evaluation"]["challenger_version"]))

    def test_active_challenger_never_gets_persisted_regime_report(self):
        self._append_events(CONFIG.calibration_event_count)
        cycle = ContinuousChallengerCycle(self.memory, release_sha=self.release_sha)
        trained = cycle.cycle()
        self.governance.sync()
        self.regimes.sync()
        self.assertIsNone(self.memory.artifact(REPORT_PREFIX + trained["challenger_version"]))
        status = self.regimes.status()
        self.assertEqual(status["final_window_reports"], 0)
        self.assertEqual(status["active_window_regime_distribution"], "HIDDEN_UNTIL_FINAL_EVALUATION")
        self.assertTrue(self.regimes.audit()["healthy"])

    def test_admin_parser_exposes_market_regime_commands(self):
        parser = nbot_admin.build_parser()
        for command in ("market-regime-sync", "market-regime-status", "market-regime-audit"):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
