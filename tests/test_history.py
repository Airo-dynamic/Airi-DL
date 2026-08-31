import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "tools/history.py"


def run(root: Path, *args: str, ok: bool = True) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=root, text=True, capture_output=True
    )
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    return result.stdout + result.stderr


def stage(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "--all"], check=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    (tmp_path / ".gitignore").write_text("/BACKGROUND/\n")
    (tmp_path / "BACKGROUND").mkdir()
    (tmp_path / "BACKGROUND/private.txt").write_text("must not be copied")
    (tmp_path / "docs/devlogs").mkdir(parents=True)
    (tmp_path / "docs/devlogs/day001.md").write_text("first day\n")
    (tmp_path / "old").mkdir()
    (tmp_path / "old/remove.txt").write_text("deleted on day002\n")
    stage(tmp_path)
    run(tmp_path, "seal", "day001")
    stage(tmp_path)
    return tmp_path


def test_two_day_replay_and_standalone(
    repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    run(repo, "verify-root")
    (repo / "old/remove.txt").unlink()
    (repo / "old").rmdir()
    (repo / "old").write_text("file replaces directory\n")
    (repo / "docs/devlogs/day001.md").write_text("root edit; frozen day001 is unchanged\n")
    (repo / "docs/devlogs/day002.md").write_text("second day\n")
    stage(repo)
    run(repo, "seal", "day002")
    stage(repo)
    run(repo, "verify-root")
    detached = tmp_path_factory.mktemp("detached") / "snapshot"
    shutil.copytree(repo / "HISTORY/day002", detached)
    run(repo, "verify", str(detached), ok=False)
    assert "replay NOT RUN" in run(repo, "verify", str(detached), "--integrity-only")
    run(repo, "verify", str(detached), "--parent", str(repo / "HISTORY/day001"))
    assert not (detached / "BACKGROUND").exists()
    run(repo, "seal", "day002", ok=False)
    (repo / "pyproject.toml").write_text("drift")
    run(repo, "verify-root", ok=False)
    run(repo, "seal", "day003", ok=False)


@pytest.mark.parametrize(
    "damage", ["extra", "missing", "hash", "duplicate", "traversal", "symlink", "mode"]
)
def test_reject_damaged_snapshot(repo: Path, damage: str) -> None:
    snapshot = repo / "HISTORY/day001"
    victim = snapshot / "old/remove.txt"
    manifest = snapshot / "MANIFEST.sha256"
    if damage == "extra":
        (snapshot / "extra.txt").write_text("extra")
    elif damage == "missing":
        victim.unlink()
    elif damage == "hash":
        victim.write_text("corrupt")
    elif damage == "mode":
        victim.chmod(0o755)
    elif damage == "symlink":
        victim.unlink()
        victim.symlink_to(repo / "old/remove.txt")
    else:
        row = (
            manifest.read_text().splitlines()[0]
            if damage == "duplicate"
            else "0" * 64 + "  ../escape"
        )
        manifest.write_text(manifest.read_text() + row + "\n")
    run(repo, "verify", str(snapshot), ok=False)


def test_patch_is_checked_even_with_rehashed_manifest(repo: Path) -> None:
    snapshot = repo / "HISTORY/day001"
    (snapshot / "CHANGES.patch").write_text("not a patch\n")
    manifest = snapshot / "MANIFEST.sha256"
    manifest.write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(snapshot)}\n"
            for p in sorted(snapshot.rglob("*"))
            if p.is_file() and p != manifest
        )
    )
    run(repo, "verify", str(snapshot), "--integrity-only")
    run(repo, "verify", str(snapshot), ok=False)
