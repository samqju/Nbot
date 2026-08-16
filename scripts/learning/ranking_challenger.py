"""Run the Phase 7.5D.1 research-only R-ranking challenger experiment."""

from __future__ import annotations

import argparse
import json

from learning.ranking_challenger import OfflineRankingChallengerExperiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train/evaluate the research-only Phase 7.5D.1 RANKING_R_V1 "
            "experiment; this command cannot activate or promote a model"
        )
    )
    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--outcome-type", default="VIRTUAL_TRADE")
    parser.add_argument("--min-train-rows", type=int, default=200)
    parser.add_argument("--min-eval-rows", type=int, default=40)
    parser.add_argument("--min-train-events", type=int, default=20)
    parser.add_argument("--min-eval-events", type=int, default=10)
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    args = parser.parse_args(argv)

    report = OfflineRankingChallengerExperiment(
        train_path=args.train,
        validation_path=args.validation,
        test_path=args.test,
        artifact_path=args.artifact,
        report_path=args.report,
        outcome_type=args.outcome_type,
        min_train_rows=args.min_train_rows,
        min_eval_rows=args.min_eval_rows,
        min_train_events=args.min_train_events,
        min_eval_events=args.min_eval_events,
        ridge_alpha=args.ridge_alpha,
        context_aware=True,
        evaluate_test=True,
    ).run()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
