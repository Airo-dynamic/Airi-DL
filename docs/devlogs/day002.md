# day002：把每日工程封存为可验证、可回放的快照

## 1. 目标、非目标、前置知识和预计时长

今天只学习一个主概念：如何证明一份历史源码既完整，又确实是前一天加上当天增量。
预计 4–5 小时。需要了解 Git 暂存区、Python 字典/Path、文件哈希和子进程；无需机器学习知识。

目标：实现 seal、verify、verify-root；写负向测试；验证可选缓存和仓库外构建。
非目标：CI（day004）、分布式 checkpoint、签名、防恶意代码执行沙箱、GPU 与训练。
不要将这里的目录 rename 当成 day057 的 fsync/COMMITTED 存储提交协议。

今日新增一方源码、测试、构建配置共 350 行（含空行），涉及 6 个文件；
另有 README 和本开发日志，共 8 个变更文件。没有变更依赖，所以 uv.lock 不变。
包与 C++ runtime 版本仍为 0.1.0.dev1；快照身份更新为 day002。

## 2. 理论与数据流

三种检查不是同一件事：

| 检查 | 证明什么 | 不能证明什么 |
|---|---|---|
| SHA-256 + 闭集清单 | 文件未改、未丢、没有夹带额外文件 | 代码行为正确、来源可信 |
| 前一日 payload + CHANGES.patch | 增量可回放到本日完整源码 | 构建通过、历史未被协同重写 |
| 仓库外 make check | 源码不依赖原仓库路径，可构建测试 | CUDA/Ubuntu 已验证 |

payload 是快照内除四个根级 metadata 文件以外的全部文件。README 和
docs/devlogs/dayNNN.md 属于 payload；DEVLOG.md 是当日日志副本。CHANGES.patch
只比较 payload，不能包含 HISTORY，否则会把快照递归装进快照。

```text
暂存区文件清单 -> 复制 payload -> DEVLOG + SNAPSHOT + patch -> manifest
                         ↓                       ↓
                  独立临时 Git index       临时目录 replay 对账
                                                 ↓
                                     rename 发布 -> 写 HISTORY/LATEST
```

manifest 不包含自身，否则产生自引用。校验时比较整个路径到哈希的字典，不能只遍历
manifest 中已有的路径；后者发现不了夹带文件。路径还要禁止绝对路径、..、控制字符、
符号链接、Git 元数据和 BACKGROUND。暂存区中强制加入的 ignored 文件也会失败。

当前只接受 Git 100644 普通非可执行文件：Python 工具显式通过解释器运行，不依赖 chmod。
未来若引入可执行脚本，应先扩展元数据中的 mode 契约和测试，不能静默忽略文件权限。

## 3. 按依赖顺序逐字符修改

学习分支从 day001 tag 开始；已经处于 day002 的读者，应先读日志，再决定是否建立学习分支。
下面依次给出全部工具/测试代码和已有源码的精确 diff，不使用伪代码省略。
README 与日志属于说明文档，完整原文在本快照的 CHANGES.patch 中；不在日志中递归复制日志自身。

```bash
git switch -c codex/learn-day002 day001
uv sync --frozen
```

### 步骤 1：路径、库存和复制

创建 tools/history.py，先录入以下内容。require 不使用 assert：验证器在 python -O 下也必须校验。
git 参数使用数组，不经过 shell；inventory 在读取文件内容前拒绝 symlink/特殊文件。
copy2 保留文件权限；当前权限白名单避免 checksum 相同但执行位丢失。

```python
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
```

```bash
uv run python -m py_compile tools/history.py
```

### 步骤 2：完整性、回放链与暂存区边界

继续追加。verify 默认必须回放：day001 从空目录开始，其他 day 必须传入正确 parent。
仅 --integrity-only 可跳过回放，并在输出中明确写 NOT RUN。这个选项方便独立快照先验文件、后构建。
chain 同时检查编号连续、目录与 metadata 的 day 一致、LATEST 指向最后一天。
canonical 只接受已暂存清单，排除整个 HISTORY，不扫描 BACKGROUND 的内部内容。

```python
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
```

```bash
uv run python -m py_compile tools/history.py
```

### 步骤 3：生成 patch、封存与命令入口

继续追加剩余代码。make_patch 在临时 Git 仓库使用 write-tree 获取基线树，不创建临时 commit，
因此不需要 Git 作者身份。先复制前一日，记录 index，再删除旧 payload、复制当日 payload，
最后比较两个 index 状态：新增、修改、删除和目录变文件都能进入 patch。
临时 index 尚无 HEAD，git rm 需要 --force；它只删除工具刚刚创建的临时副本，绝不操作真实仓库。

seal 先验证旧链并拒绝未暂存修改，再在临时目录生成全部 metadata；回放成功才发布。
只能封存连续下一天，不能覆盖已有 day。写入失败会返回非零，不能假装成功。
这里假设单个封存者、可信本地仓库，不承诺断电一致性或并发事务。

```python
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
```

```bash
uv run python tools/history.py verify HISTORY/day001
```

期望 PASS: verify (full)。day001 没有本工具，直接使用刚写的 day002 工具读取它，不修改 day001。

### 步骤 4：测试与工程入口

新增 tests/test_history.py。测试只在 pytest 临时目录创建虚构仓库；其中的 private.txt 是测试文本，
不是 BACKGROUND 中的任何真实文件。一个两日测试涵盖增删改、目录变文件、完整链、仓库外校验、重复封存和根漂移。
损坏测试覆盖额外文件、缺失、哈希不符、重复条目、路径穿越、symlink 和执行位；
最后一个测试说明：即使重新计算 manifest，坏 patch 仍不能通过完整验证。

```python
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
```

```bash
uv run pytest tests/test_history.py
```

随后按下面 diff 修改 Makefile 和三个版本位置。去掉上下文标记与行首 +/-，不要将 diff header 抄进源码。
新增源码文件无需再复制一次。AIRIDL_CACHE_DIR 只在非空时导出 UV_CACHE_DIR；未设置时沿用 uv 默认行为。
本日没有 C++ 外部依赖，因此不添加尚无用途的 FetchContent 参数。

```diff
diff --git a/Makefile b/Makefile
index 5b9aecc..33bab28 100644
--- a/Makefile
+++ b/Makefile
@@ -4,0 +5,3 @@ PROFILE ?= auto
+ifneq ($(strip $(AIRIDL_CACHE_DIR)),)
+export UV_CACHE_DIR := $(abspath $(AIRIDL_CACHE_DIR))/uv
+endif
@@ -6 +9 @@ PROFILE ?= auto
-.PHONY: help sync doctor lint typecheck py-test configure build cpp-test sanitize check
+.PHONY: help sync doctor lint typecheck py-test configure build cpp-test sanitize check history-verify
@@ -9 +12 @@ help:
-	@echo "Airi-DL day001 targets: sync doctor lint typecheck py-test build cpp-test sanitize check"
+	@echo "Airi-DL targets: sync doctor lint typecheck py-test build cpp-test sanitize check history-verify"
@@ -18,2 +21,2 @@ lint:
-	$(UV) run ruff check src tests
-	$(UV) run ruff format --check src tests
+	$(UV) run ruff check src tests tools
+	$(UV) run ruff format --check src tests tools
@@ -22 +25 @@ typecheck:
-	$(UV) run mypy src tests
+	$(UV) run mypy src tests tools
@@ -41,0 +45,3 @@ check: lint typecheck py-test cpp-test sanitize
+
+history-verify:
+	$(UV) run python tools/history.py verify-root
diff --git a/cpp/include/airidl/version.hpp b/cpp/include/airidl/version.hpp
index c96476a..2800680 100644
--- a/cpp/include/airidl/version.hpp
+++ b/cpp/include/airidl/version.hpp
@@ -8 +8 @@ inline constexpr std::string_view kProjectName{"Airi-DL"};
-inline constexpr std::string_view kSnapshot{"day001"};
+inline constexpr std::string_view kSnapshot{"day002"};
diff --git a/cpp/tests/version_test.cpp b/cpp/tests/version_test.cpp
index 8e4ac6a..8b3e470 100644
--- a/cpp/tests/version_test.cpp
+++ b/cpp/tests/version_test.cpp
@@ -6 +6 @@ int main() {
-    if (airidl::kProjectName != "Airi-DL" || airidl::kSnapshot != "day001" ||
+    if (airidl::kProjectName != "Airi-DL" || airidl::kSnapshot != "day002" ||
diff --git a/env/versions.toml b/env/versions.toml
index 4ba1b63..17874fc 100644
--- a/env/versions.toml
+++ b/env/versions.toml
@@ -7 +7 @@ version = "0.1.0.dev1"
-snapshot = "day001"
+snapshot = "day002"
```

```bash
make check
```

### 步骤 5：文档、暂存与候选验收

更新 README 为当前进度、独立校验、缓存入口和本日日志链接，并保存本日志到 docs/devlogs/day002.md。
先完整检查 diff，再明确列出这 8 个文件暂存；不要执行 git add -f，也不要把 BACKGROUND 加进 Git。

```bash
git add tools/history.py tests/test_history.py Makefile env/versions.toml \
  cpp/include/airidl/version.hpp cpp/tests/version_test.cpp \
  README.md docs/devlogs/day002.md
git diff --cached --check
git diff --cached --stat
git diff day001 -- HISTORY/day001
git ls-files BACKGROUND
```

最后两个命令必须没有输出。未暂存源码、未跟踪新文件或被强制暂存的 ignored 文件都会阻止 seal。
先在仓库外候选副本运行完整测试；不要在冻结 HISTORY 目录中执行 uv sync 或 make check。

### 步骤 6：封存、独立检查和提交

```bash
uv run python tools/history.py seal day002
git add HISTORY/day002 HISTORY/LATEST
make history-verify
snapshot_dir="$(mktemp -d)/airidl-day002"
cp -R HISTORY/day002 "$snapshot_dir"
python3.12 tools/history.py verify "$snapshot_dir" --parent HISTORY/day001
cd "$snapshot_dir"
make sync
make check
```

回到原仓库后再次执行 make history-verify、git diff --cached --check 和 day001 差异检查。
确认全部通过才创建 day002 commit 和 annotated tag；重复执行 seal 不会覆盖冻结快照。

```bash
git commit -m "day002: add snapshot sealing and replay verification"
git tag -a day002 -m "day002: independently verified snapshot tooling"
```


## 4. 每 1–2 步的 build/test 节奏

| 完成点 | 命令 | 预期 |
|---|---|---|
| 路径/文件工具 | python -m py_compile | 无语法错误 |
| verify/chain/canonical | python -m py_compile | 无语法错误 |
| seal/CLI | verify HISTORY/day001 | 空基线回放与清单通过 |
| 测试文件 | pytest tests/test_history.py | 9 passed |
| Makefile/快照编号 | make check | Python 与 C++/sanitizer 通过 |
| 候选/封存 | verify-root + 仓库外 make check | 完整链、root/latest、独立构建通过 |

## 5. 全部变更覆盖表

| CHANGES.patch 文件 | 本日志中的对应步骤 |
|---|---|
| tools/history.py | 步骤 1–3，全部 230 行 |
| tests/test_history.py | 步骤 4，全部 106 行 |
| Makefile | 步骤 4，精确 diff |
| env/versions.toml | 步骤 4，snapshot 字段 diff |
| cpp/include/airidl/version.hpp | 步骤 4，kSnapshot diff |
| cpp/tests/version_test.cpp | 步骤 4，期望值 diff |
| README.md | 步骤 5；完整文字在 patch |
| docs/devlogs/day002.md | 本文件全文；无需递归嵌入自己 |

生成物不属于手写增量：HISTORY/day002 的 payload 副本、DEVLOG.md、SNAPSHOT.json、
CHANGES.patch、MANIFEST.sha256，以及 HISTORY/LATEST。它们由 seal 生成并在提交中保存。
本日没有修改 HISTORY/day001 或任何 BACKGROUND 内容。

## 6. 实际命令、输出、性能或失败证据

执行日期：2026-08-31。宿主 macOS 15.5 arm64，Python 3.12.13、AppleClang 17、CMake 4.3.3。
本机 uv 0.12.6 位于临时工具目录，通过 Makefile 的 UV 参数传入，不写入仓库配置。

实际命令（路径是本次宿主的工具位置，不是工程依赖）：

```bash
make check UV=/tmp/airidl-uv.y6bnmY/venv/bin/uv
# 在仓库外的全新候选快照目录中；empty-cache 起初不存在。
UV_PYTHON=/Users/bilibili/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  make sync check UV=/tmp/airidl-uv.y6bnmY/venv/bin/uv \
  AIRIDL_CACHE_DIR=/tmp/airidl-day002-candidate.kWI9WF/empty-cache
# 另一份全新候选目录复用同一缓存，显式禁止 uv 访问网络。
UV_OFFLINE=1 \
UV_PYTHON=/Users/bilibili/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  make sync check UV=/tmp/airidl-uv.y6bnmY/venv/bin/uv \
  AIRIDL_CACHE_DIR=/tmp/airidl-day002-candidate.kWI9WF/empty-cache
```

```text
root (AIRIDL_CACHE_DIR unset): ruff/format PASS; strict mypy 9 files PASS
root final: pytest 19/19; CTest dev 1/1; ASan+UBSan 1/1 PASS
cold candidate: prepared 14 packages in 6.54s; installed 14; full make check PASS
shared-cache fresh copy: UV_OFFLINE=1; installed 14; full make check PASS
final candidate after directory-to-file correction: pytest 19/19; CTest 1/1 + 1/1 PASS
candidate seal + verify-root: PASS (day001 -> day002 replay and root/latest)
candidate full verify using original day001 as parent: PASS
candidate inventory: 29 payload files + 4 metadata; 32 manifest entries
manual negative: force-staged synthetic ignored .env -> FAIL: ignored file staged (exit 1)
old snapshot: git diff day001 -- HISTORY/day001 -> empty
BACKGROUND: git ls-files BACKGROUND -> empty; /BACKGROUND/ remains ignored
```

空缓存试验发生在目录替换边界修正前；修正后从 day001 再生成最终候选，使用共享缓存
完整复跑上表门禁。最终封存前只补写本节实验记录，工具、测试、配置和依赖不再改动。
离线成功仅指这一宿主已下载齐全的 Python 工具缓存，不代表任意新机器都能离线构建。
本日没有性能 benchmark，上面的依赖准备耗时不作为系统性能结论。

真实失败与修正：测试先暴露临时 Git index 尚无 HEAD，git rm 拒绝移除已暂存旧文件
（1 failed, 18 passed）。修正为只在工具创建的临时仓库执行 git rm --force 后，
目录变文件回放与全量 19 项测试通过；没有在真实项目中执行该删除命令。
单独运行 mypy tools tests 曾因漏传 src 报 import-untyped；Makefile 的正式命令
mypy src tests tools 通过，没有使用 ignore_missing_imports 掩盖类型问题。

## 7. 故障排查、自测题、局限和下一日接口

- stage new files first：按步骤 5 暂存全部本日文件；检查有无误放到根目录的临时文件。
- ignored file staged：用 git diff --cached --name-only 定位；不要通过放宽 ignore 来发布私密材料。
- manifest mismatch：禁止直接重算历史 manifest；确认是否在 HISTORY 里运行过构建。
- parent required：回放需要 --parent；只检查独立副本时明确用 --integrity-only。
- root/latest mismatch：是否还在开发下一天？未封存的根源码本就不应等于上一天。
- Git 报 patch apply 失败：检查父快照及完整 patch；不要使用 --unsafe-paths 绕过安全检查。
- uv 网络失败：记录失败原因，可重试；不能把缺依赖当成测试成功。
- seal 已发布目录但 LATEST 写入中断：停止并检查目录/清单/回放，再单独恢复指针，禁止重写快照。

自测题：

1. 为什么仅执行 sha256sum -c 发现不了额外文件？
2. 为什么 manifest 不包含自身，CHANGES.patch 不包含整个 HISTORY？
3. 为什么校验过 checksum 仍然要 git apply 和 make check？
4. Git 暂存区能否阻止已经 git add -f 的私密文件？本实现增加了哪道检查？
5. 为什么修改执行位也应失败？未来若允许脚本，需要补什么契约？
6. 为什么 shared cache 加速不等于离线构建承诺？

局限：这里只验证可信本地快照的一致性，不是签名/恶意仓库沙箱；manifest 与 patch 被协同重写
仍需由可信 Git 基线发现。day004 会加入 CI 和基于 Git 的旧快照不变检查。
当前 seal 不自动运行测试、创建 commit/tag 或推送；这些仍由验收者按日志执行。
文件预算也由 diff 人工验收，CI 门禁在 day004 实现。快照发布为单写者操作，LATEST 更新不具备断电事务保证。
本日没有 GPU workload，Ubuntu/RTX 5090/CUDA 全部仍为 not-run，云费用为 ¥0。
下一天只推进配置与 artifact schema，不提前进入 ML 训练。
