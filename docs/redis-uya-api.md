# redis-uya API

> 版本: v0.9.0-dev
> 日期: 2026-04-30

## 1. 协议

当前默认使用 RESP2 子集，支持通过 `HELLO 3` 在连接级切换到 RESP3 最小闭环。

已支持输入类型：

- RESP2：Array、Bulk String、Simple String
- RESP3：Array、Blob String、Simple String、Number、Null、Boolean、Double、Big Number、Blob Error、Verbatim String、Map、Set、Push

已支持输出类型：

- Simple String
- Error
- Integer
- Bulk String
- Null Bulk
- Array
- RESP3 Null（连接通过 `HELLO 3` 切换后）
- `HELLO 3` Map 回复
- RESP3 Push（RESP3 Pub/Sub 确认与消息）

## 2. 命令

### `HELLO`

格式：

```text
HELLO
HELLO 2
HELLO 3
HELLO 2 SETNAME name
HELLO 3 SETNAME name
```

返回：

- `HELLO 2`：切回 RESP2，并返回 RESP2 Array 形式的服务信息
- `HELLO 3`：切到 RESP3，并返回 RESP3 Map 形式的服务信息
- 不支持的协议版本：`-NOPROTO unsupported protocol version`

说明：

- 当前 `HELLO` 支持 `SETNAME` 扩展参数，不支持 `AUTH`
- RESP3 模式下，不存在的 bulk 值返回 RESP3 Null：`_\r\n`

### `PING`

格式：

```text
PING
PING message
```

返回：

- 无参数：`+PONG`
- 有参数：Bulk String 回显

### `ECHO`

格式：

```text
ECHO message
```

返回：

- Bulk String 回显

### `GET`

格式：

```text
GET key
```

返回：

- 命中：Bulk String
- 不存在：Null Bulk

### `TYPE`

格式：

```text
TYPE key
```

返回：

- 键不存在：`+none`
- 键存在：返回 `string/hash/list/set/zset`

### `SET`

格式：

```text
SET key value
```

返回：

- 成功：`+OK`
- 额外选项当前返回 `-ERR syntax error`
- 当配置了 `maxmemory` 且当前策略无法腾出预算：`-OOM command not allowed when used memory > 'maxmemory'`

说明：

- `noeviction` 策略不主动淘汰，超预算增量写命令直接失败
- `allkeys-lru` 策略会按 top-level key 的最近访问时间淘汰最久未访问 key，再执行当前写命令
- `allkeys-lfu` 策略会按 top-level key 的访问计数淘汰最低频 key，同频次用 LRU 打破平局
- `volatile-lru` / `volatile-lfu` / `volatile-ttl` 只从带 TTL 的 key 中选候选；没有可淘汰 volatile key 时返回 OOM

### `DEL`

格式：

```text
DEL key [key ...]
```

返回：

- 删除成功的键数量，Integer

### `DBSIZE`

格式：

```text
DBSIZE
```

返回：

- 当前数据库中的非过期 key 数量，Integer

### `EXISTS`

格式：

```text
EXISTS key [key ...]
```

返回：

- 存在的键数量，Integer

### `EXPIRE`

格式：

```text
EXPIRE key seconds
```

返回：

- 设置成功或秒数为 `0` 时删除成功：`1`
- 键不存在：`0`

语义：

- 秒数为 `0` 立即删除
- AOF 中会转换为绝对时间 `PEXPIREAT`

### `PEXPIREAT`

格式：

```text
PEXPIREAT key unix_ms
```

返回：

- 设置成功：`1`
- 键不存在：`0`

说明：

- 当前主要用于 AOF 回放保持绝对过期时间

### `TTL`

格式：

```text
TTL key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回剩余秒数

### `INFO`

格式：

```text
INFO
INFO server
INFO replication
INFO memory
INFO stats
INFO keyspace
```

返回：

- 支持 `server`、`clients`、`memory`、`stats`、`replication`、`keyspace`
- 未带 section 时返回上述 section 组合段
- `memory` section 当前包含 `used_memory`、`used_memory_peak`、`total_allocated`、`total_freed`、`allocator_total_allocations`、`allocator_active_allocations`、`allocator_slab_cached_blocks`、`allocator_slab_cached_bytes`、`allocator_slab_reuse_count`、`object_pool_cached_objects`、`object_pool_cached_list_nodes`、`object_pool_reuse_count`、`object_layout_size`、`list_node_layout_size`、`maxmemory`、`maxmemory_policy`

### `CONFIG`

格式：

```text
CONFIG GET pattern
CONFIG HELP
CONFIG RESETSTAT
```

返回：

- 返回 RESP Array，按 `name`、`value` 成对展开
- 当前支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`replicaof`、`masterauth`、`maxmemory`、`maxmemory-policy`、`maxclients`、`databases`、`save`
- 支持最小 `*` 通配模式
- `CONFIG HELP` 返回当前支持的 CONFIG 子命令列表
- `CONFIG RESETSTAT` 当前返回 `+OK`，用于客户端兼容；统计重置仍是最小占位语义
- 当前不支持 `CONFIG SET` 和 `CONFIG REWRITE`

### `CLIENT`

格式：

```text
CLIENT ID
CLIENT GETNAME
CLIENT SETNAME name
CLIENT INFO
CLIENT LIST
CLIENT SETINFO LIB-NAME value
CLIENT SETINFO LIB-VER value
CLIENT HELP
```

返回：

- `CLIENT ID`：当前连接的整数 ID；真实 TCP 连接使用 fd，单元测试中的无 fd 事务返回 `0`
- `CLIENT GETNAME`：未设置时返回 Null Bulk，已设置时返回 Bulk String
- `CLIENT SETNAME`：保存连接级客户端名，成功返回 `+OK`
- `CLIENT INFO`：返回当前连接的最小客户端信息行，包含 `id/name/resp/multi/sub/lib-name/lib-ver`
- `CLIENT LIST`：当前为最小兼容实现，只返回当前连接的信息行
- `CLIENT SETINFO`：保存客户端库名/版本元数据，成功返回 `+OK`
- `CLIENT HELP`：返回当前支持的 CLIENT 子命令列表

说明：

- 客户端名和 `SETINFO` 元数据存放在连接级 `ConnectionTransaction`
- 当前不支持 `CLIENT KILL`、`PAUSE`、`TRACKING` 等全局控制命令

### `CLUSTER`

格式：

```text
CLUSTER KEYSLOT key
CLUSTER INFO
CLUSTER NODES
CLUSTER SLOTS
CLUSTER MEET ip port
CLUSTER SETSLOT slot NODE node-id
CLUSTER SETSLOT slot MIGRATING node-id
CLUSTER SETSLOT slot STABLE
CLUSTER HELP
```

返回：

- `CLUSTER KEYSLOT key`：按 Redis Cluster CRC16/hash tag 规则返回 `0..16383` 槽位
- `CLUSTER INFO`：Bulk String，包含 `cluster_enabled:1`、`cluster_state:ok`、`cluster_slots_assigned`、`cluster_known_nodes` 与 `cluster_size`
- `CLUSTER NODES`：Bulk String，返回当前最小拓扑中的本地与远端节点，包含节点地址、连接状态和已归属 slot 范围
- `CLUSTER SLOTS`：RESP Array，当前返回单个 `0..16383` 槽位范围及本地节点地址、端口和 node id
- `CLUSTER MEET ip port`：在服务端最小拓扑中注册远端 master 节点元数据
- `CLUSTER SETSLOT slot NODE node-id`：把指定 slot 的稳定 owner 设置为已知节点；若 owner 不是本节点，后续首 key 落该 slot 的命令返回 `-MOVED slot host:port`
- `CLUSTER SETSLOT slot MIGRATING node-id`：把指定 slot 标记为迁移到已知节点；后续首 key 落该 slot 的命令返回 `-ASK slot host:port`
- `CLUSTER SETSLOT slot STABLE`：清除指定 slot 的迁移态 `ASK` 标记
- `CLUSTER HELP`：返回当前支持的 CLUSTER 子命令列表

说明：

- 当前 `CLUSTER` 命令使用单节点最小拓扑，默认本节点拥有全部 16384 个槽
- 当前 `MEET/SETSLOT` 是最小控制面，不实现 Redis Cluster gossip、节点握手、故障检测和配置纪元冲突解决
- 当前 `MOVED` / `ASK` 只基于命令首个 key 判断，不实现完整多 key 同槽校验和 `ASKING` 一次性放行
- 当前不支持 `CLUSTER ADDSLOTS`、`REPLICATE`、`FAILOVER` 等拓扑变更命令

### `MULTI`

格式：

```text
MULTI
```

返回：

- 成功：`+OK`
- 嵌套调用：`-ERR MULTI calls can not be nested`

说明：

- 当前实现是连接级最小事务队列
- 进入事务态后，后续命令先返回 `+QUEUED`

### `EXEC`

格式：

```text
EXEC
```

返回：

- 成功：RESP Array，按入队顺序返回每条命令的真实回复
- 未进入 `MULTI`：`-ERR EXEC without MULTI`

说明：

- 当前按单线程顺序执行队列中的命令
- 队列中的写命令会在 `EXEC` 时真正落 AOF / replication backlog

### `DISCARD`

格式：

```text
DISCARD
```

返回：

- 成功：`+OK`
- 未进入 `MULTI`：`-ERR DISCARD without MULTI`

说明：

- 会清空当前连接已入队命令，并退出事务态

### `WATCH`

格式：

```text
WATCH key [key ...]
```

返回：

- 成功：`+OK`
- 在 `MULTI` 事务态内调用：`-ERR WATCH inside MULTI is not allowed`

说明：

- 当前按键记录观察版本
- 被观察键在 `EXEC` 前被其他写命令改动时，`EXEC` 返回 Null Array

### `UNWATCH`

格式：

```text
UNWATCH
```

返回：

- 成功：`+OK`
- 在 `MULTI` 事务态内调用：`-ERR UNWATCH inside MULTI is not allowed`

说明：

- 会清空当前连接的观察集
- `EXEC` 或 `DISCARD` 完成后也会自动清空观察集

### `SUBSCRIBE`

格式：

```text
SUBSCRIBE channel [channel ...]
```

返回：

- 每个频道返回一个订阅确认：`["subscribe", channel, count]`
- RESP3 模式下订阅确认使用 Push 形式

说明：

- 当前实现为固定容量连接级订阅注册表
- 当前不支持 pattern 订阅

### `UNSUBSCRIBE`

格式：

```text
UNSUBSCRIBE
UNSUBSCRIBE channel [channel ...]
```

返回：

- 每个频道返回一个取消订阅确认：`["unsubscribe", channel, remaining_count]`

说明：

- 显式频道取消订阅后，后续 `PUBLISH` 不再向该连接推送对应消息

### `PUBLISH`

格式：

```text
PUBLISH channel message
```

返回：

- 收到消息的订阅者数量，Integer

说明：

- 订阅者会收到 `["message", channel, message]`
- RESP3 模式下消息使用 Push 形式
- 当前不把 `PUBLISH` 追加到 AOF，也不复制到 backlog

### `SAVE`

格式：

```text
SAVE
```

返回：

- 成功：`+OK`
- 当前支持把 String/Hash/List/Set/ZSet 与绝对过期时间写入项目内 RDB 子集格式

### `BGSAVE`

格式：

```text
BGSAVE
```

返回：

- 成功：`+Background saving scheduled`
- 走真实 `fork/waitpid` 子进程后台保存
- 当前写出的 RDB 子集覆盖 String/Hash/List/Set/ZSet 与绝对过期时间

### `BGREWRITEAOF`

格式：

```text
BGREWRITEAOF
```

返回：

- 成功：`+Background AOF rewrite scheduled`
- 走真实子进程后台 rewrite
- 父进程会记录 rewrite 增量缓冲，并在子进程结束后合并到新 AOF
- rewrite 产物会把当前内存态规范化写成可回放 AOF

### `REPLICAOF`

格式：

```text
REPLICAOF host port
REPLICAOF NO ONE
```

返回：

- 成功：`+OK`
- 当前仅完成复制角色与状态机切换，不包含 `PSYNC`、全量同步、增量同步和心跳

### `PSYNC`

格式：

```text
PSYNC ? -1
PSYNC replid offset
```

返回：

- 首次同步或 backlog 不命中：`+FULLRESYNC <replid> <offset>`
- backlog 命中：`+CONTINUE <master_offset>`，后跟一个 bulk payload 作为 backlog delta
- 当前支持最小全量同步：`FULLRESYNC` 后跟一份项目内 RDB 快照
- 当前 replica 侧已支持把这份快照落库
- 当前增量同步由 replica 周期性轮询 `PSYNC replid offset` 完成，不是长连接推送流

### `QUIT`

格式：

```text
QUIT
```

返回：

- `+OK`

## 3. 错误

当前已覆盖的基础错误响应：

- `-ERR unknown command`
- `-ERR wrong number of arguments`
- `-ERR syntax error`
- `-ERR invalid request`
- `-ERR protocol error`
- `-ERR value is not an integer or out of range`

协议错误会在返回错误后关闭当前连接。
