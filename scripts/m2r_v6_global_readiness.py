#!/usr/bin/env python3
"""Read-only Stage 3 PRESTART readiness gates. NEVER starts Docker or trading.

Safe to run while Stage 2 profit-protection research is still running.
Execution requires a separate full test suite and Stage 2 economic verification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import stat
import subprocess

BASE=Path("/root/nbot-v6-m1-20261016")
SOURCE=BASE/"global-next-source"
HISTORY=BASE/"january-2026-public-history-stage/futures"
DEFAULTS=("scripts/m2r_v6_global_dataset.py",
          "scripts/m2r_v6_global_batch.py",
          "scripts/m2r_v6_global_opportunity_ranker.py",
          "user_data/strategies/NbotV6GlobalOfflineResearch.py",
          "user_data/strategies/NbotV6LibraryResearch.py")

def preflight(root=BASE):
    source=root/"global-next-source"
    market=root/"january-2026-public-history-stage/futures"
    blockers=[]
    warnings=[]
    cfg=source/"user_data/config.json"
    try:
        c=json.loads(cfg.read_text())
        whitelist=c["exchange"]["pair_whitelist"]
    except (KeyError,ValueError,OSError,TypeError) as ex:
        blockers.append("MISSING_OR_BAD_OFFLINE_CONFIG_"+str(type(ex).__name__))
        whitelist=[]
        c={}
    if len(whitelist)!=25 or len(set(whitelist))!=25:
        blockers.append("REQUIRE_EXACT_25_UNIQUE_PAIRS")
    if c.get("exchange",{}).get("key") or c.get("exchange",{}).get("secret"):
        blockers.append("EXCHANGE_CREDENTIALS_MUST_BE_EMPTY")
    if c.get("dry_run") is not True or c.get("nbot_live_mode") is not False:
        blockers.append("OFFLINE_ONLY_CONFIG_GATE")
    if c.get("nbot_paper_research_mode") is not False:
        blockers.append("PAPER_RESEARCH_MUST_BE_OFF")
    if c.get("max_open_trades")!=1 or c.get("stake_amount")!=1000:
        blockers.append("RESEARCH_PORTFOLIO_CAPITAL_POLICY_MISMATCH")
    for rel in DEFAULTS:
        f=source/rel
        if not f.is_file():blockers.append("MISSING_RESEARCH_SOURCE_"+rel);continue
        if not (f.stat().st_mode & stat.S_IROTH):
            blockers.append("DOCKER_CANNOT_READ_PYTHON_"+rel)
        try:compile(f.read_text(),str(f),"exec")
        except (SyntaxError,OSError) as e:blockers.append("INVALID_PYTHON_"+rel+":"+str(e))
    for directory in ("scripts","user_data/strategies","user_data/freqaimodels"):
        p=source/directory
        if not p.is_dir():blockers.append("MISSING_CODE_DIRECTORY_"+directory);continue
        for x in p.rglob("*.py"):
            if not (x.stat().st_mode & stat.S_IROTH):
                blockers.append("DOCKER_CANNOT_READ_PYTHON_"+str(x.relative_to(source)))
    missing_pairs=[]
    for pair in whitelist:
        if not isinstance(pair,str) or not pair.endswith("/USDT:USDT"):
            blockers.append("UNEXPECTED_PAIR_FORMAT_"+str(pair));continue
        name=pair.replace("/","_").replace(":","_")
        for suffix in ("-5m-futures.feather","-1h-funding_rate.feather","-1h-mark.feather"):
            path=market/(name+suffix)
            if not path.is_file() or path.stat().st_size<1024:
                missing_pairs.append(str(path.name))
    if missing_pairs:
        blockers.append("MISSING_OR_EMPTY_HISTORICAL_MARKET_FILES_COUNT_"+str(len(missing_pairs)))
    if (root/"global-25x8-20261018/progress.json").exists():
        warnings.append("GLOBAL_RESEARCH_ALREADY_STARTED_DO_NOT_RERUN")
    # A full in-Docker data/strategy smoke is still essential; don't pretend
    # checking file existence proves all candles are continuous.
    warnings.append("STATIC_READINESS_IS_NOT_FULL_MARKET_DATA_QUALITY_OR_NATIVE_SIMULATION")
    return {
        "schema":"nbot-v6-global-third-stage-readiness-v1",
        "source":str(source),"pair_count":len(whitelist),
        "market_inputs_expected":len(whitelist)*3,
        "market_input_missing":missing_pairs,
        "python_modules_checked":len(DEFAULTS),
        "errors":blockers,"warnings":warnings,
        "static_readiness_ok":not blockers,
        "read_only":True,"no_docker_started":True,
        "no_paper_or_live_trading":True
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=BASE)
    ap.add_argument("--strict",action="store_true",help="Exit nonzero if fail-closed gates not met")
    args=ap.parse_args()
    status=preflight(args.root)
    print(json.dumps(status,indent=2,sort_keys=True))
    if args.strict and not status["static_readiness_ok"]:raise SystemExit(3)

if __name__=="__main__":
    main()
