# redis-uya Definition of Done

> 版本: v0.8.0
> 日期: 2026-04-29
> 状态: `v0.8.0` 核心路径性能基线已完成

## 1. 目标

本页用于把 `redis-uya` 的阶段能力映射到明确测试、验证脚本或 benchmark 证据。

基础一键验证入口：

```bash
bash scripts/verify_definition_of_done.sh
```

补充说明：

- `tests/integration/long_run_smoke.py` 为 30 分钟长时运行验证，不纳入默认一键脚本
- `benchmarks/v0.1.0.md` 记录同机 Redis 基线与 `floor/target/stretch` 判定
- `benchmarks/v0.8.0-performance.md` 记录 `PING/SET/GET` 热路径矩阵、同机 Redis 对照与回归阈值基线
- `benchmarks/v0.8.0-gap-report.md` 记录 v0.8.0 相对 Redis 的差距矩阵与后续优化队列
- `docs/redis-uya-release-v0.8.0.md` 与 `docs/redis-uya-test-report-v0.8.0.md` 固化 v0.8.0 封版边界和实际验证结果
- 一键验证脚本会把临时 benchmark 输出写入 `build/`，避免覆盖已记录的基线报告
- 一键验证脚本包含 `git diff --check`，用于检查本次工作区差异的基础格式问题
- 本页同时记录 `v0.1.0` 发布证据，以及后续 `v0.2.0+` 已在主线落地的能力证据

## 2. `v0.1.0-alpha`

| DoD 项 | 证据 |
|--------|------|
| `PING/GET/SET/DEL/EXISTS` 可通过 TCP smoke 交互 | `tests/integration/smoke_tcp.py` |
| SDS、Dict、Object、Engine 有单元测试 | `tests/unit/*_test.uya` |
| SDS 1MB 追加与布局说明完成 | `tests/unit/storage_sds_test.uya`、`docs/redis-uya-sds-layout.md` |
| Dict 渐进 rehash 可手动推进 | `tests/unit/storage_dict_test.uya` |
| 错误路径不会崩溃 | `tests/unit/*_test.uya` 中错误路径用例 |
| 100ms server cron 可触发主动过期扫描 | `tests/unit/storage_engine_test.uya`、`tests/unit/server_test.uya` |

## 3. `v0.1.0-beta`

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

## 4. `v0.1.0`

| DoD 项 | 证据 |
|--------|------|
| 同机 Redis 基线可复现 | `scripts/benchmark_v0_1_0.py`、`benchmarks/v0.1.0.md` |
| `PING/SET/GET` benchmark 可生成 | `scripts/benchmark_v0_1_0.py`、`benchmarks/v0.1.0.md` |
| benchmark 基线可复现 | `benchmarks/v0.1.0.md` |
| Redis 对照口径明确 | `docs/redis-uya-benchmark-format.md` |
| 发布文档齐全 | `docs/redis-uya-release-v0.1.0.md`、`docs/redis-uya-quickstart.md`、`docs/redis-uya-api.md`、`docs/redis-uya-architecture.md` |

## 5. `v0.2.0`

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

## 6. `v0.3.0`

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

## 7. `v0.4.0`

| DoD 项 | 证据 |
|--------|------|
| 复制角色与状态机可用：支持 master/slave 角色切换、`REPLICAOF`、`INFO replication`、`CONFIG GET replicaof/masterauth` | `tests/unit/config_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/server_test.uya`、`tests/integration/replication_role_state.py` |
| `PSYNC / backlog` 最小闭环可用：master 维护复制积压缓冲区，`PSYNC ? -1` 返回 `FULLRESYNC`，匹配 replid+offset 时返回 `CONTINUE` | `tests/unit/replication_backlog_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/replication_psync_backlog.py` |
| replica 侧全量同步可用：`REPLICAOF` 后可向 master 发起 `PSYNC ? -1`，拉取 RDB 快照并落当前库 | `tests/unit/persistence_rdb_test.uya`、`tests/integration/replication_full_sync.py` |
| replica 侧增量同步可用：connected 状态下可周期性拉取 backlog delta 并回放到本地库 | `tests/integration/replication_incremental_sync.py` |
| 复制心跳可用：replica 会周期性 `PING` master，掉线后回退到 `configured` 并在 master 恢复后重新同步 | `tests/integration/replication_heartbeat.py` |
| 主从一致性 smoke 覆盖当前五类对象的 full sync + incremental 复制 | `tests/integration/replication_consistency.py` |
| 复制 benchmark 可生成并落盘 | `scripts/benchmark_replication_v0_4_0.py`、`benchmarks/v0.4.0-replication.md` |

## 8. `v0.5.0`

| DoD 项 | 证据 |
|--------|------|
| RESP3 最小协议闭环可用：支持 `HELLO 2/3` 连接级协议切换、RESP3 Null/Boolean/Map 解析、RESP3 Null 回复和不支持协议版本错误路径 | `tests/unit/network_protocol_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| `MULTI/EXEC/DISCARD` 最小事务子集可用：连接级队列、`QUEUED`、`EXEC` 数组回复、`DISCARD` 丢弃、无 `MULTI` 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/error_compat.py` |
| `WATCH/UNWATCH` 最小事务观察子集可用：按键版本跟踪、变更后 `EXEC` 返回 Null Array、`UNWATCH` 清空观察集、`WATCH/UNWATCH` in-transaction 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya` |
| `PUBLISH/SUBSCRIBE/UNSUBSCRIBE` 最小 Pub/Sub 闭环可用：连接订阅注册、跨连接发布推送、发布返回订阅者数量、取消订阅后不再收到消息 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/pubsub_smoke.py` |
| `CLIENT` / `CONFIG` 控制面兼容子集可用：`CLIENT ID/GETNAME/SETNAME/INFO/LIST/SETINFO/HELP`、`HELLO SETNAME`、`CONFIG GET/HELP/RESETSTAT` | `tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py` |
| `v0.5.0` 兼容性回归覆盖协议与控制面组合路径：RESP3 Null、`HELLO SETNAME`、WATCH 中止、事务内控制命令错误、RESP3 Pub/Sub Push、控制面查询 | `tests/integration/v0_5_compat.py`、`tests/integration/error_compat.py`、`tests/integration/redis_py_subset.py` |

## 9. `v0.6.0`

| DoD 项 | 证据 |
|--------|------|
| `maxmemory` noeviction 基线可用：启动参数可设置最大内存，`CONFIG GET/INFO memory` 可观测，超预算增量写命令返回 OOM 且不落库 | `tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/maxmemory_noeviction.py` |
| `allkeys-lru` 运行时淘汰基线可用：对象记录访问时间，读写触碰更新 LRU，超预算写入可淘汰最久未访问 key 后继续执行，`CONFIG GET/INFO memory` 可观测策略 | `tests/unit/storage_engine_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/maxmemory_allkeys_lru.py` |
| `allkeys-lfu` 运行时淘汰基线可用：对象记录访问计数，读写触碰递增 LFU，超预算写入可淘汰访问次数最低 key 后继续执行，同频次用 LRU 打破平局 | `tests/unit/storage_engine_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/maxmemory_allkeys_lfu.py` |
| `volatile-*` 运行时淘汰基线可用：`volatile-lru` / `volatile-lfu` / `volatile-ttl` 只从带 TTL 的 key 中选候选，永久 key 不被 volatile 策略淘汰 | `tests/unit/storage_engine_test.uya`、`tests/integration/maxmemory_volatile_policies.py` |
| 内存统计完善：allocator 记录当前使用、峰值、累计分配、累计释放、累计分配次数和当前活跃块数，`INFO memory` 可观测这些字段 | `tests/unit/memory_allocator_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py` |
| Slab allocator 基线可用：`redis_malloc/free/realloc` 内部对 16B 到 1KB 小对象做分级 freelist 缓存，缓存块数、缓存字节数和复用次数可通过 `INFO memory` 观测 | `tests/unit/memory_allocator_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py` |
| 内存压力与淘汰回归可复现：真实 TCP 循环写入覆盖 noeviction OOM、allkeys-lru、allkeys-lfu 与 volatile-ttl 压力路径，并校验新写入存活、旧/冷/近过期 key 被淘汰、永久 key 不被 volatile 策略淘汰 | `tests/integration/maxmemory_pressure.py` |

## 10. `v0.7.0`

| DoD 项 | 证据 |
|--------|------|
| Cluster 槽位模型可用：按 Redis Cluster CRC16 计算 `0..16383` 槽位，支持 `{hash-tag}` 子串选择，空 tag、缺失右括号、多个 tag 与嵌套大括号边界行为有单元证据 | `src/cluster/slots.uya`、`tests/unit/cluster_slots_test.uya` |
| 节点元数据模型可用：支持 40 字节 node id、本地 master 默认构造、host/port/bus port、master/replica 角色、flags、config epoch 与 connected 状态，并覆盖显式元数据和角色名边界 | `src/cluster/node.uya`、`tests/unit/cluster_node_test.uya` |
| 最小集群拓扑可用：默认单节点拓扑拥有 16384 个槽，可添加远端节点、按槽位范围重新分配 owner、按 slot/key 查询 owner，并覆盖非法 slot、节点查找和容量限制 | `src/cluster/topology.uya`、`tests/unit/cluster_topology_test.uya` |
| `CLUSTER` 最小命令接口可用：支持 `KEYSLOT`、`INFO`、`NODES`、`SLOTS`、`HELP`，真实 TCP smoke 校验 hash tag 槽位、单节点拓扑输出、node id 长度和帮助列表 | `tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/cluster_smoke.py` |
| `MOVED` / `ASK` 重定向路径可用：服务端持有最小拓扑状态，`CLUSTER MEET` 可注册远端节点，`CLUSTER SETSLOT ... NODE` 可触发稳定远端槽位 `MOVED`，`CLUSTER SETSLOT ... MIGRATING` 可触发迁移态 `ASK`，失败写命令不会进入 AOF/复制追加路径 | `tests/unit/command_executor_test.uya`、`tests/integration/cluster_smoke.py` |
| 集群一致性 smoke 可复现：真实 TCP 进程中校验远端槽位后 `CLUSTER NODES` 槽位范围分裂、`MOVED/ASK` 写命令不落本地库、不进入 AOF，以及 `SETSLOT STABLE` 清除迁移态后恢复本地访问 | `tests/integration/cluster_consistency.py` |

## 11. `v0.8.0`

| DoD 项 | 证据 |
|--------|------|
| 核心 benchmark 矩阵与回归阈值可用：覆盖 `PING`、16B/1KiB `SET`、16B/1KiB `GET`，记录 p50/p95/p99、吞吐、RSS、同机 Redis 对照，并支持用既有报告作为基线判定吞吐和 p99 退化 | `scripts/benchmark_v0_8_0.py`、`make benchmark-v0.8.0`、`benchmarks/v0.8.0-performance.md` |
| `GET` bulk string 零拷贝响应路径可用：64B 及以上命中值在真实 fd 发送路径使用 `writev` 分段发送 RESP 头、对象值 body 和 CRLF，避免把 value body 复制到连接输出缓冲；小 body 保持原路径，避免 syscall 开销导致退化 | `src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-zero-copy.md make benchmark-v0.8.0` |
| RESP2/RESP3 顶层批量解析可用：一次扫描可返回多个完整顶层帧、每帧消费长度和完整前缀总消费长度；遇到首帧半包返回 `RespIncomplete`，遇到完整前缀后的半包返回已解析前缀，错误尾包会释放已解析前缀 | `src/network/protocol.uya`、`tests/unit/network_protocol_test.uya`、`make test`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-batch-resp.md make benchmark-v0.8.0` |
| SIMD 字符串比较与 CRC64 加速可用：新增 `@vector` 16 字节块的 byte-slice 比较/大小写比较工具，命令路由、配置 token、SDS 比较和 Dict key 比较复用该工具；CRC64 更新改为 256 项表驱动，并保留标量路径用于正确性对照 | `src/util/bytes.uya`、`src/util/crc64.uya`、`tests/unit/util_bytes_test.uya`、`tests/unit/util_crc64_test.uya`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-simd-crc64.md make benchmark-v0.8.0` |
| `io_uring` 评估可复现且不绑定生产路径：评估脚本记录内核、sysctl、`io_uring_setup` syscall、liburing 探测和建议，报告明确 `production_binding=no`，当前网络事件循环仍保持 epoll 路径 | `scripts/evaluate_io_uring_v0_8_0.py`、`make evaluate-io-uring-v0.8.0`、`benchmarks/v0.8.0-io-uring.md`、`docs/redis-uya-benchmark-format.md` |
| 专用对象池与布局观测可用：`RedisObject` 与 `ListNode` 释放后进入专用 freelist，复用时不触碰通用 Slab 路径；allocator stats 仍按逻辑活跃对象增减，`INFO memory` 暴露对象池缓存、复用计数和布局大小 | `src/storage/object.uya`、`src/memory/allocator.uya`、`src/command/executor.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py`、`make test`、`make test-integration`、`REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-object-pool.md make benchmark-v0.8.0` |
| Redis 对照差距报告与优化队列可复现：从 `BENCH_RESULT` 生成每个 case 的吞吐、p99、RSS 比例，输出 `PERF_GAP_RESULT` / `PERF_DEBT_RESULT` 机器可读行，并明确后续 P0/P1/P2 性能债务而不把“超越 Redis”作为单版硬门槛 | `scripts/report_v0_8_0_gaps.py`、`make report-v0.8.0-gaps`、`benchmarks/v0.8.0-gap-report.md`、`docs/redis-uya-benchmark-format.md` |
