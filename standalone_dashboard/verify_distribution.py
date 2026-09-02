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


def verify_manifest(root: Path, filename: str, base: Path) -> list[str]:
    manifest = json.loads((root / filename).read_text(encoding="utf-8"))
    failures = []
    for row in manifest["files"]:
        path = base / row["path"]
        if not path.is_file():
            failures.append(f"MISSING {path.relative_to(root)}")
        elif path.stat().st_size != row["size"] or sha256(path) != row["sha256"]:
            failures.append(f"MISMATCH {path.relative_to(root)}")
    return failures


def main() -> int:
    root = Path(__file__).resolve().parent
    failures = []
    failures += verify_manifest(root, "ENGINE_INTEGRITY.json", root / "engine")
    distribution = json.loads((root / "DISTRIBUTION_MANIFEST.json").read_text(encoding="utf-8"))
    for row in distribution["files"]:
        path = root / row["path"]
        if not path.is_file():
            failures.append(f"MISSING {row['path']}")
        elif path.stat().st_size != row["size"] or sha256(path) != row["sha256"]:
            failures.append(f"MISMATCH {row['path']}")
    if failures:
        print("Distribuzione non valida:")
        for failure in failures:
            print("FAIL", failure)
        return 1
    print(f"PASS engine files: {json.loads((root / 'ENGINE_INTEGRITY.json').read_text(encoding='utf-8'))['file_count']}")
    print(f"PASS distribution files: {distribution['file_count_excluding_manifest']}")
    print("PASS Milestone F Corrected vendored files are byte-identical to the GitHub source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

