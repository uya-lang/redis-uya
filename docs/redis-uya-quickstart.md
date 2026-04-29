# redis-uya QUICKSTART

> 版本: v0.7.0
> 日期: 2026-04-29

## 1. 前置条件

- Linux x86_64 / ARM64
- `cc`、`gcc` 或 `clang`
- Python 3
- 如需 `redis-cli` smoke：本机安装 `redis-cli`

## 2. 构建与运行

查看编译器版本：

```bash
make version
```

构建：

```bash
make build
```

启动服务：

```bash
make run
```

指定端口、最大连接数、AOF 路径和最大内存：

```bash
build/redis-uya 6380 8 build/dev.aof 1048576 allkeys-lru
```

参数顺序：

1. 监听端口
2. 最大客户端数，`0` 表示不限制
3. AOF 文件路径，可省略，默认 `build/appendonly.aof`
4. `maxmemory` 字节数，可省略，`0` 表示不限制
5. `maxmemory-policy`，可省略，当前支持 `noeviction`、`allkeys-lru`、`allkeys-lfu`、`volatile-lru`、`volatile-lfu` 与 `volatile-ttl`，默认 `noeviction`

## 3. 基础验证

单元测试：

```bash
make test
```

Python 集成 smoke：

```bash
make test-integration
```

如果本机已安装 `redis-cli`：

```bash
make test-redis-cli
```

长时运行 smoke：

```bash
REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py
```

## 4. 当前支持命令

- `PING [message]`
- `GET key`
- `SET key value`
- `DEL key [key ...]`
- `EXISTS key [key ...]`
- `EXPIRE key seconds`
- `PEXPIREAT key unix_ms`
- `TTL key`
- `INFO [section]`
- `CONFIG GET pattern`
- `CONFIG HELP`
- `CONFIG RESETSTAT`
- `CLIENT ID`
- `CLIENT GETNAME`
- `CLIENT SETNAME name`
- `CLIENT INFO`
- `CLIENT LIST`
- `CLIENT SETINFO LIB-NAME value`
- `CLIENT SETINFO LIB-VER value`
- `CLUSTER KEYSLOT key`
- `CLUSTER INFO`
- `CLUSTER NODES`
- `CLUSTER SLOTS`
- `CLUSTER MEET ip port`
- `CLUSTER SETSLOT slot NODE node-id`
- `CLUSTER SETSLOT slot MIGRATING node-id`
- `CLUSTER SETSLOT slot STABLE`
- `CLUSTER HELP`
- `HELLO 2|3 [SETNAME name]`
- `MULTI`
- `EXEC`
- `DISCARD`
- `WATCH key [key ...]`
- `UNWATCH`
- `SUBSCRIBE channel [channel ...]`
- `UNSUBSCRIBE [channel ...]`
- `PUBLISH channel message`
- `SAVE`
- `BGSAVE`
- `BGREWRITEAOF`
- `REPLICAOF host port`
- `REPLICAOF NO ONE`
- `PSYNC ? -1`
- `PSYNC replid offset`
- `QUIT`

## 5. 当前边界

- 单节点、单进程
- 集群当前提供 Cluster 槽位计算、节点元数据、最小拓扑模型、`CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`、`MOVED/ASK` 基础重定向和一致性 smoke
- RESP2 子集
- 核心数据结构子集 + String/Key/Control 子集
- AOF append + replay
- 项目内 RDB 子集 + `SAVE` / `BGSAVE`
- 复制当前已支持：`REPLICAOF`、`INFO replication`、`PSYNC / backlog`、最小 full sync、定时拉取式增量同步与心跳
- `PSYNC / backlog` 当前已支持最小握手与 backlog 命中判断
- replica 当前已支持最小全量同步：`REPLICAOF` 后可拉取 master RDB 快照
- replica 当前已支持定时拉取式增量同步与心跳
- `maxmemory` 当前已支持 noeviction、allkeys-lru、allkeys-lfu、volatile-lru、volatile-lfu、volatile-ttl 基线
- `INFO memory` 当前可观测 allocator 与 Slab 统计
- 事务、Pub/Sub、CLIENT / CONFIG 仍是最小兼容子集
- 不支持 master 主动流式推送复制、完整集群 gossip/failover、Lua、Redis 模块
