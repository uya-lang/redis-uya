# redis-uya 方案评审

> 版本: v0.8.0-planning
> 日期: 2026-04-29
> 状态: 第三轮评审：`v0.7.0` 基线后的阶段性重评审
> 评审范围: `v0.8.0` 到 `v0.12.0`

## 1. 评审结论

`redis-uya` 不需要推翻重做设计，但必须重新建立阶段性设计基线。

`v0.1.0` 到 `v0.7.0` 已经完成了单节点内核、持久化、复制、协议控制面、内存治理和集群基础。当前主要问题不是能力不足，而是后续 TODO 已经进入两个会影响核心架构的方向：

1. `v0.8.0` 的核心路径性能优化，会改动 RESP 解析、响应编码、对象布局、分配策略和 benchmark 护栏。
2. `v0.9.0+` 的集群语义、gossip、failover、resharding，会改动命令 key 提取、连接状态、拓扑状态机、复制关系和写入副作用边界。

因此后续执行原则是：

- `v0.7.0` 作为稳定功能基线，不重开已经完成的存储、持久化、复制和基础集群实现。
- `v0.8.0` 只做性能基线与可回滚优化，不改变协议、持久化、复制和集群语义。
- `v0.9.0` 之前必须补齐集群命令 key 元数据、连接级 `ASKING` 状态和写入副作用守卫设计。
- `v0.10.0+` 不能直接堆功能，必须先明确 cluster bus、拓扑传播、epoch、failover 和迁移状态机。
- TODO 需要拆成“当前执行清单”和“长期路线图”，避免历史完成项、近期任务和远期构想混在同一层级。

## 2. 当前基线判断

### 2.1 已可作为基线的能力

当前源码模块已经形成可继续演进的边界：

- `src/storage/*`: SDS、Dict、Object、Engine 与 TTL、淘汰策略基础。
- `src/network/*`: listener、connection、RESP2/RESP3 协议编解码。
- `src/command/*`: 命令路由与执行器。
- `src/persistence/*`: AOF、RDB、rewrite。
- `src/replication/*`: 复制状态与 backlog。
- `src/cluster/*`: 槽位、节点元数据、最小拓扑。
- `src/memory/*`: allocator 与 Slab 基础。

这些模块已经有单元测试和进程级 smoke 覆盖，可以作为 `v0.8.0` 的功能回归基线。

### 2.2 文档状态问题

当前文档存在版本错位：

- `redis-uya-todo.md` 和 `redis-uya-definition-of-done.md` 已推进到 `v0.7.0`，并规划到 `v0.12.0`。
- `redis-uya-design.md` 仍以 `v0.1.0-dev` 首版设计为主。
- 旧版 `redis-uya-review.md` 仍是 `v0.1.0` 首版收敛评审。

结论：评审文档必须更新为 `v0.8.0+` 阶段基线；详细设计文档也应在后续补一版“当前实现架构 + 后续演进边界”，否则 TODO 会超过设计约束。

## 3. 范围风险

### 3.1 TODO 已经不是单纯开发清单

当前 TODO 同时承载了：

- 历史完成项。
- 当前执行项。
- 全版本路线图。
- 风险登记。
- 未来测试证据占位。

这在早期有利于保留上下文，但进入 `v0.8.0+` 后会削弱执行收敛。后续应拆成：

- 当前版本执行清单：只保留 `v0.8.0` 可直接开发和验收的任务。
- 路线图：保留 `v0.9.0-v0.12.0` 的目标、非目标、验收关键词。
- 风险登记：独立维护跨版本风险。

### 3.2 性能优化可能破坏语义稳定性

`v0.8.0` 中的零拷贝响应、批量 RESP 解析、对象池、对象布局优化都可能引入隐性行为变化：

- 半包、粘包、不完整 RESP 输入的错误边界变化。
- RESP2/RESP3 连接级协议切换下的响应编码变化。
- AOF 与复制 backlog 追加时机变化。
- 对象释放、TTL、淘汰和 WATCH key version 的生命周期变化。
- benchmark 只变快但兼容性倒退。

结论：`v0.8.0` 必须 measurement-first。任何优化必须先有基线、再有目标、再有回归护栏。

### 3.3 集群状态机风险高于普通功能扩展

`v0.9.0-v0.12.0` 涉及的不是普通命令补齐，而是跨模块状态机：

- 命令是否能执行，取决于 key 所属 slot、slot owner、迁移状态、连接是否刚发送 `ASKING`。
- 写命令失败路径必须保证不落本地库、不写 AOF、不进入复制 backlog。
- gossip 和 failover 会修改拓扑，必须维护 config epoch 单调性。
- resharding 会同时影响源节点、目标节点、客户端重定向和数据迁移完整性。

结论：集群演进必须按语义正确性、成员传播、failover、resharding 四段推进，不能把 gossip、failover 和迁移提前塞进同一版。

## 4. 关键设计决策

### D1. `v0.7.0` 固定为功能基线

后续不重新设计存储、持久化、复制和基础集群。除非测试证明当前实现阻塞后续演进，否则只做局部重构。

### D2. `v0.8.0` 不允许改变功能语义

`v0.8.0` 的优化必须满足：

- Redis 协议响应不变。
- AOF/RDB 恢复语义不变。
- 复制 backlog 追加语义不变。
- `MOVED/ASK` 基础重定向语义不变。
- `make test-all`、`test-redis-cli` 和长时 smoke 仍可通过。

### D3. 先建立性能基线，再允许优化

任何热路径优化前必须记录：

- 硬件、系统、编译参数。
- 持久化配置。
- 数据规模和 value 大小。
- client 并发、pipeline 深度、请求总量。
- 吞吐、p50、p95、p99、RSS。
- 同机 Redis 对照。

没有 benchmark 基线的优化不能进入主线。

### D4. 高风险性能项先 spike

以下能力必须先做独立 spike 或可回滚实现：

- `io_uring`。
- SIMD RESP 扫描。
- SIMD CRC64。
- 对象池替代通用 allocator。
- 响应缓冲零拷贝。

这些能力进入主路径前，必须证明收益大于复杂度和兼容性风险。

### D5. `v0.9.0` 先抽象命令 key 元数据

集群多 key 语义的前置设计是命令级 key 提取。首批只覆盖：

- `DEL`
- `EXISTS`
- `MGET`
- `MSET`

命令路由层需要能表达：

- 命令是否有 key。
- key 的位置规则。
- 是否允许多 key。
- 多 key 是否要求同 slot。
- 写命令是否存在 AOF/复制副作用。

### D6. `ASKING` 是连接级一次性状态

`ASKING` 必须放在连接状态机，而不是全局拓扑或执行器临时变量。语义要求：

- 收到 `ASKING` 后只放行下一条命令。
- 放行后立即清除状态。
- 事务、WATCH、Pub/Sub 模式下的边界必须有测试。
- 未通过集群校验的写命令不得进入 AOF 和复制追加路径。

### D7. cluster bus 与客户端 TCP 通道分离

`v0.10.0` 的 gossip 不应复用普通客户端命令通道语义。需要单独定义：

- cluster bus 消息编码/解码模块。
- 节点连接状态。
- ping/pong 消息。
- gossip 携带的节点摘要。
- PFAIL/FAIL 状态机。

### D8. failover 必须以 epoch 单调性为核心不变量

`v0.11.0` 的 failover 不能只做“把 slot owner 改成 replica”。必须先明确：

- config epoch 分配和比较规则。
- replica 归属。
- 复制偏移参与候选选择的规则。
- 旧 master 恢复后的处理。
- AOF/RDB 恢复后拓扑状态如何重建。

### D9. resharding 不能只做重定向

`v0.12.0` 的 resharding 验收必须包含数据迁移闭环：

- 源节点迁出。
- 目标节点导入。
- 迁移期间 `ASK/ASKING` 可用。
- 完成后旧 owner 返回 `MOVED`。
- 数据不会在源/目标之间丢失或重复失真。

## 5. `v0.8.0` 执行建议

### 5.1 必做

- 新增 `benchmarks/v0.8.0-performance.md`。
- 扩展 benchmark 脚本，至少覆盖 `PING/SET/GET` 的吞吐、p95/p99、RSS。
- 给当前 `v0.7.0` 产出性能基线，作为 `v0.8.0` 变化前对照。
- 建立性能回归阈值：默认不允许吞吐和 p99 较基线显著退化。
- 优先优化可局部替换的路径：响应编码、批量解析、减少分配次数。

### 5.2 可做但必须受控

- 响应缓冲复用。
- RESP parser 批量扫描。
- SDS 或对象布局的小范围优化。
- CRC64/SIMD 优化 spike。
- 对象池 spike。

### 5.3 暂不做

- 把 `io_uring` 绑定到生产路径。
- 大规模 async runtime 重写。
- 为性能重写命令执行器。
- 为 benchmark 改协议语义。
- 追求单版“全面超过 Redis”。

## 6. `v0.9.0-v0.12.0` 执行建议

### 6.1 `v0.9.0`: 集群语义正确性

优先完成命令 key 提取、同槽校验、`CROSSSLOT`、`ASKING`，并补齐写入副作用守卫。

最低验收：

- 跨 slot 多 key 写命令不落库、不写 AOF、不进入复制 backlog。
- 远端稳定 owner 返回 `MOVED`。
- 迁移态未 `ASKING` 返回 `ASK`。
- `ASKING` 后下一条同 slot 命令只放行一次。

### 6.2 `v0.10.0`: gossip 与成员传播

先做三节点拓扑传播 smoke，再做失败探测。

最低验收：

- 任意节点 `MEET` 后，拓扑最终传播到其他节点。
- 节点下线后可观测 `PFAIL/FAIL`。
- gossip 不破坏本地 slot owner 和 config epoch。

### 6.3 `v0.11.0`: failover

只做最小可验证 failover，不追求完整 Redis Cluster 选举。

最低验收：

- replica 可归属 master。
- master 下线后 replica 可接管 slots。
- 新 owner 写入成功。
- 旧 master 恢复后不会覆盖更高 epoch 拓扑。

### 6.4 `v0.12.0`: resharding 与正式集群 benchmark

迁移必须包含数据路径，不能只返回重定向。

最低验收：

- slot 从节点 A 迁移到节点 B。
- 迁移期间 `ASK/ASKING` 可完成读写。
- 迁移完成后源节点不保留已迁移 key。
- benchmark 覆盖单节点、2 master、3 master，并给 Redis Cluster 对照。

## 7. 测试与发布门槛

### 7.1 默认回归

每个版本收口前至少执行：

```bash
make test-all
make test-redis-cli
```

### 7.2 长时验证

`tests/integration/long_run_smoke.py` 默认 30 分钟，不纳入默认快速回归，但作为版本发布门槛保留。

发布前应执行：

```bash
make test-long-run
```

开发中可使用显式缩短版本做快速信号：

```bash
REDIS_UYA_LONG_RUN_SECONDS=60 make test-long-run
```

### 7.3 benchmark 门槛

`v0.8.0` 起，性能相关改动必须附带 benchmark 结果。没有基线报告的性能优化不能标记完成。

### 7.4 集群门槛

`v0.9.0+` 每个集群版本必须同时具备：

- 单元测试覆盖状态机边界。
- 进程级集成 smoke 覆盖真实 TCP 行为。
- 错误路径验证不产生持久化和复制副作用。
- 对 `CLUSTER NODES/SLOTS/INFO` 的观测结果校验。

## 8. 立即行动项

1. 更新 `redis-uya-design.md`，新增 `v0.8.0+` 当前实现架构和后续演进边界。
2. 拆分 `redis-uya-todo.md`：当前执行项、路线图、风险登记分层展示。
3. 为 `v0.8.0` 新增性能基线报告模板和 benchmark 脚本改造计划。
4. 在命令路由设计中加入 key metadata 方案，为 `v0.9.0` 铺路。
5. 在连接状态机设计中预留 `ASKING` 一次性状态。
6. 在集群设计中补充 cluster bus、gossip、epoch、failover、migration 的模块边界。

## 9. 最终判断

项目已经越过“能不能做出来”的早期阶段，进入“如何避免后续状态机失控”的阶段。

当前正确策略不是继续横向扩大 TODO，而是先固定 `v0.7.0` 基线，再按 `v0.8.0` 性能护栏和 `v0.9.0+` 集群语义边界推进。只要坚持每版有明确非目标、测试证据和 benchmark 口径，现有架构可以继续演进，不需要推翻重写。
