# redis-uya Definition of Done

> 版本: v0.9.1-dev
> 日期: 2026-05-19
> 状态: 下列条目保留历史里程碑证据；截至 2026-05-19 最新复核，当前 `HEAD` 已恢复测试、benchmark 与 DoD 校验绿态，`COMMAND*` 运行时真值、当前 `CLIENT/CONFIG` 子命令矩阵状态、运行时版本串与命令完成度统计分层已对齐；主线已切到 `v0.9.2` 核心缺口补齐

## 1. 目标

本页用于把 `redis-uya` 的阶段能力映射到明确测试、验证脚本或 benchmark 证据。

重要说明：

- 本页下方的 `v0.1.0` ~ `v0.9.1` 条目首先是“历史阶段曾经落地过什么”的证据索引。
- 它们不能自动等价为“当前 `HEAD` 已重新验证通过”。
- 当前 `HEAD` 的真实性状态先看 [审计报告（2026-05-16）](./redis-uya-audit-2026-05-16.md)。

基础一键验证入口：

```bash
bash scripts/verify_definition_of_done.sh
```

补充说明：

- `tests/integration/long_run_smoke.py` 为 30 分钟长时运行验证，不纳入默认一键脚本
- `benchmarks/v0.1.0.md` 记录同机 Redis 基线与 `floor/target/stretch` 判定
- `benchmarks/v0.8.0-performance.md` 记录 `PING/SET/GET` 热路径矩阵、同机 Redis 对照与回归阈值基线
- `benchmarks/v0.8.0-gap-report.md` 记录 v0.8.0 相对 Redis 的差距矩阵与后续优化队列
- `benchmarks/v0.8.1-performance.md` 记录当前机器最近一次 `v0.8.1` guard 输出；必须结合生成日期判断它是历史通过样本还是当前失败样本
- `docs/redis-uya-release-v0.8.0.md` 与 `docs/redis-uya-test-report-v0.8.0.md` 固化 v0.8.0 封版边界和实际验证结果
- `docs/redis-uya-release-v0.8.1.md` 与 `docs/redis-uya-test-report-v0.8.1.md` 固化 v0.8.1 封版边界和实际验证结果
- 一键验证脚本会把临时 benchmark 输出写入 `build/`，避免覆盖已记录的基线报告
- 一键验证脚本包含 `git diff --check`，用于检查本次工作区差异的基础格式问题
- 本页同时记录 `v0.1.0` 发布证据，以及后续 `v0.2.0+` 已在主线落地的能力证据

## 2. 当前 HEAD 复核状态（2026-05-16）

| 项目 | 当前结果 | 说明 |
|------|----------|------|
| `make test` | `PASS` | 单元层仍可作为基础回归入口 |
| `make test-integration` | `PASS` | `maxmemory` / 压力 / 淘汰策略相关回归已按当前实现重新校准 |
| `make benchmark-v0.8.1` | `PASS` | guard 已升级为“绝对基线 + 同机 Redis 归一化兜底”，2026-05-19 当前复跑已恢复通过 |
| `bash scripts/verify_definition_of_done.sh` | `PASS` | 依赖链已恢复为通过状态，当前一键验证再次可用 |
| `COMMAND*` 真实性 | `PASS` | 运行时 `COMMAND*` 已按真实执行面隐藏未实现命令，并补齐当前 `CLIENT/CONFIG` 已实现子命令的矩阵状态 |
| 版本号一致性 | `PASS` | banner、`HELLO`、`INFO server`、README、DoD 和相关测试断言已统一到 `v0.9.1-dev` |

后续历史章节从这里开始顺延，保留原编号不代表当前 `HEAD` 已重新验收。

## 3. `v0.1.0-alpha`

| DoD 项 | 证据 |
|--------|------|
| `PING/GET/SET/DEL/EXISTS` 可通过 TCP smoke 交互 | `tests/integration/smoke_tcp.py` |
| SDS、Dict、Object、Engine 有单元测试 | `tests/unit/*_test.uya` |
| SDS 1MB 追加与布局说明完成 | `tests/unit/storage_sds_test.uya`、`docs/redis-uya-sds-layout.md` |
| Dict 渐进 rehash 可手动推进 | `tests/unit/storage_dict_test.uya` |
| 错误路径不会崩溃 | `tests/unit/*_test.uya` 中错误路径用例 |
| 100ms server cron 可触发主动过期扫描 | `tests/unit/storage_engine_test.uya`、`tests/unit/server_test.uya` |

## 4. `v0.1.0-beta`

| DoD 项 | 证据 |
|--------|------|
| AOF 重启恢复正确 | `tests/integration/persistence_aof.py` |
| AOF 追加、回放、损坏文件失败路径有单元证据 | `tests/unit/persistence_aof_test.uya` |
| 连接状态机与服务循环稳定 | `tests/integration/smoke_tcp.py`、`tests/integration/idle_client.py` |
| 空闲客户端不会阻塞其他客户端 | `tests/integration/idle_client.py` |
| `redis-cli` 可完成基础交互 smoke | `tests/integration/redis_cli_smoke.sh` |
| 慢读客户端不会因写回背压导致其他客户端停顿 | `tests/integration/slow_reader.py` |
| 错误响应与协议错误基础兼容 | `tests/integration/error_compat.py` |
| Python 子集集成测试通过 | `make test-integration` |
| 长时运行 smoke 完成 | `tests/integration/long_run_smoke.py`、`docs/redis-uya-release-v0.1.0.md` |

## 5. `v0.1.0`

| DoD 项 | 证据 |
|--------|------|
| 同机 Redis 基线可复现 | `scripts/benchmark_v0_1_0.py`、`benchmarks/v0.1.0.md` |
| `PING/SET/GET` benchmark 可生成 | `scripts/benchmark_v0_1_0.py`、`benchmarks/v0.1.0.md` |
| benchmark 基线可复现 | `benchmarks/v0.1.0.md` |
| Redis 对照口径明确 | `docs/redis-uya-benchmark-format.md` |
| 发布文档齐全 | `docs/redis-uya-release-v0.1.0.md`、`docs/redis-uya-quickstart.md`、`docs/redis-uya-api.md`、`docs/redis-uya-architecture.md` |

## 6. `v0.2.0`

| DoD 项 | 证据 |
|--------|------|
| Hash 最小对象可创建、写字段、读字段、覆盖字段并正确释放 | `tests/unit/storage_object_test.uya` |
| `HSET/HGET` 命令子集在单元与基础 TCP smoke 中可用 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| List 最小对象可创建、头插、头弹出、范围读取并正确释放 | `tests/unit/storage_object_test.uya` |
| `LPUSH/LPOP/LRANGE` 命令子集在单元与基础 TCP smoke 中可用 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| Set 最小对象可创建、去重插入、删除成员、枚举成员并正确释放 | `tests/unit/storage_object_test.uya` |
| `SADD/SREM/SMEMBERS` 命令子集在单元与基础 TCP smoke 中可用 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| ZSet 最小对象可创建、按 score 排序读取、更新成员 score、删除成员并正确释放 | `tests/unit/storage_object_test.uya` |
| `ZADD/ZRANGE/ZREM` 命令子集在单元与基础 TCP smoke 中可用 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| `SCAN` 最小语义可用：cursor 返回、`COUNT` 子集、按稳定顺序迭代非过期 key | `tests/unit/storage_engine_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| `INFO` 支持 `server/clients/memory/stats/keyspace` section 子集，`CONFIG GET` 支持最小配置查询 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_cli_smoke.sh` |
| 100ms cron 使用主动过期采样循环，过期比例高时会继续多轮清理 | `tests/unit/storage_engine_test.uya`、`tests/unit/server_test.uya` |

## 7. `v0.3.0`

| DoD 项 | 证据 |
|--------|------|
| 项目内 RDB 子集已覆盖 String/Hash/List/Set/ZSet 与绝对过期时间 save/load | `tests/unit/persistence_rdb_test.uya`、`tests/integration/persistence_bgsave.py` |
| `SAVE` 命令可写出当前五类对象的 RDB 快照 | `tests/unit/command_executor_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_cli_smoke.sh` |
| `BGSAVE` 通过真实 `fork/waitpid` 子进程在后台写出 RDB 快照，并可在去掉 AOF 后仅靠 RDB 恢复 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/server_test.uya`、`tests/integration/persistence_bgsave.py` |
| 服务启动时先加载最小 RDB，再回放 AOF 完成混合恢复 | `tests/unit/server_test.uya`、`tests/integration/persistence_rdb_aof.py` |
| `BGREWRITEAOF` 通过真实子进程后台 rewrite 与父进程增量缓冲合并，可生成可回放 AOF 并在重启/崩溃后恢复 | `tests/unit/persistence_rewrite_test.uya`、`tests/unit/server_test.uya`、`tests/integration/persistence_aof.py`、`tests/integration/persistence_crash_matrix.py` |
| Python 客户端风格子集覆盖更多命令与控制面 | `tests/integration/redis_py_subset.py` |
| RDB 损坏/截断与 AOF 损坏/截断在单元与进程级恢复路径上都有证据 | `tests/unit/persistence_rdb_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/server_test.uya`、`tests/integration/persistence_corruption.py` |
| 进程级崩溃恢复矩阵覆盖 AOF-only、rewrite in-progress、rewrite completed 三条路径 | `tests/integration/persistence_crash_matrix.py` |
| 持久化 benchmark 可生成并落盘 | `scripts/benchmark_persistence_v0_3_0.py`、`benchmarks/v0.3.0-persistence.md` |

## 8. `v0.4.0`

| DoD 项 | 证据 |
|--------|------|
| 复制角色与状态机可用：支持 master/slave 角色切换、`REPLICAOF`、`INFO replication`、`CONFIG GET replicaof/masterauth` | `tests/unit/config_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/server_test.uya`、`tests/integration/replication_role_state.py` |
| `PSYNC / backlog` 最小闭环可用：master 维护复制积压缓冲区，`PSYNC ? -1` 返回 `FULLRESYNC`，匹配 replid+offset 时返回 `CONTINUE` | `tests/unit/replication_backlog_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/replication_psync_backlog.py` |
| `REPLCONF` no-op 握手兼容面可用：常见 `CAPA` / `ACK` / 空参数形态返回 `OK`，不改变复制状态，不进入 AOF 或 replication backlog，并通过 redis-cli/redis-py/TCP/`COMMAND*` smoke 固化当前 partial 边界 | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| replica 侧全量同步可用：`REPLICAOF` 后可向 master 发起 `PSYNC ? -1`，拉取 RDB 快照并落当前库 | `tests/unit/persistence_rdb_test.uya`、`tests/integration/replication_full_sync.py` |
| replica 侧增量同步可用：connected 状态下可周期性拉取 backlog delta 并回放到本地库 | `tests/integration/replication_incremental_sync.py` |
| 复制心跳可用：replica 会周期性 `PING` master，掉线后回退到 `configured` 并在 master 恢复后重新同步 | `tests/integration/replication_heartbeat.py` |
| 主从一致性 smoke 覆盖当前五类对象的 full sync + incremental 复制 | `tests/integration/replication_consistency.py` |
| 复制 benchmark 可生成并落盘 | `scripts/benchmark_replication_v0_4_0.py`、`benchmarks/v0.4.0-replication.md` |

## 9. `v0.5.0`

| DoD 项 | 证据 |
|--------|------|
| RESP3 最小协议闭环可用：支持 `HELLO 2/3` 连接级协议切换、RESP3 Null/Boolean/Map 解析、RESP3 Null 回复和不支持协议版本错误路径 | `tests/unit/network_protocol_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| `MULTI/EXEC/DISCARD` 最小事务子集可用：连接级队列、`QUEUED`、`EXEC` 数组回复、`DISCARD` 丢弃、无 `MULTI` 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/error_compat.py` |
| `WATCH/UNWATCH` 最小事务观察子集可用：按键版本跟踪、变更后 `EXEC` 返回 Null Array、`UNWATCH` 清空观察集、`WATCH/UNWATCH` in-transaction 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya` |
| `PUBLISH/SUBSCRIBE/UNSUBSCRIBE` 最小 Pub/Sub 闭环可用：连接订阅注册、跨连接发布推送、发布返回订阅者数量、取消订阅后不再收到消息 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/pubsub_smoke.py` |
| `CLIENT` / `CONFIG` 控制面兼容子集可用：`CLIENT ID/GETNAME/GETREDIR/SETNAME/INFO/LIST/SETINFO/HELP/REPLY/UNBLOCK`、`HELLO SETNAME`、`CONFIG GET/HELP/RESETSTAT` | `tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py` |
| `v0.5.0` 兼容性回归覆盖协议与控制面组合路径：RESP3 Null、`HELLO SETNAME`、WATCH 中止、事务内控制命令错误、RESP3 Pub/Sub Push、控制面查询 | `tests/integration/v0_5_compat.py`、`tests/integration/error_compat.py`、`tests/integration/redis_py_subset.py` |

## 10. `v0.6.0`

| DoD 项 | 证据 |
|--------|------|
| `maxmemory` noeviction 基线可用：启动参数可设置最大内存，`CONFIG GET/INFO memory` 可观测，超预算增量写命令返回 OOM 且不落库 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/maxmemory_noeviction.py` |
| `allkeys-lru` 运行时淘汰基线可用：对象记录访问时间，读写触碰更新 LRU，超预算写入可淘汰最久未访问 key 后继续执行，`CONFIG GET/INFO memory` 可观测策略 | `tests/unit/storage_engine_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/maxmemory_allkeys_lru.py` |
| `allkeys-lfu` 运行时淘汰基线可用：对象记录访问计数，读写触碰递增 LFU，超预算写入可淘汰访问次数最低 key 后继续执行，同频次用 LRU 打破平局 | `tests/unit/storage_engine_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/maxmemory_allkeys_lfu.py` |
| `volatile-*` 运行时淘汰基线可用：`volatile-lru` / `volatile-lfu` / `volatile-ttl` 只从带 TTL 的 key 中选候选，永久 key 不被 volatile 策略淘汰 | `tests/unit/storage_engine_test.uya`、`tests/integration/maxmemory_volatile_policies.py` |
| 内存统计完善：allocator 记录当前使用、峰值、累计分配、累计释放、累计分配次数和当前活跃块数，`INFO memory` 可观测这些字段 | `tests/unit/memory_allocator_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py` |
| Slab allocator 基线可用：`redis_malloc/free/realloc` 内部对 16B 到 1KB 小对象做分级 freelist 缓存，缓存块数、缓存字节数和复用次数可通过 `INFO memory` 观测 | `tests/unit/memory_allocator_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py` |
| 内存压力与淘汰回归可复现：真实 TCP 循环写入覆盖 noeviction OOM、allkeys-lru、allkeys-lfu 与 volatile-ttl 压力路径，并校验新写入存活、旧/冷/近过期 key 被淘汰、永久 key 不被 volatile 策略淘汰 | `tests/integration/maxmemory_pressure.py` |

## 11. `v0.7.0`

| DoD 项 | 证据 |
|--------|------|
| Cluster 槽位模型可用：按 Redis Cluster CRC16 计算 `0..16383` 槽位，支持 `{hash-tag}` 子串选择，空 tag、缺失右括号、多个 tag 与嵌套大括号边界行为有单元证据 | `src/cluster/slots.uya`、`tests/unit/cluster_slots_test.uya` |
| 节点元数据模型可用：支持 40 字节 node id、本地 master 默认构造、host/port/bus port、master/replica 角色、flags、config epoch 与 connected 状态，并覆盖显式元数据和角色名边界 | `src/cluster/node.uya`、`tests/unit/cluster_node_test.uya` |
| 最小集群拓扑可用：默认单节点拓扑拥有 16384 个槽，可添加远端节点、按槽位范围重新分配 owner、按 slot/key 查询 owner，并覆盖非法 slot、节点查找和容量限制 | `src/cluster/topology.uya`、`tests/unit/cluster_topology_test.uya` |
| `CLUSTER` 最小命令接口可用：支持 `KEYSLOT`、`INFO`、`NODES`、`SLOTS`、`HELP`，真实 TCP smoke 校验 hash tag 槽位、单节点拓扑输出、node id 长度和帮助列表 | `tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/cluster_smoke.py` |
| `MOVED` / `ASK` 重定向路径可用：服务端持有最小拓扑状态，`CLUSTER MEET` 可注册远端节点，`CLUSTER SETSLOT ... NODE` 可触发稳定远端槽位 `MOVED`，`CLUSTER SETSLOT ... MIGRATING` 可触发迁移态 `ASK`，失败写命令不会进入 AOF/复制追加路径 | `tests/unit/command_executor_test.uya`、`tests/integration/cluster_smoke.py` |
| 集群一致性 smoke 可复现：真实 TCP 进程中校验远端槽位后 `CLUSTER NODES` 槽位范围分裂、`MOVED/ASK` 写命令不落本地库、不进入 AOF，以及 `SETSLOT STABLE` 清除迁移态后恢复本地访问 | `tests/integration/cluster_consistency.py` |

## 12. `v0.8.0`

| DoD 项 | 证据 |
|--------|------|
| 核心 benchmark 矩阵与回归阈值可用：覆盖 `PING`、16B/1KiB `SET`、16B/1KiB `GET`，记录 p50/p95/p99、吞吐、RSS、同机 Redis 对照，并支持用既有报告作为基线判定吞吐和 p99 退化 | `scripts/benchmark_v0_8_0.py`、`make benchmark-v0.8.0`、`benchmarks/v0.8.0-performance.md` |
| `GET` bulk string 零拷贝响应路径可用：64B 及以上命中值在真实 fd 发送路径使用 `writev` 分段发送 RESP 头、对象值 body 和 CRLF，避免把 value body 复制到连接输出缓冲；小 body 保持原路径，避免 syscall 开销导致退化 | `src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-zero-copy.md make benchmark-v0.8.0` |
| RESP2/RESP3 顶层批量解析可用：一次扫描可返回多个完整顶层帧、每帧消费长度和完整前缀总消费长度；遇到首帧半包返回 `RespIncomplete`，遇到完整前缀后的半包返回已解析前缀，错误尾包会释放已解析前缀 | `src/network/protocol.uya`、`tests/unit/network_protocol_test.uya`、`make test`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-batch-resp.md make benchmark-v0.8.0` |
| SIMD 字符串比较与 CRC64 加速可用：新增 `@vector` 16 字节块的 byte-slice 比较/大小写比较工具，命令路由、配置 token、SDS 比较和 Dict key 比较复用该工具；CRC64 更新改为 256 项表驱动，并保留标量路径用于正确性对照 | `src/util/bytes.uya`、`src/util/crc64.uya`、`tests/unit/util_bytes_test.uya`、`tests/unit/util_crc64_test.uya`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-simd-crc64.md make benchmark-v0.8.0` |
| `io_uring` 评估可复现且不绑定生产路径：评估脚本记录内核、sysctl、`io_uring_setup` syscall、liburing 探测和建议，报告明确 `production_binding=no`，当前网络事件循环仍保持 epoll 路径 | `scripts/evaluate_io_uring_v0_8_0.py`、`make evaluate-io-uring-v0.8.0`、`benchmarks/v0.8.0-io-uring.md`、`docs/redis-uya-benchmark-format.md` |
| 专用对象池与布局观测可用：`RedisObject` 与 `ListNode` 释放后进入专用 freelist，复用时不触碰通用 Slab 路径；allocator stats 仍按逻辑活跃对象增减，`INFO memory` 暴露对象池缓存、复用计数和布局大小 | `src/storage/object.uya`、`src/memory/allocator.uya`、`src/command/executor.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-object-pool.md make benchmark-v0.8.0` |
| Redis 对照差距报告与优化队列可复现：从 `BENCH_RESULT` 生成每个 case 的吞吐、p99、RSS 比例，输出 `PERF_GAP_RESULT` / `PERF_DEBT_RESULT` 机器可读行，并明确后续 P0/P1/P2 性能债务而不把“超越 Redis”作为单版硬门槛 | `scripts/report_v0_8_0_gaps.py`、`make report-v0.8.0-gaps`、`benchmarks/v0.8.0-gap-report.md`、`docs/redis-uya-benchmark-format.md` |

## 13. `v0.8.1`

| DoD 项 | 证据 |
|--------|------|
| WATCH 版本表懒维护可用：无活跃 WATCH 客户端时普通写命令不维护 `watch_versions`，有 WATCH 客户端时 `SET/DEL/EXPIRE` 仍推进版本并触发事务中止 | `src/storage/engine.uya`、`src/network/connection.uya`、`tests/unit/storage_engine_test.uya`、`tests/unit/network_connection_test.uya`、`make test` |
| Dict 覆盖写单次探测可用：`dict_insert_with_old()` 插入时返回 inserted，覆盖时返回旧值，`set_key_at()` 用该结果释放旧对象 | `src/storage/dict.uya`、`src/storage/engine.uya`、`tests/unit/storage_dict_test.uya`、`tests/unit/storage_engine_test.uya`、`make test` |
| AOF 分层写入可用：512B 以下命令进入 64KiB buffer，较大命令 flush 小缓冲后直接写；flush 在 server cron、客户端关闭、server close 与 BGREWRITEAOF fork 前触发 | `src/persistence/aof.uya`、`src/server.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/persistence_crash_matrix.py`、`tests/integration/cluster_consistency.py`、`make test`、`make test-integration` |
| v0.8.1 性能回归验证可复现：`make benchmark-v0.8.1` 默认以 `benchmarks/v0.8.0-performance.md` 为 guard 基线，输出 `benchmarks/v0.8.1-performance.md`，throughput guard 同时参考绝对历史基线与同机 Redis 归一化比例，五个 case 的吞吐和 p99 guard 当前复跑已通过 | `Makefile`、`scripts/benchmark_v0_8_0.py`、`benchmarks/v0.8.1-performance.md`、`make benchmark-v0.8.1` |

## 14. `v0.9.0`

| DoD 项 | 证据 |
|--------|------|
| Key/Server 第一批只读命令可用：`ECHO`、`TYPE`、`DBSIZE` 在命令路由、执行器、TCP 编解码和 redis-cli/redis-py smoke 中可用 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第二批过期毫秒语义可用：`PEXPIRE`、`PERSIST`、`PTTL` 覆盖命令执行、WATCH 版本推进、AOF 绝对过期时间回放和 TCP/redis-cli/redis-py smoke | `src/storage/engine.uya`、`src/persistence/aof.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_engine_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第一批增强命令可用：`APPEND`、`STRLEN`、`GETDEL` 覆盖执行器、AOF replay 和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第二批计数命令可用：`INCR`、`DECR`、`INCRBY`、`DECRBY` 覆盖执行器、错误路径和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第三批原子写入命令可用：`GETSET`、`SETNX`、`SETEX` 覆盖执行器、过期语义、AOF 绝对过期回放和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第四批多 key 命令可用：`MGET`、`MSET`、`MSETNX` 覆盖 nullable array 回复、多 key 写入和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第五批范围读写命令可用：`GETRANGE`、`SETRANGE` 覆盖负索引读取、空洞填充写入、AOF replay 和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| String 第六批浮点计数命令可用：`INCRBYFLOAT` 覆盖浮点参数校验、结果归一化、AOF replay 和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 第一批数值命令可用：`HINCRBY`、`HINCRBYFLOAT` 覆盖字段数值更新、浮点结果归一化和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 第二批视图命令可用：`HKEYS`、`HVALS`、`HGETALL`、`HRANDFIELD` 覆盖字段/值枚举、键值对视图、deterministic random-field partial、`WITHVALUES` 与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 第三批扫描命令可用：`HSCAN` 覆盖 cursor 返回、`COUNT` 选项、空 key 行为与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第一批扩展命令可用：`RPUSH`、`RPOP`、`LINDEX`、`LSET`、`LLEN` 覆盖正负索引、尾部弹出、原地更新与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第二批变异命令可用：`LINSERT`、`LTRIM`、`LREM` 覆盖 pivot 插入、区间裁剪、按次数删除与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第三批条件命令可用：`LPUSHX`、`RPUSHX`、`LPOS` 覆盖仅存在时写入、位置查找与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第一批随机取值命令可用：`SPOP`、`SRANDMEMBER` 覆盖空集合返回、成员返回与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第二批集合运算命令可用：`SINTER`、`SDIFF`、`SUNION` 覆盖有序结果回复、多 key 读取和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第三批写回命令可用：`SINTERSTORE`、`SDIFFSTORE`、`SUNIONSTORE` 覆盖目标 key 写回、成员计数和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第一批数值与计数命令可用：`ZINCRBY`、`ZCARD`、`ZCOUNT` 覆盖整数 score 递增、成员计数和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第二批范围读取命令可用：`ZLEXCOUNT`、`ZRANGEBYLEX`、`ZREVRANGE`、`ZREVRANGEBYLEX`、`ZRANGEBYSCORE`、`ZREVRANGEBYSCORE` 覆盖整数 score 区间读取、lex 开闭/无穷边界计数、lex `LIMIT` 正反向范围返回、升降序结果、`ZREVRANGE WITHSCORES` 和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/storage/object.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第三批范围删除、扫描与读/写路径补齐命令可用：`ZREMRANGEBYLEX`、`ZREMRANGEBYRANK`、`ZREMRANGEBYSCORE`、`ZRANGESTORE`、`ZSCAN`、`ZRANDMEMBER`、`ZDIFF`、`ZDIFFSTORE`、`ZINTER`、`ZINTERCARD`、`ZINTERSTORE`、`ZUNION`、`ZUNIONSTORE` 覆盖按 lex 删除、按 rank 删除、按 score 删除、rank 范围写回、scan 回复、deterministic random-member partial、差集读取、差集写回、交集读取、交集计数、交集写回、并集读取、并集写回、`WITHSCORES` 与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第三批命令可用：`RENAME`、`RENAMENX`、`LASTSAVE` 覆盖 key 改名、存在性语义、最近保存时间与 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/command/router.uya`、`src/command/executor.uya`、`src/server.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第四批清空命令可用：`FLUSHDB`、`FLUSHALL` 覆盖当前 DB 清空、watch 版本推进、AOF replay 与 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_engine_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第五批绝对过期命令可用：`PEXPIREAT` 覆盖绝对过期时间设置、TTL 计算和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第六批序列化命令可用：`DUMP`、`RESTORE` 覆盖项目内 RDB 子集 payload、相对毫秒 TTL 恢复、AOF replay 与 redis-cli/redis-py/TCP smoke | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`src/persistence/rdb.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第七批单库与对象检查命令可用：`SELECT`、`OBJECT` 覆盖单库 `db0` 选择、对象编码/引用计数/空闲时间/FREQ 边界，以及 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第八批单库迁移/DB 管理命令可用：`MOVE` 在当前单库模式下覆盖同库错误与越界 DB 错误；`SWAPDB` partial 覆盖 `0 0` no-op、越界 DB 错误、非法整数和 `COMMAND*` 可见面，并通过 redis-cli/redis-py/TCP smoke 固化兼容边界 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第九批复制等待命令可用：`WAIT` 覆盖参数校验、负 timeout 错误和当前单机无副本场景返回 `0` 的兼容边界；`WAITAOF` partial 覆盖本地确认数组、当前无副本 AOF ACK 返回 `0`、参数校验、负 timeout 错误和 `COMMAND*` 可见面，并通过 redis-cli/redis-py/TCP smoke 固化 | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第十五批诊断命令可用：`LOLWUT` partial 覆盖默认 bulk 文本、`VERSION` 整数校验、未知首参数默认输出、`COMMAND*` 可见面，并通过 redis-cli/redis-py/TCP smoke 固化当前不生成 Redis 原版动态图形的兼容边界 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第十批排序命令可用：`SORT` 覆盖 list/set/zset 源、`ASC/DESC`、`ALPHA`、`LIMIT`、`BY`、多 `GET`、`STORE`、hash pattern 和 `SORT STORE` 的 AOF replay | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Security baseline 可用：`requirepass`、`AUTH`、`SHUTDOWN` 覆盖配置解析、未认证 NOAUTH、密码校验、连接级认证状态、真实进程关闭和 redis-cli/redis-py/TCP smoke | `src/config.uya`、`src/main.uya`、`src/command/router.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/config_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |

## 15. `v0.9.1` 第一批

| DoD 项 | 证据 |
|--------|------|
| 官方命令全集矩阵可追踪：基于 Redis 8.6 命令页生成 `531` 个官方命令名、状态、目标版本与基础元数据，并落盘为命令矩阵文档 | `scripts/generate_command_catalog.py`、`docs/redis-uya-command-matrix.md` |
| 运行时共享目录可用：`src/command/catalog_generated*` 提供统一命令目录，`COMMAND` 家族与文档矩阵不再各维护一份命令名清单 | `src/command/catalog.uya`、`src/command/catalog_generated_base.uya`、`src/command/catalog_generated.uya`、`src/command/catalog_generated_part_*.uya` |
| `COMMAND` 控制面第一批可用：`COMMAND`、`COMMAND COUNT`、`COMMAND LIST`、`COMMAND INFO`、`COMMAND DOCS` 覆盖 RESP2/RESP3 基础返回、`LIST FILTERBY PATTERN/ACLCAT/MODULE`、`INFO` 未知命令占位和 `DOCS` 未知命令忽略边界 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| `COMMAND DOCS` 无参数全量输出可用：覆盖 `531` 个目录项的 RESP2/RESP3 全量 docs 返回，以及服务端大响应发送第一批闭环 | `src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| `COMMAND GETKEYS` / `COMMAND GETKEYSANDFLAGS` 当前命令表支持可用：覆盖 range key spec、多 key/成对 key、`RENAME` 双 key、`SORT ... STORE` / `BLMPOP` / `ZMPOP` / `BZMPOP` movablekeys、`RO/OW/RW/RM` 与 `access/update/insert/delete` 基础 flags 组合 | `src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| 单次读入批量执行可用：连接层会在一次读入中消费多个完整 RESP 顶层帧，覆盖 `MULTI/SET/GET/EXEC` 管线与 `redis-cli` stdin/pipeline 客户端路径 | `src/network/protocol.uya`、`src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/redis_cli_smoke.sh` |

## 16. `v0.9.1` 第二批

| DoD 项 | 证据 |
|--------|------|
| `CONFIG SET` 第二批运行时字段可用：支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`masterauth`、`replicaof`、`maxclients`、`databases`，覆盖非法参数、`REPLICAOF NO ONE` 提升、运行时 `maxclients` 更新与 `CONFIG GET` 回读 | `src/config.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/client_config_smoke.py` |
| `CONFIG REWRITE` 对应第二批核心字段落盘可用：运行时改写后的 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`masterauth`、`maxclients`、`databases` 与内存策略可写回到重写配置文件 | `src/config.uya`、`src/command/executor.uya`、`src/server.uya`、`tests/unit/config_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/client_config_smoke.py` |
| String/Generic TTL 扩展可用：`GETEX`、`PSETEX`、`EXPIREAT`、`EXPIRETIME`、`PEXPIRETIME` 覆盖 key 提取 flags、绝对时间/相对时间 TTL 语义、AOF 绝对过期重放，以及 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 字段基础扩展可用：`HDEL`、`HEXISTS`、`HLEN`、`HMGET`、`HSETNX`、`HSTRLEN` 覆盖 object helper、nullable array 回复、空 hash 删除与 AOF replay，以及 TCP/redis-py/redis-cli smoke | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 读路径扩展可用：`SCARD`、`SISMEMBER`、`SMISMEMBER`、`SSCAN` 覆盖成员计数、单成员命中、多成员顺序返回、scan cursor/COUNT 与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 交集计数扩展可用：`SINTERCARD` 覆盖 `numkeys`、`LIMIT`、空 key、错类型、参数错误边界与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 写路径补齐可用：`SMOVE` 覆盖同 key 搬移、空源返回、源/目标错类型、源清空删除、AOF replay 与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key 通用管理扩展可用：`TOUCH`、`UNLINK` 覆盖存在 key 计数、多 key 返回、删除后存在性边界与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key 模式读取扩展可用：`KEYS` 覆盖 `*` / `?` 最小 glob、字典序结果与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 只读排序扩展可用：`SORT_RO` 覆盖只读排序返回、`STORE` 语法错误边界与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 读路径补齐可用：`RANDOMKEY`、`TIME` 覆盖空库/单 key 语义、秒/微秒数组回复，以及 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 复制可观测读命令可用：`ROLE` 覆盖 master/replica 两种 RESP Array 返回形态，并通过 TCP/redis-py/redis-cli smoke 固化 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |

## 17. `v0.9.1` 第三批

| DoD 项 | 证据 |
|--------|------|
| Pub/Sub pattern 第一批可用：`PSUBSCRIBE`、`PUNSUBSCRIBE`、`PUBLISH` 对 pattern 订阅推送 `pmessage`，并把直连/模式匹配接收者一起计入返回值 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py` |
| Pub/Sub 管理面第一批可用：`PUBSUB HELP/CHANNELS/NUMPAT/NUMSUB` 复用连接订阅注册表返回当前频道与 pattern 计数，`PUBSUB SHARDCHANNELS/SHARDNUMSUB` 固定当前 shard 空结果边界 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py` |
| `RESET` 连接上下文重置可用：覆盖 RESP3 -> RESP2 协议回退、订阅态退出、事务/观察键清理、tracking/client metadata 清空与 deauth 行为 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/connection_reset_smoke.py` |
| Pub/Sub 订阅态命令限制第一批可用：RESP2 订阅态仅允许 `SUBSCRIBE/PSUBSCRIBE/UNSUBSCRIBE/PUNSUBSCRIBE/PING/QUIT/RESET`，RESP3 订阅态保持非 Pub/Sub 命令可用 | `src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py`、`tests/integration/connection_reset_smoke.py` |
| Pub/Sub 断开清理可用：连接关闭后会移除其频道/模式订阅项，后续 `PUBLISH` 不再把已断开连接计入接收者数量 | `src/server.uya`、`src/network/connection.uya`、`tests/integration/pubsub_smoke.py` |

## 18. `v0.9.2` 第一批

| DoD 项 | 证据 |
|--------|------|
| Blocking list 第一批可用：`BLPOP`、`BRPOP`、`BRPOPLPUSH`、`BLMOVE`、`BLMPOP` 覆盖立即命中、空源挂起、server-side unblock、超时返回、`COMMAND*` 可见性与 AOF replay | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/blocking_list_smoke.py`、`tests/integration/command_introspection.py`、`make test`、`make test-integration` |
| Blocking zset 第一批可用：`BZPOPMIN`、`BZPOPMAX`、`BZMPOP` 覆盖立即命中、空源挂起、server-side unblock、超时返回、`COMMAND*` 可见性与 AOF replay | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/blocking_zset_smoke.py`、`tests/integration/command_introspection.py`、`make test`、`make test-integration` |
| Sorted-set multi-pop partial 可用：`ZMPOP` 覆盖多 key 顺序探测、`MIN/MAX`、`COUNT`、空结果 Null Array、错类型/参数错误、`COMMAND*` 可见性、AOF replay 与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Bitmap 读路径第一批可用：`BITPOS` 覆盖 `0/1` 查找、缺省范围与 `start/end BYTE/BIT` 边界、missing key 特例、错类型/参数错误路径，以及 TCP/redis-py/redis-cli/`COMMAND*` smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test` |
| Bitmap 写路径第一批可用：`BITOP` 覆盖 `AND/OR/XOR/NOT`、all-missing 删除目标 key、`NOT` 单源限制、目标 TTL 清理、AOF replay，以及 TCP/redis-py/redis-cli/`COMMAND*` smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Bitfield 第一批可用：`BITFIELD`、`BITFIELD_RO` 覆盖 `GET/SET/INCRBY`、`iN/uN` 编码、`#` 偏移、`OVERFLOW WRAP/SAT/FAIL`、只读约束、TTL 保留、AOF replay，以及 TCP/redis-py/redis-cli/`COMMAND*` smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| HyperLogLog 第一批 partial 可用：`PFADD`、`PFCOUNT`、`PFMERGE` 覆盖增量写入、单 key / 多 key 计数、merge、AOF replay 与 TCP/redis-py/redis-cli/`COMMAND*` smoke；当前内部仍是 exact set-backed cardinality，而非 Redis 原生 HLL 编码 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Key copy partial 可用：`COPY source destination [DB 0] [REPLACE]` 覆盖当前单 DB 深拷贝、目标存在返回 `0`、`REPLACE` 覆盖、source TTL 保留、same-key 错误、非 `0` DB 错误、WATCH 版本推进、maxmemory noeviction、AOF replay、复制增量同步与 TCP/redis-py/redis-cli/`COMMAND*` smoke；当前不支持多 DB 目标复制 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/replication_incremental_sync.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Restore asking partial 可用：`RESTORE-ASKING key ttl serialized-value` 复用 `RESTORE` 的单 DB RDB payload 写入路径，覆盖路由、执行器、`COMMAND INFO/LIST/DOCS/GETKEYS` 可见面和 redis-py/redis-cli smoke；当前不校验集群 ASKING 状态，也不支持 `REPLACE` / `ABSTTL` / `IDLETIME` / `FREQ` | `src/command/router.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_x.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Geo 第一批 partial 可用：`GEOADD`、`GEODIST`、`GEOHASH`、`GEOPOS`、`GEOSEARCH`、`GEOSEARCHSTORE`、`GEORADIUS`、`GEORADIUS_RO`、`GEORADIUSBYMEMBER`、`GEORADIUSBYMEMBER_RO` 覆盖基础写入、距离查询、geohash 查询、坐标查询、search store 写回、legacy radius 查询、missing member/null 返回、`FROMMEMBER/FROMLONLAT`、`BYRADIUS/BYBOX`、`ASC/DESC`、`COUNT`、`WITHDIST/WITHCOORD/WITHHASH`、`STOREDIST` 整数距离 score、AOF replay 与 TCP/redis-py/redis-cli/`COMMAND*` smoke；当前内部仍是 exact zset-backed packed coordinate score，而非 Redis 原生 geohash 编码，`GEOSEARCHSTORE STOREDIST` 暂不保存 Redis 原生浮点距离，legacy 写型 radius 命令暂不支持 `STORE/STOREDIST` | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Scripting 第一批 partial 可用：`EVAL`、`EVALSHA`、`EVAL_RO`、`EVALSHA_RO`、`SCRIPT DEBUG/LOAD/EXISTS/FLUSH/KILL` 覆盖脚本缓存、SHA1 查找、只读脚本拒写、事务执行、AOF / 复制传播实际命令效果、debug 模式 no-op、无运行脚本 `KILL` 错误面，以及 TCP/redis-py/redis-cli/`COMMAND*` smoke；当前只支持单条 `return redis.call(...)` 脚本子集，不支持多语句 Lua、`redis.pcall` 或 Redis Lua debugger，`SCRIPT KILL` 仅覆盖 no-running-script 兼容面 | `src/command/router.uya`、`src/network/connection.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/replication_incremental_sync.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Functions 第一批 partial 可用：`FUNCTION HELP`、`FUNCTION LIST`、`FUNCTION STATS`、`FUNCTION FLUSH`、`FUNCTION DELETE`、`FUNCTION LOAD`、`FUNCTION DUMP`、`FUNCTION RESTORE`、`FUNCTION KILL`、`FCALL`、`FCALL_RO` 覆盖路由、执行器帮助数组、空库列表、空库统计、no-op flush、空库删除错误面、加载未支持错误面、空库序列化 payload、空库 payload restore、无运行脚本错误面、空库调用错误面、参数校验、`COMMAND GETKEYS*`、`COMMAND INFO/LIST/DOCS` 可见面、TCP/redis-py/redis-cli smoke；当前不支持 function library 存储、非空 `FUNCTION RESTORE` 或真实 `FCALL/FCALL_RO` 执行 | `src/command/router.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_m.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| ACL 第一批 partial 可用：`ACL CAT`、`ACL DELUSER`、`ACL DRYRUN`、`ACL GENPASS`、`ACL GETUSER`、`ACL HELP`、`ACL LIST`、`ACL LOAD`、`ACL LOG`、`ACL SAVE`、`ACL SETUSER`、`ACL USERS`、`ACL WHOAMI` 覆盖路由、执行器 ACL 分类、默认用户不可删除错误面、默认用户 dry-run 命令检查、口令生成、默认用户详情、帮助数组、默认用户 config 格式、ACL 文件未配置错误面、空 ACL 日志、默认用户 no-op SETUSER 兼容面、默认用户列表、当前默认用户、参数错误、未知子命令错误、`COMMAND INFO/LIST/DOCS` 可见面、redis-py/redis-cli/`COMMAND*` smoke；当前不支持 ACL 用户存储、命令权限、key pattern 权限、真实 ACL 日志或 ACL 文件加载保存，安全基线仍由 `requirepass` / `AUTH` 提供 | `src/command/router.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_a.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Client reply partial 可用：`CLIENT REPLY ON|OFF|SKIP` 覆盖连接级回复抑制状态、单次 skip、`OFF` 期间命令继续执行、`RESET` 清理、`CLIENT HELP`、`COMMAND INFO/LIST/DOCS` 可见面和真实 TCP/redis-cli smoke；当前只覆盖命令回复抑制，不改变 Pub/Sub push 或 `MONITOR` 推送 | `src/network/connection.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_f.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py`、`tests/integration/command_introspection.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Client unblock partial 可用：`CLIENT UNBLOCK id [TIMEOUT\|ERROR]` 覆盖阻塞 pop 等待客户端的 timeout/error 解除、未阻塞目标返回 `0`、参数错误、`CLIENT HELP`、`COMMAND INFO/LIST/DOCS` 可见面和真实 TCP/redis-cli smoke；当前只覆盖 redis-uya 内置阻塞 pop 等待，不支持模块阻塞客户端类型 | `src/network/connection.uya`、`src/server.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_f.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py`、`tests/integration/command_introspection.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Client caching partial 可用：`CLIENT CACHING YES|NO` 覆盖连接级标志存储、参数错误、`RESET` 清理、`CLIENT HELP`、`COMMAND INFO/LIST/DOCS` 可见面和真实 TCP/redis-cli smoke；当前只保存兼容标志，尚未提供 server-assisted client-side caching invalidation | `src/network/connection.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_f.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py`、`tests/integration/command_introspection.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Client no-evict partial 可用：`CLIENT NO-EVICT ON|OFF` 覆盖连接级标志存储、参数错误、`RESET` 清理、`CLIENT HELP`、`COMMAND INFO/LIST/DOCS` 可见面和真实 TCP/redis-cli smoke；当前只保存兼容标志，尚未接入 `maxmemory` 淘汰候选保护 | `src/network/connection.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_f.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py`、`tests/integration/command_introspection.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Client no-touch partial 可用：`CLIENT NO-TOUCH ON|OFF` 覆盖连接级标志存储、参数错误、`RESET` 清理、`CLIENT HELP`、`COMMAND INFO/LIST/DOCS` 可见面和真实 TCP/redis-cli smoke；当前只保存兼容标志，尚未接入对象访问路径的 LRU/LFU touch 抑制 | `src/network/connection.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_f.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py`、`tests/integration/command_introspection.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Module 第一批 partial 可用：`MODULE HELP`、`MODULE LIST` 覆盖路由、执行器帮助数组、空模块列表、参数错误、未知子命令错误、`COMMAND INFO/LIST/DOCS` 可见面、TCP/redis-py/redis-cli/`COMMAND*` smoke；当前不支持 module 加载、卸载或模块 API，`MODULE LOAD/LOADEX/UNLOAD` 不进入可见命令目录 | `src/command/router.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_u.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Memory 第一批 partial 可用：`MEMORY HELP`、`MEMORY STATS`、`MEMORY USAGE`、`MEMORY DOCTOR`、`MEMORY MALLOC-STATS`、`MEMORY PURGE` 覆盖 allocator / object-pool / `maxmemory` 观测、近似 key 占用、诊断文本、allocator bulk report、no-op purge、TCP/redis-py/redis-cli/`COMMAND*` smoke；`USAGE` 返回 redis-uya 运行时近似占用，`MALLOC-STATS` 返回 redis-uya allocator / object-pool 计数，均非 Redis 原生 jemalloc 口径，`PURGE` 不触发 Redis jemalloc purge 级别的 allocator 行为 | `src/command/router.uya`、`src/command/executor.uya`、`src/storage/dict.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Slowlog 第一批 partial 可用：`SLOWLOG HELP`、`SLOWLOG LEN`、`SLOWLOG GET`、`SLOWLOG RESET` 覆盖空日志、固定容量 ring 读取、重置、事务内执行、TCP/redis-py/redis-cli/`COMMAND*` smoke；当前 slowlog 仅保留 redis-uya 进程内最近命令，`duration_us` 固定为 `0`，客户端地址固定为占位值，不支持 Redis 原生阈值配置或真实微秒耗时 | `src/command/router.uya`、`src/command/executor.uya`、`src/command/slowlog.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Latency 第一批 partial 可用：`LATENCY HELP`、`LATENCY LATEST`、`LATENCY HISTORY`、`LATENCY RESET`、`LATENCY DOCTOR`、`LATENCY HISTOGRAM`、`LATENCY GRAPH` 覆盖空事件返回、诊断文本、参数错误、TCP/redis-py/redis-cli/`COMMAND*` smoke；当前仅提供 empty-event compatibility surface，不采样真实延迟事件或命令直方图 | `src/command/router.uya`、`src/command/executor.uya`、`src/command/catalog_generated_part_s.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Monitor 第一批 partial 可用：`MONITOR` 覆盖进入流式观测模式、跨连接命令推送、`RESET` 退出、连接关闭清理、`COMMAND*` 可见性与真实 TCP smoke；当前监控行使用 redis-uya 占位端点，不包含 Redis 原生客户端地址、DB 切换真值或微秒精度时间 | `src/command/router.uya`、`src/network/connection.uya`、`src/server.uya`、`src/command/catalog_generated_part_u.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/monitor_smoke.py`、`tests/integration/command_introspection.py`、`make test`、`make test-integration` |
| Debug standalone-error 可用：`DEBUG subcommand [arg ...]` 进入运行时路由、命令矩阵和 `COMMAND INFO/LIST/DOCS` 可见面，但在 redis-uya 单机安全 profile 中统一返回禁用错误，不开放 Redis 内部调试/破坏性子命令，也不写 AOF/复制 backlog | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/command/catalog_generated_part_j.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |
| Failover standalone-error 可用：`FAILOVER [TO host port [FORCE]] [ABORT] [TIMEOUT milliseconds]` 进入运行时路由、命令矩阵和 `COMMAND INFO/LIST/DOCS` 可见面；当前无副本/未实现 controlled failover 状态机时返回 Redis 兼容的 connected-replica 错误，不提升 replica、不切换复制角色、不写 AOF/复制 backlog | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/command/catalog_generated_part_k.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py`、`tests/integration/redis_py_subset.py`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_cli_smoke.sh`、`make test`、`make test-integration` |

## 19. `v0.9.3` 第一批

| DoD 项 | 证据 |
|--------|------|
| Streams 第一批 partial 可用：`XADD`、`XLEN`、`XRANGE`、`XREVRANGE`、`XREAD` 覆盖基础追加、自动/显式 id、长度、正反向范围、`COUNT`、非阻塞读取、错类型、RDB save/load、AOF rewrite 与真实 TCP smoke；当前不支持 `NOMKSTREAM`、`XREAD BLOCK`、consumer group 或 Redis 原生 radix-tree/listpack 编码，普通 AOF append 对 `XADD *` 回放会重新生成 ID | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`src/persistence/rdb.uya`、`src/persistence/rewrite.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/persistence_rdb_test.uya`、`tests/unit/persistence_rewrite_test.uya`、`tests/integration/streams_smoke.py`、`tests/integration/command_introspection.py`、`make test`、`make test-integration` |
| Streams 第二批 partial 可用：`XTRIM MAXLEN [=|~] count` 覆盖 stream 头部裁剪、空 key 返回 `0`、错类型、`COMMAND*` 可见性与真实 TCP/AOF replay smoke；`XDEL key id [id ...]` 覆盖精确 ID 删除、缺失 ID/缺失 key 返回 `0`、错类型、`COMMAND*` 可见性与真实 TCP/AOF replay smoke；`XACK key group id [id ...]`、`XCLAIM key group consumer min-idle-time id [id ...]` 与 `XPENDING key group [IDLE min-idle-time] start end count [consumer]` 覆盖无 group 时的 `NOGROUP`、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；`XGROUP HELP` / `XINFO HELP` 覆盖帮助兼容面、错误参数和 `COMMAND*` 可见性；`XGROUP CREATE key group id [MKSTREAM]` 覆盖参数解析、缺失 key、错类型、明确未支持错误、`COMMAND*` 可见性与真实 TCP smoke；`XGROUP DESTROY key group` 覆盖 empty-state 返回 `0`、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；`XGROUP SETID key group id [ENTRIESREAD n]` 覆盖无 group 时的 `NOGROUP`、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；`XINFO STREAM key [FULL [COUNT count]]` 覆盖 key-only 基础元数据、FULL entry 明细、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；`XINFO GROUPS key` 覆盖 empty-state 空数组、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；`XINFO CONSUMERS key group` 覆盖无 group 时的 `NOGROUP`、缺失 key、错类型、`COMMAND*` 可见性与真实 TCP smoke；当前 `~` 仅作为语法兼容占位，仍按精确裁剪执行，`XDEL` 不维护 consumer group PEL，不支持 `MINID` / `LIMIT` 或真实 consumer group 状态命令 | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/streams_smoke.py`、`tests/integration/command_introspection.py`、`make test`、`make test-integration` |
| 运维、安全与可观测余量仍在后续执行期；TLS / 更完整 `CLIENT/CONFIG/INFO/SLOWLOG/LATENCY/MEMORY/MONITOR/MODULE` 的证据待进入对应批次后补齐，其中 `LATENCY` 当前仅完成空事件兼容子集，`MONITOR` 当前仅完成流式观测 partial，`MODULE` 当前仅完成空模块列表兼容子集，`CLIENT REPLY` 当前仅完成命令回复抑制子集，`CLIENT UNBLOCK` 当前仅完成阻塞 pop 等待解除子集，`CLIENT CACHING/NO-EVICT/NO-TOUCH` 当前仅完成连接级标志兼容子集 | 以 `docs/redis-uya-todo.md` 当前 `v0.9.3` 计划为准 |
