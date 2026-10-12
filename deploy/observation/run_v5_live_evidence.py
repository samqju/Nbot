"""Manual, opt-in V5 public research capture. No installed service or orders."""
import argparse
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-only", action="store_true", required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--database", type=Path, default=Path("data/observation/v5/live_evidence.db"))
    args = parser.parse_args()
    from nbot.observation.v5_live_evidence import LiveEvidenceBridge
    from nbot.observation.v5_live_transport import run_research_capture
    bridge = LiveEvidenceBridge(args.database, symbols=args.symbols)
    bridge.initialize()
    print("V5 public research evidence capture; order authority NONE", flush=True)
    try:
        asyncio.run(run_research_capture(bridge, enabled=args.research_only))
    except KeyboardInterrupt:
        print("V5 research capture stopped; checkpoints retained", flush=True)


if __name__ == "__main__":
    main()
