#!/usr/bin/env python3
"""Read-only WSS symptoms from existing service journals; no runtime interruption."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nbot.operator.wss_diagnosis import wss_status
if __name__ == '__main__':
    print(json.dumps(wss_status(), sort_keys=True, indent=2))
