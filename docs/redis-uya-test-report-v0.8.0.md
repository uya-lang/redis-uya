# redis-uya Test Report v0.8.0

> 版本: v0.8.0
> 日期: 2026-04-29
> 状态: 发布前验证通过

> 路线更新: 2026-04-30 起，后续 `v0.9.0` 起主线调整为单机版完整功能、兼容性、性能和稳定性收敛；`v0.9.4` 是首个单机封版候选，未达标时继续 `v0.9.5`、`v0.9.6` 等 patch 版本；单机版达标后封版 `v1.0.0`，之后才重新规划集群版开发。

## 1. 目标

本报告汇总 `v0.8.0` 收口阶段已实际执行的构建、单元测试、集成测试、性能回归护栏、Redis 差距报告、`io_uring` 评估和发布前文档检查，作为封版证据。

## 2. 已执行验证

| 类别 | 命令 | 结果 |
|------|------|------|
| 构建 | `make build` | `PASS` |
| 单元测试 | `make test` | `PASS` |
| Python 集成测试 | `make test-integration` | `PASS` |
| `redis-cli` smoke | `make test-redis-cli` | `PASS` |
| v0.8.0 benchmark guard | `REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-release.md make benchmark-v0.8.0` | `PASS` |
| Redis 差距报告 | `make report-v0.8.0-gaps` | `PASS` |
| `io_uring` 评估 | `REDIS_UYA_IO_URING_OUT=build/v0.8.0-io-uring-release.md make evaluate-io-uring-v0.8.0` | `PASS` |
| DoD 一键验证 | `bash scripts/verify_definition_of_done.sh` | `PASS` |
| 格式检查 | `git diff --check` | `PASS` |

## 3. v0.8 集成覆盖

`make test-integration` 继续覆盖基础 TCP、空闲连接、慢读客户端、AOF/RDB/BGSAVE/BGREWRITEAOF、复制、事务、Pub/Sub、CLIENT/CONFIG、Cluster smoke、Cluster 一致性、maxmemory 策略、内存统计、内存压力和错误兼容路径。

`v0.8.0` 新增或强化的单元与集成覆盖包括：

- `tests/unit/network_connection_test.uya`：`GET` bulk string 零拷贝元数据路径
- `tests/unit/network_protocol_test.uya`：RESP2/RESP3 顶层批量解析、半包尾部和错误释放路径
- `tests/unit/util_bytes_test.uya`、`tests/unit/util_crc64_test.uya`：SIMD byte 比较和 CRC64 表驱动/标量对照
- `tests/unit/storage_object_test.uya`：`RedisObject` / `ListNode` 专用对象池复用、内存统计和布局大小
- `tests/unit/command_executor_test.uya`、`tests/integration/memory_info_stats.py`、`tests/integration/maxmemory_pressure.py`：`INFO memory` 对象池字段与内存治理可观测性

## 4. 性能与差距结论

- `benchmarks/v0.8.0-performance.md` 固化 `PING`、16B/1KiB `SET`、16B/1KiB `GET` 的同机 Redis 对照基线。
- `build/v0.8.0-release.md` 的 `PERF_GUARD_RESULT` 在五个 case 上均通过当前基线阈值。
- `benchmarks/v0.8.0-gap-report.md` 明确 `set_write_path` 是 P0 后续性能债务，`get_response_path` 和 `rss_residency` 是 P1，`round_trip_overhead` 与 `pipeline_and_batching` 是 P2。
- `benchmarks/v0.8.0-io-uring.md` 明确 `production_binding=no`，当前生产事件循环仍使用 epoll。

## 5. 发布前检查结果

- `docs/redis-uya-release-v0.8.0.md` 已记录能力、验证入口、限制和发布边界。
- `docs/redis-uya-definition-of-done.md` 已记录 v0.8.0 DoD 证据。
- `docs/redis-uya-todo.md` 已将 v0.8.0 标记为完成。报告生成时下一阶段曾指向集群语义；2026-04-30 路线已调整为先收敛单机版并封版 `v1.0.0`。
- `docs/redis-uya-api.md`、`docs/redis-uya-architecture.md`、`docs/redis-uya-benchmark-format.md`、`docs/README.md` 和根 `readme.md` 已同步 v0.8.0 口径。
- `scripts/verify_definition_of_done.sh` 已纳入 v0.8.0 benchmark guard、gap report 和 `io_uring` 评估的临时输出验证。
- 本次未自动创建 `v0.8.0` tag；如需正式发布 tag，应在干净工作区手动执行 tag 命令。

## 6. 结论

- `v0.8.0` 的代码、文档、测试、benchmark、评估报告和发布边界已收口。
- 当前主线满足项目对 `v0.8.0` 的核心路径可度量、不退化、可回归验证要求。
- 剩余性能工作进入后续优化队列；集群版开发调整到 `v1.0.0` 单机封版之后重新规划。

## 7. 相关文档

- [release-v0.8.0](./redis-uya-release-v0.8.0.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [Benchmark 输出格式](./redis-uya-benchmark-format.md)
- [API](./redis-uya-api.md)
- [ARCHITECTURE](./redis-uya-architecture.md)
- [v0.8.0 performance benchmark](../benchmarks/v0.8.0-performance.md)
- [v0.8.0 gap report](../benchmarks/v0.8.0-gap-report.md)
