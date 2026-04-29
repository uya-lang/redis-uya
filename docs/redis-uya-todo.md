程序的真正成本不在于编写，而在于维护。
# redis-uya 开发 TODO 文档

> 版本: v0.7.0
> 日期: 2026-04-29
> 配套设计文档: `redis-uya-design.md`
> 配套评审文档: `redis-uya-review.md`
> 开发规范: `redis-uya-development.md`

## 1. 规划原则

本页同时满足两个目标：

1. 给出当前正在执行的近端计划，确保开发有明确优先级。
2. 给出从 `v0.1.0` 到长期目标的全版本路线图，确保项目不会丢失最终愿景。

执行规则：

- 近端版本采用可执行粒度，任务细到可以直接开发和验收。
- 中远期版本保留完整功能范围、里程碑与验收方向，但不提前承诺每个实现细节。
- 任何阶段都必须满足技术可行性和完整性约束，不能因为规划全面而牺牲收敛。

## 2. 当前状态

当前已完成：

- [x] 工程骨架、`Makefile`、文档入口
- [x] 内置 Uya 工具链同步
- [x] 工具模块：`log/time/endian/crc64`
- [x] 最小单元测试框架与 `make test`
- [x] 内存分配器封装
- [x] 配置解析：文本 + 文件读取
- [x] SDS 基础能力：创建、追加、格式化追加、比较、扩缩容、复制、范围切片、1MB 压测
- [x] 项目内专用 `Dict`：插入、查找、覆盖、删除、扩容、渐进 rehash、10k 键回归
- [x] `RedisObject` 最小 String 包装：RAW/INT 编码、类型名、释放
- [x] `Engine` 最小实现：键读写删除、覆盖释放、TTL 字段、惰性过期
- [x] RESP2 最小子集解析：Simple String、Error、Integer、Bulk String、Array、Incomplete、非法输入
- [x] 命令路由：最小命令表、参数校验、未知命令错误
- [x] String/Key 命令执行：`PING/GET/SET/DEL/EXISTS/EXPIRE/TTL/INFO`
- [x] 服务闭环：TCP 监听、连接处理、Python socket smoke
- [x] 服务运行循环：单线程 epoll 多连接、100ms cron 主动过期扫描、空闲连接不阻塞其他客户端
- [x] AOF 最小闭环：写命令追加、启动回放、截断损坏安全失败、重启恢复 smoke
- [x] `v0.3.0`：持久化增强与可靠性矩阵
- [x] `v0.4.0`：复制与高可用基础
- [x] `v0.5.0`：协议与控制面增强
- [x] `v0.6.0`：内存与性能控制
- [x] `v0.7.0`：集群基础

当前进行中：

- [ ] `v0.8.0`：核心路径性能基线
- [ ] `v0.9.0+`：集群语义、gossip、failover、resharding 与正式集群 benchmark

## 3. 全版本路线图

| 版本 | 阶段定位 | 核心目标 | 验收关键词 |
|------|---------|---------|-----------|
| `v0.1.0-alpha` | 最小可运行内核 | 单节点、RESP2 子集、String/Key 子集 | `redis-cli` 基本交互 |
| `v0.1.0-beta` | 基础可靠性 | TCP 服务、TTL、AOF append/replay、Python 子集测试 | 重启恢复 |
| `v0.1.0` | 首版发布 | benchmark 基线、DoD、发布文档 | 可交付、可复现 |
| `v0.2.0` | 数据结构扩展 | Hash/List/Set/ZSet、SCAN、RDB 子集 | 类型面完整 |
| `v0.3.0` | 持久化增强 | RDB 完整化、AOF rewrite、BGSAVE/BGREWRITEAOF | 恢复与压缩 |
| `v0.4.0` | 复制与高可用基础 | 主从复制、PSYNC、复制积压缓冲区 | 副本同步 |
| `v0.5.0` | 协议与控制面增强 | RESP3、事务、Pub/Sub、CONFIG/CLIENT 完整化 | 协议兼容扩大 |
| `v0.6.0` | 内存与性能控制 | `maxmemory`、淘汰策略、主动过期强化、Slab | 内存可控 |
| `v0.7.0` | 集群基础 | Cluster 槽位、重定向、节点元数据 | 分布式闭环 |
| `v0.8.0` | 核心路径性能基线 | 零拷贝、批量解析、SIMD、对象布局、回归护栏 | 热路径可度量、不退化 |
| `v0.9.0` | 集群语义正确性 | 多 key 同槽校验、`CROSSSLOT`、`ASKING` | 重定向语义对齐 |
| `v0.10.0` | 集群成员与 gossip | 节点握手、gossip 消息、拓扑传播、PFAIL/FAIL 基础 | 多节点拓扑可传播 |
| `v0.11.0` | 集群故障转移基础 | replica 归属、config epoch、最小 failover | 槽位 owner 可切换 |
| `v0.12.0` | 重分片与集群 benchmark | `ADDSLOTS/DELSLOTS`、迁移闭环、正式集群性能报告 | resharding 可复现 |

## 4. 当前主线：`v0.1.0-alpha`

### A. 存储核心

#### A1. SDS 收尾

- [x] `sds_new()`
- [x] `sds_new_len()`
- [x] `sds_empty()`
- [x] `sds_dup()`
- [x] `sds_cat()`
- [x] `sds_range()`
- [x] `sds_cmp()`
- [x] `sds_casecmp()`
- [x] `sds_len()`
- [x] `sds_avail()`
- [x] `sds_grow()`
- [x] `sds_shrink()`
- [x] `sds_cat_fmt()` 最小实现
- [x] 1MB 追加压力测试
- [x] 内存布局与头部方案文档化

#### A2. 专用 `Dict`

- [x] 定义 `DictEntry`
- [x] 定义 `DictTable`
- [x] 定义 `Dict`
- [x] 实现 `insert()`
- [x] 实现 `lookup()`
- [x] 实现 `delete()`
- [x] 实现 `len()`
- [x] 单元测试：插入、覆盖、删除、缺失键
- [x] 单元测试：扩容后查找
- [x] 单元测试：10k 键规模回归
- [x] 第二阶段：`begin_rehash()` / `rehash_step()`

#### A3. `RedisObject` 最小实现

- [x] 定义 `ObjectType`
- [x] 定义 `Encoding`
- [x] 定义 `RedisObject`
- [x] 实现 String 变体
- [x] 实现 `create_string_object()`
- [x] 实现 `object_free()`
- [x] 实现 `object_type_name()`
- [x] 单元测试：String 对象创建/释放
- [x] 单元测试：整数编码与普通字符串编码

#### A4. `Engine` 最小实现

- [x] 定义 `RedisDb`
- [x] 定义 `Engine`
- [x] 实现 `lookup_key()`
- [x] 实现 `set_key()`
- [x] 实现 `delete_key()`
- [x] 实现 TTL 字段存储
- [x] 单元测试：键读写删除
- [x] 单元测试：惰性过期

### B. 协议与命令

#### B1. RESP2 最小子集

- [x] Simple String
- [x] Error
- [x] Integer
- [x] Bulk String
- [x] Array
- [x] 不完整输入返回 `Incomplete`
- [x] 单元测试：官方 RESP2 样本
- [x] 单元测试：半包输入
- [x] 单元测试：非法前缀与非法长度

#### B2. 命令路由

- [x] 定义 `Command`
- [x] 定义 `CommandInfo`
- [x] 注册最小命令表
- [x] 参数数量校验
- [x] 未知命令错误
- [x] 单元测试：查找、校验、错误路径

#### B3. String / Key 命令子集

- [x] `PING`
- [x] `GET`
- [x] `SET`
- [x] `DEL`
- [x] `EXISTS`
- [x] `EXPIRE`
- [x] `TTL`
- [x] `INFO` 最小段
- [x] 单元测试：每个命令正常路径
- [x] 单元测试：每个命令错误路径

### C. 服务闭环

#### C1. TCP 与连接

- [x] `listener` 最小 TCP 监听
- [x] `connection` 读写缓冲
- [x] 读取 -> 解析 -> 执行 -> 写回 闭环
- [x] `QUIT`
- [x] `maxclients` 最小限制

#### C2. 运行循环

- [x] Server 主循环
- [x] 100ms `cron`
- [x] 过期键惰性检查入口
- [x] 过期键主动扫描入口
- [x] 多连接 epoll 调度，空闲客户端不阻塞其他客户端
- [x] 启动/监听/响应 `PING` smoke

## 5. `v0.1.0-beta` 主线

### D. AOF 最小闭环

- [x] 写命令追加 AOF
- [x] 启动回放 AOF
- [x] `EXPIRE` AOF 转换为绝对 `PEXPIREAT`
- [x] 损坏 AOF 安全失败
- [x] 集成测试：写入 -> 重启 -> 恢复

### E. 稳定性与集成

- [x] `redis-cli` smoke：`tests/integration/redis_cli_smoke.sh`
- [x] Python 子集集成测试：`tests/integration/smoke_tcp.py`
- [x] Python 空闲连接回归测试：`tests/integration/idle_client.py`
- [x] Python 慢读客户端回归测试：`tests/integration/slow_reader.py`
- [x] Python AOF 重启恢复集成测试：`tests/integration/persistence_aof.py`
- [x] 错误响应与 Redis 基础兼容检查：`tests/integration/error_compat.py`
- [x] 长时运行 smoke（至少 30 分钟）

## 6. `v0.1.0` 发布闭环

### F. Benchmark 与基线

- [x] 同机 Redis 基线记录
- [x] `PING/SET/GET` benchmark
- [x] `floor/target/stretch` 判定
- [x] 输出到 `benchmarks/v0.1.0.md`

### G. 文档与验收

- [x] 完善 DoD 文档
- [x] 更新 `readme.md`
- [x] 新增 `QUICKSTART`
- [x] 新增 `API`
- [x] 新增 `ARCHITECTURE`
- [x] 新增 `release-v0.1.0`

## 7. `v0.2.0` 详细规划

### H. 数据结构扩展

- [x] Hash 最小对象实现
- [x] List 最小对象实现
- [x] Set 最小对象实现
- [x] ZSet 最小对象实现
- [x] 对应命令子集：`HSET/HGET`
- [x] 对应命令子集：`LPUSH/LPOP/LRANGE`
- [x] 对应命令子集：`SADD/SREM/SMEMBERS`
- [x] 对应命令子集：`ZADD/ZRANGE/ZREM`
- [x] `SCAN`
- [x] 更完整 `INFO` / `CONFIG`
- [x] 过期主动采样循环

### I. 持久化扩展

- [x] RDB 文件头/键值对子集
- [x] RDB 加载子集
- [x] AOF rewrite 预研

### J. 测试扩展

- [x] 五大类型单元测试
- [x] redis-py 子集覆盖更多命令
- [x] RDB/AOF 混合恢复测试

## 8. `v0.3.0` 详细规划

### K. 持久化增强

- [x] RDB 完整兼容推进
- [x] `BGSAVE`
- [x] `BGREWRITEAOF`
- [x] rewrite 增量缓冲
- [x] fork / 子进程路径验证

### L. 可靠性

- [x] 崩溃恢复矩阵
- [x] RDB/AOF 损坏与截断测试
- [x] 持久化 benchmark

## 9. `v0.4.0` 详细规划

### M. 主从复制

- [x] 复制角色与状态机
- [x] `PSYNC` / backlog
- [x] 全量同步
- [x] 增量同步
- [x] 复制心跳
- [x] 集成测试：主从一致性
- [x] 复制 benchmark

## 10. `v0.5.0` 详细规划

### N. 协议与控制面增强

- [x] RESP3
- [x] `MULTI/EXEC/DISCARD`
- [x] `WATCH/UNWATCH`
- [x] `PUBLISH/SUBSCRIBE`
- [x] `CLIENT` / `CONFIG` 命令增强
- [x] 兼容性回归测试

## 11. `v0.6.0` 详细规划

### O. 内存控制

- [x] `maxmemory`
- [x] `allkeys-lru`
- [x] `allkeys-lfu`
- [x] `volatile-*`
- [x] 内存统计完善
- [x] Slab allocator
- [x] 内存压力与淘汰测试

## 12. `v0.7.0` 详细规划

### P. 集群基础

- [x] Cluster 槽位模型
- [x] `MOVED` / `ASK`
- [x] 节点元数据
- [x] 最小集群拓扑
- [x] `CLUSTER` 最小命令接口
- [x] 集群一致性 smoke

## 13. `v0.8.0`：核心路径性能基线

### Q. 性能地基与回归护栏

- [ ] 核心 benchmark 矩阵与回归阈值
- [ ] 零拷贝响应路径
- [ ] 批量 RESP 解析
- [ ] SIMD 字符串和 CRC64
- [ ] `io_uring` 评估，不把生产路径绑定到未验证能力
- [ ] 专用对象池与布局优化
- [ ] Redis 对照差距报告与后续优化队列

验收项：

- `PING/GET/SET` 热路径吞吐和 p99 延迟较 `v0.7.0` 不退化
- benchmark 报告明确硬件、构建模式、持久化配置、数据规模和 Redis 对照口径
- 性能优化不改变协议、持久化、复制、集群基础语义
- 输出明确的后续性能债务清单，不把“超越 Redis”作为 `v0.8.0` 单版硬门槛

测试证据：

- `make test`
- `make test-integration`
- `scripts/benchmark_v0_1_0.py`
- 后续新增 `benchmarks/v0.8.0-performance.md`

## 14. `v0.9.0`：集群语义正确性

### R. 多 key 与 ASKING

- [ ] 多 key 命令统一提取所有 key，覆盖 `DEL/EXISTS/MGET/MSET` 首批命令
- [ ] 所有 key 落同一 slot 时继续执行本地或重定向判断
- [ ] 多 key 跨 slot 时返回 `CROSSSLOT Keys in request don't hash to the same slot`
- [ ] `ASKING` 连接级一次性放行：只允许下一条命令越过迁移态 `ASK`
- [ ] `ASKING` 与事务、WATCH、AOF、复制追加路径的边界收敛

验收项：

- 同槽多 key 命令在本地 owner 上保持当前语义
- 远端稳定 owner 返回 `MOVED`，迁移态 owner 在未 `ASKING` 时返回 `ASK`
- 客户端发送 `ASKING` 后，下一条同 slot 命令可执行一次，之后恢复正常 `ASK`
- 跨 slot 多 key 命令不会写本地库，不进入 AOF，不进入复制 backlog

测试证据：

- `tests/unit/command_router_test.uya` 覆盖多 key 元数据
- `tests/unit/command_executor_test.uya` 覆盖 `CROSSSLOT`、`MOVED`、`ASK`、`ASKING`
- `tests/unit/network_connection_test.uya` 覆盖连接级 `ASKING` 一次性状态
- 后续新增 `tests/integration/cluster_crossslot.py`
- 后续新增 `tests/integration/cluster_asking.py`

## 15. `v0.10.0`：集群成员与 gossip

### S. 成员发现与拓扑传播

- [ ] 抽出 cluster bus 消息编码/解码模块
- [ ] 实现节点握手状态：`MEET` -> handshake -> known node
- [ ] 实现 ping/pong gossip 消息与节点表传播
- [ ] 实现节点超时、`PFAIL`、`FAIL` 最小状态机
- [ ] `CLUSTER NODES/SLOTS/INFO` 基于真实多节点拓扑输出

验收项：

- 三节点进程 smoke 中，任意节点 `MEET` 后拓扑最终传播到其他节点
- 节点下线后可观测 `PFAIL/FAIL`，恢复后可重新连通
- gossip 更新不得破坏本地 slot owner 和 config epoch 单调性

测试证据：

- 后续新增 `src/cluster/gossip.uya`
- 后续新增 `tests/unit/cluster_gossip_test.uya`
- 后续新增 `tests/unit/cluster_topology_test.uya` 多节点传播用例
- 后续新增 `tests/integration/cluster_gossip_smoke.py`
- 后续新增 `tests/integration/cluster_node_failure_smoke.py`

## 16. `v0.11.0`：集群故障转移基础

### T. Replica 归属与 failover

- [ ] 节点元数据记录 replica master id 与复制偏移
- [ ] `CLUSTER REPLICATE` 最小实现
- [ ] replica 继承现有复制能力接入 cluster owner 视图
- [ ] failover 选择候选 replica，推进 config epoch
- [ ] failover 后更新 slot owner 并让旧 master 降级或标记 fail

验收项：

- master/replica 拓扑可通过 `CLUSTER NODES` 观测
- master 下线后，符合条件的 replica 可接管该 master 的 slots
- failover 后客户端收到新的 `MOVED` 地址，成功写入新 master
- failover 不破坏 RDB/AOF 恢复和复制一致性 smoke

测试证据：

- 后续新增 `src/cluster/failover.uya`
- 后续新增 `tests/unit/cluster_failover_test.uya`
- 后续扩展 `tests/integration/replication_consistency.py`
- 后续新增 `tests/integration/cluster_failover_smoke.py`
- 后续新增 `tests/integration/cluster_failover_recovery.py`

## 17. `v0.12.0`：重分片与正式集群 benchmark

### U. Resharding 与性能报告

- [ ] `CLUSTER ADDSLOTS` / `CLUSTER DELSLOTS` 最小实现
- [ ] `SETSLOT IMPORTING/MIGRATING/NODE/STABLE` 完整状态收敛
- [ ] 实现项目内 key 迁移闭环，优先覆盖 String 与当前核心类型
- [ ] 迁移期间 `ASK` / `ASKING` / `MOVED` 与多 key 同槽校验协同
- [ ] 建立正式集群 benchmark：单节点、2 master、3 master，对照 Redis Cluster

验收项：

- slot 可从节点 A 迁移到节点 B，迁移后旧 owner 返回 `MOVED`
- 迁移中客户端按 `ASK` + `ASKING` 可完成读写
- 迁移完成后源节点不保留已迁移 key，目标节点数据完整
- benchmark 报告包含吞吐、p50/p95/p99、RSS、slot 分布、节点数和 Redis Cluster 对照

测试证据：

- 后续新增 `src/cluster/migration.uya`
- 后续新增 `tests/unit/cluster_migration_test.uya`
- 后续新增 `tests/integration/cluster_resharding_smoke.py`
- 后续新增 `scripts/benchmark_cluster_v0_12_0.py`
- 后续新增 `benchmarks/v0.12.0-cluster.md`

## 18. 风险登记

| 风险 ID | 描述 | 可能性 | 影响 | 缓解措施 |
|---------|------|--------|------|---------|
| R1 | Uya 编译器在复杂类型组合上继续暴露后端问题 | 中 | 高 | 先写最小复现和定向测试，必要时先修编译器再前进 |
| R2 | `Dict` 首版实现复杂度失控 | 中 | 高 | 固定键/值类型，不在首版做泛型化 |
| R3 | 首版功能面再次膨胀 | 高 | 高 | 保持全版本规划，但严格控制当前执行范围 |
| R4 | AOF 与恢复语义不稳定 | 中 | 高 | 先做 append + replay，损坏路径优先补测试 |
| R5 | 性能目标过早绑死 | 中 | 中 | 先建立 benchmark 基线，再谈追平和超越 |
| R6 | 后续版本规划过粗导致执行断档 | 中 | 中 | 所有版本先保留完整任务框架，进入执行前再细化实现步骤 |
| R7 | 完整 Cluster 协议一次性铺开导致状态机失控 | 中 | 高 | 按语义正确性、gossip、failover、resharding 四段拆分，每段必须有单元与进程级 smoke |
