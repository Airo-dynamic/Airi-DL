# Airi-DL 永久重启前审计

## 可复核事实

- 审计时间：2026-08-27（Asia/Shanghai）。
- 旧本地 `main` 与远端 `origin/main`：
  `298ea9a3dcf2f28af9235366664d8784a8fa92f2`。
- 旧历史只有 2 个 commit；无 day tag、无 CI。
- 旧历史跟踪 3,974 个文件，其中 `GUIDE/` 3,339 个。
- 根 OriginDL 与 `GUIDE/day1-day28` 是两套分叉实现，根目录不是 day28。
- 根工程 CPU-only 配置后仍调用 CUDA 符号，约 25% 编译进度处失败。
- `GUIDE/day28` 在 macOS CPU-only 干净构建中 CTest 37/37；GPU 用例关闭 CUDA 后
  skip/stub，不能作为 RTX 5090 证据。
- 约 22 个 GUIDE 快照因缺失依赖、普通文本伪软链接或不完整 vendor 无法独立配置。
- 所有旧 `build.sh` 均无可执行位；每日增量常达 800-2,700 行，day24 约引入
  54,565 行第三方源码。
- 旧 `MEMORY/session/plan.md` 同时出现 40、45、46 天版本，并排除了当前要求的
  TP/PP/ZeRO。

## 删除决定

用户明确选择永久重写历史，不保留 legacy 目录、归档 tag 或旧源码副本。新历史只保留
本审计结论和删除理由。远端不可达对象可能被托管平台暂存；这不等价于公开可达的归档。

## 敏感资料边界

重启前唯一未跟踪顶层目录是 `BACKGROUND/`，约 219 MB、4,929 个文件，并包含三个
独立嵌套 Git 仓库。其中 `BACKGROUND/boss` 指向企业内部远端，可能包含实习单位代码。
新 `.gitignore` 使用根路径规则 `/BACKGROUND/`；禁止 `git clean -ffd`、
`git clean -ffdx`、`git push --all` 和 `git push --mirror`。任何背景代码均不得复制
到公开项目。

## 新边界

- 品牌/API：`Airi-DL`、Python 包 `airidl`、C++ namespace `airidl`。
- 许可证：Apache-2.0。
- 正式平台：Ubuntu 24.04 x86_64；macOS 只作 CPU bootstrap。
- 旧源码未迁移；若未来借鉴某个思路，必须作为新代码重新实现、测试并在 DEVLOG 解释。
