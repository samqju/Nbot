"""Run Phase 7.5D.2 research-only walk-forward ranking validation."""

from __future__ import annotations

import argparse
import json

from learning.ranking_walk_forward import OfflineWalkForwardRankingValidator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run research-only Phase 7.5D.2 expanding-window validation of "
            "RANKING_R_V1 against RULE_SYSTEM_V1; this command cannot activate "
            "or promote a model"
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--outcome-type", default="VIRTUAL_TRADE")
    parser.add_argument("--fold-count", type=int, default=5)
    parser.add_argument("--initial-train-fraction", type=float, default=0.50)
    parser.add_argument("--min-positive-folds", type=int, default=5)
    parser.add_argument("--min-train-rows", type=int, default=200)
    parser.add_argument("--min-eval-rows", type=int, default=40)
    parser.add_argument("--min-train-events", type=int, default=20)
    parser.add_argument("--min-eval-events", type=int, default=10)
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    parser.add_argument("--embargo-seconds", type=int, default=None)
    args = parser.parse_args(argv)

    if args.embargo_seconds is None:
        from config import TIME_SPLIT_EMBARGO_SECONDS
        embargo_seconds = int(TIME_SPLIT_EMBARGO_SECONDS)
    else:
        embargo_seconds = int(args.embargo_seconds)

    report = OfflineWalkForwardRankingValidator(
        dataset_path=args.dataset,
        report_path=args.report,
        outcome_type=args.outcome_type,
        fold_count=args.fold_count,
        initial_train_fraction=args.initial_train_fraction,
        min_positive_folds=args.min_positive_folds,
        min_train_rows=args.min_train_rows,
        min_eval_rows=args.min_eval_rows,
        min_train_events=args.min_train_events,
        min_eval_events=args.min_eval_events,
        ridge_alpha=args.ridge_alpha,
        context_aware=True,
        embargo_seconds=embargo_seconds,
    ).run()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
