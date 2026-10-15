"""G11 offline whole-loop adapter. All paths are synthetic and non-executable.

This does not supply market data, keys, paper releases, or an order client.
Original source/economic/scientific gates stay HOLD on every code path.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

from .core import FiveMinuteEvent, ObservationAuthority
from .observation import ObservationBook
from .exploration import explore_event, ExplorationBatch, ExplorationRow
from .deep_selection import choose_deep, DeepManifest
from .research_book import VirtualResearchBook, SyntheticTick, VirtualTerminal
from .research_intent import FrozenIntent
from .learning_contract import (LearningRow, lab_row, assemble_lab,
                                verified_learning_count, canonical)
from .learning_science import quality_report
from .training_lab import (LabProtocol, train_lab, evaluate_frozen_lab,
                           require_authorized_champion, TrainingHold)
from .challenger_lab import DualBookCompetition, SharedLabEvent
from .paper_contract import PaperHold


class IntegrationHold(ValueError):
    pass


def _hash(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def _regime(value: str) -> str:
    if value in ("UP", "UPTREND"):
        return "UP"
    if value in ("DOWN", "DOWNTREND"):
        return "DOWN"
    if value in ("RANGE", "FLAT", "MIXED", "SIDEWAYS"):
        return "RANGE"
    if value == "TRANSITION":
        return "TRANSITION"
    return "UNAVAILABLE"


@dataclass(frozen=True)
class BoundaryProof:
    event_open_ms: int
    snapshot_sha: str
    exploration_sha: str
    deep_sha: str
    universe_count: int
    direction_count: int
    deep_count: int
    capacity_before: int
    admitted: int
    capacity_after: int
    source_held_directions: int
    evaluated_directions: int
    source_grade: str = "SYNTHETIC_OFFLINE_TEST_ONLY"
    financial_authority: str = "NONE"
    action: str = "NO_TRADE"


@dataclass(frozen=True)
class ScienceProof:
    synthetic_rows: int
    genuine_original_rows: int
    pending_rows: int
    lab_model_sha: str | None
    scientific_model_authority: str = "NONE"
    release_action: str = "HOLD"


class OfflineIntegratedPipeline:
    """Compose existing contracts, never start a service or authorize trading.

    Five-minute event: G2->G3->G4->G5, conditional expensive Exploration.
    Between events: incremental G5 source/path updates only.
    Settlements: G5->G7 pending or explicitly SYNTHETIC modeled G6 costs.
    Offline review: G7->G8 lab with real model release veto.
    Paper-like event: G9->G10 two-book LAB, never genuine PAPER.
    """

    def __init__(self, observation: ObservationBook,
                 research: VirtualResearchBook,
                 competition: DualBookCompetition | None = None):
        if (type(observation) is not ObservationBook or
                type(research) is not VirtualResearchBook or
                (competition is not None and type(competition) is not DualBookCompetition)):
            raise IntegrationHold("G11_ONLY_VERIFIED_OFFLINE_COMPONENTS")
        self.observation = observation
        self.research = research
        self.competition = competition
        self.last_event: FiveMinuteEvent | None = None
        self.last_deep: DeepManifest | None = None
        self.history: list[BoundaryProof] = []
        self._origins: dict[str, tuple[FrozenIntent, ExplorationRow, ExplorationBatch,
                                       DeepManifest, str]] = {}
        self._processed: set[str] = set()
        self.learning_rows: list[LearningRow] = []
        self._lab_events: set[str] = set()

    def on_five_minute(self, event: FiveMinuteEvent, *,
                       supplier: Callable[[], tuple[FrozenIntent, ...]] | None = None,
                       plan_factory: Callable[[DeepManifest, ExplorationBatch],
                                              tuple[FrozenIntent, ...]] | None = None,
                       evaluation_limit: int = 200) -> BoundaryProof:
        if supplier is not None and plan_factory is not None:
            raise IntegrationHold("G11_AMBIGUOUS_PLAN_PROVIDER")
        if type(event) is not FiveMinuteEvent or (
            self.last_event is not None
            and event.event_open_ms <= self.last_event.event_open_ms
        ):
            raise IntegrationHold("G11_EVENT_NOT_NEW_CLOSED_BOUNDARY")
        if len(self.observation.manifest.symbols) != 100:
            raise IntegrationHold("G11_BROAD_MUST_BE_100")
        snapshot = self.observation.snapshot(event)
        capacity = self.research.vacancies
        # With no entry capacity G3 records 200 skipped evaluations, never
        # invents a NO_MATCH for an unevaluated detector.
        batch = explore_event(self.observation, event,
                              capacity_slots=capacity,
                              evaluation_limit=evaluation_limit)
        deep = choose_deep(self.observation.manifest, batch, count=20)
        if (len(snapshot.rows) != 100 or len(batch.rows) != 200
                or len(deep.symbols) != 20 or "BTCUSDT" not in deep.symbols
                or not deep.no_trade or any(x.source_grade !=
                       "WARMUP_HOLD_NOT_ORIGINAL_VERIFIED" for x in deep.entries)
                or any(x.authority != ObservationAuthority.NONE
                       for x in batch.rows)):
            raise IntegrationHold("G11_PIPELINE_SOURCE_OR_AUTHORITY_BREACH")
        # Build plans only AFTER actual G3/G4 contracts have frozen the
        # current event, and only when G5 has genuine capacity. This avoids
        # the caller repeating expensive G3 and protects the two-clock design.
        provider = (lambda: plan_factory(deep, batch)) if plan_factory else supplier
        result = self.research.review(event, deep, provider)
        if (result.capacity_after > 40 or result.openings > capacity or
                result.decision_denominator != 40 or
                result.no_trading_authority != "NONE"):
            raise IntegrationHold("G11_RESEARCH_CAPACITY_OR_AUTHORITY_BREACH")
        # Record source-linked actual G5 intents, not just their count.
        index = {(r.symbol, r.side): r for r in batch.rows}
        for path in self.research.active.values():
            p = path.intent
            if p.intent_id in self._origins:
                continue
            row = index.get((p.symbol, p.side))
            if (p.event_open_ms != event.event_open_ms or row is None
                    or row.status != "OBSERVED"
                    or p.cohort_sha != deep.manifest_sha
                    or p.source_grade != "SYNTHETIC_OFFLINE_TEST_ONLY"
                    or p.financial_authority != "NONE"):
                raise IntegrationHold("G11_UNLINKED_RESEARCH_ADMISSION")
            self._origins[p.intent_id] = (p, row, batch, deep,
                                          self.observation.manifest.selection_digest)
        proof = BoundaryProof(event.event_open_ms, snapshot.snapshot_id,
                              batch.batch_id, deep.manifest_sha,
                              len(snapshot.rows), len(batch.rows),
                              len(deep.symbols), result.capacity_before,
                              result.openings, result.capacity_after,
                              batch.source_skipped_pairs, batch.evaluated_pairs)
        self.history.append(proof)
        self.last_event = event
        self.last_deep = deep
        return proof

    def on_synthetic_tick(self, tick: SyntheticTick) -> tuple[VirtualTerminal, ...]:
        if self.last_event is None or type(tick) is not SyntheticTick:
            raise IntegrationHold("G11_TICK_OUTSIDE_SYNTHETIC_RUN")
        if (tick.source_grade != "SYNTHETIC_OFFLINE_TEST_ONLY"
                or tick.financial_authority != "NONE"):
            raise IntegrationHold("G11_ORIGINAL_TICK_FORGERY")
        terminal = self.research.ingest(tick)
        if any(t.qualified_net_return is not None or
               t.economic_state != "COST_PENDING_UNQUALIFIED" or
               t.financial_authority != "NONE" for t in terminal):
            raise IntegrationHold("G11_PRICE_ONLY_NOT_ECONOMIC_PROOF")
        return terminal

    def record_synthetic_outcome(self, terminal: VirtualTerminal, *,
                                 modeled_net_r: str | None = None) -> LearningRow:
        """G5->G7. A modeled R is a declared synthetic *fixture*, never a fill.

        Omit modeled_net_r when quote/fee/funding are unavailable, as they are
        in the normal G5 path. Such outcomes stay COST_PENDING and unscored.
        """
        if (type(terminal) is not VirtualTerminal
                or terminal.intent_id in self._processed
                or terminal.intent_id not in self._origins
                or self.research.closed.get(terminal.intent_id) != terminal
                or terminal.path_grade != "SYNTHETIC_PATH_ONLY_NOT_EXECUTABLE"
                or terminal.qualified_net_return is not None):
            raise IntegrationHold("G11_OUTCOME_ORIGIN_OR_REPLAY_INVALID")
        p, row, batch, deep, universe_sha = self._origins[terminal.intent_id]
        if (modeled_net_r is not None and
                (type(modeled_net_r) is not str or len(modeled_net_r) > 30)):
            raise IntegrationHold("G11_SYNTHETIC_COST_FIXTURE_INVALID")
        state = "SYNTHETIC_MODELED" if modeled_net_r is not None else "COST_PENDING"
        lineage = tuple(sorted((
            ("g2", universe_sha),
            ("g3", batch.batch_id),
            ("g4", deep.manifest_sha),
            ("g5", p.intent_id),
            ("g6", _hash({"model": "synthetic-cost-only", "net": modeled_net_r})),
            ("cost", _hash({"grade": "SYNTHETIC_NOT_EXECUTABLE",
                             "net": modeled_net_r})),
            ("path", _hash(terminal.__dict__)),
            ("policy", _hash({"fees": p.fee_policy,
                              "slippage": p.slippage_policy,
                              "funding": p.funding_policy})),
        )))
        learning = lab_row(
            experiment_id=terminal.intent_id, event_ms=p.event_open_ms,
            feature_known_ms=p.declared_at_ms, decision_ms=p.declared_at_ms,
            activated_ms=p.activates_at_ms, exit_ms=terminal.at_ms,
            matured_ms=terminal.at_ms,
            symbol=p.symbol, side=p.side, btc_regime=_regime(row.btc_regime),
            market_regime=_regime(row.market_regime),
            coin_regime=_regime(row.coin_regime),
            structure=row.structure, detector_states=tuple(sorted(row.detector_states)),
            inclusion_k=batch.evaluated_pairs,
            inclusion_n=batch.eligible_pairs,
            economic_state=state, net_r=modeled_net_r, provenance=lineage)
        # Independently run the G7 validation before admitting to the bridge.
        assemble_lab((learning,), cutoff_ms=terminal.at_ms)
        self.learning_rows.append(learning)
        self._processed.add(terminal.intent_id)
        return learning

    def review_science(self, *, cutoff_ms: int,
                       protocol: LabProtocol | None = None) -> ScienceProof:
        dataset = assemble_lab(tuple(self.learning_rows), cutoff_ms=cutoff_ms)
        report = quality_report(dataset)
        if verified_learning_count(dataset) != 0:
            raise IntegrationHold("G11_GENUINE_SCIENCE_FALSIFIED")
        model_sha = None
        if protocol is not None:
            model = train_lab(dataset, protocol)
            result = evaluate_frozen_lab(model, dataset)
            if (model.qualified_original != 0 or
                    result.release_authority != "NONE" or
                    result.scientific_advantage_proved):
                raise IntegrationHold("G11_MODEL_QUALIFICATION_FALSIFIED")
            try:
                require_authorized_champion(model)
            except TrainingHold:
                pass
            else:
                raise IntegrationHold("G11_CHAMPION_AUTHORITY_BYPASS")
            model_sha = model.model_sha256
        return ScienceProof(len(dataset.rows), verified_learning_count(dataset),
                            report.pending, model_sha)

    def on_lab_paper_event(self, event: SharedLabEvent):
        if self.competition is None or self.last_event is None:
            raise IntegrationHold("G11_NO_BOUND_G10_LAB")
        if (type(event) is not SharedLabEvent or
                event.at_ms < self.last_event.decision_at_ms or
                event.quote.symbol not in self.last_deep.symbols or
                event.event_sha256 in self._lab_events):
            raise IntegrationHold("G11_LAB_EVENT_OUTSIDE_SHARED_DEEP_COHORT")
        before = len(self.competition.events)
        audit = self.competition.step(event)  # Actual G9/G10 guardian, same feed.
        if (len(self.competition.events) != before + 1 or
                audit.authority != "NONE"):
            raise IntegrationHold("G11_PAPER_AUTHORITY_OR_AUDIT_BREACH")
        self._lab_events.add(event.event_sha256)
        return audit

    def review_competition(self):
        if self.competition is None:
            raise IntegrationHold("G11_NO_G10_CONTEST")
        result = self.competition.review()
        if (result.action != "HOLD" or result.genuine_paper_settlements != 0
                or result.independent_original_outcomes != 0
                or result.fair_real_paper_comparison):
            raise IntegrationHold("G11_RELEASE_GATE_BREACH")
        return result
