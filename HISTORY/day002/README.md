# Airi-DL

> 可逐日手写复现的 ML Systems 教学实验室。当前稳定快照：`day002`。

Airi-DL 用同一个 Llama-like TinyStories Decoder 串起单卡训练、多 GPU 并行、S3
checkpoint 与容错、C++/CUDA 推理、在线服务和调度实验。项目从 2026-08-27 起重启；
旧 OriginDL/PNNX 实现不属于新主线。

## 当前进度

- 建立 Python 3.12 `src` layout、C++20 静态库和无第三方依赖的 CTest。
- 锁定 bootstrap 工具与正式 Ubuntu/RTX 5090 目标环境。
- 提供只读的 `airidl doctor`，明确区分 CPU 开发宿主和正式 CUDA 环境。
- 首个 `HISTORY/day001` 是可复制到仓库外独立构建的完整快照。
- day002 提供暂存区封存、闭集 manifest、增量 patch 回放、root/latest 校验与可选共享缓存。

本日没有实现 Tensor、PyTorch、CUDA kernel、分布式训练或推理服务；缺少这些功能
不是测试跳过，而是 day001–day002 的明确非目标。包版本仍为 `0.1.0.dev1`；学习快照
编号独立推进，不把文档与封存工具的变化当成 runtime API 升级。

## 快速开始

需要 Python 3.12、CMake 3.28+ 和 C++20 编译器。Ninja 由开发依赖提供。

```bash
python3.12 -m pip install --user uv==0.12.6
make sync
uv run airidl doctor --json
make check
```

当前 macOS arm64 只承担 CPU bootstrap；正式目标是 Ubuntu 24.04 x86_64、GCC 13、
CUDA Toolkit 13.0.3、PyTorch 2.13.0/cu130 和 `sm_120`。在非正式宿主上通过测试不等于
RTX 5090/CUDA 已验证。

从仓库根复制快照：

```bash
python3.12 tools/history.py verify-root
snapshot_dir="$(mktemp -d)/airidl-day002"
cp -R HISTORY/day002 "$snapshot_dir"
cd "$snapshot_dir"
```

若你正在阅读已经复制出的 `day002`，跳过上面的复制操作。先验原始文件，再构建；
构建生成的 `.venv`、缓存和 `build` 不属于冻结快照，不能在 `HISTORY` 内直接构建：

```bash
python3.12 tools/history.py verify . --integrity-only
make sync
make check
```

`--integrity-only` 明确不验证增量回放。完整验证需要额外提供前一天目录：
`python3.12 tools/history.py verify /path/day002 --parent /path/day001`。
day001 没有该工具，使用根目录 day002 工具验证它，不修改旧快照。

可选地设置 `AIRIDL_CACHE_DIR=/absolute/cache/path` 后执行 `make sync/check`；Makefile
将 uv 缓存放在其 `uv/` 子目录。不设置也能构建，空缓存仅需要联网下载锁定依赖。
当前 C++ 无第三方依赖，所以没有伪造 FetchContent 缓存或离线成功结果。

封存操作、全部手写代码和失败排查见 [day002 开发日志](docs/devlogs/day002.md)。
学习时从 day001 **仓库 checkout** 开始，逐步写完 day002 后再 seal；不要在已经冻结的
day002 上重复 seal。`verify-root` 用于 Git 仓库；独立快照使用 `verify`。

## 目录

```text
src/airidl/             Python CLI 与未来训练控制面
cpp/include/airidl/     C++ 公共头文件
cpp/runtime/            Torch-free runtime（day001 仅版本契约）
cpp/tests/              CTest
tools/history.py       seal / verify / verify-root（标准库与 Git，无三方 Python 依赖）
env/versions.toml       正式目标与 bootstrap 版本
docs/                   审计、ADR、路线和开发日志
HISTORY/dayNNN/         冻结的完整学习快照
```

参阅 [day001 开发日志](docs/devlogs/day001.md)、
[80+12 天路线](docs/roadmap/80-plus-12-days.md) 和
[重启前审计](docs/audit/pre-reboot-2026-08-27.md)。

## English

Airi-DL is a day-by-day, hand-reproducible ML systems laboratory. Day 001 establishes
a Python 3.12/C++20 build, a read-only environment doctor, locked bootstrap tools, and
the first standalone history snapshot. Day 002 adds immutable snapshot sealing,
closed-set SHA-256 verification, patch replay, and optional dependency caching.
CUDA, PyTorch, training, distributed execution,
and serving deliberately begin on later days. The production target is Ubuntu 24.04
x86_64 with an RTX 5090; macOS is a CPU-only bootstrap host.

Licensed under Apache-2.0.
