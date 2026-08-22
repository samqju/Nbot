"""V3.8.1R research scalability recovery utilities.

These operations never create recommendation or execution authority.  They are
explicit maintenance/research tools for proving Ridge equivalence and resetting
only reproducible derived research state while preserving canonical raw LIVE
market evidence byte-for-byte at the logical-row level.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from .champion import CHAMPION_CONFIG
from .database import EvidenceDatabase, RAW_EVIDENCE_TABLES
from .selection import (
    FEATURE_VECTOR_NAMES,
    RidgeSufficientStatistics,
    SELECTION_CONFIG,
    _ridge_score,
)

REFERENCE_RESET_CONFIRMATION = "V381R_RESET_DERIVED_ONLY"

# Drop children before parents.  Observation control-plane tables are
# intentionally absent: this reset is research-derived state only.
DERIVED_RESEARCH_DROP_ORDER: tuple[str, ...] = (
    "rollback_records",
    "drift_reports",
    "evaluation_ledger",
    "training_jobs",
    "challenger_registry",
    "model_registry",
    "learning_foundations",
    "research_champions",
    "research_champion_evaluations",
    "research_champion_sets",
    "entry_selection_ridge_state",
    "entry_selection_predictions",
    "entry_selection_prediction_builds",
    "entry_selection_examples",
    "entry_selection_builds",
    "entry_selector_sets",
    "entry_selection_labs",
    "exit_policy_results",
    "exit_policy_builds",
    "exit_policy_sets",
    "exit_policy_labs",
    "future_path_attempts",
    "future_paths",
    "future_path_builds",
    "future_candle_cache",
    "future_path_sets",
    "signal_annotations",
    "signal_builds",
    "signal_sets",
    "canonical_features",
    "feature_builds",
    "feature_sets",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _table_primary_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    keyed = sorted(
        ((int(row[5]), str(row[1])) for row in rows if int(row[5]) > 0),
        key=lambda item: item[0],
    )
    return [name for _, name in keyed]


def raw_evidence_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    """Deterministic logical manifest of every canonical raw evidence table."""

    tables_present = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    result: dict[str, Any] = {"tables": {}, "combined_sha256": ""}
    combined = hashlib.sha256()
    for table in RAW_EVIDENCE_TABLES:
        if table not in tables_present:
            raise RuntimeError(f"NBOT_V381R_RAW_TABLE_MISSING:{table}")
        columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
        order_cols = _table_primary_key_columns(conn, table) or columns
        sql = f'SELECT * FROM "{table}"'
        if order_cols:
            sql += " ORDER BY " + ",".join(f'"{name}"' for name in order_cols)
        table_hash = hashlib.sha256()
        count = 0
        for row in conn.execute(sql):
            payload = _canonical_json(list(row)).encode("utf-8")
            table_hash.update(payload)
            table_hash.update(b"\n")
            count += 1
        digest = table_hash.hexdigest()
        result["tables"][table] = {"rows": count, "sha256": digest}
        combined.update(table.encode("utf-8"))
        combined.update(b"\0")
        combined.update(str(count).encode("ascii"))
        combined.update(b"\0")
        combined.update(digest.encode("ascii"))
        combined.update(b"\n")
    result["combined_sha256"] = combined.hexdigest()
    return result


def verify_reference_database(path: Path, expected_sha256: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("NBOT_V381R_REFERENCE_DB_MISSING")
    actual_sha = _sha256_file(path)
    if actual_sha != str(expected_sha256).strip().lower():
        raise RuntimeError(
            f"NBOT_V381R_REFERENCE_SHA_MISMATCH:{actual_sha}"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    try:
        conn.execute("PRAGMA query_only=ON")
        quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if quick != "ok" or fk:
            raise RuntimeError("NBOT_V381R_REFERENCE_INTEGRITY_FAILED")
        return {
            "reference_db": str(path),
            "sha256": actual_sha,
            "quick_check": quick,
            "foreign_key_errors": len(fk),
            "bytes": path.stat().st_size,
        }
    finally:
        conn.close()


def _score_equivalence(
    new_scores: list[float],
    old_scores: list[float],
    *,
    exact_required: bool,
    tolerance: float,
) -> dict[str, Any]:
    """Compare one event's Ridge scores without weakening ranking semantics.

    The frozen Champion validation/test window requires absolute score equality
    within tolerance.  Later events cannot change that original decision; for
    those events a common additive intercept offset is numerically irrelevant
    to ordering, so centered score differences must still match tightly.
    """

    if len(new_scores) != len(old_scores):
        return {
            "healthy": False,
            "raw_mismatch_rows": abs(len(new_scores) - len(old_scores)) or 1,
            "centered_mismatch_rows": abs(len(new_scores) - len(old_scores)) or 1,
            "max_abs_raw_diff": float("inf"),
            "max_abs_centered_diff": float("inf"),
            "intercept_offset": None,
        }
    if not new_scores:
        return {
            "healthy": True,
            "raw_mismatch_rows": 0,
            "centered_mismatch_rows": 0,
            "max_abs_raw_diff": 0.0,
            "max_abs_centered_diff": 0.0,
            "intercept_offset": 0.0,
        }

    raw_diffs = [float(new) - float(old) for new, old in zip(new_scores, old_scores)]
    max_abs_raw = max(abs(value) for value in raw_diffs)
    raw_mismatches = sum(abs(value) > tolerance for value in raw_diffs)

    # Rank-1 is the deterministic anchor because rank/symbol/side equality is
    # checked separately before this result can make the verifier healthy.
    offset = raw_diffs[0]
    centered_diffs = [value - offset for value in raw_diffs]
    max_abs_centered = max(abs(value) for value in centered_diffs)
    centered_mismatches = sum(abs(value) > tolerance for value in centered_diffs)

    return {
        "healthy": raw_mismatches == 0 if exact_required else centered_mismatches == 0,
        "raw_mismatch_rows": raw_mismatches,
        "centered_mismatch_rows": centered_mismatches,
        "max_abs_raw_diff": max_abs_raw,
        "max_abs_centered_diff": max_abs_centered,
        "intercept_offset": offset,
    }


def verify_ridge_reference_equivalence(
    path: Path,
    expected_sha256: str,
    *,
    score_tolerance: float = 1e-8,
) -> dict[str, Any]:
    """Replay V3.4.5 Ridge once against the frozen pre-recovery oracle.

    Exact rank/symbol/side ordering and chronology metadata are mandatory for
    every learned event.  Absolute scores are also mandatory for the frozen
    Champion validation+test window.  Later events are excluded by contract
    from changing that original Champion decision, so they must preserve
    within-event score differences; a common additive intercept offset caused
    only by floating-point normal-equation centering is reported but does not
    count as a semantic mismatch.
    """

    if not math.isfinite(score_tolerance) or score_tolerance <= 0:
        raise ValueError("NBOT_V381R_SCORE_TOLERANCE_INVALID")

    frozen_champion_events = (
        CHAMPION_CONFIG.min_validation_events + CHAMPION_CONFIG.min_test_events
    )
    reference = verify_reference_database(path, expected_sha256)
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        events = [
            int(row[0])
            for row in conn.execute(
                "SELECT event_open_ms FROM entry_selection_builds "
                "WHERE lab_version=? ORDER BY event_open_ms",
                (SELECTION_CONFIG.lab_version,),
            )
        ]
        state = RidgeSufficientStatistics.empty()
        compared_events = 0
        compared_rows = 0
        rank_mismatches = 0
        metadata_mismatches = 0
        frozen_score_mismatches = 0
        post_test_centered_score_mismatches = 0
        raw_score_offset_rows = 0
        post_test_intercept_shift_events = 0
        max_abs_score_diff = 0.0
        max_abs_centered_score_diff = 0.0
        max_abs_post_test_intercept_shift = 0.0
        first_mismatch: dict[str, Any] | None = None
        first_post_test_intercept_shift: dict[str, Any] | None = None
        learned_event_index = 0

        for event_open_ms in events:
            examples = [dict(row) for row in conn.execute(
                "SELECT event_open_ms,symbol,side,target_net_r,feature_vector_json,example_digest "
                "FROM entry_selection_examples WHERE lab_version=? AND event_open_ms=? "
                "ORDER BY symbol,side",
                (SELECTION_CONFIG.lab_version, event_open_ms),
            )]
            stored = [dict(row) for row in conn.execute(
                "SELECT symbol,side,score,rank_in_event,training_event_count,training_row_count,trained_through_event_ms "
                "FROM entry_selection_predictions WHERE lab_version=? AND selector_version=? AND event_open_ms=? "
                "ORDER BY rank_in_event,symbol,side",
                (
                    SELECTION_CONFIG.lab_version,
                    SELECTION_CONFIG.learned_selector_version,
                    event_open_ms,
                ),
            )]

            if stored:
                learned_event_index += 1
                exact_score_required = learned_event_index <= frozen_champion_events
                if state.event_count < SELECTION_CONFIG.min_train_events:
                    metadata_mismatches += 1
                else:
                    model = state.fit(SELECTION_CONFIG.ridge_alpha)
                    scored = [
                        (_ridge_score(model, str(row["feature_vector_json"])), row)
                        for row in examples
                    ]
                    scored.sort(
                        key=lambda item: (
                            -item[0], str(item[1]["symbol"]), str(item[1]["side"])
                        )
                    )
                    compared_events += 1
                    compared_rows += len(stored)
                    if len(scored) != len(stored):
                        rank_mismatches += abs(len(scored) - len(stored)) or 1

                    new_scores: list[float] = []
                    old_scores: list[float] = []
                    event_rank_or_meta_mismatch = False
                    for rank, ((score, example), old) in enumerate(zip(scored, stored), 1):
                        rank_ok = (
                            int(old["rank_in_event"]) == rank
                            and str(old["symbol"]) == str(example["symbol"])
                            and str(old["side"]) == str(example["side"])
                        )
                        meta_ok = (
                            int(old["training_event_count"]) == state.event_count
                            and int(old["training_row_count"]) == state.row_count
                            and old["trained_through_event_ms"] == state.through_event_ms
                        )
                        if not rank_ok:
                            rank_mismatches += 1
                            event_rank_or_meta_mismatch = True
                        if not meta_ok:
                            metadata_mismatches += 1
                            event_rank_or_meta_mismatch = True
                        new_scores.append(float(score))
                        old_scores.append(float(old["score"]))

                    score_report = _score_equivalence(
                        new_scores,
                        old_scores,
                        exact_required=exact_score_required,
                        tolerance=score_tolerance,
                    )
                    max_abs_score_diff = max(
                        max_abs_score_diff, float(score_report["max_abs_raw_diff"])
                    )
                    max_abs_centered_score_diff = max(
                        max_abs_centered_score_diff,
                        float(score_report["max_abs_centered_diff"]),
                    )
                    raw_score_offset_rows += int(score_report["raw_mismatch_rows"])

                    if exact_score_required:
                        frozen_score_mismatches += int(score_report["raw_mismatch_rows"])
                    else:
                        post_test_centered_score_mismatches += int(
                            score_report["centered_mismatch_rows"]
                        )
                        offset = float(score_report["intercept_offset"] or 0.0)
                        if abs(offset) > score_tolerance:
                            post_test_intercept_shift_events += 1
                            max_abs_post_test_intercept_shift = max(
                                max_abs_post_test_intercept_shift, abs(offset)
                            )
                            if first_post_test_intercept_shift is None:
                                first_post_test_intercept_shift = {
                                    "event_open_ms": event_open_ms,
                                    "learned_event_index": learned_event_index,
                                    "training_event_count": state.event_count,
                                    "intercept_offset": offset,
                                    "max_abs_centered_diff": score_report[
                                        "max_abs_centered_diff"
                                    ],
                                }

                    semantic_score_ok = bool(score_report["healthy"])
                    if first_mismatch is None and (
                        event_rank_or_meta_mismatch or not semantic_score_ok
                    ):
                        first_mismatch = {
                            "event_open_ms": event_open_ms,
                            "learned_event_index": learned_event_index,
                            "score_scope": (
                                "FROZEN_CHAMPION_EXACT"
                                if exact_score_required
                                else "POST_TEST_CENTERED"
                            ),
                            "max_abs_raw_score_diff": score_report[
                                "max_abs_raw_diff"
                            ],
                            "max_abs_centered_score_diff": score_report[
                                "max_abs_centered_diff"
                            ],
                        }
            state.add_event(event_open_ms, examples)

        learned_builds = int(conn.execute(
            "SELECT COUNT(*) FROM entry_selection_prediction_builds "
            "WHERE lab_version=? AND selector_version=?",
            (SELECTION_CONFIG.lab_version, SELECTION_CONFIG.learned_selector_version),
        ).fetchone()[0])
        healthy = (
            compared_events == learned_builds
            and rank_mismatches == 0
            and metadata_mismatches == 0
            and frozen_score_mismatches == 0
            and post_test_centered_score_mismatches == 0
        )
        return {
            **reference,
            "selector_version": SELECTION_CONFIG.learned_selector_version,
            "source_selection_events": len(events),
            "stored_learned_builds": learned_builds,
            "compared_events": compared_events,
            "compared_rows": compared_rows,
            "frozen_champion_event_count": frozen_champion_events,
            "score_tolerance": score_tolerance,
            "max_abs_score_diff": max_abs_score_diff,
            "max_abs_centered_score_diff": max_abs_centered_score_diff,
            "max_abs_post_test_intercept_shift": max_abs_post_test_intercept_shift,
            "rank_mismatches": rank_mismatches,
            "metadata_mismatches": metadata_mismatches,
            "frozen_score_mismatches": frozen_score_mismatches,
            "post_test_centered_score_mismatches": post_test_centered_score_mismatches,
            "raw_score_offset_rows": raw_score_offset_rows,
            "post_test_intercept_shift_events": post_test_intercept_shift_events,
            "first_post_test_intercept_shift": first_post_test_intercept_shift,
            "first_mismatch": first_mismatch,
            "healthy": healthy,
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        }
    finally:
        conn.close()


class ResearchScalabilityRecovery:
    def __init__(self, database: EvidenceDatabase):
        self.database = database

    def status(self) -> dict[str, Any]:
        path = self.database.path
        with self.database.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            counts: dict[str, int] = {}
            for table in DERIVED_RESEARCH_DROP_ORDER:
                if table in tables:
                    counts[table] = int(conn.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0])
            ridge_state = None
            if "entry_selection_ridge_state" in tables:
                row = conn.execute(
                    "SELECT through_event_ms,training_event_count,training_row_count,state_digest "
                    "FROM entry_selection_ridge_state WHERE lab_version=?",
                    (SELECTION_CONFIG.lab_version,),
                ).fetchone()
                if row is not None:
                    ridge_state = {
                        "through_event_ms": row[0],
                        "training_event_count": int(row[1]),
                        "training_row_count": int(row[2]),
                        "state_digest": str(row[3]),
                    }
            page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
            page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        return {
            "database": str(path),
            "database_bytes": path.stat().st_size if path.exists() else 0,
            "allocated_bytes": page_size * page_count,
            "derived_row_counts": counts,
            "ridge_state": ridge_state,
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        }

    def reset_derived(
        self,
        *,
        reference_db: Path,
        reference_sha256: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != REFERENCE_RESET_CONFIRMATION:
            raise RuntimeError("NBOT_V381R_RESET_CONFIRMATION_INVALID")
        reference = verify_reference_database(reference_db, reference_sha256)
        path = self.database.path
        before_bytes = path.stat().st_size
        conn = sqlite3.connect(path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            checkpoint = tuple(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
            raw_before = raw_evidence_manifest(conn)
            present = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            conn.execute("PRAGMA foreign_keys=OFF")
            for table in DERIVED_RESEARCH_DROP_ORDER:
                if table in present:
                    conn.execute(f'DROP TABLE "{table}"')
            conn.commit()
            conn.execute("PRAGMA foreign_keys=ON")
            raw_after_drop = raw_evidence_manifest(conn)
            if raw_after_drop != raw_before:
                raise RuntimeError("NBOT_V381R_RAW_MANIFEST_CHANGED_AFTER_DROP")
            fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise RuntimeError("NBOT_V381R_FOREIGN_KEY_ERRORS_AFTER_DROP")
        finally:
            conn.close()

        vacuum = sqlite3.connect(path, timeout=30.0)
        try:
            vacuum.execute("VACUUM")
        finally:
            vacuum.close()

        verify = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
        try:
            verify.execute("PRAGMA query_only=ON")
            raw_after = raw_evidence_manifest(verify)
            quick = str(verify.execute("PRAGMA quick_check").fetchone()[0])
            fk_errors = verify.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            verify.close()
        if raw_after != raw_before:
            raise RuntimeError("NBOT_V381R_RAW_MANIFEST_CHANGED_AFTER_VACUUM")
        if quick != "ok" or fk_errors:
            raise RuntimeError("NBOT_V381R_RESET_INTEGRITY_FAILED")
        after_bytes = path.stat().st_size
        return {
            "reference": reference,
            "wal_checkpoint": checkpoint,
            "raw_manifest_before": raw_before,
            "raw_manifest_after": raw_after,
            "raw_manifest_unchanged": True,
            "quick_check": quick,
            "foreign_key_errors": len(fk_errors),
            "database_bytes_before": before_bytes,
            "database_bytes_after": after_bytes,
            "bytes_reclaimed": max(0, before_bytes - after_bytes),
            "dropped_research_tables": list(DERIVED_RESEARCH_DROP_ORDER),
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        }
