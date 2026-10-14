"""One-time forward-only G4 research policy template registration.

Creates an immutable private *prospective* G4 design artifact after a ten-minute
activation lead. This neither retrospectively binds old candidates nor starts
simulated/real trades or unlocks any scientific acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

from nbot.v5.g4_prospective_policy import (
    freeze_template,ENTRY_CONVENTION,EXIT_POLICY_ID,
    RISK_POLICY_ID,COST_POLICY_ID,
)
from nbot.v5.observation_contract import INTERVAL_MS

VERSION="NBOT_V5_G4_PREDECLARED_POLICY_REGISTRY_V1"


def register_prospective_policy(*,output:str|Path,declared_at_ms:int) -> dict:
    if type(declared_at_ms) is not int or declared_at_ms<=0:
        raise ValueError("G4_PROSPECTIVE_DECLARATION_CLOCK_INVALID")
    output=Path(output)
    parent=output.parent
    if (parent.is_symlink() or not parent.is_dir()
            or not parent.name.startswith("g4-forward-")
            or parent.stat().st_mode & 0o077 or output.is_symlink()
            or output.name!="g4_research_template.json" or output.exists()):
        raise ValueError("G4_POLICY_ISOLATION_OR_EXISTENCE_INVALID")
    activate=((declared_at_ms+2*INTERVAL_MS+INTERVAL_MS-1)//INTERVAL_MS)*INTERVAL_MS
    spec={
        "declared_at_ms":declared_at_ms,
        "activates_at_ms":activate,
        "horizon_ms":4*60*60*1000,
        "max_quote_age_ms":1000,
        "atr_risk_multiple":"1.5",
        "target_r_multiple":"2.0",
        "min_risk_fraction":"0.005",
        "entry_convention":ENTRY_CONVENTION,
        "exit_policy_id":EXIT_POLICY_ID,
        "risk_policy_id":RISK_POLICY_ID,
        "cost_policy_id":COST_POLICY_ID,
        "research_authority":"OBSERVE_ONLY",
    }
    template=freeze_template(spec)
    body={
        "registry_version":VERSION,
        "template_version":template.version,
        "policy_sha256":template.policy_sha256,
        "spec":spec,
        "research_only":True,
        "source_grade":"NO_MARKET_SOURCE_BOUND_YET",
        "after_cost_outcomes":0,
        "financial_authority":"NONE",
        "model_training_authority":"NONE",
    }
    raw=json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n"
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return {
        "registry":"PREDECLARED_LOCAL_FROZEN_POLICY_ONLY",
        "file_sha256":hashlib.sha256(raw.encode()).hexdigest(),
        "policy_sha256":template.policy_sha256,
        "declared_at_ms":declared_at_ms,
        "activation_at_ms":activate,
        "min_lead_ms":activate-declared_at_ms,
        "scored_outcomes":0,
        "order_authority":"NONE",
        "source_quality_accepted":False,
    }


def main():
    import argparse
    p=argparse.ArgumentParser(description="Freeze an isolated prospective G4 policy (no trades)")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    try:
        report=register_prospective_policy(
            output=a.output,declared_at_ms=time.time_ns()//1_000_000)
        print(json.dumps(report,sort_keys=True))
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
