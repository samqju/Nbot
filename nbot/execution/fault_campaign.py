"""Canonical V3.2 mechanical fault-campaign registry.

The V3 roadmap permits capital-safety fault requirements to be proven by a
physical Testnet exercise or by a deterministic equivalent.  This module keeps
that mapping explicit without adding runtime fault injection to the capital
adapter.

Runtime fault injection is intentionally absent.  Deliberately corrupting the
real Testnet order path would add a new safety-sensitive code path solely for
validation.  Instead, V3.2.3 reuses the actual Entry/Position/Reconciliation/
Emergency and Binance Testnet adapter code under deterministic exchange fault
fixtures.  V3.2.4 remains responsible for the physical lifecycle/restart
campaign where real Testnet state is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FaultCategory = Literal["ENTRY", "STOP", "EMERGENCY"]
EvidenceMode = Literal[
    "DETERMINISTIC_EQUIVALENT",
    "DETERMINISTIC_EQUIVALENT_PLUS_PHYSICAL_V3_2_4",
]


@dataclass(frozen=True, slots=True)
class MechanicalFaultRequirement:
    scenario_id: str
    category: FaultCategory
    requirement: str
    evidence_mode: EvidenceMode
    test_ids: tuple[str, ...]
    physical_followup: str | None = None

    def __post_init__(self) -> None:
        if not self.scenario_id or self.scenario_id != self.scenario_id.strip():
            raise ValueError("V3_2_FAULT_SCENARIO_ID_INVALID")
        if self.category not in {"ENTRY", "STOP", "EMERGENCY"}:
            raise ValueError("V3_2_FAULT_CATEGORY_INVALID")
        if not self.requirement or self.requirement != self.requirement.strip():
            raise ValueError("V3_2_FAULT_REQUIREMENT_INVALID")
        if self.evidence_mode not in {
            "DETERMINISTIC_EQUIVALENT",
            "DETERMINISTIC_EQUIVALENT_PLUS_PHYSICAL_V3_2_4",
        }:
            raise ValueError("V3_2_FAULT_EVIDENCE_MODE_INVALID")
        if not self.test_ids or any(not value or value != value.strip() for value in self.test_ids):
            raise ValueError("V3_2_FAULT_TEST_IDS_INVALID")
        if self.evidence_mode.endswith("PHYSICAL_V3_2_4") and not self.physical_followup:
            raise ValueError("V3_2_FAULT_PHYSICAL_FOLLOWUP_REQUIRED")


V3_2_FAULT_REQUIREMENTS: tuple[MechanicalFaultRequirement, ...] = (
    MechanicalFaultRequirement(
        "ENTRY_NETWORK_TIMEOUT_AFTER_ORDER_MAY_HAVE_REACHED",
        "ENTRY",
        "network timeout after entry order may have reached Binance",
        "DETERMINISTIC_EQUIVALENT",
        (
            "tests.test_v319_testnet.V319TransportTests.test_network_timeout_on_write_is_ambiguous",
            "tests.test_v314_entry.AmbiguousEntryTests.test_ambiguous_order_recovers_same_identity_without_second_market_order",
        ),
    ),
    MechanicalFaultRequirement(
        "ENTRY_DUPLICATE_INVOCATION",
        "ENTRY",
        "duplicate invocation cannot create a second market entry",
        "DETERMINISTIC_EQUIVALENT",
        (
            "tests.test_v314_entry.PreEntryGateTests.test_duplicate_proposal_rejected_before_exchange",
            "tests.test_v321_testnet_mechanical_canary.V321MechanicalCanaryTests.test_manual_proposal_client_is_single_use",
        ),
    ),
    MechanicalFaultRequirement(
        "ENTRY_INSUFFICIENT_BALANCE",
        "ENTRY",
        "insufficient balance/margin rejects before order submission",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PreEntryGateTests.test_insufficient_margin_rejected",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_SPREAD_FAIL",
        "ENTRY",
        "wide spread rejects before order submission",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PreEntryGateTests.test_wide_spread_rejected",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_PRICE_DRIFT_FAIL",
        "ENTRY",
        "reference-price drift rejects before order submission",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PreEntryGateTests.test_reference_drift_rejected",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_LEVERAGE_FAIL",
        "ENTRY",
        "leverage failure rejects before durable proposal reservation",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PreEntryGateTests.test_leverage_failure_rejected_before_reservation",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_QUANTIZATION_EDGE",
        "ENTRY",
        "entry quantity that quantizes outside exchange limits fails before write",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v323_fault_equivalents.V323AdapterFaultEquivalentTests.test_entry_quantity_quantization_edge_fails_before_order_write",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_POST_FILL_SLIPPAGE_BREACH",
        "ENTRY",
        "post-fill slippage breach is protected then emergency flattened",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PostFillEmergencyTests.test_post_fill_slippage_breach_is_protected_then_emergency_flattened",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_POST_FILL_NOTIONAL_BREACH",
        "ENTRY",
        "post-fill notional breach is protected then emergency flattened",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PostFillEmergencyTests.test_post_fill_notional_breach_is_protected_then_emergency_flattened",),
    ),
    MechanicalFaultRequirement(
        "ENTRY_POST_FILL_RISK_BREACH",
        "ENTRY",
        "post-fill risk breach is protected then emergency flattened",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PostFillEmergencyTests.test_post_fill_risk_breach_is_protected_then_emergency_flattened",),
    ),
    MechanicalFaultRequirement(
        "STOP_PLACEMENT_TIMEOUT",
        "STOP",
        "ambiguous stop placement that cannot resolve identity fails closed",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v323_fault_equivalents.V323AdapterFaultEquivalentTests.test_stop_placement_timeout_fails_closed_when_identity_never_appears",),
    ),
    MechanicalFaultRequirement(
        "STOP_AMBIGUOUS_PLACEMENT",
        "STOP",
        "ambiguous stop placement recovers the deterministic client identity",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v319_testnet.V319StopTests.test_ambiguous_stop_recovers_exact_client_identity",),
    ),
    MechanicalFaultRequirement(
        "STOP_DUPLICATE_IDENTITIES",
        "STOP",
        "multiple active protective stop identities fail closed",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v319_testnet.V319StopTests.test_multiple_active_stops_fail_snapshot",),
    ),
    MechanicalFaultRequirement(
        "STOP_REPLACEMENT_TIMEOUT",
        "STOP",
        "replacement timeout preserves the old known protective stop",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v323_fault_equivalents.V323AdapterFaultEquivalentTests.test_stop_replacement_timeout_preserves_old_known_protection",),
    ),
    MechanicalFaultRequirement(
        "STOP_NEW_VISIBLE_BEFORE_OLD_REMOVAL",
        "STOP",
        "new protective stop is visible before obsolete protection is removed",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v319_testnet.V319StopTests.test_replacement_places_new_before_old_cancel",),
    ),
    MechanicalFaultRequirement(
        "STOP_MISSING_AFTER_RESTART",
        "STOP",
        "restart reconciliation restores missing protection before safe continuation",
        "DETERMINISTIC_EQUIVALENT_PLUS_PHYSICAL_V3_2_4",
        ("tests.test_v316_reconciliation.StopRecoveryTests.test_missing_stop_safe_price_is_restored",),
        physical_followup="V3.2.4 restart with an OPEN Testnet position and missing stop",
    ),
    MechanicalFaultRequirement(
        "STOP_ORPHAN_AFTER_CLOSE",
        "STOP",
        "flat reconciliation removes orphan protection and verifies clean flatness",
        "DETERMINISTIC_EQUIVALENT_PLUS_PHYSICAL_V3_2_4",
        ("tests.test_v316_reconciliation.FlatTruthTests.test_flat_orphans_are_removed_before_clean_result",),
        physical_followup="V3.2.4 external/stop/manual Testnet close followed by orphan-stop reconciliation",
    ),
    MechanicalFaultRequirement(
        "EMERGENCY_UNPROTECTED_POSITION_FLATTEN",
        "EMERGENCY",
        "unprotected confirmed fill invokes verified emergency flatten and preserves journal",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v314_entry.PostFillEmergencyTests.test_stop_placement_failure_emergency_flatten_and_preserves_fill_journal",),
    ),
    MechanicalFaultRequirement(
        "EMERGENCY_FIRST_ATTEMPT_FAILS_RETRY_SUCCEEDS",
        "EMERGENCY",
        "first emergency attempt may fail while bounded retry proves flat",
        "DETERMINISTIC_EQUIVALENT",
        ("tests.test_v317_emergency.EmergencyFlattenTests.test_first_attempt_still_open_second_attempt_flattens",),
    ),
    MechanicalFaultRequirement(
        "EMERGENCY_CANNOT_PROVE_FLAT_RETAINS_CRITICAL_STATE",
        "EMERGENCY",
        "failure to prove flat remains fail-closed with durable risk state retained",
        "DETERMINISTIC_EQUIVALENT",
        (
            "tests.test_v317_emergency.EmergencyFlattenTests.test_exhausted_attempts_with_position_remaining_fails_closed",
            "tests.test_v314_entry.PostFillEmergencyTests.test_emergency_failure_preserves_inflight_and_fails_closed",
        ),
    ),
)


def validate_fault_campaign_registry() -> None:
    scenario_ids = [item.scenario_id for item in V3_2_FAULT_REQUIREMENTS]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("V3_2_FAULT_SCENARIO_DUPLICATE")
    expected = {"ENTRY": 10, "STOP": 7, "EMERGENCY": 3}
    actual = {
        category: sum(1 for item in V3_2_FAULT_REQUIREMENTS if item.category == category)
        for category in expected
    }
    if actual != expected:
        raise ValueError(f"V3_2_FAULT_SCENARIO_COUNTS_INVALID:{actual}")


def fault_campaign_summary() -> dict[str, object]:
    validate_fault_campaign_registry()
    return {
        "authority": "TESTNET_MECHANICAL_ONLY",
        "research_evidence": False,
        "runtime_fault_injection": False,
        "scenario_count": len(V3_2_FAULT_REQUIREMENTS),
        "category_counts": {
            "ENTRY": 10,
            "STOP": 7,
            "EMERGENCY": 3,
        },
        "physical_followup_scenarios": [
            item.scenario_id
            for item in V3_2_FAULT_REQUIREMENTS
            if item.evidence_mode == "DETERMINISTIC_EQUIVALENT_PLUS_PHYSICAL_V3_2_4"
        ],
    }


validate_fault_campaign_registry()
