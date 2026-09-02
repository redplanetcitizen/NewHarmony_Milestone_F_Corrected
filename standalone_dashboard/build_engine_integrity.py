from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    engine = root / "engine"
    source = args.source.resolve()
    rows = []
    for path in sorted(engine.rglob("*")):
        if not path.is_file() or any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        relative = path.relative_to(engine)
        original = source / relative
        if not original.is_file():
            raise SystemExit(f"File incorporato assente nella sorgente: {relative}")
        target_hash = sha256(path)
        source_hash = sha256(original)
        if target_hash != source_hash or path.stat().st_size != original.stat().st_size:
            raise SystemExit(f"File incorporato non identico: {relative}")
        rows.append({"path": relative.as_posix(), "size": path.stat().st_size, "sha256": target_hash})
    report = {
        "source_repository": "https://github.com/redplanetcitizen/NewHarmony_Milestone_F_Corrected",
        "source_commit": "d71a68c6f02cde756ed814b8e209b23177ab56e0",
        "file_count": len(rows),
        "all_included_files_byte_identical": True,
        "files": rows,
    }
    (root / "ENGINE_INTEGRITY.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Engine incorporato: {len(rows)} file identici")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

