# redis-uya Command Scope

> 版本: v0.9.0-planning
> 日期: 2026-04-30
> 基线: Redis 8.6 Commands Reference

## 1. 目标

`redis-uya` 单机版 `v1.0.0` 的命令目标是覆盖 Redis Open Source 官方命令参考中的全部命令名。

实现要求分两层：

- 单机可执行命令必须实现完整 standalone 语义，并覆盖协议、错误、过期、持久化、复制、事务和内存限制边界。
- Cluster/Sentinel 等模式相关命令必须进入同一兼容矩阵；`v1.0.0` 前实现 standalone 兼容行为或明确错误，完整分布式语义在 `v1.0.0` 之后的集群版重新规划。

## 2. 命令全集基线

命令全集以 Redis 官方当前命令参考为准，并在每个 redis-uya 规划版本开始时重新核对。

当前基线功能组：

- ACL / Security
- Bloom filter
- Bitmap
- Cuckoo filter
- Cluster management
- Count-min sketch
- Connection management
- Generic
- Geospatial indices
- Hash
- HyperLogLog
- JSON
- List
- Pub/Sub
- Redis Search
- Scripting and functions
- Server management
- Set
- Sorted set
- Stream
- String
- Auto-suggest
- T-digest
- Time series
- Top-k
- Transactions
- Vector set

## 3. 兼容矩阵状态

每个官方命令名必须在兼容矩阵中有且只有一个状态：

- `full`: 单机语义完整实现。
- `partial`: 可用但存在明确差异，必须列出差异和补齐版本。
- `standalone-error`: 命令名已识别，但在单机模式下按 Redis 兼容方式拒绝，例如完整集群状态机相关命令。
- `alias`: deprecated 或别名命令映射到 canonical 命令。
- `deferred`: 已进入计划但尚未实现，不能作为 `v1.0.0` 封版状态。

`v1.0.0` 封版时，除模式相关命令可保持 `standalone-error` 外，不允许存在 `deferred`。

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

## 5. 非命令范围

以下不计入“Redis 命令全集”：

- `redis-cli`、`redis-benchmark` 等客户端/工具命令。
- Redis Cloud / Redis Software 企业平台管理 API。
- 非 Redis Open Source 官方命令参考中的第三方模块命令。

## 6. 来源

- Redis Commands Reference: https://redis.io/docs/latest/commands/
