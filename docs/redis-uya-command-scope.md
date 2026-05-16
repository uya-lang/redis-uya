# redis-uya Command Scope

> 版本: v0.9.1-dev
> 日期: 2026-05-16
> 基线: Redis 8.6 Commands Reference

## 1. 目标

`redis-uya` 单机版 `v1.0.0` 的命令目标是覆盖 Redis Open Source 单机部署下的核心命令面，并对模式相关命令给出兼容的 standalone 行为。

实现要求分两层：

- 单机可执行命令必须实现完整 standalone 语义，并覆盖协议、错误、过期、持久化、复制、事务和内存限制边界。
- Cluster/Sentinel 等模式相关命令必须进入同一兼容矩阵；`v1.0.0` 前实现 standalone 兼容行为或明确错误，完整分布式语义在 `v1.0.0` 之后的集群版重新规划。

## 2. 命令全集基线

命令全集仍以 Redis 官方当前命令参考为总目录来源，但 `v1.0.0` 的封版门槛必须区分三个层次，避免把模块命令数量当作单机完成度。

### 2.1 Tier A: `v1.0.0` 必须完成的 Redis Open Source 单机核心

- ACL / Security
- Bitmap / Bitfield
- Connection management
- Generic
- Geospatial indices
- Hash
- HyperLogLog
- List
- Pub/Sub
- Scripting and functions
- Server management
- Set
- Sorted set
- Stream
- String
- Transactions

### 2.2 Tier B: `v1.0.0` 前可保持 standalone-error 的模式命令

- Cluster management
- Sentinel

### 2.3 Tier C: 当前继续追踪，但不作为 `v1.0.0` 单机封版门槛的模块命令

- Bloom filter
- Cuckoo filter
- Count-min sketch
- JSON
- Redis Search
- Auto-suggest
- T-digest
- Time series
- Top-k
- Vector set

### 2.4 当前主线实现说明

- 运行时目录当前由 `src/command/catalog_generated*` 提供，并通过 `docs/redis-uya-command-matrix.md` 暴露人类可读矩阵。
- 该矩阵当前跟踪的是“总目录”，不是“当前 `HEAD` 已可执行命令面”。
- `v1.0.0` 的完成度评估必须以 Tier A + Tier B 为主，不能拿 Tier C 的条目总数包装当前单机进度。

## 3. 兼容矩阵状态

每个官方命令名必须在兼容矩阵中有且只有一个状态：

- `full`: 单机语义完整实现。
- `partial`: 可用但存在明确差异，必须列出差异和补齐版本。
- `standalone-error`: 命令名已识别，但在单机模式下按 Redis 兼容方式拒绝，例如完整集群状态机相关命令。
- `alias`: deprecated 或别名命令映射到 canonical 命令。
- `deferred`: 已进入计划但尚未实现，不能作为 `v1.0.0` 封版状态。

`v1.0.0` 封版时：

- Tier A 中不允许存在 `deferred`。
- Tier B 可保持 `standalone-error`，但必须有稳定、兼容、可测试的错误语义。
- Tier C 可以继续保留 `deferred`，但必须与 Tier A/B 的完成度分开统计。

## 4. 单机命令验收

每个 `full` 命令至少需要覆盖：

- 正常路径和边界参数。
- 参数错误、语法错误、整数/浮点解析错误。
- 错类型。
- key 不存在、空集合、空结果。
- TTL 和惰性/主动过期。
- AOF 追加、AOF replay、RDB save/load。
- 主从复制和 backlog。
- 事务、WATCH、脚本原子边界。
- `maxmemory`、淘汰策略和 OOM 边界。
- RESP2 / RESP3 响应形态。
- redis-cli 或 redis-py 兼容 smoke。
- `COMMAND*`、README、DoD 与测试报告不得夸大该命令的当前支持状态。

## 5. 非命令范围

以下不计入 `v1.0.0` 单机封版的必需命令范围：

- `redis-cli`、`redis-benchmark` 等客户端/工具命令。
- Redis Cloud / Redis Software 企业平台管理 API。
- 仅属于 Redis Stack / 模块分发的命令家族，即使它们被总目录继续追踪。

## 6. 来源

- Redis Commands Reference: https://redis.io/docs/latest/commands/
