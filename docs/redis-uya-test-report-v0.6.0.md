# redis-uya Test Report v0.6.0

> 版本: v0.6.0
> 日期: 2026-04-29
> 状态: 发布前验证通过

## 1. 目标

本报告汇总 `v0.6.0` 收口阶段已实际执行的构建、单元测试、集成 smoke、内存压力回归和发布前文档检查，作为发布前准备证据。

## 2. 已执行验证

| 类别 | 命令 | 结果 |
|------|------|------|
| 构建 | `make build` | `PASS` |
| 单元测试 | `make test` | `PASS` |
| Python 集成测试 | `make test-integration` | `PASS` |
| `redis-cli` smoke | `make test-redis-cli` | `PASS` |
| v0.6 内存压力回归 | `python3 tests/integration/maxmemory_pressure.py` | `PASS` |
| 格式检查 | `git diff --check` | `PASS` |

## 3. v0.6 集成覆盖

`make test-integration` 已纳入并覆盖：

- `tests/integration/maxmemory_noeviction.py`
- `tests/integration/maxmemory_allkeys_lru.py`
- `tests/integration/maxmemory_allkeys_lfu.py`
- `tests/integration/maxmemory_volatile_policies.py`
- `tests/integration/memory_info_stats.py`
- `tests/integration/maxmemory_pressure.py`

这些脚本覆盖 `maxmemory` noeviction、allkeys-lru、allkeys-lfu、volatile-lru、volatile-lfu、volatile-ttl、allocator/Slab 统计观测，以及真实 TCP 写入压力下的淘汰路径。

## 4. 发布前检查结果

- `docs/redis-uya-release-v0.6.0.md` 已记录能力、验证入口、限制和发布边界。
- `docs/redis-uya-definition-of-done.md` 已记录 v0.6.0 DoD 证据。
- `docs/redis-uya-todo.md` 已将 v0.6.0 标记为完成，当前进行中切到 v0.7.0。
- `docs/redis-uya-api.md`、`docs/redis-uya-architecture.md`、`docs/redis-uya-quickstart.md`、`docs/README.md` 和根 `readme.md` 已同步 v0.6.0 口径。
- 本次未自动创建 `v0.6.0` tag；如需正式发布 tag，应在干净工作区手动执行 tag 命令。

## 5. 结论

- `v0.6.0` 的代码、文档、测试和发布边界已收口。
- 当前主线满足项目对 `v0.6.0` 的内存可控、可观测、可回归验证要求。
- 剩余性能工作进入后续版本：LFU 衰减、采样池、淘汰事件优化和正式内存 benchmark。

## 6. 相关文档

- [release-v0.6.0](./redis-uya-release-v0.6.0.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [API](./redis-uya-api.md)
- [ARCHITECTURE](./redis-uya-architecture.md)
