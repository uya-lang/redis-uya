# redis-uya release v0.7.0

> 版本: v0.7.0
> 日期: 2026-04-29
> 状态: 收口完成（仍未打正式 tag）

## 1. 阶段定位

`v0.7.0` 聚焦集群基础，在 `v0.6.0` 内存与性能控制基础上补齐 Redis Cluster 槽位模型、节点元数据、最小拓扑模型、`CLUSTER` 最小控制面、`MOVED/ASK` 基础重定向，以及真实 TCP 集群一致性 smoke。

## 2. 已完成能力

- Cluster 槽位模型：按 Redis Cluster CRC16 计算 `0..16383` slot，支持 `{hash-tag}` 选择规则
- 节点元数据：40 字节 node id、host/port/bus port、master/replica 角色、flags、config epoch 与 connected 状态
- 最小集群拓扑：默认单节点拥有 16384 个 slot，可注册远端节点并把单个 slot 指派给远端 owner
- `CLUSTER` 最小命令接口：`KEYSLOT`、`INFO`、`NODES`、`SLOTS`、`HELP`、`MEET`、`SETSLOT`
- `MOVED` / `ASK` 基础重定向：命令执行前按首个 key 计算 slot，远端稳定 owner 返回 `MOVED`，迁移态 owner 返回 `ASK`
- 集群一致性 smoke：验证远端 slot 后的 `CLUSTER NODES` 槽位范围、重定向写命令不落库不进 AOF、`SETSLOT STABLE` 清除迁移态后恢复本地访问

## 3. 验证入口

- `make test`
- `make build`
- `python3 tests/integration/cluster_smoke.py`
- `python3 tests/integration/cluster_consistency.py`
- `make test-integration`
- `make test-redis-cli`
- `git diff --check`

## 4. 发布前检查

- 工作区必须干净：`git status --short`
- 默认构建、单元测试、完整 Python 集成测试和 `redis-cli` smoke 必须通过
- v0.7.0 新增集群脚本必须纳入 `make test-integration`
- 发布文档、测试报告、DoD、TODO、API、ARCHITECTURE、QUICKSTART 和根 README 必须保持一致
- 如需正式发布 tag，建议在干净工作区执行 `git tag -a v0.7.0 -m "redis-uya v0.7.0"`，本次收口文档未自动打 tag

## 5. 已知限制

- 当前没有 Redis Cluster gossip、节点握手、故障检测、failover 或 resharding
- `CLUSTER MEET` / `CLUSTER SETSLOT` 是最小测试控制面，不实现配置纪元冲突解决
- `MOVED` / `ASK` 当前只基于命令首个 key 判断，不做完整多 key 同槽校验
- 当前不实现 `ASKING` 一次性放行，`ASK` 仅作为迁移态提示返回
- `CLUSTER SLOTS` 仍返回单节点 `0..16383` 最小兼容形状，复杂拓扑展示以后续版本补齐

## 6. 发布边界

`v0.7.0` 承诺：

- `v0.6.0` 内存、淘汰、allocator 统计和 Slab 基线继续可用
- Cluster 槽位计算与 hash tag 规则可用
- 节点元数据和服务端最小拓扑可用
- `CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT` 可用
- `MOVED` / `ASK` 基础重定向可用，重定向写命令不会落本地库或进入 AOF
- 集群 smoke 和一致性 smoke 纳入 `make test-integration`

`v0.7.0` 不承诺：

- 完整 Redis Cluster 协议、gossip、failover、resharding
- `ASKING`、`MIGRATE`、`ADDSLOTS`、`DELSLOTS`、`REPLICATE`、`FAILOVER`
- 多 key 同槽完整校验和跨节点事务语义
- 正式集群性能 benchmark

## 7. 发布物

- 入口二进制：`build/redis-uya`
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
- 测试报告：[redis-uya-test-report-v0.7.0.md](./redis-uya-test-report-v0.7.0.md)
