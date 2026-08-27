# ADR 0001：以 PyTorch-first 方式重启

- 状态：Accepted
- 日期：2026-08-27

## 背景

旧工程同时维护通用 Tensor/Autograd、多个 Mat backend、PNNX 和两套分叉的每日代码。
这些工作无法形成 DDP/FSDP2、可靠 checkpoint 或 LLM serving 的连续证据链。

## 决策

1. 新历史从 day001 开始，不继承 OriginDL、PNNX 或 `.odl` API。
2. PyTorch 是模型、Autograd、训练和官方分布式实现的正确性参照。
3. 自研范围聚焦 Torch-free C++/CUDA kernel core、通信实验、checkpoint 协议、
   inference runtime、Paged KV、调度和可观测性。
4. 同一个 TinyStories Decoder 和 ModelBundle 契约贯穿训练与推理。
5. 每个 day 先通过验收再冻结；未在真实硬件运行的能力必须标为未验证。

## 后果

不再投入时间扩建通用深度学习框架；早期代码只能作为本地背景材料，不复制到新历史。
项目会更早接触 ML 理论，并能将分布式存储经验转化为 S3 checkpoint 主线。
