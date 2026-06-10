# redis-uya ARCHITECTURE

> 版本: v0.9.1-dev
> 日期: 2026-05-09

## 1. 总体结构

`redis-uya` 当前是单进程、单线程、带历史最小集群拓扑模型的 Redis 内核。

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
- `connection.uya`：RESP 请求处理、连接级 RESP2/RESP3 模式、CLIENT 元数据、回复编码、非阻塞读写、待发送缓冲、`GET` bulk string 零拷贝发送路径，以及 blocking list / zset pop 命令的挂起/恢复判定
- `protocol.uya`：RESP2 与 RESP3 最小解析；支持一次扫描多个顶层 RESP 帧并返回每帧消费长度，供 pipeline 和后续连接层批处理复用

### `src/command/`

- `router.uya`：命令表、命令名匹配、参数数量校验
- `executor.uya`：命令执行与控制面拼装
- `catalog.uya`：共享命令目录查询、过滤和 pattern 匹配
- `catalog_generated_base.uya`、`catalog_generated.uya`、`catalog_generated_part_*.uya`：由 `scripts/generate_command_catalog.py` 生成的官方命令目录分片

### `src/cluster/`

- `slots.uya`：Redis Cluster CRC16、hash tag 选择和 `0..16383` 槽位计算；当前作为集群后续命令与重定向的基础工具模块
- `node.uya`：最小集群节点元数据，记录 40 字节 node id、host/port/bus port、master/replica 角色、flags、config epoch 和连接状态
- `topology.uya`：最小拓扑状态，当前支持单节点全槽归属、添加节点、槽位范围分配、slot/key owner 查询和本地归属判断

### `src/storage/`

- `sds.uya`：动态字符串
- `dict.uya`：项目内专用字典，支持渐进 rehash；key 比较复用 `util/bytes.uya` 的 16 字节块比较，key hash 使用表驱动 CRC64
- `object.uya`：最小 `RedisObject`，Set/ZSet 当前都基于项目内 `Dict` 容器；Stream 第一批使用 list-backed entry 存储并记录 last-generated id；`SINTERCARD` 这类读命令直接扫描当前 set 成员视图，`SMOVE` 这类成员搬移命令在现有对象上原地修改成员集，空源集合由执行器负责删 key
- `engine.uya`：键空间、TTL、主动/惰性过期

### `src/util/`

- `bytes.uya`：基于 `@vector` 的 16 字节块 byte-slice 比较与 ASCII 大小写比较，当前用于命令路由、配置解析、SDS 和 Dict key 热路径
- `crc64.uya`：Redis CRC64；默认使用 256 项表驱动更新，保留标量更新路径作为测试对照

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
- RESP 批量解析 API 会对读缓冲中的顶层帧做完整前缀扫描，半包尾部保留在输入缓冲，错误尾包释放已解析前缀后返回协议错误
- 连接层当前会在一次读入中批量消费多个完整 RESP 顶层帧；这条路径用于 `redis-cli` stdin/pipeline、事务管线和后续多命令批处理
- `close_after_write`：`QUIT` 等命令的延迟关闭标志
- `transaction`：连接级事务队列、WATCH 集合、RESP 协议版本、CLIENT 名称/库信息、Pub/Sub 订阅计数与 blocking deadline 状态
- `blocked_request` / `blocked_request_len`：当前被挂起的 blocking list / zset 原始 RESP 请求；server 在 key 就绪或超时后把它前插回 `input` 并复用既有执行链恢复

调度规则：

- 默认关注 `EPOLLIN`
- 当写回遇到 `EAGAIN` 时，保留剩余输出并切换到 `EPOLLOUT`
- 输出全部发完后恢复到 `EPOLLIN`
- `BLPOP` / `BRPOP` / `BRPOPLPUSH` / `BLMOVE` / `BLMPOP` / `BZPOPMIN` / `BZPOPMAX` / `BZMPOP` 在 source 未就绪时不会消费后续 pipeline 命令；当前连接会先进入 blocked 状态，等待 server 主循环在 key 就绪或 timeout 后重放同一条原始请求
- `HRANDFIELD` 当前复用 hash field 字典序视图提供 deterministic random-field partial，支持 `count`、负数重复与 `WITHVALUES`，真实随机采样保留为后续完整语义
- `ZMPOP` 是非阻塞 sorted-set multi-pop，执行层复用 zset pop 编码与删除路径；连接层只在成功返回数组时追加 AOF，空结果不落盘
- `ZRANGE` / `ZREVRANGE` 当前复用 rank-based zset 视图，支持正负索引、`REV` 和 `WITHSCORES`；`ZRANGE ... BYSCORE`、`ZRANGEBYSCORE` / `ZREVRANGEBYSCORE` 支持整数 score 闭区间、`WITHSCORES` 和 `LIMIT`；`ZRANGE ... BYLEX` 复用 lex 边界扫描，支持 `REV` 和 `LIMIT`，不支持 `WITHSCORES`
- `ZRANGESTORE` 当前复用 rank-based、score-range 或 lex-range 视图写回项目内 zset，支持 `BYSCORE`、`BYLEX`、`REV` 和 `LIMIT` 并保留源 member 的整数 score
- `ZDIFF` / `ZINTER` / `ZINTERSTORE` / `ZUNION` / `ZUNIONSTORE` 这类 sorted-set 多 key 命令在执行层扫描项目内 zset `(score, member)` 排序视图；`ZINTER` / `ZINTERSTORE` / `ZUNION` / `ZUNIONSTORE` 当前支持整数 score 的默认 SUM 聚合、整数 `WEIGHTS` 和 `AGGREGATE SUM|MIN|MAX`，仍不支持 Redis 原生浮点 score / weight 口径
- `PFADD` / `PFCOUNT` / `PFMERGE` 当前使用项目内 set 对象保存 exact HLL 成员视图；`PFSELFTEST` 是 no-op self-test 兼容面，返回 `OK`，不触发 Redis 原生 HLL 编码自检；`PFDEBUG` 是安全 profile 下的 standalone-error，不开放内部 HLL 调试输出
- `SWAPDB` 当前由执行层按单 DB 模型处理；`0 0` 是 no-op partial，任一非 `0` DB 返回越界错误，真实多 DB 数据交换保留到多 DB 模型落地后再补
- `LOLWUT` 当前由执行层返回固定 bulk 文本 partial，只校验 `VERSION` 的整数参数，不读取或修改存储状态
- `WAIT` / `WAITAOF` 由执行层提供当前复制/持久化等待兼容面；`WAIT` 在无副本 ACK 收敛路径下返回 `0`，`WAITAOF` 返回 `[local, replicas]`，其中本地确认按 `numlocal` 归一到 `0/1`，副本 AOF ACK 当前固定为 `0`
- 空闲客户端不再阻塞活跃客户端
- `v0.8.0` 已新增 `io_uring` 主机能力评估报告，但生产事件循环仍绑定在 epoll 路径；后续只有在独立原型和 benchmark 证明收益后才考虑切换

## 4. 控制面最小闭环

- `CONFIG` 仍由 `command/executor.uya` 执行，当前覆盖 `GET`、`SET` 运行时子集、`REWRITE`、`HELP`、`RESETSTAT`
- `CONFIG GET` 从 `CommandRuntimeInfo` 暴露运行时配置快照，支持 `maxclients`、`databases` 等兼容字段
- `MEMORY` / `SLOWLOG` / `LATENCY` 由 `command/executor.uya` 执行；其中 `MEMORY MALLOC-STATS` 当前暴露 redis-uya allocator / object-pool 计数而非 Redis 原生 jemalloc 报告，`MEMORY PURGE` 当前是 no-op allocator purge 兼容面，`SLOWLOG` 记录 runtime-measured 命令耗时并受 `CONFIG SET slowlog-log-slower-than` 和 `slowlog-max-len` 控制但精度受毫秒级时间源限制，`LATENCY` 当前记录 `command` 事件的进程内历史与 top-level 命令名累计直方图，`CONFIG SET latency-tracking yes|no` 可控制后续直方图采样，真实 Redis 事件门限和子命令名粒度后续再接入观测管线
- `MODULE HELP/LIST` 由 `command/executor.uya` 执行，当前只暴露空模块列表兼容面和 `COMMAND*` 可见面，不支持 module 加载、卸载或模块 API
- `MONITOR` 由 `connection.uya` 维护连接级 monitor 状态和全局 fd 注册表；普通命令成功执行后向 monitor fd 推送兼容行，连接关闭和 `RESET` 会清理注册项
- `DEBUG` 由 `command/executor.uya` 执行为单机安全 profile 的 `standalone-error`；命令进入路由和 `COMMAND*` 可见面，但不会开放 Redis 内部调试/破坏性子命令，也不进入 AOF/复制传播
- `XACK/XADD/XCLAIM/XDEL/XGROUP CREATE/XGROUP DESTROY/XGROUP HELP/XGROUP SETID/XINFO HELP/XINFO GROUPS/XINFO CONSUMERS/XINFO STREAM/XLEN/XPENDING/XRANGE/XREVRANGE/XREAD/XTRIM` 由 `command/executor.uya` 执行；当前覆盖基础 stream 追加、精确 ID 删除、XGROUP/XINFO 帮助兼容面、`XACK` / `XCLAIM` / `XPENDING` 无 group 错误面、`XGROUP CREATE` key/type 校验与明确未支持错误、`XGROUP DESTROY` empty-state 返回值、`XGROUP SETID` 无 group 错误面、key-only stream 元数据、`XINFO STREAM FULL [COUNT count]` entry 明细、empty-state group 列表、无 group 时的 `XINFO CONSUMERS` 错误面、长度、范围读取、非阻塞 `XREAD` 和 `MAXLEN` 头部裁剪，持久化层的 RDB/AOF rewrite 会写出显式 stream id，普通 AOF append 对 `XADD *` 仍按原始请求回放并重新生成 id
- `EVAL/EVALSHA/EVAL_RO/EVALSHA_RO/SCRIPT DEBUG/LOAD/EXISTS/FLUSH/KILL` 由 `connection.uya` 处理，因为脚本缓存、事务重放、AOF append 和 replication backlog 需要连接层传播边界；当前仅支持单条 `return redis.call(...)` 子集，`*_RO` 在执行前解析内部命令并拒绝写标记命令，`SCRIPT DEBUG` 是 no-op 兼容面，`SCRIPT KILL` 只覆盖无运行脚本错误面
- `FUNCTION HELP/LIST/STATS/FLUSH/DELETE/DUMP/RESTORE/KILL` 与 `FCALL/FCALL_RO` 由 `command/executor.uya` 执行，当前只提供 Functions 控制面的帮助、空库列表、空库统计、no-op flush、空库删除错误面、空库序列化 payload、空库 payload restore、无运行脚本错误面、空库调用错误面、`COMMAND GETKEYS*` 和 `COMMAND*` 可见面，function library 存储与真实 `FCALL*` 执行后续再补
- `ACL CAT/DELUSER/DRYRUN/GENPASS/GETUSER/HELP/LIST/LOAD/LOG/SAVE/SETUSER/USERS/WHOAMI` 由 `command/executor.uya` 执行，当前只提供 ACL 分类、默认用户不可删除错误面、默认用户 dry-run 命令检查、口令生成、默认用户详情、ACL 控制面帮助、默认用户 config 格式、ACL 文件未配置错误面、空 ACL 日志、默认用户 no-op SETUSER 兼容面、默认用户列表、默认用户查询与 `COMMAND*` 可见面，ACL 用户存储、命令权限、key pattern 权限、真实 ACL 日志和 ACL 文件加载保存后续再补
- `COMMAND` 由 `command/executor.uya` 执行，当前覆盖 `COMMAND`、`COUNT`、`LIST`、`INFO`、`DOCS`，运行时数据统一来自 `catalog_generated*`
- `COMMAND DOCS` 已支持命令名定向查询和无参数全量 docs 查询；连接/服务端当前使用扩大的输出缓冲完成 RESP2/RESP3 大响应发送第一批闭环
- `CLUSTER` 由 `command/executor.uya` 执行，当前通过服务端最小拓扑提供 `KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`
- `CLIENT` 在 `connection.uya` 处理，因为 `SETNAME/GETNAME/SETINFO/INFO/LIST` 依赖连接级状态
- `HELLO 2/3 SETNAME name` 与 `CLIENT SETNAME` 共享同一份连接级客户端名
- `CLIENT LIST` 通过连接级注册表返回当前活跃连接的信息行快照，连接关闭时由 `server.uya` 注销
- `CLIENT KILL` / `UNBLOCK` / `PAUSE` / `UNPAUSE` 通过 `ConnectionProcessResult` 把控制请求传回 `server.uya`，由 server 侧关闭目标连接、解除阻塞等待或更新全局 pause 状态；`PAUSE WRITE` 使用连接层 RESP 探针和命令目录写标志只阻塞写命令
- `CLIENT TRACKING` 当前维护连接级 flags/redirect/prefix 状态，并通过 `CLIENT GETREDIR` / `CLIENT TRACKINGINFO` 暴露，不包含 invalidation push 通道
- `CLIENT REPLY` 当前在连接层维护 `OFF` / `SKIP` 回复抑制状态，覆盖命令回复编码路径；不改变 Pub/Sub push 或 `MONITOR` 推送
- `CLIENT UNBLOCK` 当前在 server 侧定位目标连接并解除阻塞 pop 等待，`TIMEOUT` 复用连接层回复编码生成空阻塞结果，`ERROR` 返回 `UNBLOCKED` 错误
- `CLIENT CACHING` 当前只维护连接级兼容标志；server-assisted client-side caching invalidation 还未实现
- `CLIENT NO-EVICT` 当前只维护连接级兼容标志；`maxmemory` 淘汰候选保护还未接入存储层
- `CLIENT NO-TOUCH` 当前只维护连接级兼容标志；存储层的 LRU/LFU touch 抑制还未接入命令执行路径
- `CommandRuntimeInfo.protocol_version` 由连接层注入，供 `COMMAND DOCS` 等控制面在 RESP2/RESP3 下切换集合和 map 形态

## 5. Pub/Sub 最小闭环

- `connection.uya` 维护固定容量订阅注册表，记录 `fd -> channel/pattern` 与连接协议版本
- `SUBSCRIBE` / `UNSUBSCRIBE` / `PSUBSCRIBE` / `PUNSUBSCRIBE` 在连接层更新注册表并返回确认消息
- `PUBLISH` 在连接层按频道和 pattern 扫描订阅表，向匹配 fd 推送 `message` / `pmessage` 事件，并向发布者返回接收者数量
- `PUBSUB HELP/CHANNELS/NUMPAT/NUMSUB` 直接复用同一份订阅注册表；`SHARDCHANNELS/SHARDNUMSUB` 当前返回空结果边界，不额外维护 shard 订阅状态
- RESP2 订阅态在连接层限制为 `SUBSCRIBE` / `PSUBSCRIBE` / `UNSUBSCRIBE` / `PUNSUBSCRIBE` / `PING` / `QUIT` / `RESET`；RESP3 订阅态保持普通命令可继续执行
- 客户端关闭时，`server.uya` 会清理该 fd 的订阅项

当前 Pub/Sub 已覆盖直连订阅、pattern 订阅、`PUBSUB` 管理面第一批与 RESP2/RESP3 订阅态限制，但仍不包含高水位背压队列。

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
- `storage/object.uya` 在 Slab 之上增加 `RedisObject` 与 `ListNode` 专用对象池：释放对象时从 allocator 活跃统计扣除但保留 payload 供后续同类型对象复用，池满后再回退 `redis_free`
- `INFO memory` 暴露 `object_pool_cached_objects`、`object_pool_cached_list_nodes`、`object_pool_reuse_count`、`object_layout_size` 与 `list_node_layout_size`，用于验证对象池复用和结构体布局变化
- `RedisObject.lru_at_ms` 记录 top-level key 最近访问时间，`RedisObject.lfu_counter` 记录访问计数，`set_key_at()` 写入时初始化，`lookup_key_at()` 读取时刷新
- `command/executor.uya` 在可能增量分配的写命令执行前做预算检查；`noeviction` 直接 OOM，`allkeys-*` 与 `volatile-*` 分别调用对应 `engine_evict_*()` 后重试预算判断
- `volatile-lru` / `volatile-lfu` / `volatile-ttl` 扫描主 keyspace 并用 TTL 字典过滤候选，只淘汰带过期时间的 key
- 超出预算且策略无法腾挪时返回 `OOM command not allowed when used memory > 'maxmemory'`，失败命令不落 Engine、AOF 或 replication backlog
- `tests/integration/maxmemory_pressure.py` 用真实 TCP 循环写入覆盖 noeviction、allkeys-lru、allkeys-lfu 与 volatile-ttl 的压力路径

当前淘汰策略是全量扫描基线，尚未包含 Redis 风格采样池、LFU 衰减和淘汰事件持久化优化。

## 8. AOF 语义

- 写命令直接追加 RESP2 原始请求
- `EXPIRE`、`EXPIREAT`、`PEXPIRE`、`SETEX`、`PSETEX` 会在 AOF 里规范化为绝对时间 `PEXPIREAT`
- `GETEX` 在带 TTL / `PERSIST` 选项时只把状态变更写入 AOF；相对 TTL 选项同样折算成绝对 `PEXPIREAT`
- `WAITAOF` 当前只读取本地兼容状态并返回确认数组，不触发 AOF flush/fsync，也不追加到 AOF 或 replication backlog
- 回放按流式解析逐条执行
- `BGREWRITEAOF` 使用子进程写出规范化 AOF 快照，父进程继续追加旧 AOF 并记录 rewrite 增量缓冲，子进程结束后合并并原子替换
- 截断、非法协议、非法命令、执行错误都会安全失败

## 9. 集群基础（历史能力）

本节记录 `v0.7.0` 已完成的集群基础。按照当前路线，`v1.0.0` 前不继续扩展 Redis Cluster gossip、failover、resharding 和正式集群 benchmark；这些能力在单机版封版后重新规划。

- `cluster/slots.uya` 已提供 Redis Cluster hash slot 基础模型
- `cluster_key_slot()` 使用 CRC16 计算槽位并限制在 `0..16383`
- `cluster_hash_key()` 复用 Redis hash tag 规则：首个有效 `{...}` 中的非空内容作为 hash key，空 tag 或缺失右括号时回退完整 key
- `cluster/node.uya` 已提供节点元数据模型，可构造本地 master 节点和显式远端节点元数据
- `cluster/topology.uya` 已提供最小拓扑模型，单节点默认拥有全部 16384 个槽，也可在测试和当前最小控制面中把槽位范围重新分配给远端节点
- `RedisServer` 持有最小 `ClusterTopology`；`CommandRuntimeInfo.cluster_topology` 将该拓扑传入命令执行器
- `CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT` 已接入命令路由和执行器，当前可注册远端节点并把单个 slot 置为稳定远端 owner 或迁移态 owner
- key 命令执行前会按首个 key 计算 slot；稳定远端 owner 返回 `MOVED slot host:port`，迁移态 owner 返回 `ASK slot host:port`
- 当前重定向是最小首 key 判断，不覆盖完整 Redis 多 key 同槽校验、`ASKING` 一次性放行和 gossip 协议

## 10. 当前限制

- 单线程
- `BGSAVE` / `BGREWRITEAOF` 已有最小子进程后台路径，但仍未做更细粒度的后台资源隔离与吞吐优化
- RDB 已覆盖当前五类对象和绝对过期时间，但仍不是 Redis 完整二进制兼容
- 复制当前已覆盖角色与状态机、`PSYNC / backlog`、`REPLCONF` no-op 握手 partial、replica 侧全量同步、定时拉取式增量同步与心跳；`FAILOVER` 当前为无副本/未支持 controlled failover 的 `standalone-error`；仍不是 Redis 那种长连接流式推送复制
- 集群当前已有槽位模型、节点元数据、最小拓扑模型、`CLUSTER` 最小命令接口和 `MOVED/ASK` 基础重定向；`v1.0.0` 前不继续扩展完整多节点握手、gossip、故障检测、failover 和 resharding
- 事务当前已覆盖连接级最小 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，但仍没有更完整的 Redis 事务中止传播、脚本联动和控制面扩展
- `RESET` 当前由 `connection.uya` 直接处理，重置连接级协议版本、事务/观察键、Pub/Sub、tracking 和认证状态，作为连接重连语义的最小闭环
- RESP3 当前是 `HELLO 2/3` 驱动的最小闭环，仍不是完整 RESP3 类型输出与客户端兼容矩阵
- Pub/Sub 当前是固定容量最小闭环，已支持 pattern 订阅和 RESP2 subscribed-mode 命令限制，但仍没有背压缓冲
- 控制面当前覆盖 `CLIENT` / `CONFIG` 的兼容子集，`CONFIG SET` 已支持 `port/bind/dir/dbfilename/appendfilename/requirepass/masterauth/replicaof/maxmemory/maxmemory-policy/maxclients/databases/save/latency-tracking/slowlog-log-slower-than/slowlog-max-len` 运行时子集，`CONFIG REWRITE` 已支持把当前有效配置写到 `<appendfilename>.conf`，`CLIENT KILL/PAUSE/TRACKING/GETREDIR` 已有最小闭环且 `CLIENT PAUSE WRITE` 可区分读写命令、`CLIENT TRACKING` 可回显 `BCAST PREFIX` 列表；仍没有其余 `CONFIG SET` 热更新、更完整的 rewrite 保真度，以及 tracking invalidation 和 richer client filters
- `maxmemory` 当前已覆盖 noeviction、allkeys-* 与 volatile-* 基线，并补齐 allocator 统计观测、Slab 小对象缓存和压力回归；仍没有 LFU 衰减、采样池、淘汰事件持久化优化和正式内存 benchmark
