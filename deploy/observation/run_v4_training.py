#!/usr/bin/env python3
"""Train at most one ready V4 generation batch and exit."""
from __future__ import annotations
import json
from nbot.observation.v4_generation import V4GenerationTrainer

def main() -> int:
    trainer=V4GenerationTrainer()
    print(json.dumps(trainer.train_next(),sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
