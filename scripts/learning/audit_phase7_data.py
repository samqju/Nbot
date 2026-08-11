"""Run the Phase 7.0 learning-data completeness audit."""

from __future__ import annotations

import argparse
import json

import config
from learning.phase7_data_audit import Phase7DataAudit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations",
        default=config.CANDIDATE_OBSERVATIONS_PATH,
    )
    parser.add_argument(
        "--outcomes",
        default=config.CANDIDATE_OUTCOMES_PATH,
    )
    args = parser.parse_args()
    report = Phase7DataAudit(
        observations_path=args.observations,
        outcomes_path=args.outcomes,
    ).run()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
