from __future__ import annotations

import hashlib
import json
from pathlib import Path


IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_manifest(root: Path) -> dict:
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    tree = hashlib.sha256(
        json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    # Non serializzare il percorso assoluto dell'utente nei pacchetti distribuibili.
    return {"root": root.name, "file_count": len(files), "tree_sha256": tree, "files": files}


def write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assert_unchanged(before: dict, after: dict) -> None:
    if before["tree_sha256"] != after["tree_sha256"]:
        before_map = {row["path"]: row for row in before["files"]}
        after_map = {row["path"]: row for row in after["files"]}
        changed = sorted(
            path
            for path in set(before_map) | set(after_map)
            if before_map.get(path) != after_map.get(path)
        )
        raise RuntimeError("Milestone F Corrected è cambiato: " + ", ".join(changed))
