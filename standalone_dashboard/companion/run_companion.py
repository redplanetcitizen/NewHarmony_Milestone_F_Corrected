from __future__ import annotations

import argparse
import json
from pathlib import Path

from eco_companion import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Contabilità ecologica ex post per Milestone F Corrected"
    )
    parser.add_argument("--milestone-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    report = run_pipeline(args.milestone_root, root, output)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.serve:
        from dashboard.server import serve

        serve(root / "dashboard", args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

