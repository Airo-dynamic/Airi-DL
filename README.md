# Airi-DL

> 可逐日手写复现的 ML Systems 教学实验室。当前稳定快照：`day001`。

Airi-DL 用同一个 Llama-like TinyStories Decoder 串起单卡训练、多 GPU 并行、S3
checkpoint 与容错、C++/CUDA 推理、在线服务和调度实验。项目从 2026-08-27 起重启；
旧 OriginDL/PNNX 实现不属于新主线。

## day001 做了什么

- 建立 Python 3.12 `src` layout、C++20 静态库和无第三方依赖的 CTest。
- 锁定 bootstrap 工具与正式 Ubuntu/RTX 5090 目标环境。
- 提供只读的 `airidl doctor`，明确区分 CPU 开发宿主和正式 CUDA 环境。
- 首个 `HISTORY/day001` 是可复制到仓库外独立构建的完整快照。

本日没有实现 Tensor、PyTorch、CUDA kernel、分布式训练或推理服务；缺少这些功能
不是测试跳过，而是 day001 的明确非目标。

## 快速开始

需要 Python 3.12、CMake 3.28+ 和 C++20 编译器。Ninja 由开发依赖提供。

```bash
python3.12 -m pip install --user uv==0.12.6
uv sync --frozen
uv run airidl doctor --json
make check
```

当前 macOS arm64 只承担 CPU bootstrap；正式目标是 Ubuntu 24.04 x86_64、GCC 13、
CUDA Toolkit 13.0.3、PyTorch 2.13.0/cu130 和 `sm_120`。在非正式宿主上通过测试不等于
RTX 5090/CUDA 已验证。

从仓库根复制快照：

```bash
snapshot_dir="$(mktemp -d)/airidl-day001"
cp -R HISTORY/day001 "$snapshot_dir"
cd "$snapshot_dir"
```

若你正在阅读已经复制出的 `day001`，跳过上面三行，直接在当前目录运行：

```bash
python3.12 -c 'from pathlib import Path; m={line.split(maxsplit=1)[1].removeprefix("./") for line in Path("MANIFEST.sha256").read_text().splitlines()}; a={str(p).removeprefix("./") for p in Path(".").rglob("*") if p.is_file()}; assert a == m | {"MANIFEST.sha256"}, (a-m, m-a)'
if command -v sha256sum >/dev/null; then sha256sum -c MANIFEST.sha256; else shasum -a 256 -c MANIFEST.sha256; fi
uv sync --frozen
make check
```

## 目录

```text
src/airidl/             Python CLI 与未来训练控制面
cpp/include/airidl/     C++ 公共头文件
cpp/runtime/            Torch-free runtime（day001 仅版本契约）
cpp/tests/              CTest
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
the first standalone history snapshot. CUDA, PyTorch, training, distributed execution,
and serving deliberately begin on later days. The production target is Ubuntu 24.04
x86_64 with an RTX 5090; macOS is a CPU-only bootstrap host.

Licensed under Apache-2.0.
