# redis-uya Test Report v0.8.1

> 版本: v0.8.1
> 日期: 2026-04-29
> 状态: 发布前验证通过

> 路线更新: 2026-04-30 起，后续 `v0.9.0` 起主线调整为单机版完整功能、兼容性、性能和稳定性收敛；`v0.9.4` 是首个单机封版候选，未达标时继续 `v0.9.5`、`v0.9.6` 等 patch 版本；单机版达标后封版 `v1.0.0`，之后才重新规划集群版开发。

## 1. 目标

本报告汇总 `v0.8.1` 写路径性能修复阶段实际执行的单元测试、集成测试、性能回归护栏和发布前检查，作为封版证据。

## 2. 已执行验证

| 类别 | 命令 | 结果 |
|------|------|------|
| 单元测试 | `make test` | `PASS` |
| Python 集成测试 | `make test-integration` | `PASS` |
| v0.8.1 benchmark guard | `make benchmark-v0.8.1` | `PASS` |
| DoD 一键验证 | `bash scripts/verify_definition_of_done.sh` | `PASS` |
| 格式检查 | `git diff --check` | `PASS` |

## 3. 新增覆盖

- `tests/unit/storage_engine_test.uya`：WATCH 版本懒维护、活跃 WATCH 客户端下版本推进
- `tests/unit/network_connection_test.uya`：WATCH 注册/清理会维护 engine 级活跃 watch client 计数
- `tests/unit/storage_dict_test.uya`：`dict_insert_with_old()` 插入/覆盖返回值
- `tests/unit/persistence_aof_test.uya`：AOF flush 可在 close 前落盘，大命令绕过小命令 buffer 后可直接 replay
- `tests/integration/persistence_crash_matrix.py`：等待周期 flush 后再执行 crash 恢复断言
- `tests/integration/cluster_consistency.py`：等待成功本地写进入 AOF，同时继续断言重定向失败写不进入 AOF
- `tests/integration/maxmemory_volatile_policies.py`：进程级 volatile-lru 断言收敛到“只淘汰 TTL 候选，永久 key 不被淘汰”，精确 LRU 顺序由单元测试覆盖

## 4. 性能结论

`benchmarks/v0.8.1-performance.md` 相对 `benchmarks/v0.8.0-performance.md` 的 guard 全部通过：

- 吞吐 guard：`ping`、`set_16b`、`get_16b`、`set_1024b`、`get_1024b` 均为 `pass`
- p99 guard：`ping`、`set_16b`、`get_16b`、`set_1024b`、`get_1024b` 均为 `pass`

`SET` 绝对性能仍明显低于 Redis；本报告只证明 `v0.8.1` 相对 `v0.8.0` 基线不退化，并完成首批写路径开销收敛。

## 5. 发布前检查结果

- `docs/redis-uya-release-v0.8.1.md` 已记录能力、验证入口、限制和发布边界。
- `docs/redis-uya-definition-of-done.md` 已记录 v0.8.1 DoD 证据。
- `docs/redis-uya-todo.md` 已将 v0.8.1 标记为完成。报告生成时下一阶段曾指向集群语义；2026-04-30 路线已调整为先收敛单机版并封版 `v1.0.0`。
- `docs/README.md` 和根 `readme.md` 已同步 v0.8.1 口径。
- `scripts/verify_definition_of_done.sh` 已纳入 v0.8.1 benchmark guard 的临时输出验证。
- 本次未自动创建 `v0.8.1` tag；如需正式发布 tag，应在干净工作区手动执行 tag 命令。

## 6. 结论

- `v0.8.1` 的代码、文档、测试、benchmark 和发布边界已收口。
- 当前主线满足项目对 `v0.8.1` 的写路径修复、不退化和可回归验证要求。
- 剩余性能工作继续进入后续优化队列；集群版开发调整到 `v1.0.0` 单机封版之后重新规划。

## 7. 相关文档

- [release-v0.8.1](./redis-uya-release-v0.8.1.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [Benchmark 输出格式](./redis-uya-benchmark-format.md)
- [v0.8.1 performance benchmark](../benchmarks/v0.8.1-performance.md)
