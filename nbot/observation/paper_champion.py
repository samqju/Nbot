"""V3.9.6A frozen Paper Champion acceptance contract.

This module freezes the long-term LIVE/PAPER evidence gate before any V3.9
Research Champion is allowed to collect evidence toward PAPER_CHAMPION.  It is
Observation-only governance metadata.  It does not promote a Research Champion,
does not mutate recommendation authority, and has no Execution/order imports.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from .challengers import AUTHORITY
from .governance import CHAMPION_POINTER_GENESIS_KEY

CHAMPION_POINTER_PREFIX = "v39:registry:champion-pointer:"
from .market_regimes import CONTRACT_KEY as MARKET_REGIME_CONTRACT_KEY
from .operational_regimes import CONTRACT_KEY as OPERATIONAL_REGIME_CONTRACT_KEY
from .research_memory import ResearchMemoryStore


VERSION = "V39_PAPER_CHAMPION_GATE_V1"
CONTRACT_KEY = f"v39:paper-champion:contract:{VERSION}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PaperChampionGateConfig:
    version: str = VERSION
    min_completed_paper_trades: int = 150
    min_independent_market_events: int = 100
    min_elapsed_days: int = 30
    min_distinct_utc_dates: int = 20
    bootstrap_samples: int = 2000
    confidence_level: float = 0.95
    max_drawdown_r: float = 5.0
    max_losing_streak: int = 5
    recent_trade_window: int = 30
    min_recent_average_net_r: float = 0.0
    max_symbol_concentration: float = 0.25
    max_date_concentration: float = 0.20
    max_regime_concentration: float = 0.70
    min_observed_trend_regimes: int = 2
    min_observed_volatility_regimes: int = 2
    min_observed_liquidity_regimes: int = 2
    max_mean_operational_degradation_r: float = 0.10
    min_median_winner_capture: float = 0.50

    def validate(self) -> None:
        expected = PaperChampionGateConfig()
        if self != expected:
            raise ValueError("NBOT_V396_PAPER_CHAMPION_GATE_CONTRACT_IMMUTABLE")


CONFIG = PaperChampionGateConfig()
CONFIG.validate()


class PaperChampionGate:
    """Read-only status around an immutable predeclared V3.9.6 gate."""

    def __init__(self, memory: ResearchMemoryStore, *, config: PaperChampionGateConfig = CONFIG) -> None:
        self.memory = memory
        self.config = config
        self.config.validate()

    def contract(self) -> dict[str, Any]:
        thresholds = asdict(self.config)
        thresholds.pop("version", None)
        return {
            "version": VERSION,
            "roadmap_scope": "V3.9.6_PAPER_CHAMPION",
            "authority": AUTHORITY,
            "freeze_rule": "THRESHOLDS_FROZEN_BEFORE_ANY_RESEARCH_CHAMPION_LIVE_PAPER_EVIDENCE_COUNTS",
            "sample_basis": "V1_50_PERCENT_CANARY_REFERENCE_150_TRADES_100_INDEPENDENT_EVENTS_STRENGTHENED_FOR_V3",
            "thresholds": thresholds,
            "economic_gates": {
                "after_cost_expectancy": "MARKET_EVENT_BOOTSTRAP_MEAN_CI_LOW_GT_0",
                "recent_expectancy": "LAST_30_COMPLETED_PAPER_TRADES_MEAN_NET_R_GT_0",
                "drawdown": "MAX_DRAWDOWN_R_LE_5",
                "losing_streak": "MAX_CONSECUTIVE_LOSSES_LE_5",
                "selection_quality": "LINKED_RESEARCH_CHAMPION_MUST_HAVE_BEAT_FROZEN_WEAK_BASELINES",
                "winner_capture": "MEDIAN_WINNER_CAPTURE_GE_0_50",
                "operational_degradation": "MEAN_EXPECTED_MINUS_ACTUAL_PAPER_R_LE_0_10",
            },
            "concentration_gates": {
                "symbol": "MAX_SHARE_LE_0_25",
                "utc_date": "MAX_SHARE_LE_0_20",
                "market_regime": "MAX_SHARE_LE_0_70",
                "trend_regimes_observed": "AT_LEAST_2",
                "volatility_regimes_observed": "AT_LEAST_2",
                "liquidity_regimes_observed": "AT_LEAST_2",
                "funding": "MONITOR_AS_AVAILABLE_DO_NOT_MANUFACTURE_VARIATION",
            },
            "operational_gates": {
                "drift": "MONITORED",
                "safety_defect": "NONE_UNRESOLVED",
                "testnet_regression": "CURRENT_RELEASE_PASS_REQUIRED_BEFORE_FINAL_JUDGMENT",
                "operational_regimes": "V3_9_5_LEDGER_REVIEW_REQUIRED",
                "automatic_rollback": "PROVE_IF_ENABLED",
            },
            "research_prerequisite": "CURRENT_RESEARCH_CHAMPION_POINTER_REQUIRED",
            "paper_evidence_start_rule": "ONLY_EVIDENCE_AFTER_RESEARCH_CHAMPION_ACTIVATION_MAY_COUNT",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    @property
    def contract_hash(self) -> str:
        return _digest(self.contract())

    def sync(self) -> dict[str, Any]:
        stored = self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        return {
            "version": VERSION,
            "contract_hash": self.contract_hash,
            "contract_artifact_digest": stored["artifact_digest"],
            "status": self.status(),
        }

    def _research_champion_pointer(self) -> dict[str, Any] | None:
        records = self.memory.list_artifacts(prefix=CHAMPION_POINTER_PREFIX)
        if not records:
            record = self.memory.artifact(CHAMPION_POINTER_GENESIS_KEY)
            return None if record is None else record["payload"]
        records.sort(key=lambda row: (
            int(row["payload"].get("generation", -1)),
            int(row["recorded_at_ms"]),
            str(row["artifact_key"]),
        ))
        return records[-1]["payload"]

    def status(self) -> dict[str, Any]:
        contract_record = self.memory.artifact(CONTRACT_KEY)
        pointer = self._research_champion_pointer()
        champion = None if pointer is None else pointer.get("current_research_champion")
        if champion is None:
            decision = "WAIT_FOR_RESEARCH_CHAMPION"
            evidence_collection = "BLOCKED_NO_RESEARCH_CHAMPION"
        else:
            decision = "READY_TO_BEGIN_CONTROLLED_LIVE_PAPER_EVIDENCE"
            evidence_collection = "REQUIRES_SEPARATE_V3_9_6_ACTIVATION_GATE"
        return {
            "version": VERSION,
            "contract_initialized": contract_record is not None,
            "contract_hash": self.contract_hash,
            "thresholds": asdict(self.config),
            "research_champion": champion,
            "decision": decision,
            "paper_evidence_collection": evidence_collection,
            "paper_evidence_counted": 0,
            "market_regime_contract_initialized": self.memory.artifact(MARKET_REGIME_CONTRACT_KEY) is not None,
            "operational_regime_contract_initialized": self.memory.artifact(OPERATIONAL_REGIME_CONTRACT_KEY) is not None,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def audit(self) -> dict[str, Any]:
        stored = self.memory.artifact(CONTRACT_KEY)
        expected = self.contract()
        status = self.status()
        report = {
            "version": VERSION,
            "authority": AUTHORITY,
            "contract_missing_or_mismatch": int(stored is None or stored["payload"] != expected),
            "premature_paper_champion": int(status.get("paper_champion_authority") is not False),
            "premature_execution_authority": int(status.get("execution_authority") != "NONE"),
            "premature_evidence_count": int(int(status.get("paper_evidence_counted", 0)) != 0),
            "automatic_promotion_violation": int(status.get("automatic_promotion") is not False),
        }
        report["healthy"] = all(
            value == 0 for key, value in report.items()
            if key not in {"version", "authority", "healthy"}
        )
        return report
