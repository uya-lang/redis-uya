# redis-uya release v0.9.0

> 版本: v0.9.0
> 日期: 2026-05-09
> 状态: 收口完成（仍未打正式 tag）

## 1. 阶段定位

`v0.9.0` 是单机主线切换后的首个核心命令补齐版，目标是在既有 String/Hash/List/Set/ZSet、持久化、复制、事务、Pub/Sub 和历史 Cluster 基础上，补齐单机常用核心命令与最小安全基线，为后续 `v0.9.1` 的命令全集矩阵奠定稳定底座。

## 2. 已完成能力

- String 扩展命令：
  - `APPEND`、`STRLEN`、`GETDEL`
  - `INCR`、`DECR`、`INCRBY`、`DECRBY`、`INCRBYFLOAT`
  - `GETSET`、`SETNX`、`SETEX`
  - `MGET`、`MSET`、`MSETNX`
  - `GETRANGE`、`SETRANGE`
- Hash 扩展命令：
  - `HINCRBY`、`HINCRBYFLOAT`
  - `HKEYS`、`HVALS`、`HGETALL`
  - `HSCAN`
- List 扩展命令：
  - `RPUSH`、`RPOP`、`LINDEX`、`LSET`、`LLEN`
  - `LINSERT`、`LTRIM`、`LREM`
  - `LPUSHX`、`RPUSHX`、`LPOS`
- Set 扩展命令：
  - `SPOP`、`SRANDMEMBER`
  - `SINTER`、`SDIFF`、`SUNION`
  - `SINTERSTORE`、`SDIFFSTORE`、`SUNIONSTORE`
- ZSet 扩展命令：
  - `ZINCRBY`、`ZCARD`、`ZCOUNT`
  - `ZRANGEBYSCORE`、`ZREVRANGEBYSCORE`
  - `ZREMRANGEBYRANK`、`ZREMRANGEBYSCORE`
  - `ZSCAN`
- Key/Server 扩展命令：
  - `ECHO`、`TYPE`、`DBSIZE`
  - `PEXPIRE`、`PERSIST`、`PTTL`、`PEXPIREAT`
  - `RENAME`、`RENAMENX`、`LASTSAVE`
  - `FLUSHDB`、`FLUSHALL`
  - `DUMP`、`RESTORE`
  - `SELECT`、`OBJECT`
  - `MOVE`
  - `WAIT`
  - `SORT`
- Security baseline：
  - `requirepass`
  - `AUTH`
  - `SHUTDOWN`

## 3. 验证入口

- `make test`
- `make build`
- `make test-integration`
- `bash scripts/verify_definition_of_done.sh`
- `bash tests/integration/redis_cli_smoke.sh`
- `git diff --check`

## 4. 行为边界

- 当前 `SELECT` 只暴露单库 `db0` 兼容行为
- 当前 `MOVE` 固化单库下的同库错误与越界 DB 错误
- 当前 `WAIT` 在无副本 ACK 路径下返回 `0`
- 当前 `OBJECT` 支持 `ENCODING/REFCOUNT/IDLETIME/FREQ/HELP`，并保留 LFU/LRU 边界
- 当前 `SORT` 支持 list/set/zset 源、`ASC/DESC`、`ALPHA`、`LIMIT`、`BY`、重复 `GET`、`STORE`、`BY nosort` 和 hash field pattern
- 当前安全基线只支持默认用户 `default`，尚未进入 ACL / TLS / 命令级权限控制

## 5. 已知限制

- `HELLO` 当前不支持内联 `AUTH`
- `AUTH` 只支持默认用户，不支持 ACL 用户体系
- `CONFIG` 仍不支持 `SET` / `REWRITE`
- `CLIENT` 仍不支持 `KILL`、`PAUSE`、`TRACKING`
- `SHUTDOWN` 当前只覆盖最小 `SHUTDOWN` / `NOSAVE` / `SAVE` 形状
- Redis 官方命令全集、Connection/Server/Transaction 管理面补齐进入 `v0.9.1`

## 6. 发布边界

`v0.9.0` 承诺：

- 单机核心命令补齐计划全部落地
- 常用 redis-cli / redis-py / TCP smoke 路径可复现
- 既有持久化、复制、事务、Pub/Sub、内存治理和历史 Cluster 基础能力继续可用
- 安全基线 `requirepass/AUTH/SHUTDOWN` 可用

`v0.9.0` 不承诺：

- Redis 官方命令全集已经完成
- ACL / TLS / 命令权限 / key pattern 权限
- 完整 `HELLO AUTH`、`CONFIG SET/REWRITE`、`CLIENT KILL/PAUSE/TRACKING`
- Streams / Scripting / Bitmap / Geo / HyperLogLog / 高级数据能力
- 单机封版性能目标已经达成

## 7. 发布物

- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
- 测试报告：[redis-uya-test-report-v0.9.0.md](./redis-uya-test-report-v0.9.0.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- TODO：[redis-uya-todo.md](./redis-uya-todo.md)
