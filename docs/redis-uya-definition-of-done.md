# redis-uya Definition of Done

> 版本: v0.1.0-dev
> 日期: 2026-04-28
> 状态: `v0.5.0` 进行中

## 1. 目标

本页用于把 `redis-uya` 的阶段能力映射到明确测试、验证脚本或 benchmark 证据。

基础一键验证入口：

```bash
bash scripts/verify_definition_of_done.sh
```

补充说明：

- `tests/integration/long_run_smoke.py` 为 30 分钟长时运行验证，不纳入默认一键脚本
- `benchmarks/v0.1.0.md` 记录同机 Redis 基线与 `floor/target/stretch` 判定
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

## 8. `v0.5.0`（进行中）

| DoD 项 | 证据 |
|--------|------|
| RESP3 最小协议闭环可用：支持 `HELLO 2/3` 连接级协议切换、RESP3 Null/Boolean/Map 解析、RESP3 Null 回复和不支持协议版本错误路径 | `tests/unit/network_protocol_test.uya`、`tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py` |
| `MULTI/EXEC/DISCARD` 最小事务子集可用：连接级队列、`QUEUED`、`EXEC` 数组回复、`DISCARD` 丢弃、无 `MULTI` 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya`、`tests/integration/smoke_tcp.py`、`tests/integration/error_compat.py` |
| `WATCH/UNWATCH` 最小事务观察子集可用：按键版本跟踪、变更后 `EXEC` 返回 Null Array、`UNWATCH` 清空观察集、`WATCH/UNWATCH` in-transaction 错误路径 | `tests/unit/command_router_test.uya`、`tests/unit/network_connection_test.uya` |
