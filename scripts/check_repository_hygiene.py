from __future__ import annotations

import subprocess
from pathlib import PurePosixPath


FORBIDDEN_DIRS = {
    ".next",
    ".venv",
    "backups",
    "build",
    "dist",
    "node_modules",
}
FORBIDDEN_NAMES = {
    ".env",
    "code_dumper.py",
    "full_keshepool_project_code.txt",
}
FORBIDDEN_SUFFIXES = (
    ".backup",
    ".cer",
    ".crt",
    ".dump",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sql",
    ".sql.gz",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
)


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=False,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def rejection_reason(path_text: str) -> str | None:
    path = PurePosixPath(path_text)
    lowered_parts = tuple(part.lower() for part in path.parts)
    name = path.name.lower()

    if lowered_parts == ("backups", ".gitkeep"):
        return None
    if any(part in FORBIDDEN_DIRS for part in lowered_parts[:-1]):
        return "generated or private directory"
    if name in FORBIDDEN_NAMES:
        return "forbidden source or environment file"
    if name.startswith(".env.") and name != ".env.example":
        return "private environment file"
    if name.endswith(FORBIDDEN_SUFFIXES):
        return "dump, key, certificate, or archive file"
    return None


def main() -> int:
    rejected = [
        (path, reason)
        for path in tracked_paths()
        if (reason := rejection_reason(path)) is not None
    ]
    if not rejected:
        print("repository hygiene check passed")
        return 0

    for path, reason in rejected:
        print(f"repository hygiene check failed: {path}: {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
