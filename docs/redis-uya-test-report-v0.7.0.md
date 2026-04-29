# redis-uya Test Report v0.7.0

> 版本: v0.7.0
> 日期: 2026-04-29
> 状态: 发布前验证通过

## 1. 目标

本报告汇总 `v0.7.0` 收口阶段已实际执行的构建、单元测试、集成 smoke、集群一致性回归和发布前文档检查，作为发布前准备证据。

## 2. 已执行验证

| 类别 | 命令 | 结果 |
|------|------|------|
| 构建 | `make build` | `PASS` |
| 单元测试 | `make test` | `PASS` |
| 集群基础 smoke | `python3 tests/integration/cluster_smoke.py` | `PASS` |
| 集群一致性 smoke | `python3 tests/integration/cluster_consistency.py` | `PASS` |
| Python 集成测试 | `make test-integration` | `PASS` |
| `redis-cli` smoke | `make test-redis-cli` | `PASS` |
| 格式检查 | `git diff --check` | `PASS` |

## 3. v0.7 集成覆盖

`make test-integration` 已纳入并覆盖：

- `tests/integration/cluster_smoke.py`
- `tests/integration/cluster_consistency.py`

这些脚本覆盖 `CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`、hash tag 槽位、单节点拓扑输出、远端节点注册、`MOVED` / `ASK` 基础重定向、`CLUSTER NODES` 远端 slot 展示、重定向写命令不落库不进 AOF，以及 `SETSLOT STABLE` 清除迁移态后的本地访问恢复。

## 4. 发布前检查结果

- `docs/redis-uya-release-v0.7.0.md` 已记录能力、验证入口、限制和发布边界。
- `docs/redis-uya-definition-of-done.md` 已记录 v0.7.0 DoD 证据。
- `docs/redis-uya-todo.md` 已将 v0.7.0 标记为完成，当前进行中切到 v0.8.0 及以后性能路线。
- `docs/redis-uya-api.md`、`docs/redis-uya-architecture.md`、`docs/redis-uya-quickstart.md`、`docs/README.md` 和根 `readme.md` 已同步 v0.7.0 口径。
- 本次未自动创建 `v0.7.0` tag；如需正式发布 tag，应在干净工作区手动执行 tag 命令。

## 5. 结论

- `v0.7.0` 的代码、文档、测试和发布边界已收口。
- 当前主线满足项目对 `v0.7.0` 的集群基础可用、可观测、可回归验证要求。
- 剩余集群工作进入后续版本：gossip、failover、resharding、`ASKING`、多 key 同槽校验和正式集群 benchmark。

## 6. 相关文档

- [release-v0.7.0](./redis-uya-release-v0.7.0.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [API](./redis-uya-api.md)
- [ARCHITECTURE](./redis-uya-architecture.md)
