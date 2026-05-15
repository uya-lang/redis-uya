# redis-uya Definition of Done

> 版本: v0.9.1-dev
> 日期: 2026-05-14
> 状态: 当前 DoD 已实锤到 `v0.9.1`；`v0.9.2` 高级数据能力与 `v0.9.3` 运维/安全能力仅保留预留段，待进入执行期后再补证据

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
- `benchmarks/v0.8.1-performance.md` 记录 v0.8.1 写路径修复后相对 v0.8.0 基线的 guard 结果
- `docs/redis-uya-release-v0.8.0.md` 与 `docs/redis-uya-test-report-v0.8.0.md` 固化 v0.8.0 封版边界和实际验证结果
- `docs/redis-uya-release-v0.8.1.md` 与 `docs/redis-uya-test-report-v0.8.1.md` 固化 v0.8.1 封版边界和实际验证结果
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
| `CLIENT` / `CONFIG` 控制面兼容子集可用：`CLIENT ID/GETNAME/GETREDIR/SETNAME/INFO/LIST/SETINFO/HELP`、`HELLO SETNAME`、`CONFIG GET/HELP/RESETSTAT` | `tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/client_config_smoke.py` |
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

## 12. `v0.8.1`

| DoD 项 | 证据 |
|--------|------|
| WATCH 版本表懒维护可用：无活跃 WATCH 客户端时普通写命令不维护 `watch_versions`，有 WATCH 客户端时 `SET/DEL/EXPIRE` 仍推进版本并触发事务中止 | `src/storage/engine.uya`、`src/network/connection.uya`、`tests/unit/storage_engine_test.uya`、`tests/unit/network_connection_test.uya`、`make test` |
| Dict 覆盖写单次探测可用：`dict_insert_with_old()` 插入时返回 inserted，覆盖时返回旧值，`set_key_at()` 用该结果释放旧对象 | `src/storage/dict.uya`、`src/storage/engine.uya`、`tests/unit/storage_dict_test.uya`、`tests/unit/storage_engine_test.uya`、`make test` |
| AOF 分层写入可用：512B 以下命令进入 64KiB buffer，较大命令 flush 小缓冲后直接写；flush 在 server cron、客户端关闭、server close 与 BGREWRITEAOF fork 前触发 | `src/persistence/aof.uya`、`src/server.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/persistence_crash_matrix.py`、`tests/integration/cluster_consistency.py`、`make test`、`make test-integration` |
| v0.8.1 性能回归验证可复现：`make benchmark-v0.8.1` 默认以 `benchmarks/v0.8.0-performance.md` 为 guard 基线，输出 `benchmarks/v0.8.1-performance.md`，五个 case 的吞吐和 p99 guard 均通过 | `Makefile`、`scripts/benchmark_v0_8_0.py`、`benchmarks/v0.8.1-performance.md`、`make benchmark-v0.8.1` |

## 13. `v0.9.0`

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
| Hash 第二批视图命令可用：`HKEYS`、`HVALS`、`HGETALL` 覆盖字段/值枚举、键值对视图与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 第三批扫描命令可用：`HSCAN` 覆盖 cursor 返回、`COUNT` 选项、空 key 行为与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第一批扩展命令可用：`RPUSH`、`RPOP`、`LINDEX`、`LSET`、`LLEN` 覆盖正负索引、尾部弹出、原地更新与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第二批变异命令可用：`LINSERT`、`LTRIM`、`LREM` 覆盖 pivot 插入、区间裁剪、按次数删除与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| List 第三批条件命令可用：`LPUSHX`、`RPUSHX`、`LPOS` 覆盖仅存在时写入、位置查找与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第一批随机取值命令可用：`SPOP`、`SRANDMEMBER` 覆盖空集合返回、成员返回与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第二批集合运算命令可用：`SINTER`、`SDIFF`、`SUNION` 覆盖有序结果回复、多 key 读取和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 第三批写回命令可用：`SINTERSTORE`、`SDIFFSTORE`、`SUNIONSTORE` 覆盖目标 key 写回、成员计数和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第一批数值与计数命令可用：`ZINCRBY`、`ZCARD`、`ZCOUNT` 覆盖整数 score 递增、成员计数和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第二批范围读取命令可用：`ZRANGEBYSCORE`、`ZREVRANGEBYSCORE` 覆盖整数 score 区间读取、升降序结果和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/storage/object.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| ZSet 第三批范围删除与扫描命令可用：`ZREMRANGEBYRANK`、`ZREMRANGEBYSCORE`、`ZSCAN` 覆盖按 rank 删除、按 score 删除、scan 回复与 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第三批命令可用：`RENAME`、`RENAMENX`、`LASTSAVE` 覆盖 key 改名、存在性语义、最近保存时间与 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/command/router.uya`、`src/command/executor.uya`、`src/server.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第四批清空命令可用：`FLUSHDB`、`FLUSHALL` 覆盖当前 DB 清空、watch 版本推进、AOF replay 与 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_engine_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第五批绝对过期命令可用：`PEXPIREAT` 覆盖绝对过期时间设置、TTL 计算和 redis-cli/redis-py/TCP smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第六批序列化命令可用：`DUMP`、`RESTORE` 覆盖项目内 RDB 子集 payload、相对毫秒 TTL 恢复、AOF replay 与 redis-cli/redis-py/TCP smoke | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`src/persistence/rdb.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第七批单库与对象检查命令可用：`SELECT`、`OBJECT` 覆盖单库 `db0` 选择、对象编码/引用计数/空闲时间/FREQ 边界，以及 redis-cli/redis-py/TCP smoke | `src/storage/engine.uya`、`src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第八批单库迁移命令可用：`MOVE` 在当前单库模式下覆盖同库错误与越界 DB 错误，并通过 redis-cli/redis-py/TCP smoke 固化兼容边界 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第九批复制等待命令可用：`WAIT` 覆盖参数校验、负 timeout 错误和当前单机无副本场景返回 `0` 的兼容边界，并通过 redis-cli/redis-py/TCP smoke 固化 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key/Server 第十批排序命令可用：`SORT` 覆盖 list/set/zset 源、`ASC/DESC`、`ALPHA`、`LIMIT`、`BY`、多 `GET`、`STORE`、hash pattern 和 `SORT STORE` 的 AOF replay | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Security baseline 可用：`requirepass`、`AUTH`、`SHUTDOWN` 覆盖配置解析、未认证 NOAUTH、密码校验、连接级认证状态、真实进程关闭和 redis-cli/redis-py/TCP smoke | `src/config.uya`、`src/main.uya`、`src/command/router.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/config_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |

## 14. `v0.9.1` 第一批

| DoD 项 | 证据 |
|--------|------|
| 官方命令全集矩阵可追踪：基于 Redis 8.6 命令页生成 `531` 个官方命令名、状态、目标版本与基础元数据，并落盘为命令矩阵文档 | `scripts/generate_command_catalog.py`、`docs/redis-uya-command-matrix.md` |
| 运行时共享目录可用：`src/command/catalog_generated*` 提供统一命令目录，`COMMAND` 家族与文档矩阵不再各维护一份命令名清单 | `src/command/catalog.uya`、`src/command/catalog_generated_base.uya`、`src/command/catalog_generated.uya`、`src/command/catalog_generated_part_*.uya` |
| `COMMAND` 控制面第一批可用：`COMMAND`、`COMMAND COUNT`、`COMMAND LIST`、`COMMAND INFO`、`COMMAND DOCS` 覆盖 RESP2/RESP3 基础返回、`LIST FILTERBY PATTERN/ACLCAT/MODULE`、`INFO` 未知命令占位和 `DOCS` 未知命令忽略边界 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| `COMMAND DOCS` 无参数全量输出可用：覆盖 `531` 个目录项的 RESP2/RESP3 全量 docs 返回，以及服务端大响应发送第一批闭环 | `src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| `COMMAND GETKEYS` / `COMMAND GETKEYSANDFLAGS` 当前命令表支持可用：覆盖 range key spec、多 key/成对 key、`RENAME` 双 key、`SORT ... STORE` movablekeys、`RO/OW/RW/RM` 与 `access/update/insert/delete` 基础 flags 组合 | `src/command/executor.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/command_introspection.py` |
| 单次读入批量执行可用：连接层会在一次读入中消费多个完整 RESP 顶层帧，覆盖 `MULTI/SET/GET/EXEC` 管线与 `redis-cli` stdin/pipeline 客户端路径 | `src/network/protocol.uya`、`src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/redis_cli_smoke.sh` |

## 15. `v0.9.1` 第二批

| DoD 项 | 证据 |
|--------|------|
| `CONFIG SET` 第二批运行时字段可用：支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`masterauth`、`replicaof`、`maxclients`、`databases`，覆盖非法参数、`REPLICAOF NO ONE` 提升、运行时 `maxclients` 更新与 `CONFIG GET` 回读 | `src/config.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/server.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/client_config_smoke.py` |
| `CONFIG REWRITE` 对应第二批核心字段落盘可用：运行时改写后的 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`masterauth`、`maxclients`、`databases` 与内存策略可写回到重写配置文件 | `src/config.uya`、`src/command/executor.uya`、`src/server.uya`、`tests/unit/config_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/client_config_smoke.py` |
| String/Generic TTL 扩展可用：`GETEX`、`PSETEX`、`EXPIREAT`、`EXPIRETIME`、`PEXPIRETIME` 覆盖 key 提取 flags、绝对时间/相对时间 TTL 语义、AOF 绝对过期重放，以及 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`src/network/connection.uya`、`src/persistence/aof.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Hash 字段基础扩展可用：`HDEL`、`HEXISTS`、`HLEN`、`HMGET`、`HSETNX`、`HSTRLEN` 覆盖 object helper、nullable array 回复、空 hash 删除与 AOF replay，以及 TCP/redis-py/redis-cli smoke | `src/storage/object.uya`、`src/command/router.uya`、`src/command/executor.uya`、`tests/unit/storage_object_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 读路径扩展可用：`SCARD`、`SISMEMBER`、`SMISMEMBER`、`SSCAN` 覆盖成员计数、单成员命中、多成员顺序返回、scan cursor/COUNT 与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Set 写路径补齐可用：`SMOVE` 覆盖同 key 搬移、空源返回、源/目标错类型、源清空删除、AOF replay 与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/persistence_aof_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key 通用管理扩展可用：`TOUCH`、`UNLINK` 覆盖存在 key 计数、多 key 返回、删除后存在性边界与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| Key 模式读取扩展可用：`KEYS` 覆盖 `*` / `?` 最小 glob、字典序结果与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 只读排序扩展可用：`SORT_RO` 覆盖只读排序返回、`STORE` 语法错误边界与 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 读路径补齐可用：`RANDOMKEY`、`TIME` 覆盖空库/单 key 语义、秒/微秒数组回复，以及 TCP/redis-py/redis-cli smoke | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |
| 复制可观测读命令可用：`ROLE` 覆盖 master/replica 两种 RESP Array 返回形态，并通过 TCP/redis-py/redis-cli smoke 固化 | `src/command/router.uya`、`src/command/executor.uya`、`tests/unit/command_router_test.uya`、`tests/unit/command_executor_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/redis_py_subset.py`、`tests/integration/redis_cli_smoke.sh` |

## 16. `v0.9.1` 第三批

| DoD 项 | 证据 |
|--------|------|
| Pub/Sub pattern 第一批可用：`PSUBSCRIBE`、`PUNSUBSCRIBE`、`PUBLISH` 对 pattern 订阅推送 `pmessage`，并把直连/模式匹配接收者一起计入返回值 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py` |
| Pub/Sub 管理面第一批可用：`PUBSUB HELP/CHANNELS/NUMPAT/NUMSUB` 复用连接订阅注册表返回当前频道与 pattern 计数，`PUBSUB SHARDCHANNELS/SHARDNUMSUB` 固定当前 shard 空结果边界 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py` |
| `RESET` 连接上下文重置可用：覆盖 RESP3 -> RESP2 协议回退、订阅态退出、事务/观察键清理、tracking/client metadata 清空与 deauth 行为 | `src/command/router.uya`、`src/network/connection.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/connection_reset_smoke.py` |
| Pub/Sub 订阅态命令限制第一批可用：RESP2 订阅态仅允许 `SUBSCRIBE/PSUBSCRIBE/UNSUBSCRIBE/PUNSUBSCRIBE/PING/QUIT/RESET`，RESP3 订阅态保持非 Pub/Sub 命令可用 | `src/network/connection.uya`、`tests/unit/network_connection_test.uya`、`tests/unit/test_runner.uya`、`tests/integration/pubsub_smoke.py`、`tests/integration/connection_reset_smoke.py` |
| Pub/Sub 断开清理可用：连接关闭后会移除其频道/模式订阅项，后续 `PUBLISH` 不再把已断开连接计入接收者数量 | `src/server.uya`、`src/network/connection.uya`、`tests/integration/pubsub_smoke.py` |

## 17. `v0.9.2` 预留

| DoD 项 | 证据 |
|--------|------|
| 高级数据能力阶段尚未进入执行期；Bitmap / Bitfield / HyperLogLog / Geo / JSON / Search / Time Series / 概率结构 / Vector 的证据待首批实现落地后补齐 | 以 `docs/redis-uya-todo.md` 当前 `v0.9.2` 计划为准 |

## 18. `v0.9.3` 预留

| DoD 项 | 证据 |
|--------|------|
| 运维、安全与可观测阶段尚未进入执行期；ACL / TLS / 更完整 `CLIENT/CONFIG/INFO/SLOWLOG/LATENCY/MEMORY/MONITOR` 的证据待进入执行期后补齐 | 以 `docs/redis-uya-todo.md` 当前 `v0.9.3` 计划为准 |
