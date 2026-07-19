# redis-uya ARCHITECTURE

> 版本: v0.9.3-dev
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
- `blocked_request` / `blocked_request_len`：当前被挂起的 blocking list / zset 原始 RESP 请求；server 在成功保存请求后增加 `blocked_clients`，在唤醒、`CLIENT UNBLOCK` 或连接关闭时递减，计数为零时主循环跳过阻塞客户端全表扫描；key 就绪或超时后仍把请求前插回 `input` 并复用既有执行链恢复
- server 维护当前 `input_len > 0` 的客户端计数：网络读入只在零到非零转换时增加，完整消费和连接关闭时递减，阻塞请求回填保持同步；计数为零时主循环跳过 buffered-client 全表扫描，半包、流水线和暂停请求仍沿用原调度规则
- server loop 为单线程 `AsyncFramePool` 启用 `set_async_frame_allocator_single_thread`，Future 装箱直接读取该 pool；Uya 默认多线程 setter 仍使用 pthread TSD，快速模式不改变装箱头、释放路径或 Future ABI
- server loop 在维护批次、计算 epoll timeout 前和 epoll 返回后刷新 `event_time_ms`；同一事件批次内的命令执行时间、`CLIENT PAUSE` 判断/截止时间、accept/read 交互时间复用该缓存，cron 与维护等待仍使用显式刷新时间，避免逐命令读取系统时钟
- `RedisServer.runtime_info` 持久缓存命令执行元数据，普通请求只刷新客户端计数、复制 offset/backlog、maxmemory 排除量、后台任务、lastsave 与拓扑指针等动态字段，不再逐命令复制完整 `ServerConfig`；连接层仍按请求覆盖 RESP 版本与 `CLIENT NO-TOUCH` 状态
- runtime 同时持有 `config` 与 `pending_config`：执行器只在成功解析 `CONFIG SET` 后把候选配置写入 pending 槽，连接层在响应成功编码后原子提交到 `runtime.config`，因此输出缓冲不足不会产生无响应的配置变更，同一 pipeline 中的后续 `CONFIG GET` 仍能立即看到新值
- 稳定配置缓存必须在配置变更点同步：启动参数 `requirepass` 通过 `server_set_requirepass()` 写入，成功 `CONFIG SET` 先提交 runtime 配置再同步 `server.config`，`REPLICAOF` 主从切换随后同步角色字段；直接绕过这些入口修改配置会破坏后续命令可见性
- AOF rewrite 状态机包含打开 writer、复制缓冲和临时路径等大对象，release 代码会为该慢路径生成约 321KiB 栈帧；server loop 仅在 `aof_rewrite_requested` 或 `aof_rewrite_in_progress` 为真时进入该函数，活动 `BGREWRITEAOF` 的启动、轮询、合并与替换流程保持不变

调度规则：

- 默认关注 `EPOLLIN`
- 当写回遇到 `EAGAIN` 时，保留剩余输出并切换到 `EPOLLOUT`
- 输出全部发完后恢复到 `EPOLLIN`
- `BLPOP` / `BRPOP` / `BRPOPLPUSH` / `BLMOVE` / `BLMPOP` / `BZPOPMIN` / `BZPOPMAX` / `BZMPOP` 在 source 未就绪时不会消费后续 pipeline 命令；当前连接会先进入 blocked 状态，等待 server 主循环在 key 就绪或 timeout 后重放同一条原始请求
- `HRANDFIELD` 当前复用 hash field 字典序视图提供 deterministic random-field partial，支持 `count`、负数重复与 `WITHVALUES`，真实随机采样保留为后续完整语义
- Hash field TTL 当前在 hash 对象上保存 field 级绝对毫秒过期字典：`HGETEX` 可读取并设置/清理 field TTL，`HSETEX` 支持 `FNX/FXX` 与 `EX/PX/EXAT/PXAT/KEEPTTL`，`HEXPIRE/HPEXPIRE/HEXPIREAT/HPEXPIREAT` 按 `NX/XX/GT/LT` 写入或删除 field，`HTTL/HPTTL/HEXPIRETIME/HPEXPIRETIME/HPERSIST` 返回真实 TTL/过期时间/清理结果；普通 hash 访问路径会 lazy expire 到期 field，普通写入会清理目标 field TTL；项目内 RDB 子集保存 field TTL，AOF append、AOF rewrite 与复制 backlog 通过绝对 `HPEXPIREAT` / `PXAT` 语义重建 field TTL
- `ZMPOP` 是非阻塞 sorted-set multi-pop，执行层复用 zset pop 编码与删除路径；连接层只在成功返回数组时追加 AOF，空结果不落盘
- `ZRANGE` / `ZREVRANGE` 当前复用 rank-based zset 视图，支持正负索引、`REV` 和 `WITHSCORES`；`ZRANGE ... BYSCORE`、`ZREVRANGE ... BYSCORE`、`ZRANGEBYSCORE` / `ZREVRANGEBYSCORE` 支持整数 score 闭区间、`WITHSCORES` 和 `LIMIT`；`ZRANGE ... BYLEX` / `ZREVRANGE ... BYLEX` 复用 lex 边界扫描，支持 `REV` 和 `LIMIT`，不支持 `WITHSCORES`
- `ZRANGESTORE` 当前复用 rank-based、score-range 或 lex-range 视图写回项目内 zset，支持 `BYSCORE`、`BYLEX`、`REV` 和 `LIMIT` 并保留源 member 的整数 score
- `ZDIFF` / `ZINTER` / `ZINTERSTORE` / `ZUNION` / `ZUNIONSTORE` 这类 sorted-set 多 key 命令在执行层扫描项目内 zset `(score, member)` 排序视图；`ZINTER` / `ZINTERSTORE` / `ZUNION` / `ZUNIONSTORE` 当前支持整数 score 的默认 SUM 聚合、整数 `WEIGHTS` 和 `AGGREGATE SUM|MIN|MAX`，仍不支持 Redis 原生浮点 score / weight 口径
- `SUBSTR` 是运行时路由层对 `GETRANGE` 的兼容 alias，执行层复用同一个字符串范围读取路径
- `LCS` 当前由执行层按字符串值计算最长公共子序列，支持基础 Bulk String 返回、`LEN`、`IDX`、`MINMATCHLEN` 和 `WITHMATCHLEN` 明细输出，大输入有 4096 字节 partial guard
- `INCREX` 当前在执行层实现 partial：默认 / `BYINT` 复用字符串整数解析并通过 raw RESP 编码返回两个 Integer；`BYFLOAT` 复用 `INCRBYFLOAT` 的浮点解析、归一化和 TTL 写入路径，并返回两个 Bulk String
- `DIGEST` 当前在执行层实现短字符串 partial，使用 XXH3_64 生成 16 字节小写十六进制 Bulk String；missing 返回 Null Bulk，错类型返回 `WRONGTYPE`，超过 128 字节的 String 返回显式 partial 错误，`DELEX IFDEQ/IFDNE` 复用同一 digest 口径
- `PFADD` / `PFCOUNT` / `PFMERGE` 当前使用项目内 set 对象保存 exact HLL 成员视图；`PFSELFTEST` 是 no-op self-test 兼容面，返回 `OK`，不触发 Redis 原生 HLL 编码自检；`PFDEBUG` 是安全 profile 下的 standalone-error，不开放内部 HLL 调试输出
- `SWAPDB` 当前由执行层按单 DB 模型处理；`0 0` 是 no-op partial，任一非 `0` DB 返回越界错误，真实多 DB 数据交换保留到多 DB 模型落地后再补
- `LOLWUT` 当前由执行层返回固定 bulk 文本 partial，只校验 `VERSION` 的整数参数，不读取或修改存储状态
- `MIGRATE` 当前由执行层作为单机安全 profile 的 `standalone-error` 处理；命令可见但不会建立远端连接、不会执行跨实例迁移，也不进入 AOF/复制传播
- `WAIT` / `WAITAOF` 由执行层提供当前复制/持久化等待兼容面；`WAIT` 在无副本 ACK 收敛路径下返回 `0`，`WAITAOF` 返回 `[local, replicas]`，其中本地确认按 `numlocal` 归一到 `0/1`，副本 AOF ACK 当前固定为 `0`
- 空闲客户端不再阻塞活跃客户端
- `v0.8.0` 已新增 `io_uring` 主机能力评估报告，但生产事件循环仍绑定在 epoll 路径；后续只有在独立原型和 benchmark 证明收益后才考虑切换

## 4. 控制面最小闭环

- `CONFIG` 仍由 `command/executor.uya` 执行，当前覆盖 `GET`、`SET` 运行时子集、`REWRITE`、`HELP`、`RESETSTAT`
- `CONFIG GET` 从 `CommandRuntimeInfo` 暴露运行时配置快照，支持 `maxclients`、`databases` 等兼容字段
- `MEMORY` / `SLOWLOG` / `LATENCY` 由 `command/executor.uya` 执行；其中 `MEMORY MALLOC-STATS` 当前暴露 redis-uya allocator / object-pool 计数而非 Redis 原生 jemalloc 报告，`MEMORY PURGE` 当前是 no-op allocator purge 兼容面，`SLOWLOG` 记录 runtime-measured 命令耗时并受 `CONFIG SET slowlog-log-slower-than` 和 `slowlog-max-len` 控制但精度受毫秒级时间源限制，`LATENCY` 当前记录受 `latency-monitor-threshold` 控制的 `command` 事件进程内历史与 top-level 命令名累计直方图，`CONFIG SET latency-tracking yes|no` 可控制后续直方图采样，子命令名粒度后续再接入观测管线
- `MODULE HELP/LIST` 由 `command/executor.uya` 执行，当前只暴露空模块列表兼容面和 `COMMAND*` 可见面；`MODULE LOAD/LOADEX/UNLOAD` 同样由 `command/executor.uya` 执行为单机安全 profile 的 `standalone-error`，不加载动态库、不维护模块 API 状态，也不进入 AOF/复制传播
- Redis Array `AR*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不加载 Redis Array、不维护 Array 编码，也不进入 AOF/复制传播
- RedisJSON `JSON.*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不加载 RedisJSON、不维护 JSON 编码或 JSONPath 解析器，也不进入 AOF/复制传播
- RediSearch `FT.*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不加载 RediSearch、不维护全文索引、查询游标、同义词或 suggestion 编码，也不进入 AOF/复制传播
- Redis Vector Set `V*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不维护向量索引、向量距离计算或 Vector Set 编码，也不进入 AOF/复制传播
- RedisBloom `BF.*` / `CF.*` / `CMS.*` / `TOPK.*` / `TDIGEST.*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不加载 RedisBloom、不维护 Bloom/Cuckoo/Count-Min Sketch/Top-K/t-digest 编码，也不进入 AOF/复制传播
- RedisTimeSeries `TS.*` 模块命令当前由通用模块禁用路径作为 `standalone-error` 处理；命令可见但不加载 RedisTimeSeries、不维护 time series 编码，也不进入 AOF/复制传播
- `MONITOR` 由 `connection.uya` 维护连接级 monitor 状态、全局 fd 注册表和活动订阅计数；普通命令成功执行后仅在活动计数非零时构造兼容行并向 monitor fd 推送，连接关闭、`RESET`、事务销毁和发送失败会清理注册项并同步计数
- `DEBUG` 由 `command/executor.uya` 执行为单机安全 profile 的 `standalone-error`；命令进入路由和 `COMMAND*` 可见面，但不会开放 Redis 内部调试/破坏性子命令，也不进入 AOF/复制传播
- `HOTKEYS` 由 `command/executor.uya` 执行为 standalone 诊断兼容 partial；`HELP/GET/RESET/START/STOP` 进入路由和 `COMMAND*` 可见面，当前不维护热 key 采样状态，`GET` 返回空数组，状态变更子命令为 no-op
- `XACK/XACKDEL/XADD/XAUTOCLAIM/XCFGSET/XCLAIM/XDEL/XDELEX/XGROUP CREATE/XGROUP CREATECONSUMER/XGROUP DELCONSUMER/XGROUP DESTROY/XGROUP HELP/XGROUP SETID/XIDMPRECORD/XINFO HELP/XINFO GROUPS/XINFO CONSUMERS/XINFO STREAM/XLEN/XNACK/XPENDING/XRANGE/XREVRANGE/XREAD/XREADGROUP/XSETID/XTRIM` 由 `command/executor.uya` 执行；当前覆盖基础 stream 追加、`XADD NOMKSTREAM` 缺失 key 空返回、`XADD MAXLEN|MINID [=|~] threshold [LIMIT count]` 追加后头部裁剪、精确 ID 删除、`XCFGSET` IDMP 配置 no-op 校验面、`XIDMPRECORD` stream entry IDMP 记录 no-op 校验面、`XDELEX` per-id 删除状态兼容面、XGROUP/XINFO 帮助兼容面、`XACK` / `XACKDEL` / `XNACK` / `XAUTOCLAIM` / `XCLAIM` / `XPENDING` 无 group 错误面、`XGROUP CREATE` key/type 校验与明确未支持错误、`XGROUP CREATECONSUMER` / `XGROUP DELCONSUMER` 无 group 错误面、`XGROUP DESTROY` empty-state 返回值、`XGROUP SETID` 无 group 错误面、`XREADGROUP` 非阻塞语法校验与无 group 错误面、`XSETID` key/type/ID 校验与明确未支持错误、key-only stream 元数据、`XINFO STREAM FULL [COUNT count]` entry 明细、empty-state group 列表、无 group 时的 `XINFO CONSUMERS` 错误面、长度、范围读取、非阻塞 `XREAD` 和 `MAXLEN` / `MINID` / `LIMIT` 头部裁剪，持久化层的 RDB/AOF rewrite 会写出显式 stream id，普通 AOF append 对 `XADD *` 仍按原始请求回放并重新生成 id，当前 `XIDMPRECORD` no-op 校验面不进入普通 AOF/复制传播；`XACKDEL` / `XCFGSET` / `XIDMPRECORD` / `XNACK` / `XDELEX` 不维护 consumer group / PEL 或 IDMP 元数据，`XDELEX ACKED` 只返回未删除状态
- `EVAL/EVALSHA/EVAL_RO/EVALSHA_RO/SCRIPT DEBUG/LOAD/EXISTS/FLUSH/KILL` 由 `connection.uya` 处理，因为脚本缓存、事务重放、AOF append 和 replication backlog 需要连接层传播边界；当前仅支持单条 `return redis.call(...)` 子集，`*_RO` 在执行前解析内部命令并拒绝写标记命令和 `SORT ... STORE` 等参数驱动写路径，`SCRIPT DEBUG` 是 no-op 兼容面，`SCRIPT KILL` 只覆盖无运行脚本错误面
- `FUNCTION HELP/LIST/STATS/FLUSH/DELETE/DUMP/RESTORE/KILL` 与 `FCALL/FCALL_RO` 由 `command/executor.uya` 执行，当前只提供 Functions 控制面的帮助、空库列表、空库统计、no-op flush、空库删除错误面、空库序列化 payload、空库 payload restore、无运行脚本错误面、空库调用错误面、`COMMAND GETKEYS*` 和 `COMMAND*` 可见面，function library 存储与真实 `FCALL*` 执行后续再补
- `ACL CAT/GENPASS/HELP/LOAD/SAVE/WHOAMI` 仍由 `command/executor.uya` 执行；`ACL SETUSER/DRYRUN/LIST/GETUSER/USERS/DELUSER/LOG` 在真实连接路径由 `connection.uya` 接管默认用户的进程内命令 deny list、分类 deny list、key pattern、channel pattern、named user 元数据、named user deny list、named user key/channel pattern、`requirepass` 只读回显和拒绝日志，以便在命令执行前统一返回 `NOPERM` 并记录 `ACL LOG`。当前支持默认用户和 named user 的命令级 `+cmd/-cmd`、分类级 `+@category/-@category` 允许/拒绝、`resetcommands` 清空命令与分类拒绝、`allkeys/resetkeys/~pattern` 固定 key range 权限 partial、`allchannels/resetchannels/&pattern` Pub/Sub channel 权限 partial、`clearselectors/resetselectors` 兼容 no-op、named user 进程内创建/列出/详情/删除和 dry-run 用户存在性检查、`>password` / `<password` / `resetpass` / `nopass` 口令管理、`AUTH username password` / `HELLO ... AUTH username password` 认证、`ACL WHOAMI` 当前用户名回显、`ACL LIST` / `ACL GETUSER` 回显当前规则、`requirepass` 哈希标记、事务队列前置拒绝、脚本内部命令拒绝和当前用户命令/key/channel 权限拒绝 ring 日志基础审计字段，`client-info` 记录拒绝发生时的真实连接 id、addr 与 laddr；selector 权限、ACL 文件加载保存和 Redis 动态 key spec / movablekeys 完整解析后续再补
- `COMMAND` 由 `command/executor.uya` 执行，当前覆盖 `COMMAND`、`COUNT`、`LIST`、`INFO`、`DOCS`，运行时数据统一来自 `catalog_generated*`
- `COMMAND DOCS` 已支持命令名定向查询和无参数全量 docs 查询；连接/服务端当前使用扩大的输出缓冲完成 RESP2/RESP3 大响应发送第一批闭环
- `CLUSTER` 由 `command/executor.uya` 执行，当前通过服务端最小拓扑提供 `KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`
- `CLIENT` 在 `connection.uya` 处理，因为 `SETNAME/GETNAME/SETINFO/INFO/LIST` 依赖连接级状态
- `HELLO 2/3 SETNAME name` 与 `CLIENT SETNAME` 共享同一份连接级客户端名
- `CLIENT LIST` 通过连接级注册表返回当前活跃连接的信息行快照，连接关闭时由 `server.uya` 注销
- `CLIENT KILL` / `UNBLOCK` / `PAUSE` / `UNPAUSE` 通过 `ConnectionProcessResult` 把控制请求传回 `server.uya`，由 server 侧关闭目标连接、解除阻塞等待或更新全局 pause 状态；`PAUSE WRITE` 使用连接层 RESP 探针和命令目录写标志只阻塞写命令
- `CLIENT TRACKING` 当前维护连接级 flags/redirect/prefix 状态，并通过 `CLIENT GETREDIR` / `CLIENT TRACKINGINFO` 暴露，不包含 invalidation push 通道
- `CLIENT REPLY` 当前在连接层维护 `OFF` / `SKIP` 回复抑制状态，覆盖命令回复编码路径；不改变 Pub/Sub push 或 `MONITOR` 推送
- `CommandReply` 与 `ConnectionProcessResult` 不携带完整 `ServerConfig`；稀有的 `CONFIG SET` 通过持久 `CommandRuntimeInfo.pending_config` 传递候选状态，普通回复、零拷贝和批处理返回结构不再为配置更新承担宽字段复制成本
- `CLIENT UNBLOCK` 当前在 server 侧定位目标连接并解除阻塞 pop 等待，`TIMEOUT` 复用连接层回复编码生成空阻塞结果，`ERROR` 返回 `UNBLOCKED` 错误
- `CLIENT CACHING` 当前只维护连接级兼容标志；server-assisted client-side caching invalidation 还未实现
- `CLIENT NO-EVICT` 当前只维护连接级兼容标志；`maxmemory` 淘汰候选保护还未接入存储层
- `CLIENT NO-TOUCH` 当前只维护连接级兼容标志；存储层的 LRU/LFU touch 抑制还未接入命令执行路径
- `CommandRuntimeInfo.protocol_version` 由连接层注入，供 `COMMAND DOCS` 等控制面在 RESP2/RESP3 下切换集合和 map 形态

## 5. Pub/Sub 最小闭环

- `connection.uya` 维护固定容量订阅注册表，记录 `fd -> channel/pattern` 与连接协议版本
- `SUBSCRIBE` / `UNSUBSCRIBE` / `PSUBSCRIBE` / `PUNSUBSCRIBE` / `SSUBSCRIBE` / `SUNSUBSCRIBE` 在连接层更新注册表并返回确认消息
- `PUBLISH` 在连接层按频道和 pattern 扫描订阅表，向匹配 fd 推送 `message` / `pmessage` 事件，并向发布者返回接收者数量；`SPUBLISH` 只扫描 shard 订阅项并推送 `smessage`
- `PUBSUB HELP/CHANNELS/NUMPAT/NUMSUB` 直接复用同一份订阅注册表；`SHARDCHANNELS/SHARDNUMSUB` 统计 `SSUBSCRIBE` 注册的 shard 订阅项
- RESP2 订阅态在连接层限制为 `SUBSCRIBE` / `PSUBSCRIBE` / `SSUBSCRIBE` / `UNSUBSCRIBE` / `PUNSUBSCRIBE` / `SUNSUBSCRIBE` / `PING` / `QUIT` / `RESET`；RESP3 订阅态保持普通命令可继续执行
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
- `redis_malloc/free/realloc` 内部对 16B、32B、64B、128B、256B、512B、1024B 小对象做 Slab freelist 缓存；这些常规 class 每类最多缓存 64 个空闲块，超出后回退系统 `free`
- 1KiB 字符串值的 SDS payload 需要 1025B（内容加结尾零字节），会越过 1024B class；allocator 为 1025B 到 1032B 请求增加专用 arena class，每次向底层 allocator 申请一个包含 62 个块、总尺寸低于 64KiB 的页，再通过 freelist 分发，避免逐值进入底层 `malloc` 所有权查找
- 专用 arena 页按进程高水位保留并整页管理，单块释放只返回该 class freelist；测试专用 `reset_memory_stats_for_test()` 会在没有活跃块的前提下整页释放，生产请求路径不执行该 reset
- Slab 复用不改变上层释放契约：调用方仍只通过 `redis_free()` 释放 payload 指针，allocator header 负责记录请求大小、可用 class 大小与 class index
- `storage/object.uya` 在 Slab 之上增加 `RedisObject` 与 `ListNode` 专用对象池：释放对象时从 allocator 活跃统计扣除但保留 payload 供后续同类型对象复用，池满后再回退 `redis_free`
- `INFO memory` 暴露 `object_pool_cached_objects`、`object_pool_cached_list_nodes`、`object_pool_reuse_count`、`object_layout_size` 与 `list_node_layout_size`，用于验证对象池复用和结构体布局变化
- `RedisObject.lru_at_ms` 记录 top-level key 最近访问时间，`RedisObject.lfu_counter` 记录访问计数，`set_key_at()` 写入时初始化，`lookup_key_at()` 读取时刷新
- `command/executor.uya` 在可能增量分配的写命令执行前做预算检查；`noeviction` 直接 OOM，`allkeys-*` 与 `volatile-*` 分别调用对应 `engine_evict_*()` 后重试预算判断
- 复制 backlog 与进行中的 AOF rewrite buffer 属于复制/持久化传输缓冲，不参与 keyspace 淘汰预算；`server_runtime_info()` 将其已分配容量作为 `maxmemory_excluded_bytes` 传入执行器，对外 `maxmemory` 配置值和 `used_memory` 观测值保持不变，`INFO memory` / `MEMORY STATS` 通过 `mem_not_counted_for_evict` 暴露该口径
- `volatile-lru` / `volatile-lfu` / `volatile-ttl` 扫描主 keyspace 并用 TTL 字典过滤候选，只淘汰带过期时间的 key
- 超出预算且策略无法腾挪时返回 `OOM command not allowed when used memory > 'maxmemory'`，失败命令不落 Engine、AOF 或 replication backlog
- `tests/integration/maxmemory_pressure.py` 用真实 TCP 循环写入覆盖 noeviction、allkeys-lru、allkeys-lfu 与 volatile-ttl 的压力路径

当前淘汰策略是全量扫描基线，尚未包含 Redis 风格采样池、LFU 衰减和淘汰事件持久化优化。

## 8. AOF 语义

- 写命令追加 RESP2 原始请求；不超过 64KiB 的追加批次统一进入 AOF 写缓冲，由缓冲容量、100ms server cron、连接关闭或显式 flush 落盘，超过 64KiB 的聚合批次先 flush 既有缓冲再直接写
- `EXPIRE`、`EXPIREAT`、`PEXPIRE`、`SETEX`、`PSETEX` 会在 AOF 里规范化为绝对时间 `PEXPIREAT`
- `GETEX` 在带 TTL / `PERSIST` 选项时只把状态变更写入 AOF；相对 TTL 选项同样折算成绝对 `PEXPIREAT`
- `HGETEX` 在带 TTL / `PERSIST` 选项时只写入 field TTL 状态变更；`HSETEX` 只在条件成功时写入；hash field 相对 TTL 会折算成绝对 `HPEXPIREAT` / `PXAT`，复制 backlog 复用同一编码
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
- RDB 已覆盖当前五类对象、key 绝对过期时间和 hash field TTL，但仍不是 Redis 完整二进制兼容
- 复制当前已覆盖角色与状态机、`PSYNC / backlog`、`REPLCONF` no-op 握手 partial、replica 侧全量同步、定时拉取式增量同步与心跳；backlog 使用逻辑起点丢弃过期前缀，累计废弃前缀达到阈值后再做一次物理压缩，避免固定容量满后每条写命令复制整个 backlog；`FAILOVER` 当前为无副本/未支持 controlled failover 的 `standalone-error`；仍不是 Redis 那种长连接流式推送复制
- 集群当前已有槽位模型、节点元数据、最小拓扑模型、`CLUSTER` 最小命令接口和 `MOVED/ASK` 基础重定向；`v1.0.0` 前不继续扩展完整多节点握手、gossip、故障检测、failover 和 resharding
- 事务当前已覆盖连接级最小 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，但仍没有更完整的 Redis 事务中止传播、脚本联动和控制面扩展
- `RESET` 当前由 `connection.uya` 直接处理，重置连接级协议版本、事务/观察键、Pub/Sub、tracking 和认证状态，作为连接重连语义的最小闭环
- RESP3 当前是 `HELLO 2/3` 驱动的最小闭环，仍不是完整 RESP3 类型输出与客户端兼容矩阵
- Pub/Sub 当前是固定容量最小闭环，已支持 pattern 订阅和 RESP2 subscribed-mode 命令限制，但仍没有背压缓冲
- 控制面当前覆盖 `CLIENT` / `CONFIG` 的兼容子集，`CONFIG SET` 已支持 `port/bind/dir/dbfilename/appendfilename/requirepass/masterauth/replicaof/maxmemory/maxmemory-policy/maxclients/databases/timeout/save/latency-tracking/latency-monitor-threshold/slowlog-log-slower-than/slowlog-max-len` 运行时子集，`CONFIG REWRITE` 已支持把当前有效配置写到 `<appendfilename>.conf`，其中 `timeout` 会驱动 server cron 关闭普通空闲连接；`CLIENT KILL/PAUSE/TRACKING/GETREDIR` 已有最小闭环且 `CLIENT PAUSE WRITE` 可区分读写命令、`CLIENT TRACKING` 可回显 `BCAST PREFIX` 列表；仍没有其余 `CONFIG SET` 热更新、更完整的 rewrite 保真度，以及 tracking invalidation 和 richer client filters
- `maxmemory` 当前已覆盖 noeviction、allkeys-* 与 volatile-* 基线，并补齐 allocator 统计观测、Slab 小对象缓存和压力回归；仍没有 LFU 衰减、采样池、淘汰事件持久化优化和正式内存 benchmark
