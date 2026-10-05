"""Bounded paper-learning evidence helpers; no order authority."""
from pathlib import Path
from collections import defaultdict
import math
import re
import subprocess

SHADOW_WEIGHT = .25
COOLDOWN_MS = 60 * 60_000
LOSS_WINDOW_MS = 6 * 60 * 60_000
# These define fills, risk units, attribution and outcome interpretation.
EVIDENCE_PATHS = ["nbot/common", "nbot/config", "nbot/exchange/paper.py", "nbot/exchange/contracts.py",
    "nbot/execution/entry.py", "nbot/execution/position.py", "nbot/execution/risk.py",
    "nbot/execution/outcomes.py", "nbot/communication/contracts.py",
    "nbot/observation/candidate_setups.py", "nbot/observation/context_learning.py"]

def compatible_evidence_release(old, current, repo_root=None):
    if old == current:
        return True
    if not all(isinstance(s,str) and re.fullmatch(r"[0-9a-f]{40}",s) for s in (old,current)):
        return False
    root = repo_root or Path(__file__).resolve().parents[2]
    try:
        ancestor = subprocess.run(["git","merge-base","--is-ancestor",old,current],
                                 cwd=root,capture_output=True,timeout=3)
        if ancestor.returncode:
            return False
        diff = subprocess.run(["git","diff","--no-ext-diff","--name-only",old,current,"--",*EVIDENCE_PATHS],
                              cwd=root,capture_output=True,timeout=3)
        return diff.returncode == 0 and not diff.stdout.strip()
    except (OSError,subprocess.TimeoutExpired):
        return False

def loss_cooldowns(samples, cutoff_ms):
    groups=defaultdict(list)
    for s in samples:
        if s["available_ms"] < cutoff_ms and s["closed_ms"] >= cutoff_ms-LOSS_WINDOW_MS:
            groups[s["symbol"]+"|"+s["side"]].append(s)
    result={}
    for key, rows in groups.items():
        latest=sorted(rows,key=lambda s:(s["closed_ms"],s["outcome_id"]),reverse=True)[:3]
        if len(latest)==3 and all(s["net_r"]<0 for s in latest):
            until=latest[0]["closed_ms"]+COOLDOWN_MS
            if until>cutoff_ms:
                result[key]={"until_ms":until,"losses":3,
                             "outcome_ids":[s["outcome_id"] for s in latest]}
    return result

def shadow_sample(p, *, cutoff_ms, catalog_digest):
    """Only closed forward fills qualify. Never convert a cancellation into PnL."""
    if not p.get("eligible") or p.get("reason")!="STOP" or p.get("profile")!="live-paper":
        return None
    if p.get("authority")!="SHADOW_ONLY_NO_EXECUTION" or p.get("catalog_digest")!=catalog_digest:
        return None
    # No historical context is reconstructed. Older records train the broad
    # candidate+side group only; newer records also retain decision-time context.
    if p.get("version")!="SHADOW_CANDIDATE_ACCOUNTS_V1" or p.get("side") not in ("LONG","SHORT"):
        return None
    try:
        if not (p["decision_ms"] < p["entered_ms"] <= p["closed_ms"] <= p["available_ms"] < cutoff_ms):
            return None
        risk=float(p["config"]["risk_usd"]); net=float(p["net_usd"]); rr=float(p["net_r"])
        if not all(math.isfinite(v) for v in (risk,net,rr)) or risk<=0 or not math.isclose(net/risk,rr,rel_tol=1e-6,abs_tol=1e-8):
            return None
        key="CANDIDATE:"+p["candidate_id"]
        keys=[key+"|ALL|"+p["side"]]
        context=p.get("decision_context")
        if isinstance(context,str) and context:
            keys.insert(0,key+"|"+context+"|"+p["side"])
        return {"outcome_id":"SHADOW:"+p["id"],"symbol":p["symbol"],"side":p["side"],
                "keys":keys,"candidate_id":p["candidate_id"],"learning_r":max(-3.,min(3.,rr)),
                "net_r":rr,"entered_ms":p["entered_ms"],"closed_ms":p["closed_ms"],
                "available_ms":p["available_ms"],"source":"SHADOW","weight":SHADOW_WEIGHT}
    except (KeyError,TypeError,ValueError,OverflowError):
        return None
