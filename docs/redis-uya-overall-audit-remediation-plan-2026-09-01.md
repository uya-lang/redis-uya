# redis-uya 项目整体审核、整改与功能完善计划

> 版本口径: `v0.9.3-dev`
> 审核日期: 2026-09-01
> 代码基线: `f411fcd638a683abacbc8f4baf664ee9ba5c0fba`
> 文档状态: 整体审核报告与后续执行计划
> 适用范围: `v0.9.3-dev` 到 `v1.0.0` 单机版封版

## 1. 文档目的

本文档合并记录：

1. `redis-uya` 当前项目管理、技术实现、测试、性能、文档与发布工程的整体审核结论。
2. 针对审核问题的整改任务、优先级、依赖、验收标准与证据要求。
3. `v0.9.3`、`v0.9.4`、封版候选和 `v1.0.0` 的功能完善路线。

本文档不将“当前尚未达到 `v1.0.0`”定义为项目缺陷。项目已明确采用“达到生产可用、功能、稳定性、性能和交付标准后才封版 `v1.0.0`”的版本策略。

## 2. 审核范围与证据

### 2.1 审核范围

- Git 分支、版本与里程碑策略
- 命令矩阵与 Redis Open Source 单机兼容进度
- 存储、网络、持久化、复制、事务、Pub/Sub、Streams、ACL 和运维能力
- 单元测试、集成测试、redis-cli smoke 和 DoD 验证链
- release benchmark、Redis 对照、p99 与 RSS
- README、TODO、DoD、API、Architecture 与命令矩阵口径
- CI、开源许可、安全响应和发布工程

### 2.2 已执行的验证

- `make test`
- `make test-integration`
- `make test-redis-cli`
- `bash scripts/verify_definition_of_done.sh`
- `python3 scripts/verify_command_scope.py`
- `python3 scripts/verify_doc_truth.py`
- `git diff --check`
- 5K release 快速回归
- 50K release 正式复测

### 2.3 当前验证结果

| 项目 | 结果 |
|------|------|
| Uya 源码契约 | `PASS` |
| 命令范围门禁 | `PASS` |
| 命令门禁负例 | 6 项全部 `PASS` |
| 完整单元测试 | `PASS` |
| Makefile 当前集成测试 | 36 项全部 `PASS` |
| redis-cli smoke | `PASS` |
| DoD 一键验证 | `PASS` |
| 文档真值门禁 | `PASS` |
| 当前 50K release 绝对吞吐/p99 guard | 5 项全部 `PASS` |
| 当前 50K Redis normalized guard | 3 项 `PASS`，2 项 `MISS` |

## 3. 整体审核结论

### 3.1 结论摘要

`redis-uya` 当前适合作为 `v0.9.3-dev` 持续开发主线。版本定位、单机先行、模块/集群后置与达标后再封版 `v1.0.0` 的策略合理。

项目已具备较广的 Redis 单机功能面、较完整的本机测试链和持续性能优化证据。当前的主要任务已从“建立基础能力”转为“补齐 partial 语义、兼容边界、稳定性和正式交付能力”。

### 3.2 分项判定

| 审核维度 | 判定 | 说明 |
|----------|------|------|
| 版本策略 | 符合 | `v0.9.x-dev` 持续收敛，达标后才封版 `v1.0.0` |
| 项目范围 | 基本符合 | 单机核心优先，模块和集群不与当前封版门槛混算 |
| 功能广度 | 较高 | Tier A 无 `deferred`，但 `partial` 仍占主体 |
| 功能完整度 | 收敛中 | Streams、Script/Functions、复制、持久化、运维仍有关键语义缺口 |
| 正确性回归 | 当前通过 | 完整单元、36 项集成和 redis-cli 当前为绿 |
| 性能回归 | 当前通过 | 绝对吞吐和 p99 guard 通过 |
| Redis 对标性能 | 未完成 | 严格全场景稳定超越目标尚未达到 |
| 文档真实性 | 已完成一轮整改 | README/TODO/DoD 已统一，并新增自动门禁 |
| 持续交付 | 待建设 | 缺少仓库 CI 配置和跨环境自动验证 |
| 正式开源交付 | 待完善 | 封版前需补 LICENSE、SECURITY、CONTRIBUTING、CHANGELOG 等 |
| 生产可用性 | 未进入封版验收 | 符合当前 `v0.9.3-dev` 定位 |

## 4. 项目进度审核

### 4.1 不使用单一总完成率

TODO 中包含 `v0.1.0` 到当前主线的历史条目，因此总勾选率不能代表 `v1.0.0` 完成度。项目进度应按里程碑和命令兼容状态分层评估。

### 4.2 当前命令矩阵

| 层级 | 官方命令名 | `full` | `partial` | `standalone-error` | `alias` | `deferred` |
|------|---------------:|-------:|----------:|-------------------:|--------:|-----------:|
| Tier A: 单机核心 | 382 | 152 | 220 | 7 | 3 | 0 |
| Tier B: 模式命令 | 34 | 1 | 7 | 26 | 0 | 0 |
| Tier C: 模块命令 | 158 | 0 | 0 | 153 | 0 | 5 |

当前 Tier A 的特征是：

- 命令名广度已覆盖。
- `deferred=0` 只表示命令已进入真实执行面或明确错误面。
- 220 个 `partial` 是当前功能收敛的主体。
- `partial` 需按业务价值、风险和持久化/复制影响分批转为 `full`。

### 4.3 `v0.9.3` 主线进度

| 主项 | 状态 | 当前边界 |
|------|------|----------|
| Streams 第一批 | 已完成 | 基础追加、范围读取、裁剪和持久化 partial |
| Streams 第二批 | 已完成 | 容器命令、错误面和基础元数据 partial |
| Functions / Script 收口 | 进行中 | 单调用 Lua 子集与固定容量 Functions partial |
| ACL 收口 | 进行中 | 核心用户、selector、方向键和审计已落地，仍需随命令补动态 key spec |
| 运维与诊断 | 进行中 | CLIENT/CONFIG/MEMORY/SLOWLOG/LATENCY/MONITOR 存在 partial 边界 |
| 复制/持久化深化 | 进行中 | ACK/WAIT、只读副本、RDB 兼容和重连仍需收口 |

## 5. 技术实现与可维护性审核

### 5.1 已具备的工程能力

- 内置 Uya 工具链和可复核的版本/哈希记录。
- 单元、集成、redis-cli、持久化损坏和复制一致性测试。
- 命令矩阵和运行时 `COMMAND*` 的共享目录。
- 源码契约、命令范围和文档真值门禁。
- AOF append/replay、RDB 子集、BGREWRITEAOF、BGSAVE 和 BACKUP partial。
- PSYNC/backlog、full/incremental sync 和复制心跳基础。
- Slab/object pool、零拷贝回复、RESP 借用解析和事件循环优化。

### 5.2 可维护性风险

| 风险 | 证据 | 影响 |
|------|------|------|
| 命令执行器过大 | `src/command/executor.uya` 约 22.9K 行 | 命令族扩展、评审和冲突成本上升 |
| 连接层过大 | `src/network/connection.uya` 约 15.4K 行 | 协议、ACL、脚本、事务和传播责任耦合 |
| 超大测试文件 | 执行器单测约 11.7K 行，redis-cli smoke 约 4.3K 行 | 用例定位和增量评审困难 |
| 单一主要贡献者 | Git 历史主要由同一开发者完成 | Bus Factor 和知识集中风险 |

### 5.3 工程门禁缺口

- 缺少仓库级 CI。
- 缺少覆盖率基线。
- 缺少 ASan/UBSan 或同类内存/未定义行为验证。
- 缺少协议解析、RDB/AOF 输入和命令参数的 fuzz 回归。
- 默认 C 构建未开启 `-Wall/-Wextra/-Werror`。
- 30 分钟长稳脚本未进入默认 DoD。

## 6. 性能审核

### 6.1 测试口径

- release 构建
- Intel Xeon E5-2698 v4
- Linux x86_64，4 个可见 CPU
- 单连接
- pipeline=1
- AOF enabled，无显式 fsync
- Redis 7.0.15 同机对照
- 50K iterations / 2000 warmup

### 6.2 当前 50K 结果

| 场景 | redis-uya req/s | Redis req/s | 吞吐比 | redis-uya p99 | Redis p99 | 结果 |
|------|----------------:|------------:|-------:|--------------:|----------:|------|
| PING | 28139 | 28335 | 0.99x | 59us | 57us | watch |
| SET 16B | 19325 | 16955 | 1.14x | 103us | 122us | target |
| GET 16B | 23440 | 22541 | 1.04x | 68us | 69us | target |
| SET 1KiB | 19453 | 14888 | 1.31x | 120us | 129us | target |
| GET 1KiB | 20338 | 20723 | 0.98x | 76us | 77us | watch |

RSS 比值为 `1.68x`。

当前报告：`benchmarks/v0.9.3-release-performance-2026-09-01-current-50k.md`。

### 6.3 性能结论

- 当前没有超出项目自身的绝对吞吐和 p99 回归容忍线。
- `SET 16B`、`GET 16B` 和 `SET 1KiB` 在本轮同机对照中达到或高于 Redis 吞吐。
- PING 和 GET 1KiB 仍低于 Redis，严格 1.10x 全场景目标尚未达到。
- RSS 仍是明确性能债务。
- 当前矩阵只覆盖单连接、pipeline=1 和五个基础场景，不能代替生产工作负载验收。

### 6.4 性能口径管理

- 5K iterations / 200 warmup：每次改动的快速 release 回归。
- 50K iterations / 2000 warmup：里程碑和封版候选正式验收。
- 自身历史回归 guard：判定性能是否发生不可接受的倒退。
- Redis target gate：判定是否达到封版对标目标。

回归 guard 通过不能等价为 Redis target 已达成。

## 7. 文档与真实性审核

### 7.1 已完成的整改

2026-09-01 已完成 README、TODO 和 DoD 口径收口：

- 官方命令名数量统一为 574。
- top-level 命令数量统一为 420。
- 当前集成测试数量统一为 36。
- Tier A 口径统一为 `full=152/partial=220/standalone-error=7/alias=3/deferred=0`。
- Sharded Pub/Sub 统一为 standalone partial。
- Hash field TTL 统一记录持久化和 replication backlog 传播能力。
- Streams 统一记录 `NOMKSTREAM`、`MAXLEN|MINID` 与 `LIMIT` 当前能力。
- benchmark 统一区分 5K 快速回归和 50K 正式验收。
- 历史 A/B 数据明确不代替当前 HEAD 证据。
- `scripts/verify_doc_truth.py` 已接入 `make test`。

### 7.2 文档管理剩余问题

- API、Architecture、Quickstart、Design 也应逐步接入真值检查。
- 超长 TODO 同时承担历史记录和当前执行计划，查阅成本较高。
- `partial` 命令的目标版本、差异索引和验收证据还需结构化。
- 正式发布前需补当前版本 release/test/benchmark 报告和 Changelog。

## 8. 发布与开源工程审核

### 8.1 当前状态

- 项目当前没有宣布 `v1.0.0` 或生产可用。
- 项目保留 `v0.1.0` 到 `v0.9.0` 的历史 release 文档。
- 当前 Git tag 数量为 0。
- 当前仓库未发现根目录 LICENSE。
- 当前未发现仓库级 CI 配置。

### 8.2 封版前需补齐

- LICENSE
- SECURITY.md
- CONTRIBUTING.md
- CHANGELOG.md
- 支持平台和工具链矩阵
- 部署、运维、备份恢复和升级指南
- 已知限制和兼容差异索引
- 发布检查清单
- 版本 tag 与可复现发布产物

## 9. 风险分级

### 9.1 P0 风险

P0 表示会阻止进入封版候选或可能造成数据错误、安全问题、持久化不可恢复的风险。

- 未说明的 Tier A 核心语义缺口。
- 持久化、复制或事务下数据效果不一致。
- 严重内存安全、越界、use-after-free 或崩溃问题。
- AUTH/ACL/TLS 或保护模式存在默认暴露风险。
- RDB/AOF 损坏时静默读取错误数据。

### 9.2 P1 风险

- Redis 核心命令重要选项仍为 partial。
- 多连接、pipeline、慢客户端或长时间运行出现稳定性问题。
- RSS 高水位和内存碎片长期增长。
- PING/GET 热路径达不到封版性能目标。
- 缺少 CI、Sanitizer 和长稳门禁。

### 9.3 P2 风险

- 内部模块过大导致维护效率下降。
- 历史文档数量大、当前状态入口分散。
- 非封版必需的模块与集群能力占用当前主线资源。

## 10. 整改执行原则

1. 当前 HEAD 证据高于历史报告。
2. 命令从 `partial` 转为 `full` 必须同时具备代码、错误语义、持久化、复制、事务、内存限制、测试和文档证据。
3. 回归性能和封版目标性能分开判定。
4. 不为追求命令数量优先扩展 Tier C 模块。
5. `v1.0.0` 前不扩展新的集群主线。
6. 每个阶段必须有可机器验证的退出条件。
7. 历史证据保留，但不再作为当前 HEAD 结论。

## 11. 整改计划

### 11.1 整改任务总表

| ID | 优先级 | 任务 | 目标阶段 | 前置依赖 | 验收标准 | 证据 |
|----|----------|------|----------|----------|----------|------|
| R-001 | P0 | README/TODO/DoD 真值收口 | 已完成 | 当前测试与 50K 报告 | 三文档数据一致，旧口径不再出现 | `scripts/verify_doc_truth.py` |
| R-002 | P0 | 文档真值门禁接入默认测试 | 已完成 | R-001 | `make test` 自动检查命令数、集成数、性能口径与当前报告 | Makefile、DoD |
| R-003 | P0 | 建立仓库 CI | `v0.9.3` | 稳定构建环境 | 每次提交执行 debug/release、unit、integration、redis-cli、doc truth | CI 配置和绿色运行记录 |
| R-004 | P0 | 增加 LICENSE | `v0.9.3` | 项目所有者确认许可证 | 根目录存在明确开源许可，README 说明 | LICENSE、README |
| R-005 | P1 | 增加 SECURITY/CONTRIBUTING/CHANGELOG | `v0.9.4` | R-004 | 安全报告、贡献、版本变更流程可执行 | 文档文件 |
| R-006 | P0 | 增加 ASan/UBSan 专项门禁 | `v0.9.4` | CI | 核心 unit/integration 无 Sanitizer 报错 | CI 任务与报告 |
| R-007 | P1 | 建立覆盖率基线 | `v0.9.4` | CI | 记录核心模块覆盖率，新增核心命令不得降低门槛 | coverage 报告 |
| R-008 | P1 | 建立 fuzz 入口 | `v0.9.4` | Sanitizer | RESP/RDB/AOF/配置解析器有可持续 fuzz 的 harness | fuzz corpus 与崩溃回归 |
| R-009 | P1 | 拆分执行器和连接层 | `v0.9.4+` | 功能语义稳定 | 按命令族/职责拆分，全部测试与 benchmark guard 不退化 | 代码结构和 A/B 报告 |
| R-010 | P1 | 建立当前版本执行看板 | `v0.9.3` | TODO 重构 | 每项有负责角色、依赖、状态、验收和目标版本 | 当前里程碑看板 |

### 11.2 R-001/R-002 已完成说明

已完成：

- 新增当前 50K release 报告。
- README/TODO/DoD 统一当前命令、测试、功能与性能口径。
- 新增 `scripts/verify_doc_truth.py`。
- `verify-doc-truth` 已接入 `make test`。
- 完整 DoD 验证通过。

## 12. 功能完善计划

### 12.1 功能优先级原则

功能优先级按以下顺序判定：

1. 数据正确性和可恢复性。
2. 安全和默认部署边界。
3. Redis Open Source 单机核心命令的完整语义。
4. 复制、事务、脚本和持久化交叉语义。
5. 运维可观测性和故障诊断。
6. 性能、内存和长时间运行稳定性。
7. 模块和完整集群能力在 `v1.0.0` 之后重新评审。

### 12.2 Functions / Script

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-SCRIPT-01 | P0 | 明确 `v1.0.0` Lua 目标：完整 Lua 引擎或明确可封版子集 | 命令矩阵、API、错误语义和封版标准一致 |
| F-SCRIPT-02 | P0 | 补脚本超时、中止和 `SCRIPT KILL` 运行态 | 有运行中脚本、可中止/不可中止边界与错误回归 |
| F-SCRIPT-03 | P0 | 补脚本原子性和错误中止 | 部分执行失败不遗留非预期状态，WATCH/AOF/backlog 语义一致 |
| F-SCRIPT-04 | P0 | Functions library 持久化 | RDB/AOF/rewrite/复制/重启后 library 元数据和函数保持一致 |
| F-SCRIPT-05 | P1 | 补 Functions flags、metadata 和容量边界 | `FUNCTION LIST/STATS/DUMP/RESTORE` 与执行真值一致 |
| F-SCRIPT-06 | P1 | 补 RESP2/RESP3、ACL、MULTI 交叉回归 | 正常、错误、权限、持久化和复制路径全部有证据 |

### 12.3 Streams

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-STREAM-01 | P0 | 实现 consumer group 真实状态 | `XGROUP CREATE/DESTROY/SETID`、group last-delivered-id 和重启一致 |
| F-STREAM-02 | P0 | 实现 PEL 与 consumer 状态 | `XREADGROUP`、`XPENDING`、`XACK`、`XCLAIM`、`XAUTOCLAIM` 语义闭环 |
| F-STREAM-03 | P0 | 补 `XREAD BLOCK` 和 `XREADGROUP BLOCK` | 立即命中、阻塞、超时、新条目唤醒、客户端关闭回归 |
| F-STREAM-04 | P0 | Stream group/PEL 持久化和复制 | RDB/AOF rewrite/full sync/incremental sync 保持组、consumer、PEL 一致 |
| F-STREAM-05 | P1 | 补 `XADD`/`XTRIM` 选项组合和返回差异 | 精确/近似裁剪、`LIMIT`、ID 边界与 Redis 对照 |
| F-STREAM-06 | P1 | 收口 `XINFO` 真值 | STREAM/GROUPS/CONSUMERS/FULL 与实际内部状态一致 |
| F-STREAM-07 | P2 | 评估 stream 内部编码 | 基于 benchmark 决定保留 list-backed 或引入更紧凑编码 |

### 12.4 复制与一致性

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-REPL-01 | P0 | 实现 `REPLCONF ACK/GETACK` | master 记录 replica ACK offset，GETACK 可触发回复 |
| F-REPL-02 | P0 | 实现真实 `WAIT` | 按副本数和 timeout 阻塞/返回，无副本、部分 ACK、超时有回归 |
| F-REPL-03 | P0 | 实现真实 `WAITAOF` | 本地 AOF 与副本 AOF ACK 按参数收敛 |
| F-REPL-04 | P0 | 副本只读限制 | replica 写命令拒绝、配置切换和内部回放语义正确 |
| F-REPL-05 | P0 | 断线重连和 partial resync 强化 | backlog 窗口内 CONTINUE，超出窗口 FULLRESYNC，数据一致 |
| F-REPL-06 | P1 | 强化 full sync 传输和损坏处理 | 快照传输、中断、校验失败和重试可观测 |
| F-REPL-07 | P1 | 复制状态可观测 | `INFO replication`、ROLE 与真实连接/offset/ACK 状态一致 |

### 12.5 持久化与恢复

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-PERSIST-01 | P0 | 建立当前数据类型持久化矩阵 | 每类型列明 RDB/AOF/rewrite/DUMP/RESTORE/复制状态 |
| F-PERSIST-02 | P0 | RDB 二进制兼容深化 | 明确支持版本、编码、checksum、未知 opcode 和拒绝边界 |
| F-PERSIST-03 | P0 | AOF rewrite 并发压测 | rewrite 期间持续写入、增量合并、失败回退和重启一致 |
| F-PERSIST-04 | P0 | 磁盘故障矩阵 | ENOSPC、部分写、rename/fsync 失败、权限失败均不静默成功 |
| F-PERSIST-05 | P1 | 明确 AOF fsync 策略 | no/always/everysec 当前支持边界和性能/持久性取舍可配置、可测试 |
| F-PERSIST-06 | P1 | BACKUP partial 收口 | 快照与增量一致、manifest 验证、清理和从备份恢复可自动测试 |

### 12.6 ACL、认证与安全

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-SEC-01 | P0 | 完成所有 Tier A 动态 key spec ACL 审计 | 每个 movablekeys/参数驱动命令有 key/channel 权限回归 |
| F-SEC-02 | P0 | 保护模式和默认绑定策略 | 未配置认证时不得默认暴露于非受信网络 |
| F-SEC-03 | P0 | TLS 路线决策与首版实现 | 明确 `v1.0.0` 是否必需；若必需，完成证书、密钥、握手、错误与性能测试 |
| F-SEC-04 | P1 | ACL LOG 和用户生命周期长稳 | 容量、聚合、重载、断开与多连接长时间运行正确 |
| F-SEC-05 | P1 | 密码、随机数与敏感信息处理复核 | 口令不明文落盘，日志不泄露敏感信息，GENPASS 只使用系统熅源 |

### 12.7 运维和可观测性

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| F-OPS-01 | P0 | `CONFIG` 可变项真值矩阵 | GET/SET/REWRITE/重启一致，未支持项不伪装成功 |
| F-OPS-02 | P0 | `CLIENT` 子命令收口 | INFO/LIST/KILL/PAUSE/TRACKING/UNBLOCK 真实状态与连接行为一致 |
| F-OPS-03 | P1 | `INFO` section 完整度 | server/memory/persistence/replication/stats/clients 关键字段有来源和回归 |
| F-OPS-04 | P1 | MEMORY/SLOWLOG/LATENCY/MONITOR 真值和精度 | 时间精度、内存口径、客户端元数据和容量边界可观测 |
| F-OPS-05 | P1 | 建立运维错误相容性矩阵 | 参数错误、权限错误、状态错误和不支持错误稳定可测 |

### 12.8 其他 Tier A `partial` 收口

| ID | 优先级 | 命令族 | 重点差异 |
|----|----------|--------|----------|
| F-CORE-01 | P0 | Generic/Key | 多 DB、COPY/MOVE/SWAPDB、WAIT、排序、过期交叉语义 |
| F-CORE-02 | P0 | Hash | field TTL 完整差异、HIMPORT 边界和复制一致性 |
| F-CORE-03 | P1 | Geo/HLL | Redis 原生编码、浮点精度、WITHHASH/STOREDIST、HLL dense/sparse |
| F-CORE-04 | P1 | Sorted Set | 浮点 score、权重、范围精度和大数据集复杂度 |
| F-CORE-05 | P1 | List/Blocking | 多客户端公平唤醒、超时、断开和 AOF/复制语义 |
| F-CORE-06 | P1 | Pub/Sub | 输出背压、慢订阅者、RESP2/RESP3 push 和 shard standalone 边界 |
| F-CORE-07 | P1 | Transactions | WATCH 版本、错误排队、EXEC 中止、脚本和 ACL 交叉 |
| F-CORE-08 | P2 | Bitmap/Bitfield | 有符号、溢出模式、负偏移和大字符串性能 |

## 13. 性能与稳定性完善计划

### 13.1 性能矩阵

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| P-001 | P0 | 固化 5K/50K 两级 benchmark | 快速和正式入口不互相覆盖报告，口径自动检查 |
| P-002 | P0 | 增加多连接并发 | 1/8/32/64 连接的吞吐、p95/p99、RSS 和错误率 |
| P-003 | P0 | 增加 pipeline 矩阵 | pipeline 1/8/16/64，覆盖 PING/GET/SET/混合读写 |
| P-004 | P0 | 增加 value size 矩阵 | 16B/64B/1KiB/4KiB/64KiB，覆盖吞吐、p99 和 RSS |
| P-005 | P0 | 增加写路径持久化矩阵 | AOF no/everysec/always 或明确当前支持边界 |
| P-006 | P1 | 增加复制 benchmark | full sync、incremental sync、重连、WAIT/WAITAOF |
| P-007 | P1 | 增加重路径 benchmark | AOF rewrite、RDB SAVE、Streams、blocking、Pub/Sub |
| P-008 | P1 | 建立 RSS/碎片趋势报告 | 冷启动、稳态、删除、重写和长时间运行 RSS 可观测 |
| P-009 | P1 | 优化 PING/GET 热路径 | 基于 profile 提交，不以单轮墙钟抖动作为结论 |

### 13.2 稳定性矩阵

| ID | 优先级 | 任务 | 验收标准 |
|----|----------|------|----------|
| S-001 | P0 | 30 分钟快速长稳 | 无崩溃、连接泄漏、明显 RSS 持续增长或数据错误 |
| S-002 | P0 | 6-24 小时混合负载 | 定期记录吞吐、p99、RSS、键数、过期和复制 offset |
| S-003 | P0 | 慢客户端和背压 | 单个慢客户端不拖垮其他客户端，输出上限和断开可预期 |
| S-004 | P0 | 半包/粘包/大响应压力 | 无越界、无死循环、无丢帧，RESP2/RESP3 一致 |
| S-005 | P0 | 崩溃恢复矩阵 | append/rewrite/save/backup 各阶段 kill -9 后结果可说明、可恢复 |
| S-006 | P0 | 损坏文件矩阵 | RDB/AOF/manifest 截断、checksum、长度和未知类型均安全失败 |
| S-007 | P1 | 资源极限 | maxclients、maxmemory、fd 耗尽、分配失败、磁盘空间不足 |
| S-008 | P1 | 主从网络抖动 | 丢包、延迟、断线、重连和 backlog 超窗口有稳定结果 |

## 14. 分阶段执行路线

### 14.1 阶段 0：真实性基线收口

**状态：已完成本轮核心整改。**

完成项：

- README/TODO/DoD 口径统一。
- 36 项当前集成数量固化。
- 574/420 命令数量固化。
- 关键能力边界统一。
- 5K/50K 性能口径分层。
- 当前 50K 证据报告。
- 文档真值自动门禁。

退出条件：

- `python3 scripts/verify_doc_truth.py` 通过。
- `bash scripts/verify_definition_of_done.sh` 通过。
- `git diff --check` 通过。

### 14.2 阶段 1：`v0.9.3` 功能收口

**目标：关闭当前主线的功能正确性和数据一致性缺口。**

建议顺序：

1. 复制 ACK/WAIT/WAITAOF 和副本只读。
2. Streams consumer group/PEL/blocking。
3. Functions library 持久化与脚本原子性。
4. RDB/AOF/rewrite 与故障恢复深化。
5. ACL 动态 key spec、保护模式和 TLS 决策。
6. CONFIG/CLIENT/INFO 真值收口。

退出条件：

- `v0.9.3` 四个进行中主项关闭或拆成有明确目标版本的后续项。
- 新增写命令全部覆盖 AOF/RDB/rewrite/backlog/WATCH/maxmemory。
- Tier A 不存在未说明的 P0 语义缺口。
- 完整 DoD 连续通过。

### 14.3 阶段 2：`v0.9.4` 性能与稳定性收敛

**目标：把“本机功能回归稳定”提升为“多负载、长时间和故障环境可复核”。**

建议顺序：

1. CI、Sanitizer、coverage、fuzz 基础设施。
2. 并发、pipeline、value size 和混合读写矩阵。
3. 30 分钟快速长稳与 6-24 小时正式长稳。
4. 持久化、复制、Streams 重路径 benchmark。
5. RSS、碎片、PING 和 GET 热路径优化。
6. 核心超大文件按证据拆分。

退出条件：

- CI 连续绿色。
- Sanitizer 无 P0/P1 问题。
- 长稳无不可解释的 RSS 持续增长。
- 故障恢复矩阵通过。
- 正式 50K 与多连接/pipeline 矩阵达到当前发布目标。

### 14.4 阶段 3：封版候选

**目标：生成首个可审核的单机版候选。**

任务：

- 锁定命令矩阵和已知差异。
- 锁定工具链、构建参数和支持平台。
- 生成 release/test/benchmark/security 报告。
- 补齐 LICENSE、SECURITY、CONTRIBUTING、CHANGELOG、部署和升级文档。
- 执行全新环境可复现构建。
- 只修复 P0/P1，冻结新功能。

退出条件：

- Tier A 无 `deferred`，且所有剩余 `partial` 都已明确是可接受发布差异或已转 `full`。
- Tier B 达到 `full` 或稳定 `standalone-error`。
- 无未关闭 P0/P1 正确性、安全和稳定性问题。
- 正式性能目标达成。
- 发布产物可复现。

### 14.5 阶段 4：`v1.0.0` 封版

`v1.0.0` 只在以下条件同时满足后发布：

- 单机计划内功能完成并具备证据。
- Redis Open Source 单机核心兼容矩阵达到封版标准。
- 所有差异均已说明，不存在“文档说有、执行没有、测试没覆盖”的裂缝。
- 生产稳定性、故障恢复和安全门禁达标。
- 性能达到项目已确定的封版 target。
- 无 P0/P1 未关闭问题。
- 开源许可、发布说明、运维、安全、迁移和已知限制文档齐全。
- DoD、正式 benchmark、长稳、Sanitizer 和全新环境构建全部通过。
- 建立版本 tag 和可复现发布产物。

## 15. 建议排期

以当前单一主要维护者的实际产能为基准，建议使用阶段退出条件，不建议为 `v1.0.0` 预先锁定不可调整的日期。

| 阶段 | 建议工作量 | 主要交付 |
|------|------------|----------|
| 阶段 0：真实性基线 | 已完成 | 文档收口、真值门禁、当前 50K 证据 |
| 阶段 1：`v0.9.3` 功能收口 | 6-10 个单人工作周 | 复制、Streams、Script/Functions、持久化、安全、运维 |
| 阶段 2：`v0.9.4` 性能/稳定性 | 4-6 个单人工作周 | CI、Sanitizer、长稳、性能矩阵、RSS 优化 |
| 阶段 3：封版候选 | 2-4 个单人工作周 | 冻结、报告、发布文档、可复现产物 |

上述工作量是项目管理建议，不是对发布日期的承诺。如果增加并行维护者，应优先按“持久化/复制”、“Streams/Script”、“性能/稳定性”和“文档/发布”四条责任线拆分。

## 16. 项目管理看板字段建议

后续每个当前里程碑任务应至少包含：

| 字段 | 说明 |
|------|------|
| ID | 稳定任务编号 |
| 优先级 | P0/P1/P2 |
| 负责角色 | core/persistence/replication/security/performance/docs |
| 目标版本 | `v0.9.3`、`v0.9.4`、RC 或 `v1.0.0+` |
| 状态 | pending/in-progress/blocked/done |
| 前置依赖 | 必须先完成的任务 |
| 兼容差异 | 当前与 Redis 的差异 |
| 验收标准 | 可机器执行的通过条件 |
| 证据 | 测试、benchmark、报告或文档路径 |
| 风险 | 数据、兼容、性能、安全或工具链风险 |

## 17. 封版检查清单

### 17.1 功能与兼容

- [ ] 单机计划内功能完成。
- [ ] Tier A 所有差异已说明并有证据。
- [ ] Tier B 达到 `full` 或稳定 `standalone-error`。
- [ ] 所有写命令覆盖 AOF/RDB/rewrite/复制/WATCH/maxmemory。
- [ ] RESP2/RESP3、redis-cli 和 redis-py 关键路径通过。

### 17.2 稳定性与安全

- [ ] CI 稳定通过。
- [ ] Sanitizer 无 P0/P1 问题。
- [ ] 长稳测试通过。
- [ ] 崩溃、损坏文件、磁盘故障和网络故障矩阵通过。
- [ ] AUTH/ACL/保护模式/TLS 达到封版安全标准。
- [ ] 无未关闭 P0/P1 问题。

### 17.3 性能

- [ ] 50K 正式核心矩阵达标。
- [ ] 多连接和 pipeline 矩阵达标。
- [ ] 持久化、复制和 Streams 重路径无 P0/P1 性能债务。
- [ ] RSS 和长时间内存趋势达标。
- [ ] 回归 guard 与 Redis target gate 分开报告。

### 17.4 文档与发布

- [ ] README/TODO/DoD/API/Architecture/Command Matrix 一致。
- [ ] LICENSE、SECURITY、CONTRIBUTING、CHANGELOG 齐全。
- [ ] 部署、运维、备份恢复、升级和已知限制文档齐全。
- [ ] release/test/benchmark/security 报告齐全。
- [ ] 全新环境可复现构建通过。
- [ ] 版本 tag 和发布产物可验证。

## 18. 最终建议

1. 保持当前 `v0.9.3-dev` 定位，不为追求版本号提前封版。
2. `v0.9.3` 先关闭数据正确性、复制、Streams、Script/Functions、持久化和安全主项。
3. `v0.9.4` 专注 CI、Sanitizer、长稳、故障恢复、性能矩阵和 RSS 收敛。
4. 封版候选期冻结新功能，只关闭 P0/P1 问题和交付缺口。
5. 仅在功能、生产稳定性、性能、安全和发布工程全部达到既定目标后封版 `v1.0.0`。
