"""One bounded, explicitly opt-in NBOT V6 native offline candidate trial.

Default --plan prints the Freqtrade native command without accessing VPS.
--execute requires root on the isolated V6 VPS, explicit offline consent,
clean correct branch, no other Docker container, verified history archive,
no exchange keys and no paper/live services. Never schedules or self-runs.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"source"
HISTORY=ROOT/"january-2026-public-history-stage"
OUTPUT=ROOT/"library-20261018"
BRANCH="prototype/v6-freqtrade-freqai-20261016"

CANDIDATES={
 "ema_cross":("NbotV6EmaCrossResearch","NbotV6EmaCrossLightGBMResearch"),
 "donchian_breakout":("NbotV6DonchianResearch","NbotV6DonchianLightGBMResearch"),
 "bollinger_reversion":("NbotV6BollingerResearch","NbotV6BollingerLightGBMResearch"),
 "rsi_reversion":("NbotV6RsiResearch","NbotV6RsiLightGBMResearch"),
 "macd_momentum":("NbotV6MacdResearch","NbotV6MacdLightGBMResearch"),
 "stochastic_reversal":("NbotV6StochasticResearch","NbotV6StochasticLightGBMResearch"),
 "atr_breakout":("NbotV6AtrBreakoutResearch","NbotV6AtrBreakoutLightGBMResearch"),
 "volume_trend":("NbotV6VolumeTrendResearch","NbotV6VolumeTrendLightGBMResearch"),
}
# Frozen OFFLINE exit-policy variants to run only after original batch is complete.
# Trailing variants use same entry signals and baseline 60-minute holding limit.
PROFIT_PROTECTION_VARIANTS = {
 "protect_trail_1p0_gap_0p5": "TrailEarlyOne",
 "protect_trail_1p5_gap_0p5": "TrailEarlyOneHalf",
 "protect_trail_2p0_gap_0p5": "TrailTightTwo",
 "protect_take_profit_2p0": "TakeProfitTwo",
 "protect_take_profit_3p0": "TakeProfitThree",
}

PERIODS={
 "tuning_may_june":"20260501-20260701",
 "validation_july":"20260701-20260801",
 "replication_august":"20260801-20260901",
 "replication_september":"20260901-20261001",
}
OVERLAYS={
 "native":"config.v6-library-native-offline.json",
 "trailing":"config.v6-library-native-offline.json",
 "baseline":"config.v6-library-native-offline.json",
 "hyperopt":"config.v6-library-native-offline.json",
 "lgbm":"config.v6-library-lgbm-offline.json",
 "rl":"config.v6-library-rl-offline.json",
 "adaptive":"config.v6-library-adaptive-offline.json",
 **{key:"config.v6-library-native-offline.json" for key in PROFIT_PROTECTION_VARIANTS},
}

def plan(kind:str, family:str, period:str, *, overlay_path:str="/results/exact-overlay.json") -> list[str]:
    if family not in CANDIDATES or kind not in OVERLAYS or period not in PERIODS:
        raise ValueError("ONLY_ALLOWLISTED_V6_OFFLINE_TRIALS")
    if kind=="hyperopt" and period!="tuning_may_june":
        raise ValueError("HYPEROPT_MUST_NEVER_USE_OOS_HOLDOUT")
    if kind=="adaptive" and period=="tuning_may_june":
        raise ValueError("ADAPTIVE_USE_REQUIRES_HISTORICAL_EVIDENCE")
    strategy=CANDIDATES[family][1] if kind=="lgbm" else CANDIDATES[family][0]
    if kind in PROFIT_PROTECTION_VARIANTS:
        strategy=strategy.replace("Research", PROFIT_PROTECTION_VARIANTS[kind]+"Research")
    if kind=="trailing":strategy=strategy.replace("Research","TrailingResearch")
    if kind=="baseline":strategy="NbotV6NoML"
    if kind=="rl":strategy="NbotV6RLResearch"
    if kind=="adaptive":strategy="NbotV6AdaptiveLibraryResearch"
    common=[
        "-c","/research/user_data/config.json","-c",overlay_path,
        "--userdir","/results","--datadir","/history",
        "--strategy",strategy,"--strategy-path","/research/user_data/strategies",
        "--timerange",PERIODS[period],"--fee","0.0005",
    ]
    if kind=="hyperopt":
        task=["hyperopt",*common,"--hyperopt-loss","MultiMetricHyperOptLoss",
              "--spaces","buy","-e","60","-j","1","--random-state","20261017",
              "--disable-param-export","--enable-protections"]
    else:
        task=["backtesting",*common,"--cache","none","--export","trades"]
        # The identical native Freqtrade max-drawdown / stoploss guards
        # must be ON even for LightGBM and PPO aftercost evaluations.
        task+=["--enable-protections"]
        if kind=="lgbm":
            task+=["--freqaimodel","NbotV6PurgedLightGBMRegressor",
                   "--freqaimodel-path","/research/user_data/freqaimodels"]
        if kind=="rl":
            task+=["--freqaimodel","NbotV6CostAwareRLResearch",
                   "--freqaimodel-path","/research/user_data/freqaimodels"]
    return ["timeout","-s","TERM","-k","60","14400","docker","run","--rm",
            "--name","nbot-v6-library-single-native-offline",
            "--network","bridge","--cpus=2","--memory=6g",
            "-v",str(SOURCE)+":/research:ro",
            "-v",str(HISTORY)+":/history:ro",
            "-v",str(OUTPUT/kind/family/period)+":/results",
            "--entrypoint","freqtrade",
            "freqtradeorg/freqtrade:stable_freqairl" if kind=="rl"
            else "freqtradeorg/freqtrade:stable_freqai",*task]

def _safe_overrides(kind:str,family:str) -> dict:
    base=json.loads((SOURCE/"user_data"/OVERLAYS[kind]).read_text())
    assert base["dry_run"] is True and base["nbot_live_mode"] is False
    assert base["nbot_paper_research_mode"] is False
    assert base["max_open_trades"]==1 and base["stake_amount"]==1000
    assert base["force_entry_enable"] is False
    assert base["exchange"]=={"key":"","secret":""}
    assert base["telegram"]["enabled"] is False and base["api_server"]["enabled"] is False
    if kind=="lgbm":
        assert base["nbot_m2r_research_only"] is True
        assert base["nbot_m2r_purge_internal"] is True
        assert base["nbot_v6_library_ml_research_only"] is True
        base["freqai"]["identifier"]="nbot-v6-library-"+family+"-native-frozen-20261017"
    if kind in ("native","trailing","baseline","hyperopt","adaptive") or kind in PROFIT_PROTECTION_VARIANTS:
        assert base["freqai"]["enabled"] is False
        assert base["nbot_v6_library_research_only"] is True
    if kind=="rl":
        assert base["nbot_v6_rl_research_only"] is True
        assert base["freqai"]["continual_learning"] is False
    return base

def _run(command:list[str],cwd:Path|None=None) -> str:
    result=subprocess.run(command,cwd=cwd,check=True,capture_output=True,text=True)
    return result.stdout.strip()

def execute(kind:str, family:str, period:str) -> int:
    if os.environ.get("NBOT_V6_LIBRARY_OFFLINE_EXECUTION")!="OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY":
        raise RuntimeError("EXPLICIT_OFFLINE_ONLY_CONSENT_REQUIRED")
    if os.geteuid()!=0 or not (SOURCE/".git").is_dir():
        raise RuntimeError("ISOLATED_V6_VPS_ROOT_AND_CHECKOUT_REQUIRED")
    if _run(["git","branch","--show-current"],SOURCE)!=BRANCH:
        raise RuntimeError("WRONG_RESEARCH_BRANCH")
    if _run(["git","status","--porcelain=v1"],SOURCE):
        raise RuntimeError("DIRTY_V6_CHECKOUT")
    if _run(["docker","ps","-q"]):
        raise RuntimeError("ANOTHER_DOCKER_JOB_BUSY_DO_NOT_COMPETE_WITH_ORIGINAL_RESEARCH")
    if not (HISTORY/"futures").is_dir():
        raise RuntimeError("HISTORICAL_MARKET_DATA_NOT_INSTALLED")
    if not _run(["git","rev-parse","HEAD"],SOURCE):
        raise RuntimeError("MISSING_GIT_COMMIT")
    overrides=_safe_overrides(kind,family)
    out=OUTPUT/kind/family/period
    if out.exists():
        raise RuntimeError("NEVER_OVERWRITE_PRIOR_RESEARCH_EVIDENCE")
    out.mkdir(parents=True)
    # Official Freqtrade image uses non-root ftuser uid/gid 1000. Do not
    # repeat the Oct17 root-only mounted-output permission failure.
    os.chown(out, 1000, 1000)
    os.chmod(out, 0o750)
    (out/"exact-overlay.json").write_text(json.dumps(overrides,indent=2)+"\n")
    (out/"run-state.txt").write_text(
        "START_UTC="+datetime.now(timezone.utc).isoformat()+"\n"
        +"GIT_COMMIT="+_run(["git","rev-parse","HEAD"],SOURCE)+"\n"
        +"RESEARCH_KIND="+kind+"\nFAMILY="+family+"\nPERIOD="+period+"\n")
    # Read access to the overlay and writable isolated output are required
    # by the Docker UID1000 process. Keep input source/history read-only.
    os.chmod(out/"exact-overlay.json", 0o644)
    if _run(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_STARTED_DURING_PREFLIGHT_ABORT")
    command=plan(kind,family,period)
    with (out/"native.log").open("w") as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
    with (out/"run-state.txt").open("a") as state:
        state.write("EXIT_CODE="+str(result.returncode)+"\n"
                    +"FINISH_UTC="+datetime.now(timezone.utc).isoformat()+"\n")
    print("NATIVE_OFFLINE_JOB_END",kind,family,period,"exit",result.returncode,"output",str(out),flush=True)
    return result.returncode

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("plan","execute"))
    p.add_argument("kind",choices=tuple(OVERLAYS))
    p.add_argument("family",choices=tuple(CANDIDATES))
    p.add_argument("period",choices=tuple(PERIODS))
    a=p.parse_args()
    command=plan(a.kind,a.family,a.period)
    print(json.dumps({"research_only":True,"no_paper_or_live":True,
                      "historical_august_and_september_are_not_blind":True,
                      "single_offline_native_trial":command},indent=2))
    return execute(a.kind,a.family,a.period) if a.mode=="execute" else 0

if __name__=="__main__":
    sys.exit(main())
