"""Print or refresh the unified Phase 5.13 auto-learning status."""

from __future__ import annotations

import argparse
import json

from learning.operator_status import build_configured_publisher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show the unified autonomous-learning operator status"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the atomic JSON document instead of the operator view",
    )
    args = parser.parse_args(argv)

    publisher = build_configured_publisher()
    document = publisher.refresh()
    if args.json:
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(publisher.render_console(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
