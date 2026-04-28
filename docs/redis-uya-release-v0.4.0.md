# redis-uya release-v0.4.0

> 版本: v0.4.0-dev
> 日期: 2026-04-28
> 状态: 收口完成（仍未打正式 tag）

## 1. 范围

`v0.4.0` 的目标是在 `v0.3.0` 持久化基础上，把主从复制推进到“可握手、可全量同步、可最小增量同步、可心跳、可一致性验证、可基准化”的阶段，而不是完整 Redis 复制实现。

当前版本包含：

- 复制角色与状态机
- `REPLICAOF`
- `PSYNC / backlog`
- replica 侧全量同步
- replica 侧定时拉取式增量同步
- 复制心跳
- 主从一致性 smoke
- 复制 benchmark

## 2. 支持命令

- `v0.3.0` 全部命令
- `REPLICAOF`
- `PSYNC`

## 3. 验证入口

基础验证：

```bash
make build
make test
make test-integration
```

补充验证：

```bash
make test-redis-cli
make benchmark-replication-v0.4.0
```

## 4. 已知限制

- 当前复制不是 Redis 风格长连接流式推送复制，而是最小定时拉取式增量同步
- 当前没有事务
- 当前没有 RESP3
- 当前没有 Pub/Sub
- 当前没有集群

## 5. 发布边界

`v0.4.0` 承诺：

- `v0.3.0` 单节点与持久化能力继续可用
- `REPLICAOF`
- `PSYNC / backlog`
- 全量同步
- 最小增量同步
- 复制心跳
- 主从一致性 smoke
- 复制 benchmark 工件

`v0.4.0` 不承诺：

- Redis 那种长连接流式复制
- Sentinel / 高可用切换
- 事务
- RESP3
- Pub/Sub
- 集群

## 6. 发布物

- 入口二进制：`build/redis-uya`
- 复制 benchmark：[../benchmarks/v0.4.0-replication.md](../benchmarks/v0.4.0-replication.md)
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
