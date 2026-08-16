#!/usr/bin/env python3
from __future__ import annotations

import logging

from nbot.binance import BinancePublicClient
from nbot.config import CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.Formatter.converter = __import__("time").gmtime
    logging.getLogger("nbot.v2").info("NBOT_V2_START")
    db = EvidenceDB(CONFIG)
    client = BinancePublicClient(CONFIG)
    MarketEvidenceObserver(CONFIG, client, db).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
