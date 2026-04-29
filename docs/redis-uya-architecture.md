# redis-uya ARCHITECTURE

> 版本: v0.7.0
> 日期: 2026-04-29

## 1. 总体结构

`redis-uya` 当前是单进程、单线程、带最小集群拓扑模型的 Redis 内核。

主数据路径：

```text
TCP listener
-> epoll event loop
-> per-client input buffer
-> RESP2 / RESP3 parser
-> command router
-> command executor
-> storage engine
-> reply encode
-> nonblocking socket write
```

写命令旁路：

```text
command executor
-> AOF append
```

启动恢复路径：

```text
server open
-> load minimal RDB snapshot if present
-> open AOF
-> replay AOF
-> start listener
```

## 2. 模块分工

### `src/network/`

- `listener.uya`：loopback TCP 监听、accept、listener 级 epoll fd
- `connection.uya`：RESP 请求处理、连接级 RESP2/RESP3 模式、CLIENT 元数据、回复编码、非阻塞读写、待发送缓冲、`GET` bulk string 零拷贝发送路径
- `protocol.uya`：RESP2 与 RESP3 最小解析

### `src/command/`

- `router.uya`：命令表、命令名匹配、参数数量校验
- `executor.uya`：String/Key 命令执行

### `src/cluster/`

- `slots.uya`：Redis Cluster CRC16、hash tag 选择和 `0..16383` 槽位计算；当前作为集群后续命令与重定向的基础工具模块
- `node.uya`：最小集群节点元数据，记录 40 字节 node id、host/port/bus port、master/replica 角色、flags、config epoch 和连接状态
- `topology.uya`：最小拓扑状态，当前支持单节点全槽归属、添加节点、槽位范围分配、slot/key owner 查询和本地归属判断

### `src/storage/`

- `sds.uya`：动态字符串
- `dict.uya`：项目内专用字典，支持渐进 rehash
- `object.uya`：最小 `RedisObject`
- `engine.uya`：键空间、TTL、主动/惰性过期

### `src/persistence/`

- `aof.uya`：写命令追加、流式回放、损坏安全失败
- `rdb.uya`：项目内最小 RDB 子集 save/load
- `rewrite.uya`：离线 AOF rewrite 原型

### `src/server.uya`

- 维护全局 `RedisServer`
- 驱动单线程 epoll 事件循环
- 维护客户端槽位、输入缓冲、待发送输出
- 驱动 100ms `cron`

## 3. 当前事件循环

每个客户端槽位维护：

- `input`：读缓冲
- `input_len`：当前已读字节数
- `output`：待发送响应
- `output_len` / `output_sent`：发送进度
- `GET` 命中且 bulk body 不小于 64B 时，连接层会把 RESP header 写入 `output`，再用 `writev` 直接发送对象 value body 与 CRLF；若非阻塞写发生部分发送，剩余字节会退回到 `pending` 缓冲
- `close_after_write`：`QUIT` 等命令的延迟关闭标志
- `transaction`：连接级事务队列、WATCH 集合、RESP 协议版本、CLIENT 名称/库信息与 Pub/Sub 订阅计数状态

调度规则：

- 默认关注 `EPOLLIN`
- 当写回遇到 `EAGAIN` 时，保留剩余输出并切换到 `EPOLLOUT`
- 输出全部发完后恢复到 `EPOLLIN`
- 空闲客户端不再阻塞活跃客户端

## 4. 控制面最小闭环

- `CONFIG` 仍由 `command/executor.uya` 执行，当前覆盖 `GET`、`HELP`、`RESETSTAT`
- `CONFIG GET` 从 `CommandRuntimeInfo` 暴露运行时配置快照，支持 `maxclients`、`databases` 等兼容字段
- `CLUSTER` 由 `command/executor.uya` 执行，当前通过服务端最小拓扑提供 `KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`
- `CLIENT` 在 `connection.uya` 处理，因为 `SETNAME/GETNAME/SETINFO/INFO/LIST` 依赖连接级状态
- `HELLO 2/3 SETNAME name` 与 `CLIENT SETNAME` 共享同一份连接级客户端名
- `CLIENT LIST` 当前只返回当前连接的信息行，不扫描 `RedisServer.clients`

## 5. Pub/Sub 最小闭环

- `connection.uya` 维护固定容量订阅注册表，记录 `fd -> channel` 与连接协议版本
- `SUBSCRIBE` / `UNSUBSCRIBE` 在连接层更新注册表并返回确认消息
- `PUBLISH` 在连接层按频道扫描订阅表，向匹配 fd 推送 `message` 事件，并向发布者返回订阅者数量
- 客户端关闭时，`server.uya` 会清理该 fd 的订阅项

当前 Pub/Sub 是最小闭环，不包含 pattern 订阅、完整 subscribed-mode 命令限制和高水位背压队列。

## 6. 过期策略

当前同时有两条路径：

- 惰性过期：访问键时检查 TTL
- 主动过期：100ms `cron` 内做受限扫描

## 7. 内存限制与淘汰基线

- `main.uya` 支持第四个可选启动参数 `maxmemory`，单位为字节，`0` 表示不限制
- `main.uya` 支持第五个可选启动参数 `maxmemory-policy`，当前可选 `noeviction`、`allkeys-lru`、`allkeys-lfu`、`volatile-lru`、`volatile-lfu` 与 `volatile-ttl`
- `server_runtime_info()` 将 `ServerConfig.maxmemory` / `maxmemory_policy` 暴露给命令执行器、`INFO memory` 与 `CONFIG GET`
- `memory/allocator.uya` 记录 `used_memory`、峰值、累计分配/释放和分配块计数，`INFO memory` 暴露这些字段作为内存治理观测面
- `redis_malloc/free/realloc` 内部对 16B、32B、64B、128B、256B、512B、1024B 小对象做 Slab freelist 缓存；每个 class 当前最多缓存 64 个空闲块，超出后回退系统 `free`
- Slab 复用不改变上层释放契约：调用方仍只通过 `redis_free()` 释放 payload 指针，allocator header 负责记录请求大小、可用 class 大小与 class index
- `RedisObject.lru_at_ms` 记录 top-level key 最近访问时间，`RedisObject.lfu_counter` 记录访问计数，`set_key_at()` 写入时初始化，`lookup_key_at()` 读取时刷新
- `command/executor.uya` 在可能增量分配的写命令执行前做预算检查；`noeviction` 直接 OOM，`allkeys-*` 与 `volatile-*` 分别调用对应 `engine_evict_*()` 后重试预算判断
- `volatile-lru` / `volatile-lfu` / `volatile-ttl` 扫描主 keyspace 并用 TTL 字典过滤候选，只淘汰带过期时间的 key
- 超出预算且策略无法腾挪时返回 `OOM command not allowed when used memory > 'maxmemory'`，失败命令不落 Engine、AOF 或 replication backlog
- `tests/integration/maxmemory_pressure.py` 用真实 TCP 循环写入覆盖 noeviction、allkeys-lru、allkeys-lfu 与 volatile-ttl 的压力路径

当前淘汰策略是全量扫描基线，尚未包含 Redis 风格采样池、LFU 衰减和淘汰事件持久化优化。

## 8. AOF 语义

- 写命令直接追加 RESP2 原始请求
- `EXPIRE` 追加时重写成绝对时间 `PEXPIREAT`
- 回放按流式解析逐条执行
- `BGREWRITEAOF` 使用子进程写出规范化 AOF 快照，父进程继续追加旧 AOF 并记录 rewrite 增量缓冲，子进程结束后合并并原子替换
- 截断、非法协议、非法命令、执行错误都会安全失败

## 9. 集群基础

- `cluster/slots.uya` 已提供 Redis Cluster hash slot 基础模型
- `cluster_key_slot()` 使用 CRC16 计算槽位并限制在 `0..16383`
- `cluster_hash_key()` 复用 Redis hash tag 规则：首个有效 `{...}` 中的非空内容作为 hash key，空 tag 或缺失右括号时回退完整 key
- `cluster/node.uya` 已提供节点元数据模型，可构造本地 master 节点和显式远端节点元数据
- `cluster/topology.uya` 已提供最小拓扑模型，单节点默认拥有全部 16384 个槽，也可在测试和后续控制面中把槽位范围重新分配给远端节点
- `RedisServer` 持有最小 `ClusterTopology`；`CommandRuntimeInfo.cluster_topology` 将该拓扑传入命令执行器
- `CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT` 已接入命令路由和执行器，当前可注册远端节点并把单个 slot 置为稳定远端 owner 或迁移态 owner
- key 命令执行前会按首个 key 计算 slot；稳定远端 owner 返回 `MOVED slot host:port`，迁移态 owner 返回 `ASK slot host:port`
- 当前重定向是最小首 key 判断，不覆盖完整 Redis 多 key 同槽校验、`ASKING` 一次性放行和 gossip 协议

## 10. 当前限制

- 单线程
- `BGSAVE` / `BGREWRITEAOF` 已有最小子进程后台路径，但仍未做更细粒度的后台资源隔离与吞吐优化
- RDB 已覆盖当前五类对象和绝对过期时间，但仍不是 Redis 完整二进制兼容
- 复制当前已覆盖角色与状态机、`PSYNC / backlog`、replica 侧全量同步、定时拉取式增量同步与心跳；仍不是 Redis 那种长连接流式推送复制
- 集群当前已有槽位模型、节点元数据、最小拓扑模型、`CLUSTER` 最小命令接口和 `MOVED/ASK` 基础重定向，尚未提供完整多节点握手、gossip、故障检测和 failover
- 事务当前已覆盖连接级最小 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，但仍没有更完整的 Redis 事务中止传播、脚本联动和控制面扩展
- RESP3 当前是 `HELLO 2/3` 驱动的最小闭环，仍不是完整 RESP3 类型输出与客户端兼容矩阵
- Pub/Sub 当前是固定容量最小闭环，仍没有 pattern 订阅、完整 subscribed-mode 命令限制和背压缓冲
- 控制面当前覆盖 `CLIENT` / `CONFIG` 的兼容子集，仍没有 `CONFIG SET/REWRITE`、全局 `CLIENT LIST`、`CLIENT KILL/PAUSE/TRACKING`
- `maxmemory` 当前已覆盖 noeviction、allkeys-* 与 volatile-* 基线，并补齐 allocator 统计观测、Slab 小对象缓存和压力回归；仍没有 LFU 衰减、采样池、淘汰事件持久化优化和正式内存 benchmark
