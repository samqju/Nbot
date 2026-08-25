"""V3.9.4 immutable market-regime evidence over compact research memory.

The regime taxonomy is frozen from the governance-epoch pre-cutoff audit and is
Observation-only.  It creates companion artifacts for *finalized* challenger
windows; it never rewrites challenger evaluations or V3.9.3 rolling reports and
never exposes active-window regime distributions before the final window closes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import statistics
from typing import Any

from .challengers import (
    AUTHORITY,
    CHALLENGER_PREFIX,
    EVALUATION_PREFIX,
    FINAL_EVALUATION_STATUSES,
    MODEL_PREFIX,
)
from .governance import ELIGIBILITY_EPOCH_KEY
from .research_memory import ResearchMemoryStore
from .selection import _f, _ridge_score


REGIME_VERSION = "V39_MARKET_REGIME_EVIDENCE_V1"
CONTRACT_KEY = f"v39:market-regime:contract:{REGIME_VERSION}"
REPORT_PREFIX = "v39:market-regime:report:"


@dataclass(frozen=True)
class MarketRegimeConfig:
    regime_version: str = REGIME_VERSION
    calibration_cutoff_event_ms: int = 1_787_581_200_000
    calibration_event_count: int = 480

    # Frozen from the pre-cutoff audit supplied before V3.9.4 implementation.
    btc_ret_1h_bear_q25: float = -0.001699781383127985
    btc_ret_1h_bull_q75: float = 0.0029015525037671686
    median_market_ret_1h_bear_q25: float = -0.004072190941042553
    median_market_ret_1h_bull_q75: float = 0.004806672864879125
    breadth_risk_off_q25: float = 0.29203199507768035
    breadth_risk_on_q75: float = 0.7292235288115706

    realized_vol_1h_low_q25: float = 0.010481341275716888
    realized_vol_1h_high_q75: float = 0.013203273069951154
    realized_vol_1h_shock_q95: float = 0.0164711382188941
    sudden_move_abs_median_market_ret_5m: float = 0.0035

    # Funding had no pre-cutoff variation (all event medians were 0.00005).
    # Use semantic absolute thresholds and explicitly report missing coverage.
    funding_low_max: float = 0.0
    funding_high_min: float = 0.0001

    quote_volume_low_q25: float = 15_859_610.058798864
    quote_volume_high_q75: float = 17_276_024.720867142
    spread_tight_q25_pct: float = 0.02559823908438957
    spread_wide_q75_pct: float = 0.02837391607812728

    min_regime_events_for_economic_summary: int = 3
    catastrophic_regime_mean_r: float = -1.0

    def validate(self) -> None:
        if self.regime_version != REGIME_VERSION:
            raise ValueError("NBOT_V394_REGIME_VERSION_IMMUTABLE")
        if self.calibration_cutoff_event_ms != 1_787_581_200_000:
            raise ValueError("NBOT_V394_CALIBRATION_CUTOFF_IMMUTABLE")
        if self.calibration_event_count != 480:
            raise ValueError("NBOT_V394_CALIBRATION_EVENT_COUNT_IMMUTABLE")
        if not self.btc_ret_1h_bear_q25 < self.btc_ret_1h_bull_q75:
            raise ValueError("NBOT_V394_BTC_TREND_THRESHOLDS_INVALID")
        if not self.median_market_ret_1h_bear_q25 < self.median_market_ret_1h_bull_q75:
            raise ValueError("NBOT_V394_MARKET_TREND_THRESHOLDS_INVALID")
        if not 0.0 <= self.breadth_risk_off_q25 < self.breadth_risk_on_q75 <= 1.0:
            raise ValueError("NBOT_V394_BREADTH_THRESHOLDS_INVALID")
        if not 0.0 < self.realized_vol_1h_low_q25 < self.realized_vol_1h_high_q75 < self.realized_vol_1h_shock_q95:
            raise ValueError("NBOT_V394_VOLATILITY_THRESHOLDS_INVALID")
        if self.sudden_move_abs_median_market_ret_5m != 0.0035:
            raise ValueError("NBOT_V394_SHOCK_MOVE_THRESHOLD_IMMUTABLE")
        if not self.funding_low_max < self.funding_high_min:
            raise ValueError("NBOT_V394_FUNDING_THRESHOLDS_INVALID")
        if not self.quote_volume_low_q25 < self.quote_volume_high_q75:
            raise ValueError("NBOT_V394_VOLUME_THRESHOLDS_INVALID")
        if not self.spread_tight_q25_pct < self.spread_wide_q75_pct:
            raise ValueError("NBOT_V394_SPREAD_THRESHOLDS_INVALID")
        if self.min_regime_events_for_economic_summary != 3:
            raise ValueError("NBOT_V394_REGIME_SAMPLE_IMMUTABLE")
        if self.catastrophic_regime_mean_r != -1.0:
            raise ValueError("NBOT_V394_REGIME_FLOOR_IMMUTABLE")


CONFIG = MarketRegimeConfig()
CONFIG.validate()


REQUIRED_CATEGORIES: dict[str, tuple[str, ...]] = {
    "trend": ("BULLISH_TREND", "BEARISH_TREND", "SIDEWAYS_CHOP"),
    "volatility": ("LOW", "NORMAL", "HIGH", "SHOCK"),
    "breadth": ("RISK_ON", "BALANCED", "RISK_OFF"),
    "funding": ("LOW", "NORMAL", "HIGH"),
    "liquidity": ("HIGH", "NORMAL", "LOW"),
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _median(values: list[float]) -> float:
    if not values:
        raise RuntimeError("NBOT_V394_MEDIAN_EMPTY")
    return float(statistics.median(values))


def _event_context(record: dict[str, Any]) -> dict[str, float]:
    longs = [row for row in record["examples"] if str(row.get("side")) == "LONG"]
    if not longs:
        raise RuntimeError(f"NBOT_V394_LONG_EXAMPLE_MISSING:{record['event_open_ms']}")
    vectors = [json.loads(str(row["feature_vector_json"])) for row in longs]
    broad_fields = (
        "btc_ret_5m_side",
        "btc_ret_1h_side",
        "btc_ret_4h_side",
        "breadth_5m_side",
        "breadth_1h_side",
        "median_ret_5m_side",
        "median_ret_1h_side",
    )
    first = vectors[0]
    for field in broad_fields:
        values = [float(vector[field]) for vector in vectors]
        if max(values) - min(values) > 1e-12:
            raise RuntimeError(
                f"NBOT_V394_BROAD_MARKET_CONTEXT_NOT_INVARIANT:{record['event_open_ms']}:{field}"
            )
    return {
        "btc_ret_5m": float(first["btc_ret_5m_side"]),
        "btc_ret_1h": float(first["btc_ret_1h_side"]),
        "btc_ret_4h": float(first["btc_ret_4h_side"]),
        "breadth_positive_5m": (float(first["breadth_5m_side"]) + 1.0) / 2.0,
        "breadth_positive_1h": (float(first["breadth_1h_side"]) + 1.0) / 2.0,
        "median_market_ret_5m": float(first["median_ret_5m_side"]),
        "median_market_ret_1h": float(first["median_ret_1h_side"]),
        "median_realized_vol_1h": _median([float(vector["realized_vol_1h"]) for vector in vectors]),
        "median_funding_rate": _median([float(vector["funding_rate_side"]) for vector in vectors]),
        "median_quote_volume_24h_usd": _median([
            math.expm1(float(vector["log_quote_volume_24h"])) for vector in vectors
        ]),
        "median_spread_pct": _median([float(vector["spread_pct"]) for vector in vectors]),
    }


def classify_context(context: dict[str, float], config: MarketRegimeConfig = CONFIG) -> dict[str, str]:
    config.validate()
    bull_votes = sum((
        context["btc_ret_1h"] >= config.btc_ret_1h_bull_q75,
        context["median_market_ret_1h"] >= config.median_market_ret_1h_bull_q75,
        context["breadth_positive_1h"] >= config.breadth_risk_on_q75,
    ))
    bear_votes = sum((
        context["btc_ret_1h"] <= config.btc_ret_1h_bear_q25,
        context["median_market_ret_1h"] <= config.median_market_ret_1h_bear_q25,
        context["breadth_positive_1h"] <= config.breadth_risk_off_q25,
    ))
    if bull_votes >= 2 and bear_votes == 0:
        trend = "BULLISH_TREND"
    elif bear_votes >= 2 and bull_votes == 0:
        trend = "BEARISH_TREND"
    else:
        trend = "SIDEWAYS_CHOP"

    vol = context["median_realized_vol_1h"]
    sudden = abs(context["median_market_ret_5m"]) >= config.sudden_move_abs_median_market_ret_5m
    if sudden or vol >= config.realized_vol_1h_shock_q95:
        volatility = "SHOCK"
    elif vol <= config.realized_vol_1h_low_q25:
        volatility = "LOW"
    elif vol >= config.realized_vol_1h_high_q75:
        volatility = "HIGH"
    else:
        volatility = "NORMAL"

    breadth = context["breadth_positive_1h"]
    if breadth >= config.breadth_risk_on_q75:
        breadth_regime = "RISK_ON"
    elif breadth <= config.breadth_risk_off_q25:
        breadth_regime = "RISK_OFF"
    else:
        breadth_regime = "BALANCED"

    funding = context["median_funding_rate"]
    if funding <= config.funding_low_max:
        funding_regime = "LOW"
    elif funding >= config.funding_high_min:
        funding_regime = "HIGH"
    else:
        funding_regime = "NORMAL"

    quote_volume = context["median_quote_volume_24h_usd"]
    spread = context["median_spread_pct"]
    if quote_volume >= config.quote_volume_high_q75 and spread <= config.spread_tight_q25_pct:
        liquidity = "HIGH"
    elif quote_volume <= config.quote_volume_low_q25 and spread >= config.spread_wide_q75_pct:
        liquidity = "LOW"
    else:
        liquidity = "NORMAL"

    return {
        "trend": trend,
        "volatility": volatility,
        "breadth": breadth_regime,
        "funding": funding_regime,
        "liquidity": liquidity,
    }


class MarketRegimeEvidence:
    """Create immutable V3.9.4 companion reports for finalized windows only."""

    def __init__(self, memory: ResearchMemoryStore, *, config: MarketRegimeConfig = CONFIG) -> None:
        self.memory = memory
        self.config = config
        self.config.validate()

    def _calibration_records(self) -> list[dict[str, Any]]:
        rows = [
            record for record in self.memory.iter_event_records()
            if int(record["event_open_ms"]) <= self.config.calibration_cutoff_event_ms
        ]
        if len(rows) != self.config.calibration_event_count:
            raise RuntimeError(
                f"NBOT_V394_CALIBRATION_EVENT_COUNT_MISMATCH:{len(rows)}"
            )
        if not rows or int(rows[-1]["event_open_ms"]) != self.config.calibration_cutoff_event_ms:
            raise RuntimeError("NBOT_V394_CALIBRATION_CUTOFF_NOT_LATEST_PRE_CUTOFF_EVENT")
        return rows

    def _calibration_evidence(self) -> dict[str, Any]:
        records = self._calibration_records()
        contexts = [_event_context(record) for record in records]
        funding_values = sorted({context["median_funding_rate"] for context in contexts})
        source_digest = _digest([
            [
                int(record["event_open_ms"]),
                str(record["archive_digest"]),
                str(record["training_digest"]),
            ]
            for record in records
        ])
        categories: dict[str, dict[str, int]] = {dimension: {} for dimension in REQUIRED_CATEGORIES}
        for context in contexts:
            regime = classify_context(context, self.config)
            for dimension, value in regime.items():
                categories[dimension][value] = categories[dimension].get(value, 0) + 1
        return {
            "calibration_cutoff_event_ms": self.config.calibration_cutoff_event_ms,
            "calibration_event_count": len(records),
            "calibration_source_digest": source_digest,
            "funding_unique_event_medians": len(funding_values),
            "funding_variation_status": (
                "INSUFFICIENT_VARIATION" if len(funding_values) < 2 else "VARIATION_OBSERVED"
            ),
            "observed_regime_counts": categories,
        }

    def contract(self) -> dict[str, Any]:
        evidence = self._calibration_evidence()
        return {
            "regime_version": self.config.regime_version,
            "record_type": "MARKET_REGIME_CONTRACT",
            "authority": AUTHORITY,
            "source_rule": "THRESHOLDS_FROZEN_FROM_PRE_GOVERNANCE_CUTOFF_AUDIT_ONLY",
            "calibration": evidence,
            "trend": {
                "method": "TWO_OF_THREE_BTC_1H_MARKET_MEDIAN_1H_BREADTH_1H",
                "btc_bear_q25": self.config.btc_ret_1h_bear_q25,
                "btc_bull_q75": self.config.btc_ret_1h_bull_q75,
                "market_bear_q25": self.config.median_market_ret_1h_bear_q25,
                "market_bull_q75": self.config.median_market_ret_1h_bull_q75,
                "breadth_risk_off_q25": self.config.breadth_risk_off_q25,
                "breadth_risk_on_q75": self.config.breadth_risk_on_q75,
                "categories": list(REQUIRED_CATEGORIES["trend"]),
            },
            "volatility": {
                "realized_vol_low_q25": self.config.realized_vol_1h_low_q25,
                "realized_vol_high_q75": self.config.realized_vol_1h_high_q75,
                "realized_vol_shock_q95": self.config.realized_vol_1h_shock_q95,
                "sudden_move_abs_median_market_ret_5m": self.config.sudden_move_abs_median_market_ret_5m,
                "categories": list(REQUIRED_CATEGORIES["volatility"]),
            },
            "breadth": {
                "risk_off_max": self.config.breadth_risk_off_q25,
                "risk_on_min": self.config.breadth_risk_on_q75,
                "categories": list(REQUIRED_CATEGORIES["breadth"]),
            },
            "funding": {
                "low_max": self.config.funding_low_max,
                "high_min": self.config.funding_high_min,
                "calibration_variation_status": evidence["funding_variation_status"],
                "rule": "SEMANTIC_ABSOLUTE_THRESHOLDS_BECAUSE_PRE_CUTOFF_MEDIAN_FUNDING_WAS_CONSTANT",
                "categories": list(REQUIRED_CATEGORIES["funding"]),
            },
            "liquidity": {
                "high_requires_quote_volume_min": self.config.quote_volume_high_q75,
                "high_requires_spread_max_pct": self.config.spread_tight_q25_pct,
                "low_requires_quote_volume_max": self.config.quote_volume_low_q25,
                "low_requires_spread_min_pct": self.config.spread_wide_q75_pct,
                "categories": list(REQUIRED_CATEGORIES["liquidity"]),
            },
            "window_rule": "ONLY_FINALIZED_CHALLENGER_TEST_EVENTS_RECEIVE_PERSISTED_REGIME_REPORTS",
            "active_window_visibility": "HIDDEN_UNTIL_FINAL_EVALUATION",
            "historical_window_rule": "COMPANION_REPORT_ONLY_NEVER_REWRITES_IMMUTABLE_EVALUATION",
            "pre_governance_window_policy": "DESCRIPTIVE_AUDIT_ONLY_EXCLUDED_FROM_RESEARCH_CHAMPION_ELIGIBILITY",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    @property
    def contract_hash(self) -> str:
        return _digest(self.contract())

    def _eligibility_cutoff(self) -> int | None:
        record = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        if record is None:
            return None
        return int(record["payload"]["minimum_training_cutoff_event_ms"])

    @staticmethod
    def _select_event(model: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
        scored = [(_ridge_score(model, str(row["feature_vector_json"])), row) for row in examples]
        if not scored:
            raise RuntimeError("NBOT_V394_EVENT_EXAMPLES_EMPTY")
        scored.sort(key=lambda item: (-item[0], str(item[1]["symbol"]), str(item[1]["side"])))
        score, row = scored[0]
        traded = float(score) > 0.0
        return {
            "score": float(score),
            "traded": traded,
            "symbol": str(row["symbol"]),
            "side": str(row["side"]),
            "event_net_r": _f(row["target_net_r"]) if traded else 0.0,
        }

    def _report_payload(
        self,
        evaluation_record: dict[str, Any],
        challenger_record: dict[str, Any],
        model_record: dict[str, Any],
    ) -> dict[str, Any]:
        evaluation = evaluation_record["payload"]
        challenger = challenger_record["payload"]
        model_payload = model_record["payload"]
        if str(evaluation.get("status")) not in FINAL_EVALUATION_STATUSES:
            raise RuntimeError("NBOT_V394_NONFINAL_EVALUATION_REPORT_FORBIDDEN")
        if int(challenger["training_cutoff_event_ms"]) != int(evaluation["training_cutoff_event_ms"]):
            raise RuntimeError("NBOT_V394_CHALLENGER_EVALUATION_CUTOFF_MISMATCH")
        test_events = [int(value) for value in evaluation["test_events"]]
        wanted = set(test_events)
        records = {
            int(record["event_open_ms"]): record
            for record in self.memory.iter_event_records(after_event_ms=int(evaluation["training_cutoff_event_ms"]))
            if int(record["event_open_ms"]) in wanted
        }
        if set(records) != wanted:
            raise RuntimeError("NBOT_V394_FINAL_TEST_EVENT_RECORD_MISSING")
        model = model_payload["model"]
        dimensions: dict[str, dict[str, list[dict[str, Any]]]] = {
            dimension: {} for dimension in REQUIRED_CATEGORIES
        }
        event_rows = []
        for event in test_events:
            record = records[event]
            context = _event_context(record)
            regime = classify_context(context, self.config)
            selected = self._select_event(model, record["examples"])
            event_row = {
                "event_open_ms": event,
                "regime": regime,
                "traded": bool(selected["traded"]),
                "event_net_r": float(selected["event_net_r"]),
            }
            event_rows.append(event_row)
            for dimension, category in regime.items():
                dimensions[dimension].setdefault(category, []).append(event_row)

        def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
            values = [float(row["event_net_r"]) for row in rows]
            traded_values = [float(row["event_net_r"]) for row in rows if row["traded"]]
            return {
                "events": len(rows),
                "trade_events": len(traded_values),
                "mean_event_net_r": statistics.fmean(values) if values else None,
                "mean_traded_net_r": statistics.fmean(traded_values) if traded_values else None,
            }

        breakdown = {
            dimension: {
                category: group_summary(rows)
                for category, rows in sorted(groups.items())
            }
            for dimension, groups in dimensions.items()
        }
        coverage = {}
        covered_economic_groups = []
        for dimension, required in REQUIRED_CATEGORIES.items():
            groups = dimensions[dimension]
            observed = sorted(groups)
            missing = [category for category in required if category not in groups]
            max_concentration = (
                max(len(rows) for rows in groups.values()) / len(test_events)
                if groups and test_events else None
            )
            coverage[dimension] = {
                "observed_categories": observed,
                "missing_categories": missing,
                "max_category_concentration": max_concentration,
                "complete": not missing,
            }
            covered_economic_groups.extend(
                rows for rows in groups.values()
                if len(rows) >= self.config.min_regime_events_for_economic_summary
            )
        no_catastrophe = all(
            statistics.fmean([float(row["event_net_r"]) for row in rows])
            > self.config.catastrophic_regime_mean_r
            for rows in covered_economic_groups
        )
        epoch_cutoff = self._eligibility_cutoff()
        training_cutoff = int(evaluation["training_cutoff_event_ms"])
        source_digest = _digest([
            [event, str(records[event]["archive_digest"]), str(records[event]["training_digest"])]
            for event in test_events
        ])
        return {
            "regime_version": self.config.regime_version,
            "record_type": "FINAL_WINDOW_MARKET_REGIME_COMPANION",
            "challenger_version": str(evaluation["challenger_version"]),
            "model_version": str(evaluation["model_version"]),
            "status": str(evaluation["status"]),
            "training_cutoff_event_ms": training_cutoff,
            "test_events": len(test_events),
            "test_start_event_ms": min(test_events) if test_events else None,
            "test_end_event_ms": max(test_events) if test_events else None,
            "immutable_evaluation_digest": str(evaluation["evaluation_digest"]),
            "immutable_evaluation_artifact_digest": str(evaluation_record["artifact_digest"]),
            "challenger_artifact_digest": str(challenger_record["artifact_digest"]),
            "model_artifact_digest": str(model_record["artifact_digest"]),
            "regime_contract_hash": self.contract_hash,
            "source_digest": source_digest,
            "breakdown": breakdown,
            "coverage": coverage,
            "covered_economic_regime_groups": len(covered_economic_groups),
            "no_catastrophic_covered_regime": no_catastrophe,
            "eligibility_epoch_cutoff_event_ms": epoch_cutoff,
            "eligibility_counting_window": bool(epoch_cutoff is not None and training_cutoff >= epoch_cutoff),
            "active_window_distribution_exposed": False,
            "historical_final_test_mutable": False,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def _expected_reports(self) -> list[dict[str, Any]]:
        challengers = {
            str(record["payload"]["challenger_version"]): record
            for record in self.memory.list_artifacts(prefix=CHALLENGER_PREFIX)
        }
        models = {
            str(record["payload"]["model_version"]): record
            for record in self.memory.list_artifacts(prefix=MODEL_PREFIX)
        }
        reports = []
        for evaluation_record in self.memory.list_artifacts(prefix=EVALUATION_PREFIX):
            evaluation = evaluation_record["payload"]
            if str(evaluation.get("status")) not in FINAL_EVALUATION_STATUSES:
                continue
            challenger = challengers.get(str(evaluation["challenger_version"]))
            model = models.get(str(evaluation["model_version"]))
            if challenger is None or model is None:
                raise RuntimeError("NBOT_V394_ARTIFACT_REFERENCE_MISSING")
            reports.append(self._report_payload(evaluation_record, challenger, model))
        reports.sort(key=lambda report: (
            int(report.get("test_end_event_ms") or -1), str(report["challenger_version"])
        ))
        return reports

    @staticmethod
    def _aggregate_coverage(reports: list[dict[str, Any]]) -> dict[str, Any]:
        eligible = [report for report in reports if report.get("eligibility_counting_window") is True]
        categories: dict[str, dict[str, int]] = {dimension: {} for dimension in REQUIRED_CATEGORIES}
        total_events = 0
        for report in eligible:
            total_events += int(report["test_events"])
            for dimension, groups in report["breakdown"].items():
                for category, row in groups.items():
                    categories[dimension][category] = categories[dimension].get(category, 0) + int(row["events"])
        dimensions = {}
        for dimension, required in REQUIRED_CATEGORIES.items():
            observed = sorted(categories[dimension])
            missing = [category for category in required if category not in categories[dimension]]
            max_concentration = (
                max(categories[dimension].values()) / total_events
                if total_events and categories[dimension] else None
            )
            dimensions[dimension] = {
                "observed_categories": observed,
                "missing_categories": missing,
                "event_counts": dict(sorted(categories[dimension].items())),
                "max_category_concentration": max_concentration,
                "complete": not missing,
            }
        return {
            "eligibility_counting_final_windows": len(eligible),
            "eligibility_counting_test_events": total_events,
            "dimensions": dimensions,
            "all_required_market_regimes_observed": bool(dimensions) and all(
                row["complete"] for row in dimensions.values()
            ),
            "coverage_policy": "MONITOR_AS_AVAILABLE_DO_NOT_MANUFACTURE_UNOBSERVED_REGIMES",
        }

    def sync(self) -> dict[str, Any]:
        contract = self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        reports = self._expected_reports()
        for report in reports:
            self.memory.persist_artifact(REPORT_PREFIX + str(report["challenger_version"]), report)
        return {
            "regime_version": self.config.regime_version,
            "contract_hash": self.contract_hash,
            "contract_artifact_digest": contract["artifact_digest"],
            "final_window_reports_synced": len(reports),
            "coverage": self._aggregate_coverage(reports),
            "active_window_regime_distribution": "HIDDEN_UNTIL_FINAL_EVALUATION",
            "authority": AUTHORITY,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    def status(self) -> dict[str, Any]:
        contract_record = self.memory.artifact(CONTRACT_KEY)
        reports = [record["payload"] for record in self.memory.list_artifacts(prefix=REPORT_PREFIX)]
        reports.sort(key=lambda report: (
            int(report.get("test_end_event_ms") or -1), str(report["challenger_version"])
        ))
        return {
            "regime_version": self.config.regime_version,
            "contract_initialized": contract_record is not None,
            "contract_hash": self.contract_hash,
            "calibration": self._calibration_evidence(),
            "final_window_reports": len(reports),
            "latest_final_window_regime_report": None if not reports else reports[-1],
            "coverage": self._aggregate_coverage(reports),
            "active_window_regime_distribution": "HIDDEN_UNTIL_FINAL_EVALUATION",
            "authority": AUTHORITY,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    def audit(self) -> dict[str, Any]:
        report = {
            "regime_version": self.config.regime_version,
            "authority": AUTHORITY,
            "contract_missing_or_mismatch": 0,
            "final_report_missing_or_mismatch": 0,
            "authority_mismatch": 0,
            "active_window_exposure_violation": 0,
            "immutable_evaluation_reference_mismatch": 0,
        }
        contract = self.memory.artifact(CONTRACT_KEY)
        expected_contract = self.contract()
        if contract is None or contract["payload"] != expected_contract:
            report["contract_missing_or_mismatch"] += 1
        expected = self._expected_reports()
        stored = {
            str(record["payload"].get("challenger_version")): record["payload"]
            for record in self.memory.list_artifacts(prefix=REPORT_PREFIX)
        }
        final_versions = {str(row["challenger_version"]) for row in expected}
        for row in expected:
            version = str(row["challenger_version"])
            if stored.get(version) != row:
                report["final_report_missing_or_mismatch"] += 1
            if row.get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1
            evaluation = self.memory.artifact(EVALUATION_PREFIX + version)
            if evaluation is None or str(evaluation["payload"].get("evaluation_digest")) != str(row["immutable_evaluation_digest"]):
                report["immutable_evaluation_reference_mismatch"] += 1
        for version, row in stored.items():
            if version not in final_versions:
                report["active_window_exposure_violation"] += 1
            if row.get("active_window_distribution_exposed") is not False:
                report["active_window_exposure_violation"] += 1
        report["healthy"] = all(
            int(value) == 0
            for key, value in report.items()
            if key not in {"regime_version", "authority", "healthy"}
        )
        return report
