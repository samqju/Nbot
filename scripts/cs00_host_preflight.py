"""Read-only CS-00 resource snapshot; never starts or configures services."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nbot_v5_1.cs00_host_monitor import inspect_offline_host

if __name__=="__main__":
    result=inspect_offline_host()
    print(json.dumps(result,sort_keys=True),flush=True)
