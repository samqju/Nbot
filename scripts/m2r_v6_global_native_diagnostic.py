#!/usr/bin/env python3
"""Read-only auditor for an isolated Stage3 Freqtrade diagnostic archive."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from m2r_v6_global_batch import native_audit
p=argparse.ArgumentParser()
p.add_argument("folder",type=Path)
p.add_argument("--policy",choices=("fixed","trailing"),default="fixed")
p.add_argument("--days",type=int,choices=(30,60,90,180),default=30)
a=p.parse_args()
print(json.dumps(native_audit(a.folder,a.policy,a.days),sort_keys=True,indent=2))
