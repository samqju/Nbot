#!/usr/bin/env python3
"""Read-only NBOT V4 research/generation status."""
from __future__ import annotations
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from nbot.observation.decision_ledger import DecisionLedger
from nbot.observation.v4_generation import V4GenerationTrainer
from nbot.observation.v4_research import BATCH_SIZE, CAPACITY, V4ResearchStore
from nbot.observation.v4_paper_contest import V4PaperContestStore


def main() -> int:
    ledger=DecisionLedger(Path("data/observation/v4/research_ledger.db"))
    ledger.initialize()
    counts=ledger.counts()
    pending=len(ledger.pending_decisions())
    meta=V4ResearchStore(Path("data/observation/v4/research_meta.db")).status()
    generations=V4GenerationTrainer().status()
    paper=V4PaperContestStore().status()
    resolved=counts["matured_research"]
    print(json.dumps({
        "capacity":CAPACITY,
        "open_pending":pending,
        "resolved":resolved,
        "unresolved":counts["unresolved"],
        "batch_size":BATCH_SIZE,
        "next_training_at":((resolved//BATCH_SIZE)+1)*BATCH_SIZE,
        "research_batches":meta["batches"],
        "generation":generations,
        "paper_contest":paper,
        "order_authority":"NONE",
    },sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
