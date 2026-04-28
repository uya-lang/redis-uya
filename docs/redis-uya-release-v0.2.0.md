# redis-uya release-v0.2.0

> 版本: v0.2.0-dev
> 日期: 2026-04-28
> 状态: 收口完成（仍未打正式 tag）

## 1. 范围

`v0.2.0` 的目标是在 `v0.1.0` 最小单节点内核上，把核心数据结构和最小控制面扩展补齐，形成“类型面完整”的单节点版本，而不是完整 Redis。

当前版本包含：

- Hash / List / Set / ZSet 最小对象实现
- `HSET/HGET`、`LPUSH/LPOP/LRANGE`、`SADD/SREM/SMEMBERS`、`ZADD/ZRANGE/ZREM`
- `SCAN`
- 更完整 `INFO` / `CONFIG GET`
- 主动过期采样循环
- 项目内最小 RDB 子集：String / Hash / List / Set / ZSet + 绝对过期时间
- `SAVE`

## 2. 支持命令

- `PING`
- `GET`
- `SET`
- `DEL`
- `EXISTS`
- `EXPIRE`
- `PEXPIREAT`
- `TTL`
- `INFO`
- `CONFIG GET`
- `SCAN`
- `SAVE`
- `HSET`
- `HGET`
- `LPUSH`
- `LPOP`
- `LRANGE`
- `SADD`
- `SREM`
- `SMEMBERS`
- `ZADD`
- `ZRANGE`
- `ZREM`
- `QUIT`

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
```

## 4. 已知限制

- 当前 RDB 仍是项目内兼容子集，不是 Redis 完整二进制兼容
- 当前没有 `BGSAVE`
- 当前没有 `BGREWRITEAOF`
- 当前没有复制与 `PSYNC`
- 当前没有事务

## 5. 发布边界

`v0.2.0` 承诺：

- 单节点、单进程
- RESP2 子集
- 五大核心数据结构最小子集
- `SCAN`
- 最小 RDB 子集和 `SAVE`

`v0.2.0` 不承诺：

- 完整 RESP3
- Redis 完整 RDB 二进制兼容
- 后台持久化
- 主从复制
- 事务
- Pub/Sub
- 集群

## 6. 发布物

- 入口二进制：`build/redis-uya`
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
