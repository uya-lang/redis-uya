# redis-uya 方案评审

> 版本: v0.9.0-planning
> 日期: 2026-04-30
> 状态: 第四轮评审：单机版封版路线重评审
> 评审范围: `v0.8.1` 之后到 `v1.0.0` 单机版封版，以及 `v1.0.0` 之后的集群版边界

## 1. 评审结论

`redis-uya` 不需要推翻已有实现，但后续路线必须从“继续扩展集群”调整为“先把单机版做完整、做稳、做快”。

新的执行原则：

- `v0.9.0` 起后续主线只迭代单机版，覆盖 Redis Open Source 官方命令参考中的全部命令名，以及单机部署下可用的主要功能。
- `v0.9.4` 是首个单机封版候选；如未达到 `v1.0.0` 封版条件，继续使用 `v0.9.5`、`v0.9.6` 等 patch 版本顺序迭代。
- `v1.0.0` 是单机版封版发布点，必须满足功能完整、性能达标、文档和测试证据齐全。
- `v1.0.0` 之后才重新规划集群版开发。
- `v0.7.0` 已有 Cluster 槽位、节点元数据、最小拓扑和 `MOVED/ASK` 基础重定向，作为历史实验能力保留；在 `v1.0.0` 前只做必要维护，不继续扩展集群状态机。

这个调整的核心原因是：当前最大风险不是“能不能继续堆集群能力”，而是单机命令面、高级数据能力、安全运维面和写路径性能仍未达到封版要求。过早扩大集群状态机会放大测试和性能债务。

## 2. 当前基线判断

### 2.1 已可作为基线的能力

当前源码模块已经形成可继续演进的边界：

- `src/storage/*`: SDS、Dict、Object、Engine、TTL、淘汰策略基础。
- `src/network/*`: listener、connection、RESP2/RESP3 协议编解码。
- `src/command/*`: 命令路由与执行器。
- `src/persistence/*`: AOF、RDB、rewrite。
- `src/replication/*`: 复制状态与 backlog。
- `src/cluster/*`: 槽位、节点元数据、最小拓扑，后续冻结到 `v1.0.0` 之后。
- `src/memory/*`: allocator 与 Slab 基础。

这些模块已经有单元测试和进程级 smoke 覆盖，可以作为单机版后续补功能和做性能优化的回归基线。

### 2.2 当前主要缺口

当前主线还不能宣称单机完整：

- 基础命令族仍缺大量 Redis 常用命令。
- 还没有以官方命令全集驱动的兼容矩阵，无法证明所有 Redis 命令名都已被跟踪。
- Streams、Lua、Functions、ACL、TLS、CLIENT/CONFIG 管理面仍需补齐。
- Bitmap、Bitfield、HyperLogLog、Geo、JSON、Search、Time Series、概率结构和 Vector 等数据能力尚未形成完整实现。
- RDB 二进制兼容、AOF rewrite 压测、复制断线恢复、`WAIT` 语义和只读副本限制仍需收敛。
- `SET` 写路径和大 value 写入仍明显落后 Redis 对照，不能作为生产性能封版依据。

## 3. 范围边界

### 3.1 `v0.9.0` 起单机范围

单机版目标不是只实现五大基础类型，而是覆盖 Redis 官方命令全集和以下能力面：

- 核心命令：String、Hash、List、Set、ZSet、Key、Server、Connection、Database、Transaction、Pub/Sub、Stream、Scripting、Function。
- 核心数据结构：String、Hash、List、Set、Sorted Set、Bitmap、Bitfield、HyperLogLog、Geo、Stream。
- 高级数据能力：JSON、Search、Time Series、Bloom、Cuckoo、Count-Min Sketch、Top-K、t-digest、Vector。
- 可靠性：RDB、AOF、rewrite、混合持久化、崩溃恢复、复制一致性。
- 安全和运维：AUTH、ACL、TLS、CONFIG、CLIENT、INFO、MEMORY、SLOWLOG、LATENCY、MONITOR、COMMAND。
- 性能工程：解析、路由、字典、对象编码、内存分配、网络写回、持久化写路径、长时运行。

每个官方命令名都必须进入 `redis-uya-command-scope.md` 定义的兼容矩阵。非模式相关命令在 `v1.0.0` 前必须达到完整 standalone 语义；Cluster/Sentinel 等模式相关命令在 `v1.0.0` 前至少达到 standalone 兼容错误或明确行为。

### 3.2 `v1.0.0` 前非目标

以下能力不进入 `v1.0.0` 前主线：

- Cluster gossip。
- Cluster failover。
- Cluster resharding。
- 正式 Redis Cluster benchmark。
- 为集群语义重写命令执行器、复制或持久化路径。

已有 `src/cluster/*` 只能做兼容维护和测试保绿；如果某个单机功能与现有集群基础冲突，优先保证单机功能和已有测试不退化，不新增集群语义。

## 4. 关键设计决策

### D1. `v0.8.1` 固定为当前功能和性能回归基线

后续新增功能必须继续通过 `make test`、`make test-integration` 和当前 benchmark guard。性能优化不能改变协议、持久化、复制、事务、Pub/Sub 或历史集群基础的已有语义。

### D2. 命令补齐必须以官方命令全集兼容矩阵驱动

每个 Redis 官方命令名都要维护明确状态：

- 已实现且语义对齐。
- 部分实现，列出差异。
- 未实现，列出进入版本。
- 明确不支持，列出原因。

不能只在 TODO 里写命令名，必须把功能组、arity、flags、key spec、ACL category、错误回复、错类型、空 key、过期、事务、AOF/RDB、复制和 maxmemory 边界一起纳入验收。该矩阵还应作为 `COMMAND`、`COMMAND INFO`、`COMMAND DOCS` 等命令的运行时数据来源。

### D3. 高级数据能力先设计再实现

JSON、Search、Time Series、概率结构和 Vector 不能直接堆命令。每类能力进入实现前必须先明确：

- 内部数据结构和编码。
- 命令语义和错误兼容。
- 持久化格式。
- 复制/AOF 表达。
- 内存上界和淘汰行为。
- benchmark 和测试数据集。

### D4. Lua 与 Functions 必须守住原子边界

脚本能力不能只做 `EVAL` 字面执行。最小可接受设计必须覆盖脚本缓存、只读脚本、错误中止、写命令副作用、事务/WATCH 边界、AOF/复制传播和超时控制。

### D5. 安全和运维面是封版门槛

`v1.0.0` 不能只有数据命令。AUTH、ACL、TLS、CONFIG、CLIENT、INFO、MEMORY、SLOWLOG、LATENCY 等能力直接影响生产可用性，必须进入单机封版范围。

### D6. 性能目标以 Redis 同机对照为准

所有性能结论必须记录硬件、构建模式、持久化配置、value 大小、请求数、并发、pipeline、p50/p95/p99、吞吐、RSS 和 Redis 对照。没有 benchmark 证据的“优化”不能标记完成。

### D7. 集群版冻结到 `v1.0.0` 之后

`v1.0.0` 前不再扩展集群状态机。`v1.0.0` 后再重新评审：

- 多 key 同槽校验、`CROSSSLOT`、`ASKING`。
- cluster bus、节点握手、gossip、`PFAIL/FAIL`。
- replica 归属、config epoch、failover。
- `ADDSLOTS/DELSLOTS`、迁移状态机、key 迁移闭环。

### D8. 文档必须跟随路线调整

README、TODO、开发规范、DoD、API、ARCHITECTURE 和发布报告必须区分：

- 历史版本已经完成了什么。
- 当前主线正在做什么。
- `v1.0.0` 前不会做什么。
- `v1.0.0` 后才规划什么。

## 5. 执行建议

### 5.1 `v0.9.0`: 单机核心命令补齐

优先补齐 String、Hash、List、Set、ZSet、Key、Server 和 Security baseline。并启动官方命令全集兼容矩阵，确保所有命令名从一开始就可追踪。每批命令都要同步单元测试、redis-py/redis-cli smoke、AOF/RDB/复制边界和 benchmark guard。

### 5.2 `v0.9.1-v0.9.3`: 单机完整功能面

按风险拆分推进 Streams、Pub/Sub 完整化、Lua/Functions、RESP3 兼容矩阵、Bitmap/Bitfield/HLL/Geo、JSON/Search/Time Series/概率结构/Vector、ACL/TLS 和运维诊断命令。此阶段必须让所有官方命令名进入命令表或 standalone 兼容错误处理。

### 5.3 `v0.9.4` 起: 单机封版候选

集中处理性能、稳定性、长时运行、故障恢复、内存泄漏、慢客户端、磁盘损坏矩阵、兼容矩阵和发布文档。此阶段不再扩大功能范围，只允许修缺口和稳定性问题。`v0.9.4` 未达标时继续 `v0.9.5`、`v0.9.6` 等 patch 版本。

### 5.4 `v1.1.0+`: 集群版

`v1.0.0` 发布后重新做集群设计评审，再按语义、成员传播、故障转移、重分片和正式集群 benchmark 分阶段推进。

## 6. 测试与发布门槛

### 6.1 默认回归

每个版本收口前至少执行：

```bash
make test
make test-integration
```

如果本机工具可用，还应执行：

```bash
make test-redis-cli
```

### 6.2 长时验证

长时运行 smoke 不纳入默认快速回归，但作为版本发布门槛保留：

```bash
REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py
```

### 6.3 benchmark 门槛

性能相关改动必须附带 benchmark 结果。默认至少对照当前 `v0.8.1` guard；封版候选阶段必须给出 Redis 同机对照和多数据集报告。

### 6.4 兼容性门槛

新增命令或数据结构必须覆盖：

- 正常路径。
- 参数错误。
- 错类型。
- 空 key / 空集合。
- 过期键。
- AOF/RDB 恢复。
- 复制恢复。
- 事务/WATCH 交互。
- maxmemory 和淘汰策略边界。

## 7. 立即行动项

1. 更新 `redis-uya-todo.md`，把当前进行中从集群语义改为单机版封版路线。
2. 更新 README 和开发规范，明确 `v0.9.0` 起只做单机版，`v1.0.0` 后才规划集群版。
3. 为 `v0.9.0` 建立官方命令全集兼容矩阵。
4. 为高级数据结构建立设计模板，避免直接进入不可维护实现。
5. 为 `v1.0.0` 定义性能 target、长时运行门槛、发布文档清单和已知限制格式。

## 8. 最终判断

当前正确策略是先完成单机版，而不是继续扩大集群状态机。已有集群基础可以保留为历史能力和后续参考，但 `redis-uya` 的下一个重大目标应当是：从 `v0.9.0` 开始按 patch 位顺序迭代，经过 `v0.9.1`、`v0.9.2`、`v0.9.3`、`v0.9.4`，必要时继续 `v0.9.5`、`v0.9.6`，直到单机功能、兼容性、性能和稳定性达到 `v1.0.0` 封版标准。
