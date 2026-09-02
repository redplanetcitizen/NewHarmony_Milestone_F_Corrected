from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="NewHarmony F Corrected Eco standalone")
    parser.add_argument("--serve", action="store_true", help="avvia il cruscotto locale")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    companion = root / "companion"
    sys.path.insert(0, str(companion))
    sys.dont_write_bytecode = True
    from eco_companion import run_pipeline

    report = run_pipeline(root / "engine", companion, root / "outputs")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.serve:
        from dashboard.server import serve

        serve(companion / "dashboard", args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

