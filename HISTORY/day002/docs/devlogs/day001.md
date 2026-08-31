# day001：重启、双语言骨架与环境自检

## 1. 目标、非目标、前置知识和预计时长

目标是从空 Git tree 建立第一个可独立 configure/build/test 的 Airi-DL 快照，并让
`airidl doctor` 诚实描述“当前开发宿主能做什么”。预计 4-5 小时。

前置知识：基本 shell、Git commit、C++ 编译/链接和 Python module。不了解 CMake preset、
`src` layout 或 uv 没关系，本日志会在第一次出现时解释。

非目标：Tensor、Autograd、PyTorch、CUDA 编译、GPU 测试、模型训练、分布式通信。
day001 在 CPU 环境通过不代表 RTX 5090 已验证。

## 2. 理论与数据流

C++ 构建链是：

```text
version.cpp -> object -> libairidl_core.a -> version_test.cpp -> executable -> CTest
```

`target_include_directories`、warning 和 sanitizer 全挂在具体 target 上，避免旧工程的
global flags 污染所有目标。源码显式列举，不使用 `GLOB`。

Python 路径是：

```text
pyproject.toml -> uv.lock -> editable package -> airidl.cli:main -> doctor report
```

`src/airidl` 避免在仓库根意外 import 未安装源码。doctor 只探测，不安装、不编译、
不创建缓存；profile 将 macOS CPU 开发、portable CI 与 Ubuntu CUDA 正式环境分开。

## 3. 按依赖顺序逐字符修改

从空目录手写时，以同目录 `CHANGES.patch` 为逐字符真源：10 个实现/测试文件按 patch
逐行录入，去掉最左侧 `+`，不要复制 diff header。Apache LICENSE 从官方文本核对，
`uv.lock` 必须由固定 uv 命令生成，snapshot metadata 由封存步骤生成，禁止手工伪造
checksum。每完成下面一步就运行对应检查，不要抄完整个 patch 后才排错。

### 步骤 1：仓库边界和版本

1. 写 `.gitignore`，第一条有效规则必须是 `/BACKGROUND/`。
2. 写 `.gitattributes`、`.editorconfig`、`.python-version` 和 Apache-2.0 `LICENSE`。
3. 写 `env/versions.toml`。区分系统 CUDA 13.0.3、PyTorch wheel 构建 CUDA 13.0.2
   和 wheel variant `cu130`；三者不是同一个版本字段。

检查：

```bash
git status --short
git check-ignore -v BACKGROUND
git ls-files --stage | grep '^160000 ' && exit 1 || true
```

### 步骤 2：C++20 最小库

1. 先写 `cpp/include/airidl/version.hpp`，只暴露常量和 `Version()`。
2. 再写 `cpp/runtime/version.cpp`，实现版本字符串。
3. 写 `cpp/tests/version_test.cpp`；失败返回 1，成功返回 0。
4. 写 `CMakeLists.txt` 和 `CMakePresets.json`，最后写 Makefile 的 C++ targets。

检查：

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

### 步骤 3：Python 包和 doctor

1. 写 `pyproject.toml`，runtime dependency 保持为空。
2. 写 `src/airidl/__init__.py` 和 `__main__.py`。
3. 写 `doctor.py`：先定义状态和 Check，再写无副作用 probe，最后组合 report。
4. 写 `cli.py`；`python -m airidl` 与 console script 必须共用同一个 `main()`。
5. 按 `test_version.py -> test_doctor.py -> test_cli.py` 顺序写测试。

检查：

```bash
uv lock
uv sync --frozen
uv run ruff check src tests
uv run mypy src tests
uv run pytest
uv run airidl doctor --json
```

### 步骤 4：文档和独立快照

1. 写根 README、ADR、重启审计、路线和本日志。
2. 将根目录的一方工程复制为 `HISTORY/day001`，排除 `.git`、`BACKGROUND`、`build`、
   `.venv` 和整个根 `HISTORY`。
3. 生成 `SNAPSHOT.json`；`CHANGES.patch` 是空 tree 到一方工程的 patch。
4. `MANIFEST.sha256` 覆盖快照内除自身外的所有文件。
5. 写 `HISTORY/LATEST=day001`；冻结后只能通过 ERRATA 说明错误。

检查：

```bash
snapshot_dir="$(mktemp -d)/airidl-day001"
cp -R HISTORY/day001 "$snapshot_dir"
cd "$snapshot_dir"
# 若当前目录本来就是独立 day001，从这里开始。
python3.12 -c 'from pathlib import Path; m={line.split(maxsplit=1)[1].removeprefix("./") for line in Path("MANIFEST.sha256").read_text().splitlines()}; a={str(p).removeprefix("./") for p in Path(".").rglob("*") if p.is_file()}; assert a == m | {"MANIFEST.sha256"}, (a-m, m-a)'
if command -v sha256sum >/dev/null; then sha256sum -c MANIFEST.sha256; else shasum -a 256 -c MANIFEST.sha256; fi
uv sync --frozen
make check
```

## 4. Build/test 节奏

| 完成点 | 必跑命令 | 失败时先看 |
|---|---|---|
| C++ header/source/test | `cmake --preset dev && cmake --build --preset dev` | target 源文件和 include scope |
| C++ test | `ctest --preset dev` | executable 返回码 |
| Python CLI | `uv run pytest tests/test_cli.py` | stdout 是否只有一个 JSON |
| Python 全量 | `ruff`、`mypy`、`pytest` | 格式、类型、行为分别处理 |
| 封存前 | `make check` + 仓库外快照重放 | 隐式根路径或未锁依赖 |

## 5. 全部变更覆盖表

| Patch 区域 | 文件 | 手写目的 |
|---|---|---|
| 治理 | `.gitignore` `.gitattributes` `.editorconfig` `.python-version` `LICENSE` | 边界、文本和许可证 |
| 构建 | `CMakeLists.txt` `CMakePresets.json` `Makefile` | C++20、CTest、sanitizer、任务入口 |
| 依赖 | `pyproject.toml` `uv.lock` `env/versions.toml` | Python/工具链可复现 |
| C++ | `cpp/include/airidl/version.hpp` `cpp/runtime/version.cpp` `cpp/tests/version_test.cpp` | 最小链接契约 |
| Python | `src/airidl/{__init__,__main__,cli,doctor}.py` | 包、CLI、环境报告 |
| 测试 | `tests/test_{version,doctor,cli}.py` | 版本、schema、退出码 |
| 决策 | `README.md` `docs/adr/...` `docs/audit/...` `docs/roadmap/...` | 范围和路线 |
| 快照 | `HISTORY/LATEST` `README.md` `DEVLOG.md` `SNAPSHOT.json` `CHANGES.patch` `MANIFEST.sha256` | 独立封存 |

`CHANGES.patch` 不包含三个由封存过程生成的 metadata 文件；它们由 day001 手工生成，
day002 再实现通用 `seal/verify`。除该明确例外，表中每个一方文件都必须在 patch 中出现。
day001 因 empty-tree bootstrap 具有唯一规模例外；从 day002 起严格执行 350 行/10 文件。

## 6. 实际命令、输出和证据

当前执行宿主是 macOS arm64，因此只记录 CPU bootstrap；
Ubuntu 24.04、RTX 5090、CUDA 13.0.3 和 PyTorch 2.13.0/cu130 均为“已锁定、未实机验证”。

```text
root: ruff/format PASS; strict mypy PASS; pytest 10/10 PASS
root: CTest dev 1/1 PASS; ASan+UBSan CTest 1/1 PASS
wheel: build/install PASS; packaged versions.toml policy resource PASS
doctor macos-dev: overall=pass, cpp=true, cuda=false (3 expected skips)
doctor unit matrix: Ubuntu CUDA driver 579=fail, 580.126.20=pass
snapshot: 26 canonical files; patch replay/parity PASS
snapshot: closed file set 30/30; manifest payload checksum 29/29 PASS
snapshot outside repository: ruff/mypy/pytest/CMake/CTest/sanitizers PASS
fresh empty dependency cache: one files.pythonhosted timeout after 3 retries
shared cache retry: PASS; cache is acceleration only and no root path was read
```

## 7. 故障排查、自测题、局限和下一日接口

常见故障：

- `uv` 拒绝运行：确认版本精确为 0.12.6。
- Python 3.14 被选中：运行 `uv python pin 3.12`，不要放宽项目到 3.14。
- CMake 找不到 Ninja：先 `uv sync --frozen`，再通过 `uv run cmake ...` 或 Makefile。
- macOS doctor 报 CUDA skip：这是预期；若选择 `ubuntu-cuda` profile 才必须失败。
- 快照只在根目录能构建：搜索绝对路径、`../` 回读和 symlink。

自测题：

1. 为什么 static library 成功编译仍不能证明 executable 能链接？
2. 为什么 `sm_120` 不应写入 Python dependency？
3. 为什么 macOS 缺 CUDA 是 skip，而 Ubuntu CUDA profile 缺 CUDA 是 fail？
4. 为什么 MANIFEST 不能包含自身的 SHA-256？
5. `--force-with-lease=<old-sha>` 比裸 `--force` 多保护了什么？

局限：day001 的 doctor 只建立并单测能力契约，不运行 GPU workload；正式 Ubuntu/5090
结果仍是 `not-run`。day002 只扩展 snapshot seal/verify，不得提前引入 ML 代码。
