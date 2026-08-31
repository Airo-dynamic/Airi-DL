"""Seal staged first-party files; verify closed manifests and replayable patches."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

META = {"SNAPSHOT.json", "CHANGES.patch", "MANIFEST.sha256", "DEVLOG.md"}
FORBIDDEN = {".git", "BACKGROUND", "HISTORY", "build", ".venv", "__pycache__", "vendor"}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)


def safe(name: str) -> bool:
    path = Path(name)
    return (
        bool(name)
        and not path.is_absolute()
        and path.as_posix() == name
        and not (set(path.parts) & (FORBIDDEN | {".."}) or "\\" in name)
        and not any(ord(character) < 32 for character in name)
    )


def inventory(root: Path) -> dict[str, str]:
    result = {}
    require(not root.is_symlink(), f"symlink: {root}")
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        require(safe(name) and not path.is_symlink(), f"unsafe path: {name}")
        require(path.is_file() or path.is_dir(), f"non-regular path: {name}")
        if path.is_file():
            require(path.stat().st_mode & 0o111 == 0, "executable files unsupported")
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def payload(root: Path) -> dict[str, str]:
    return {name: sha for name, sha in inventory(root).items() if name not in META}


def copy_files(source: Path, target: Path, names: dict[str, str]) -> None:
    for name in names:
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target / name)


def verify(snapshot: Path, parent: Path | None = None, integrity_only: bool = False) -> None:
    actual = inventory(snapshot)
    listed = {}
    for line in (snapshot / "MANIFEST.sha256").read_text().splitlines():
        sha, separator, name = line.partition("  ")
        name = name.removeprefix("./")
        require(bool(separator and re.fullmatch(r"[0-9a-f]{64}", sha)), "bad manifest row")
        require(safe(name) and name not in listed and name != "MANIFEST.sha256", "bad path")
        listed[name] = sha
    actual.pop("MANIFEST.sha256")
    require(actual == listed, "manifest mismatch: modified, missing or extra files")
    info = json.loads((snapshot / "SNAPSHOT.json").read_text())
    day = info["day"]
    require(info["schema"] == "airidl.snapshot/v1", "unsupported snapshot schema")
    require(isinstance(day, str) and bool(re.fullmatch(r"day\d{3}", day)), "bad day")
    require(
        (snapshot / "DEVLOG.md").read_bytes()
        == (snapshot / "docs/devlogs" / f"{day}.md").read_bytes(),
        "DEVLOG mismatch",
    )
    require(len(payload(snapshot)) == info["source"]["canonical_file_count"], "file count")
    if integrity_only:
        return
    with tempfile.TemporaryDirectory(prefix="airidl-replay-") as directory:
        replay = Path(directory)
        if info["parent"] is not None:
            require(
                parent is not None, "parent required for replay; use --integrity-only explicitly"
            )
            if parent is not None:
                verify(parent, integrity_only=True)
                require(
                    json.loads((parent / "SNAPSHOT.json").read_text())["day"] == info["parent"],
                    "wrong parent",
                )
                copy_files(parent, replay, payload(parent))
        else:
            require(day == "day001" and parent is None, "invalid empty-tree base")
        git(replay, "apply", "--binary", "--whitespace=nowarn", str(snapshot / "CHANGES.patch"))
        require(inventory(replay) == payload(snapshot), "patch replay mismatch")


def chain(root: Path) -> list[Path]:
    snapshots = sorted((root / "HISTORY").glob("day*"))
    for number, snapshot in enumerate(snapshots, 1):
        require(snapshot.name == f"day{number:03d}", "non-contiguous days")
        verify(snapshot, snapshots[number - 2] if number > 1 else None)
        require(
            json.loads((snapshot / "SNAPSHOT.json").read_text())["day"] == snapshot.name,
            "directory/day mismatch",
        )
    if snapshots:
        require(
            (root / "HISTORY/LATEST").read_text().strip() == snapshots[-1].name, "LATEST mismatch"
        )
    return snapshots


def canonical(root: Path) -> dict[str, str]:
    require(
        not git(root, "ls-files", "--others", "--exclude-standard").strip(), "stage new files first"
    )
    require(not git(root, "ls-files", "-ci", "--exclude-standard").strip(), "ignored file staged")
    names = {}
    for row in git(root, "ls-files", "--stage", "-z").split("\0"):
        if not row:
            continue
        attributes, name = row.split("\t", 1)
        mode, _, stage = attributes.split()
        if name.startswith("HISTORY/"):
            continue
        require(
            mode == "100644" and stage == "0", "only regular non-executable source files allowed"
        )
        require(safe(name) and name not in META, f"forbidden payload: {name}")
        require(not any(p.is_symlink() for p in [root / name, *(root / name).parents]), "symlink")
        names[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return names


def make_patch(previous: Path | None, current: Path, names: dict[str, str]) -> str:
    with tempfile.TemporaryDirectory(prefix="airidl-diff-") as directory:
        tree = Path(directory)
        old = payload(previous) if previous else {}
        if previous:
            copy_files(previous, tree, old)
        git(tree, "init", "-q")
        git(tree, "add", "--all", "--force")
        base = git(tree, "write-tree").strip()
        git(tree, "rm", "-r", "--force", "--quiet", "--ignore-unmatch", "--", ".")
        copy_files(current, tree, names)
        git(tree, "add", "--all", "--force")
        return git(tree, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", base)


def seal(root: Path, day: str) -> None:
    snapshots = chain(root)
    require(day == f"day{len(snapshots) + 1:03d}", "seal only the next day; never overwrite")
    git(root, "diff", "--exit-code", "--quiet")
    names = canonical(root)
    previous = snapshots[-1] if snapshots else None
    history = root / "HISTORY"
    history.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".seal-", dir=history) as directory:
        snapshot = Path(directory) / day
        snapshot.mkdir()
        copy_files(root, snapshot, names)
        shutil.copy2(root / "docs/devlogs" / f"{day}.md", snapshot / "DEVLOG.md")
        info = {
            "schema": "airidl.snapshot/v1",
            "day": day,
            "parent": previous.name if previous else None,
            "project_version": tomllib.loads((root / "pyproject.toml").read_text())["project"][
                "version"
            ],
            "created_at": datetime.now(UTC).isoformat(),
            "source": {"canonical_file_count": len(names)},
        }
        (snapshot / "SNAPSHOT.json").write_text(json.dumps(info, indent=2) + "\n")
        (snapshot / "CHANGES.patch").write_text(make_patch(previous, root, names))
        (snapshot / "MANIFEST.sha256").write_text(
            "".join(f"{sha}  ./{name}\n" for name, sha in inventory(snapshot).items())
        )
        verify(snapshot, previous)
        snapshot.rename(history / day)
    (history / "LATEST").write_text(day + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sealing = commands.add_parser("seal")
    sealing.add_argument("day")
    checking = commands.add_parser("verify")
    checking.add_argument("snapshot", type=Path)
    checking.add_argument("--parent", type=Path)
    checking.add_argument("--integrity-only", action="store_true")
    commands.add_parser("verify-root")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            verify(
                args.snapshot.absolute(),
                args.parent.absolute() if args.parent else None,
                args.integrity_only,
            )
        else:
            root = Path.cwd()
            require(
                git(root, "rev-parse", "--show-toplevel").strip() == str(root), "run at Git root"
            )
            if args.command == "seal":
                seal(root, args.day)
            else:
                snapshots = chain(root)
                require(bool(snapshots), "no snapshots")
                require(canonical(root) == payload(snapshots[-1]), "root/latest mismatch")
        scope = (
            "integrity only; replay NOT RUN" if getattr(args, "integrity_only", False) else "full"
        )
        print(f"PASS: {args.command} ({scope})")
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
