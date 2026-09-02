from __future__ import annotations

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
    root = Path(__file__).resolve().parent
    target = root / "DISTRIBUTION_MANIFEST.json"
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == target:
            continue
        if any(part in {".venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        files.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)})
    target.write_text(
        json.dumps(
            {
                "package": "NewHarmony_F_Corrected_Eco_Standalone",
                "source_commit": "d71a68c6f02cde756ed814b8e209b23177ab56e0",
                "file_count_excluding_manifest": len(files),
                "files": files,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Manifest distribuzione: {len(files)} file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

