# Airi-DL 80+12 天路线

## 使用规则

一个 day 是 4-5 小时量级的学习单元，不强制等于自然日。目标新增 100-250 行一方代码，
硬上限 350 行和 10 个文件；超过即拆分。验收未通过不得封存或开始下一天。

day001 是从 empty tree 建立仓库的唯一 bootstrap 例外：10 个实现/测试文件仍需逐字手写；
标准 Apache LICENSE、工具生成的 `uv.lock`/snapshot metadata 和治理文档不计入代码
行数与文件数。day002 起不再允许该例外。

每个机制必须标注证据等级：

- L1：核心机制自行实现，并与参考实现对账。
- L2：调用官方实现，完成配置、观测、故障或性能实验。
- L3：确定性模拟器或缩小版教学实现。
- L4：阅读/架构映射/受硬件限制的实验设计，不宣称实现或验证。

固定模型是 8 层、hidden 512、8 attention heads/4 KV heads、FFN 1536、context 512、
vocab 8192 的约 30M Llama-like TinyStories Decoder。`airi-debug` 用于快速正确性测试；
300M/1B synthetic Decoder 只用于显存与扩展性实验。

## Phase 0：治理与可复现性

| Day | 交付与验收 |
|---|---|
| 001 | orphan 重启、双语言骨架、版本锁、`airidl doctor`、独立快照。 |
| 002 | `seal/verify`、manifest、patch、共享缓存与仓库外回放。 |
| 003 | strict config、ModelBundle/checkpoint/benchmark schema、CLI、JSON log。 |
| 004 G0 | CI、fresh clone、root/latest、patch/manifest 与手写流程门禁。 |

## Phase 1：ML 与同一 Decoder

| Day | 交付与验收 |
|---|---|
| 005 | Tensor shape/broadcast/matmul、链式法则和线性回归对账。 |
| 006 | 稳定 softmax/cross-entropy、SGD/AdamW、数值梯度。 |
| 007 | 自回归目标、teacher forcing、perplexity。 |
| 008 | 8192 byte-level BPE 与中英文/emoji round-trip fixture。 |
| 009 | TinyStories 许可/哈希、确定性 split、streaming shards。 |
| 010 | packing/next-token label、无泄漏、重复运行 hash 一致。 |
| 011 | causal self-attention 的逐步 PyTorch 实现。 |
| 012 | MHA/GQA 与 SDPA forward/backward 对账。 |
| 013 | RMSNorm、RoPE、SwiGLU 数学和梯度。 |
| 014 | Pre-Norm Decoder block、residual、dropout。 |
| 015 | 完整 debug/30M 模型与 HF Llama 权重命名。 |
| 016 | BF16 trainer、梯度累积、activation checkpoint、clip、LR schedule。 |
| 017 G1 | exact resume、固定 batch loss `<0.1`、10M-token pilot、固定 prompts。 |

## Phase 2：CUDA 性能工程

| Day | 交付与验收 |
|---|---|
| 018 | Torch-free kernel ABI、Torch adapter、custom-op 注册。 |
| 019 | HBM、coalescing、vectorized load/store、有效带宽。 |
| 020 | warp shuffle、shared-memory reduction、非 2 次幂边界。 |
| 021 | 教学 GEMM、cuBLASLt/Tensor Core 与 roofline；生产不自造 GEMM。 |
| 022 | 奇数 shape、BF16/FP32、compute-sanitizer、Nsight baseline。 |
| 023 | fused RMSNorm forward/backward。 |
| 024 | RoPE kernel 与增量 position offset。 |
| 025 | fused SwiGLU forward/backward。 |
| 026 | online softmax 与 Triton 对照实现。 |
| 027 | 固定 head dim、causal、forward-only 教学 FlashAttention。 |
| 028 | stream/event、pinned H2D、双缓冲与计算传输重叠。 |
| 029 | 固定 shape CUDA Graph capture/replay。 |
| 030 G2 | custom-op fallback 训练集成、Nsight 报告、100M-token 回归。 |

## Phase 3：通信与 DDP

| Day | 交付与验收 |
|---|---|
| 031 | rank/world/process group/rendezvous 与 2-4 rank Gloo harness。 |
| 032 | 基于 P2P 的 Broadcast 与 Reduce。 |
| 033 | Ring AllReduce = ReduceScatter + AllGather。 |
| 034 | Tree AllReduce、小消息延迟、NUMA/PCIe/topology 成本模型。 |
| 035 | AllGather、ReduceScatter、All-to-All 契约。 |
| 036 | 字节模型、超时/断连、collective 算法对比门禁。 |
| 037 | C++ NCCL backend、异步 Work、stream、abort；不重写 NCCL。 |
| 038 | 逐参数同步的教学 DDP。 |
| 039 | autograd hook、稳定 bucket 顺序、bucket 大小实验。 |
| 040 | 独立通信 stream、event 依赖、计算通信重叠。 |
| 041 | `no_sync`、梯度累积、DP 与 DDP 对照。 |
| 042 | 云 Gate A：2 GPU 必达、4 GPU 目标，nccl-tests 与 DDP scaling。 |
| 043 G3 | global batch 等价、scaling efficiency、通信占比和原始证据。 |

## Phase 4：参数分片、FSDP2 与 TP

| Day | 交付与验收 |
|---|---|
| 044 | 显存账本与 ZeRO-1 optimizer-state sharding。 |
| 045 | ZeRO-2 gradient ReduceScatter。 |
| 046 | 仅 debug block 的教学 ZeRO-3 gather/reshard。 |
| 047 | 官方 FSDP2、DTensor、DeviceMesh、sharded state dict。 |
| 048 | 300M/1B synthetic 的峰值显存、最大 batch、resume 门禁。 |
| 049 | Column Parallel Linear。 |
| 050 | Row Parallel Linear。 |
| 051 | attention-head TP 与完整 Decoder block。 |
| 052 | 真实 TP=2 云验证 logits/loss/gradient 与显存。 |
| 053 G4 | DeepSpeed ZeRO-2 vs FSDP2；Megatron/TorchTitan 源码映射。 |

## Phase 5：数据、S3 Checkpoint、容错与观测

| Day | 交付与验收 |
|---|---|
| 054 | rank/epoch 可重现的 dataset sharding 与 sampler cursor。 |
| 055 | worker prefetch、pinned staging、三磁盘 NVMe locality。 |
| 056 | MinIO/S3 dataset shards、checksum、本地 cache。 |
| 057 | checkpoint manifest 与 POSIX/S3 提交协议。 |
| 058 | DCP `async_save`、CPU/pinned staging、训练阻塞比例。 |
| 059 | 不同 world size 的 DCP reshard 恢复。 |
| 060 | heartbeat、deadline、timeout、retry、communicator abort。 |
| 061 | TorchElastic kill/restart、rank 不稳定、sampler 重建。 |
| 062 | 单个 debug step 的 straggler 注入、Prometheus/OTel trace 与 critical path。 |
| 063 G5 | 云 Gate B：多节点 kill/中断/损坏 shard/S3 恢复；RDMA 可选。 |

## Phase 6：C++ LLM Serving

| Day | 交付与验收 |
|---|---|
| 064 | ModelBundle export、SafeTensors、tokenizer golden、logits parity。 |
| 065 | `DeviceBuffer/TensorView/CudaArena` 与 mmap loader。 |
| 066 | C++ byte-level BPE 与 Python token-id 对账。 |
| 067 | C++ Llama forward、固定输入 logits 对账。 |
| 068 | greedy、temperature、top-p sampling 与确定性测试。 |
| 069 | 连续 KV cache、prefill/decode 分离。 |
| 070 | 静态/动态 batching baseline 与统一 workload generator。 |
| 071 | 请求状态机与 iteration-level continuous batching。 |
| 072 | KV block allocator/table、cancel/OOM/reclaim、Paged KV。 |
| 073 | decode-only PagedAttention 与连续 KV reference 对账。 |
| 074 G6 | 新增 chunked prefill；复用既有 fairness/Graph，执行 30 分钟压力门禁。 |

## Phase 7：API、展示与调度

| Day | 交付与验收 |
|---|---|
| 075 | `POST /v1/responses`、SSE、backpressure、cancel、metrics、SDK contract。 |
| 076 | PyTorch eager/compile、自研 runtime、vLLM 同 workload 比较。 |
| 077 | Web：故事、queue/KV map、延迟分位数、训练/故障状态。 |
| 078 | 确定性 GPU 集群模拟器：resource/topology/gang/bin packing。 |
| 079 | DRF/weighted fairness、preemption、fragmentation、checkpoint-aware victim。 |
| 080 G7 | 30M 模型累计训练 600M tokens、恢复、export、serving、压测和求职证据。 |

## day081-day092 选修扩展

| Day | 交付与验收 |
|---|---|
| 081 | Pipeline Parallel GPipe。 |
| 082 | 1F1B schedule、bubble、activation checkpoint。 |
| 083 | MoE top-k router、capacity、load-balancing loss。 |
| 084 | Expert Parallel All-to-All。 |
| 085 | Prefix Cache hash/refcount/eviction。 |
| 086 | greedy speculative decoding。 |
| 087 | 随机采样下分布正确的 speculative decoding。 |
| 088 | per-channel INT8 weight-only quantization。 |
| 089 | 单一 GPTQ W4A16 adapter；TensorRT-LLM 只作兼容测量/架构映射。 |
| 090 | Prefill/Decode disaggregation 与 KV transfer 模拟。 |
| 091 | 单个 kind 集群的 Volcano Queue/PodGroup/gang；Slurm/Ray 仅作 L4 对照。 |
| 092 | 两节点 IB/RoCE/RDMA/GPUDirect nccl-tests；无硬件则保持 L4。 |

## 阶段门禁与预算

- G0：fresh clone 和快照独立构建，root/latest/patch/manifest 一致。
- G1：debug fixed-batch loss `<0.1`，resume 后 batch/RNG/参数轨迹一致。
- G2：边界 shape、BF16/FP32、gradcheck、sanitizer、profiler 全通过。
- G3：真实 `world_size >= 2`，固定 global batch 的更新对齐并报告 scaling。
- G4：300M/1B 峰值显存、TP 对齐、sharded state 保存恢复。
- G5：覆盖 kill -9、上传中断、对象缺失/损坏、straggler，只恢复最后完整提交。
- G6：逐 token 对齐、Paged KV 随机状态机、并发 1/8/32 各压测 30 分钟。
- G7：`make demo` 从 day080 干净快照启动全闭环；简历描述逐条链接原始证据。

Gate A 上限 ¥300，Gate B 上限 ¥600，保留 ¥100 应急，总计不超过 ¥1000。
云资源只在本地脚本 dry-run 后启动，并设置预算告警和自动关机。
RDMA/IB/RoCE/GPUDirect 不是 day080 完成条件，不得伪造未运行的结果。

## 证据等级账本

等级描述的是当日主要机制；组合等级表示“自研边界 + 官方集成/对照”，不能把 L2 写成
“自行实现了框架”。Gate 日的等级指其验证对象。

| Days | 等级 | 边界 |
|---|---|---|
| 001-008 | L1 | 自研治理工具、数学练习和 tokenizer；不重造通用 Autograd。 |
| 009-017 | L1+L2 | 自研数据/模型/trainer，PyTorch 算子作为 reference。 |
| 018-020 | L1 | Torch-free ABI、访存和 reduction。 |
| 021-022 | L1+L2 | 教学 GEMM；cuBLASLt、sanitizer、Nsight 是官方工具。 |
| 023-025 | L1 | 自研融合算子与 backward。 |
| 026 | L1+L2 | 自研 online softmax，Triton 为对照。 |
| 027-029 | L1 | 缩小版 FlashAttention、overlap 和 Graph harness。 |
| 030 | L1+L2 | 自研 op 集成 PyTorch trainer 并用 Nsight 验证。 |
| 031-036 | L1+L3 | 教学 collective 自研；topology/字节成本为确定性模型。 |
| 037 | L2 | 自研 wrapper/backend，底层 collective 明确由 NCCL 实现。 |
| 038-041 | L1+L2 | 教学 DDP 与官方 DDP 对照。 |
| 042-043 | L2 | 真实 NCCL/DDP 云实验与证据。 |
| 044-046 | L1 | 缩小版 ZeRO-1/2/3 教学实现。 |
| 047-048 | L2 | 官方 FSDP2/DTensor 集成和显存实验。 |
| 049-051 | L1 | Column/Row/Attention TP。 |
| 052 | L2 | 真实 TP 云验收。 |
| 053 | L2+L4 | DeepSpeed 实验；Megatron/TorchTitan 只作源码映射。 |
| 054-057 | L1+L2 | 自研 shard/cache/提交协议，MinIO/S3 是集成对象。 |
| 058-059 | L2 | 官方 DCP async/reshard。 |
| 060 | L1+L2 | 自研 failure policy，communicator 由官方 backend 提供。 |
| 061 | L2 | TorchElastic 集成。 |
| 062 | L1+L2 | 自研注入/critical-path 汇总，Prometheus/OTel 为集成。 |
| 063 | L2+L4 | TCP 多节点必测；RDMA 只在硬件存在时升级为 L2。 |
| 064-073 | L1 | ModelBundle、C++ runtime、KV、continuous batching、PagedAttention。 |
| 074 | L1+L2 | 自研 chunking/scheduler，CUDA Graph 为官方机制集成。 |
| 075 | L1+L2 | 自研网关/取消链，官方 Responses contract 作对照。 |
| 076 | L2+L4 | vLLM 可运行基线；SGLang/TensorRT-LLM 可为架构矩阵。 |
| 077-080 | L1+L2 | 自研 Web/模拟器/闭环，依赖官方基础设施集成。 |
| 081-082 | L1+L2 | 自研 schedule，并与官方 pipeline API 对照。 |
| 083-088 | L1 | 缩小版 MoE/EP/cache/speculative/INT8。 |
| 089 | L2+L4 | 单一量化 adapter；未运行的 vendor 路径保持 L4。 |
| 090 | L3 | 单机逻辑 worker 与 KV transfer 模拟。 |
| 091 | L2+L4 | Volcano 实验；Slurm/Ray 只作对照。 |
| 092 | L2 或 L4 | 有合格硬件才是 L2，否则明确未验证。 |

额外 L4 知识账本覆盖 NVLink/NVSwitch、SM、SGLang、Slurm、Ray、Parallel File System
和 GPU failure；它们服务于 topology、生态或故障矩阵，不占用核心实现日，也不进入
“已实现”简历表述。
