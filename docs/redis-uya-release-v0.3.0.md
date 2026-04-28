# redis-uya release-v0.3.0

> 版本: v0.3.0-dev
> 日期: 2026-04-28
> 状态: 收口完成（仍未打正式 tag）

## 1. 范围

`v0.3.0` 的目标是在 `v0.2.0` 的类型面基础上，把持久化能力推进到“可后台保存、可后台重写、可恢复、可故障验证、可基准化”的阶段，而不是完整 Redis 持久化兼容。

当前版本包含：

- 项目内 RDB 子集覆盖当前五类对象与绝对过期时间
- `SAVE`
- `BGSAVE`
- `BGREWRITEAOF`
- rewrite 增量缓冲
- 启动恢复顺序：RDB -> AOF
- RDB/AOF 损坏与截断测试
- 崩溃恢复矩阵
- 持久化 benchmark

## 2. 支持命令

- `v0.2.0` 全部命令
- `BGSAVE`
- `BGREWRITEAOF`

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
make benchmark-persistence-v0.3.0
```

## 4. 已知限制

- 当前 RDB 仍不是 Redis 完整二进制兼容
- `BGREWRITEAOF` 已有真实子进程后台路径，但还不是 Redis 那种成熟的后台重写实现
- 当前没有复制与 `PSYNC`
- 当前没有事务

## 5. 发布边界

`v0.3.0` 承诺：

- `v0.2.0` 单节点能力继续可用
- 当前五类对象的 RDB save/load 子集
- `BGSAVE`
- `BGREWRITEAOF`
- 损坏/截断/崩溃恢复验证
- 持久化 benchmark 工件

`v0.3.0` 不承诺：

- Redis 完整 RDB 二进制兼容
- Redis 完整 AOF rewrite 语义
- 主从复制
- 事务
- Pub/Sub
- 集群

## 6. 发布物

- 入口二进制：`build/redis-uya`
- 持久化 benchmark：[../benchmarks/v0.3.0-persistence.md](../benchmarks/v0.3.0-persistence.md)
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
