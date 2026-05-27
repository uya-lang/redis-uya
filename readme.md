# redis-uya

> 使用 Uya 从零实现 Redis 兼容内存数据库
> 零 GC 路线 · 显式错误处理 · 可测试演进 · 长期性能目标超过 Redis

> 版本: v0.9.1-dev
> 日期: 2026-05-19

## 简介

`redis-uya` 是一个使用 **Uya 编程语言** 从零实现的内存数据库系统。项目长期目标是兼容 Redis Open Source；当前主线先收敛单机版，优先补齐 Redis Open Source 单机核心命令、持久化、复制、脚本、安全、运维与性能工程，单机版功能和性能达标后再考虑 `v1.0.0` 封版以及后续集群规划。

`v1.0.0` 的版本目标不是提前兑现“全面超过 Redis”，而是先把单机核心做真、做稳、做快：功能边界真实、兼容语义真实、测试和 benchmark 结果真实，并在这一前提下持续缩小与 Redis 的性能差距。长期性能目标仍然是超过 Redis，但那是 `v1.0.0` 之后继续迭代的方向，不是拿来包装当前完成度的口号。

历史上，项目已经完成 `v0.9.0` 单机核心命令补齐，并在 `v0.9.1` 主线落地共享命令目录、`COMMAND*` 第一批和若干连接/管理面扩展。当前 `HEAD` 已恢复 `make test`、`make test-integration`、`make benchmark-v0.8.1` 与 `bash scripts/verify_definition_of_done.sh` 的绿态；`COMMAND*` 真值与版本号口径也已收口。当前第一优先级已转回命令完成度统计分层和剩余单机核心缺口，而不是继续修 benchmark 红灯。

## 核心目标

- **协议兼容**：从 RESP2 子集起步，逐步扩展到 RESP3 与更完整的 Redis 命令语义。
- **命令全集**：以 Redis 官方 Commands Reference 为总目录基线；单机版 `v1.0.0` 先收敛 Redis Open Source 单机核心命令，模式相关命令至少提供 standalone 兼容行为，模块命令继续追踪但不与当前封版门槛混算。
- **数据结构完整**：按版本推进 String、Hash、List、Set、ZSet、Bitmap、Bitfield、HyperLogLog、Geo、Stream、JSON、Search、Time Series、概率结构和 Vector。
- **可靠持久化**：首版优先 AOF append/replay，后续补齐 RDB、AOF rewrite、BGSAVE/BGREWRITEAOF。
- **高性能路线**：建立 Redis 同机对照基线，再优化解析、字典、内存分配、零拷贝、批处理和事件循环。
- **单机先行**：`v0.9.0` 起只收敛单机版，`v1.0.0` 单机封版后才重新规划集群版。
- **小步版本**：后续最小迭代按最后一位递增，例如 `v0.9.0`、`v0.9.1`、`v0.9.2`；`v0.9.4` 先做性能与稳定性收敛，`v0.9.5` 起进入首个封版候选阶段，未达标时继续 `v0.9.6`。
- **工程可控**：所有能力必须有测试、错误路径、释放路径、恢复路径或 benchmark 证据。

## 当前状态

2026-05-16 审计后的当前状态，经 2026-05-19 当前复核后应理解为：

- `make test`、`make test-integration`、`make benchmark-v0.8.1` 与 `bash scripts/verify_definition_of_done.sh` 当前已恢复为通过状态。
- `maxmemory` 集成测试口径已按当前实现重新校准；`benchmark-v0.8.1` guard 现已改为“绝对基线 + 同机 Redis 归一化兜底”并恢复转绿。
- `COMMAND*` 真值、版本号一致性与命令完成度统计分层已收口；`v0.9.1` 审计整改主线现已完成，下一阶段主线转入 `v0.9.2` 的 Redis Open Source 单机核心缺口补齐。
- `v1.0.0` 的封版门槛先收敛 Redis Open Source 单机核心，不再把模块命令数量当作当前完成度包装。

下方列表主要记录历史里程碑沉淀与当前代码库已落地模块，不等价于“当前 `HEAD` 已重新全量复核通过”。

历史沉淀与已落地模块：

- 工程骨架、内置 Uya 工具链、`Makefile`
- 基础测试框架与 `make test`
- 工具模块：`log`、`time`、`endian`、`crc64`
- 内存分配器封装
- 配置解析：文本解析与文件读取
- SDS 基础能力：创建、追加、格式化追加、比较、扩缩容、复制、范围切片、1MB 压测
- 项目内专用 `Dict`：插入、查找、覆盖、删除、扩容、渐进 rehash、10k 键回归
- `RedisObject` 最小 String 包装：RAW/INT 编码、类型名、释放
- `Engine` 最小实现：键读写删除、覆盖释放、TTL 字段、惰性过期
- RESP2 最小子集解析：Simple String、Error、Integer、Bulk String、Array、Incomplete、非法输入
- RESP3 最小协议闭环：`HELLO 2/3` 连接级协议切换，支持 Null、Boolean、Map 等常用 RESP3 类型解析和 RESP3 Null 回复
- 命令路由：最小命令表、大小写匹配、参数数量校验、未知命令错误、RESP Array 转命令
- String/Key/Control 命令执行：`PING`、`GET`、`SET`、`DEL`、`EXISTS`、`KEYS`、`RANDOMKEY`、`EXPIRE`、`EXPIREAT`、`EXPIRETIME`、`PEXPIRE`、`PEXPIREAT`、`PEXPIRETIME`、`PERSIST`、`TTL`、`PTTL`、`TIME`、`ROLE`、`INFO` 多 section、`CONFIG GET/HELP/RESETSTAT`、`CLIENT` 兼容子集、`AUTH`、`SAVE`
- String TTL 扩展：`GETEX`、`SETEX`、`PSETEX`
- Hash 最小对象：基于项目内 `Dict` 的最小 hash value 容器
- Hash 命令子集：`HSET`、`HGET`、`HDEL`、`HEXISTS`、`HLEN`、`HMGET`、`HSETNX`、`HSTRLEN`
- List 最小对象：基于双向链表的最小 list value 容器
- List 命令子集：`LPUSH`、`LPOP`、`LRANGE`
- Blocking list/zset 第一批：`BLPOP`、`BRPOP`、`BRPOPLPUSH`、`BZPOPMIN`、`BZPOPMAX`、`BZMPOP` 已支持立即命中、server-side block/unblock、超时返回与 AOF replay
- Set 最小对象：基于项目内 `Dict` 的最小 set value 容器
- Set 命令子集：`SADD`、`SCARD`、`SISMEMBER`、`SMISMEMBER`、`SMEMBERS`、`SREM`、`SMOVE`、`SSCAN`
- ZSet 最小对象：基于项目内 `Dict` 的最小 zset value 容器，支持按 score 排序范围读取
- ZSet 命令子集：`ZADD`、`ZRANGE`、`ZREM`
- Key 迭代子集：`SCAN`，支持 cursor 返回与 `COUNT` 最小参数
- TCP 服务闭环：loopback 监听、连接读写缓冲、请求解析执行写回、`QUIT`、`maxclients`、Python socket smoke
- 服务运行循环：单线程 epoll 多连接、100ms cron 主动过期采样循环、空闲连接不阻塞其他客户端
- RDB 当前类型闭环：项目内 RDB 子集已覆盖 String/Hash/List/Set/ZSet + 绝对过期时间 save/load、`SAVE`
- `BGSAVE`：真实 `fork/waitpid` 子进程落盘，支持去掉 AOF 后仅靠 RDB 恢复
- AOF 最小闭环：写命令追加、启动回放、截断损坏安全失败、SET/DEL 重启恢复 smoke
- 启动恢复顺序：先加载最小 RDB，再回放 AOF
- AOF TTL 语义：`EXPIRE`、`EXPIREAT`、`PEXPIRE`、`SETEX`、`PSETEX` 追加时会规范化为绝对 `PEXPIREAT`；`GETEX` 在带 TTL/PERSIST 选项时只落对应状态变更，回放保持绝对过期时间
- `BGREWRITEAOF`：真实子进程后台 rewrite + 父进程增量缓冲合并，可把当前内存态规范化重写为可回放 AOF
- 复制角色与状态机：支持 master/slave 角色切换、`REPLICAOF` 控制入口、`INFO replication` 与复制配置可观测
- `PSYNC / backlog`：master 维护复制积压缓冲区，支持 `FULLRESYNC` / `CONTINUE` 最小握手判断
- 全量同步：replica 可通过 `REPLICAOF -> PSYNC ? -1` 拉取 master 当前 RDB 快照并落库
- 增量同步：replica 在 connected 状态下周期性 `PSYNC replid offset` 拉取 backlog delta 并回放
- 复制心跳：replica 周期性 `PING` master，链路失败时回到 `configured` 并等待重同步
- 主从一致性：当前五类对象已有 full sync + incremental smoke
- 事务控制最小子集：连接级 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，支持 `QUEUED`、`EXEC` 数组回复、观察键变更后的 Null Array 中止和 `DISCARD` 丢弃
- Pub/Sub 第一批子集：`SUBSCRIBE/UNSUBSCRIBE` 直连订阅、`PSUBSCRIBE/PUNSUBSCRIBE` pattern 订阅、`PUBLISH` 跨连接推送 `message/pmessage` 并返回匹配接收者数量，连接关闭后会清理订阅项
- Pub/Sub 管理面第一批：`PUBSUB HELP/CHANNELS/NUMPAT/NUMSUB` 可用；`PUBSUB SHARDCHANNELS/SHARDNUMSUB` 在未实现 `SSUBSCRIBE/SPUBLISH` 前返回空数组或 `0` 计数，固定当前 shard 边界
- Pub/Sub 订阅态兼容边界：RESP2 订阅态下只允许 `SUBSCRIBE/PSUBSCRIBE/UNSUBSCRIBE/PUNSUBSCRIBE/PING/QUIT/RESET`，RESP3 订阅态可继续执行非 Pub/Sub 命令
- 控制面兼容子集：`CLIENT ID/GETNAME/GETREDIR/SETNAME/INFO/LIST/SETINFO/HELP/KILL/PAUSE/UNPAUSE/TRACKING/TRACKINGINFO`、`HELLO SETNAME`、`RESET`、`CONFIG GET/HELP/RESETSTAT/SET/REWRITE`
- 安全基线：`requirepass`、`AUTH`、`SHUTDOWN`
- `v0.9.1` 命令全集矩阵第一批：基于 Redis 8.6 官方命令页生成 `531` 个官方命令名目录，落地 `docs/redis-uya-command-matrix.md` 与 `src/command/catalog_generated*`
- `COMMAND` 控制面第一批已收口：`COMMAND`、`COMMAND COUNT`、`COMMAND LIST`、`COMMAND INFO`、`COMMAND DOCS`、`COMMAND GETKEYS`、`COMMAND GETKEYSANDFLAGS` 共用同一份运行时目录；`COMMAND DOCS` 无参数时已支持全量 docs 输出，并打通 RESP2/RESP3 大响应发送第一批闭环，`GETKEYS*` 当前也已覆盖 `BZMPOP` 的 movablekeys 提取
- v0.5 兼容性回归：覆盖 RESP3 Null、WATCH 中止、事务内控制命令错误、RESP3 Pub/Sub Push、CLIENT/CONFIG 组合路径
- `maxmemory` noeviction 基线：启动参数可设置最大内存，超预算增量写命令返回 OOM 且不落库
- `allkeys-lru` 淘汰基线：对象记录最近访问时间，超预算写入可淘汰最久未访问 key 后继续执行
- `allkeys-lfu` 淘汰基线：对象记录访问计数，超预算写入可淘汰访问次数最低 key 后继续执行
- `volatile-*` 淘汰基线：`volatile-lru`、`volatile-lfu`、`volatile-ttl` 只从带 TTL 的 key 中选择候选
- `INFO memory` allocator 统计：当前使用、峰值、累计分配/释放、活跃块数、Slab 统计、对象池计数和对象布局大小可观测
- Slab 小对象缓存基线：16B 到 1KB 分级 freelist
- 内存压力与淘汰回归：覆盖 noeviction OOM、allkeys-lru、allkeys-lfu、volatile-ttl
- Cluster 基础：槽位计算、节点元数据、单节点最小拓扑、`CLUSTER KEYSLOT/INFO/NODES/SLOTS/HELP/MEET/SETSLOT`、`MOVED/ASK` 基础重定向和一致性 smoke
- Python 客户端风格集成：覆盖更多命令与控制面交互
- v0.8.0 核心 benchmark 矩阵与回归阈值：`make benchmark-v0.8.0` 覆盖 `PING`、16B/1KiB `SET`、16B/1KiB `GET`，记录同机 Redis 对照、p50/p95/p99、吞吐、RSS 和吞吐/p99 guard
- v0.8.0 `GET` bulk string 零拷贝响应路径：64B 及以上命中值通过 `writev` 直接发送对象 value body，小 body 保持原编码路径以避免 syscall 开销退化
- v0.8.0 RESP2/RESP3 顶层批量解析：一次扫描可返回多个完整顶层帧、每帧消费长度和完整前缀总消费长度，覆盖半包尾部与错误释放路径
- v0.8.0 SIMD 字符串和 CRC64：新增 `@vector` 16 字节块 byte-slice 比较工具并接入命令路由、配置解析、SDS 和 Dict key 热路径；CRC64 更新改为表驱动并保留标量对照测试
- v0.8.0 `io_uring` 评估：`make evaluate-io-uring-v0.8.0` 生成主机能力报告，记录 syscall、sysctl、liburing 探测和 `production_binding=no` 边界
- v0.8.0 专用对象池与布局观测：`RedisObject` / `ListNode` 释放后进入专用 freelist，复用时绕过通用 Slab；`INFO memory` 暴露缓存、复用计数和布局大小
- v0.8.0 Redis 对照差距报告：`make report-v0.8.0-gaps` 生成吞吐、p99、RSS 比例矩阵与 P0/P1/P2 后续优化队列
- v0.8.1 写路径性能修复：WATCH 版本表仅在存在 WATCH 客户端时维护，`SET` 覆盖写使用 Dict 单次探测返回旧值，AOF 512B 以下命令缓冲写、较大命令直写；对应 benchmark guard 当前已恢复通过

下一阶段：

- `v0.9.1`：审计整改与真实性修复已完成，当前已修复 `maxmemory` 集成测试口径、收回当前 `CLIENT/CONFIG` 子命令矩阵真值、统一运行时版本串，并恢复 benchmark / DoD 校验转绿。
- `v0.9.2`：继续补 Redis Open Source 单机核心缺口，当前优先脚本第一批；`PFADD/PFCOUNT/PFMERGE` 已以 exact set-backed partial 形态落地，`GEOADD/GEODIST/GEOSEARCH` 已以 exact zset-backed partial 形态落地，`EVAL/EVALSHA/SCRIPT LOAD|EXISTS|FLUSH` 已以 single-call script subset partial 形态落地，`MEMORY HELP/STATS/USAGE/DOCTOR` 已以 runtime-approx partial 形态落地，`SLOWLOG HELP/LEN/GET/RESET` 已以 in-process ring partial 形态落地，`LATENCY HELP/LATEST/HISTORY/RESET/DOCTOR/HISTOGRAM/GRAPH` 已以 empty-event compatibility partial 形态落地。
- `v0.9.3`：收口 Streams、Functions/Script、ACL 与运维诊断第一批，再推进持久化/复制边界深化。

当前阶段尚未生产可用。

## 快速开始

查看编译器版本：

```bash
make version
```

构建：

```bash
make build
```

运行：

```bash
make run
```

测试：

```bash
make test
```

TCP 集成 smoke：

```bash
make test-integration
```

`make test-integration` 当前覆盖基础 TCP smoke、blocking list/zset、空闲连接不阻塞其他客户端、持久化/复制/事务/Pub/Sub/控制面兼容路径，`maxmemory` / 淘汰策略 / 内存统计 / 压力回归，以及历史集群基础 smoke。当前 `HEAD` 该目标已恢复为全绿；当前主线已转入 `v0.9.2` 的 bitmap/bitfield、HLL/GEO 与脚本第一批缺口补齐，详见 `docs/redis-uya-todo.md`。

v0.8.0 核心性能基线：

```bash
make benchmark-v0.8.0
```

v0.8.1 写路径性能回归验证：

```bash
make benchmark-v0.8.1
```

当前 `HEAD` 的 `make benchmark-v0.8.1` 已恢复通过：throughput guard 现在同时参考绝对历史基线与同机 Redis 归一化比例，避免把主机波动误判成产品回退。`benchmarks/v0.8.1-performance.md` 仍需结合生成日期解读，因为它同时承担历史回归证据和当前机器输出两种角色。

v0.8.0 Redis 对照差距报告：

```bash
make report-v0.8.0-gaps
```

v0.8.0 `io_uring` 主机能力评估：

```bash
make evaluate-io-uring-v0.8.0
```

如本机已安装 `redis-cli`，可额外运行：

```bash
make test-redis-cli
```

如需长时运行 smoke：

```bash
REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py
```

如需生成当前机器的 `v0.1.0` benchmark 报告：

```bash
make benchmark-v0.1.0
```

如需生成当前机器的持久化 benchmark 报告：

```bash
make benchmark-persistence-v0.3.0
```

如需生成当前机器的复制 benchmark 报告：

```bash
make benchmark-replication-v0.4.0
```

清理构建产物：

```bash
make clean
```

默认使用工程内置编译器：

```bash
./uya/bin/uya build src/main.uya -o ../build/redis-uya --c99 -e
```

如需临时指定其他 Uya 编译器：

```bash
make build UYA=/path/to/uya
```

开发调试时可指定监听端口和最大连接数：

```bash
build/redis-uya 6380 1
```

## 工具链

- Uya 编译器：工程内置 `./uya/bin/uya`
- 当前同步源：`../uya` 当前发布线（按 `v0.9.7` 工具链能力使用）
- C 宿主工具链：`cc`、`gcc` 或 `clang`
- 目标平台：Linux x86_64 / ARM64

说明：

- `../uya` 已打 `v0.9.7` tag，标签提交为 `f9db011b`
- 当前同步时参考的 `../uya` 工作线 HEAD 为 `28100f29`，即位于 `v0.9.7` tag 之后 4 个提交
- 当前同步完成后，`./uya/bin/uya --version` 已返回 `v0.9.7`，源码版本分支与内置二进制版本串已经对齐
- 因此，`redis-uya` 当前记录的 `v0.9.7` 工具链基线同时体现在上游 `../uya` 的 tag / 代码线、同步后的标准库能力和当前内置编译器版本输出上
- `uya/` 内置副本需要按 `../uya` 当前发布线持续同步；后续开发默认可以使用当前内置工具链已经支持的 `v0.9.7` 能力

## `v0.1.0` 发布边界

`v0.1.0` 只承诺交付最小生产内核：

- 单节点、单进程服务模型
- RESP2 子集
- String 与 Key 命令子集
- 项目内专用 `Dict`
- AOF append + replay
- `redis-cli` smoke 与 Python 子集集成测试
- 同机 Redis benchmark 基线

`v0.1.0` 不包含：

- 完整 RESP3
- 完整 RDB 兼容
- 复制与 `PSYNC`
- 主从复制
- 基础集群
- Lua 脚本
- Redis 模块系统

说明：这段只描述 `v0.1.0` 当时的发布承诺，不等于当前仓库主线能力。

## 当前主线能力边界

当前仓库主线已完成 `v0.8.1`，已经包含：

- 单节点、单进程服务模型
- RESP2 子集
- RESP3 最小闭环：`HELLO 2/3`、常用 RESP3 输入类型解析、RESP3 Null 回复
- String / Hash / List / Set / ZSet / `SCAN`
- String 第一批增强：`APPEND`、`STRLEN`、`GETDEL`
- String 第二批计数：`INCR`、`DECR`、`INCRBY`、`DECRBY`
- String 第三批原子写入：`GETSET`、`SETNX`、`SETEX`
- String 第四批多 key：`MGET`、`MSET`、`MSETNX`
- String 第五批范围读写：`GETRANGE`、`SETRANGE`
- String 第六批浮点计数：`INCRBYFLOAT`
- Bitmap / Bitfield 第一批：`GETBIT`、`SETBIT`、`BITCOUNT`、`BITPOS`、`BITOP`、`BITFIELD`、`BITFIELD_RO`
- HyperLogLog 第一批 partial：`PFADD`、`PFCOUNT`、`PFMERGE` 当前可用，但内部暂以 exact set-backed cardinality 近似 Redis 语义，尚未落地 Redis 原生 dense/sparse HLL 字符串编码
- Geo 第一批 partial：`GEOADD`、`GEODIST`、`GEOSEARCH` 当前可用，但内部暂以 exact zset-backed packed coordinate score 实现，`WITHHASH` 返回当前 packed score，而不是 Redis 原生 geohash 整数
- Scripting 第一批 partial：`EVAL`、`EVALSHA`、`SCRIPT LOAD/EXISTS/FLUSH` 当前可用，但只支持单条 `return redis.call(...)` 脚本子集；AOF/复制传播的是脚本内部实际执行的命令效果，而不是原始 `EVAL*`
- Memory 第一批 partial：`MEMORY HELP`、`MEMORY STATS`、`MEMORY USAGE`、`MEMORY DOCTOR` 当前可用；`USAGE` 返回基于 redis-uya 对象布局、dict/list 节点和 SDS 容量的近似运行时占用，不是 Redis 原生 jemalloc 口径
- Slowlog 第一批 partial：`SLOWLOG HELP`、`SLOWLOG LEN`、`SLOWLOG GET`、`SLOWLOG RESET` 当前可用；slowlog 当前是 redis-uya 进程内固定容量 ring，记录执行命令与占位 `duration_us=0`，不含 Redis 原生阈值配置、真实微秒耗时和客户端端点/名称真值
- Latency 第一批 partial：`LATENCY HELP`、`LATENCY LATEST`、`LATENCY HISTORY`、`LATENCY RESET`、`LATENCY DOCTOR`、`LATENCY HISTOGRAM`、`LATENCY GRAPH` 当前可用；当前暴露空事件兼容面，尚未采样真实延迟事件和命令直方图
- Hash 第一批数值：`HINCRBY`、`HINCRBYFLOAT`
- Hash 第二批视图：`HKEYS`、`HVALS`、`HGETALL`
- Hash 第三批扫描：`HSCAN`
- List 第一批基础：`RPUSH`、`RPOP`、`LINDEX`、`LSET`、`LLEN`
- List 第二批变异：`LINSERT`、`LTRIM`、`LREM`
- List 第三批条件：`LPUSHX`、`RPUSHX`、`LPOS`
- Set 第一批随机取值：`SPOP`、`SRANDMEMBER`
- Set 第二批集合运算：`SINTER`、`SDIFF`、`SUNION`
- Set 第三批集合写回：`SINTERSTORE`、`SDIFFSTORE`、`SUNIONSTORE`
- Set 第四批读路径：`SCARD`、`SISMEMBER`、`SMISMEMBER`、`SSCAN`
- ZSet 第一批数值与计数：`ZINCRBY`、`ZCARD`、`ZCOUNT`
- ZSet 第二批范围读取：`ZRANGEBYSCORE`、`ZREVRANGEBYSCORE`
- ZSet 第三批范围删除与扫描：`ZREMRANGEBYRANK`、`ZREMRANGEBYSCORE`、`ZSCAN`
- Key/Server 第三批：`RENAME`、`RENAMENX`、`LASTSAVE`
- Key/Server 第四批：`FLUSHDB`、`FLUSHALL`
- Key/Server 第五批：`PEXPIREAT`
- Key/Server 第六批：`DUMP`、`RESTORE`
- Key/Server 第七批：`SELECT`、`OBJECT`
- Key/Server 第八批：`MOVE`
- Key/Server 第九批：`WAIT`
- Key/Server 第十批通用 key 管理：`TOUCH`、`UNLINK`
- Key/Server 第十一批模式读取：`KEYS`
- Key/Server 第十批：`SORT`
- Key/Server 第一批：`ECHO`、`TYPE`、`DBSIZE`
- Key/Server 第二批：`PEXPIRE`、`PERSIST`、`PTTL`
- AOF append/replay、RDB 子集、`SAVE`、`BGSAVE`、`BGREWRITEAOF`
- 主从复制最小闭环：`REPLICAOF`、`PSYNC / backlog`、全量同步、定时拉取式增量同步、复制心跳
- 事务最小子集：`MULTI/EXEC/DISCARD/WATCH/UNWATCH`
- Pub/Sub 第一批子集：`PUBLISH/SUBSCRIBE/UNSUBSCRIBE/PSUBSCRIBE/PUNSUBSCRIBE`
- `CLIENT` / `CONFIG` 控制面兼容子集
- v0.5 协议与控制面兼容性回归
- `maxmemory` noeviction、`allkeys-*` 与 `volatile-*` 基线
- `INFO memory` allocator 与对象池统计观测：当前使用、峰值、累计分配/释放、活跃块数、Slab、对象池和布局大小
- Slab 小对象缓存基线：16B 到 1KB 分级 freelist，缓存与复用统计可观测
- 内存压力与淘汰回归：noeviction OOM、allkeys-lru、allkeys-lfu、volatile-ttl
- 历史集群基础：Cluster 槽位模型、节点元数据、单节点最小拓扑、`CLUSTER` 最小控制面、`MOVED/ASK` 基础重定向和一致性 smoke；该能力在 `v1.0.0` 前只做必要维护，不作为 `v0.9.0` 起的后续主线继续扩展
- `redis-cli` smoke、Python 集成 smoke、持久化与复制 benchmark

当前主线仍未包含：

- 完整 RESP3 类型覆盖与客户端兼容矩阵
- 完整 Redis RDB 二进制兼容
- Redis 风格长连接流式复制
- Pub/Sub 模式下的完整命令限制、pattern 订阅与背压处理
- 更完整的 `CONFIG REWRITE`、`CONFIG SET` 其余字段，以及更完整的 `CLIENT KILL/PAUSE/TRACKING`
- LFU 衰减、采样池与正式内存 benchmark
- 完整 Redis Cluster gossip、failover、resharding、`ASKING` 一次性放行和多 key 同槽校验；这些能力在 `v1.0.0` 之后重新规划
- Lua 脚本
- Redis 模块系统

## 路线图

| 版本 | 阶段定位 | 核心目标 |
|------|---------|---------|
| `v0.1.0-alpha` | 最小可运行内核 | 单节点、RESP2 子集、String/Key 子集 |
| `v0.1.0-beta` | 基础可靠性 | TCP 服务、TTL、AOF append/replay、集成测试 |
| `v0.1.0` | 首版发布 | benchmark 基线、DoD、发布文档 |
| `v0.2.0` | 数据结构扩展 | Hash/List/Set/ZSet、SCAN、RDB 子集 |
| `v0.3.0` | 持久化增强 | RDB 完整化、AOF rewrite、后台保存 |
| `v0.4.0` | 复制基础 | 主从复制、PSYNC、复制积压缓冲区 |
| `v0.5.0` | 协议与控制面 | RESP3、事务、Pub/Sub、CONFIG/CLIENT |
| `v0.6.0` | 内存与性能控制 | `maxmemory`、淘汰策略、主动过期、Slab |
| `v0.7.0` | 集群基础实验 | Cluster 槽位、重定向、节点元数据，后续冻结到 v1.0.0 之后 |
| `v0.8.0` | 核心路径性能基线 | 零拷贝、批量解析、SIMD、对象布局、回归护栏 |
| `v0.8.1` | 写路径性能修复 | WATCH 懒维护、Dict 单次探测、AOF 分层写入 |
| `v0.9.0` | 单机核心命令补齐 | String/Hash/List/Set/ZSet/Key/Server/Security 核心命令 |
| `v0.9.1` | 审计整改与真实性修复 | 修正文档/控制面/测试/benchmark 口径，统一版本号 |
| `v0.9.2` | 单机核心缺口补齐 I | blocking list/zset、bitmap/bitfield、HLL/GEO、脚本第一批、Memory/Slowlog/Latency 第一批 |
| `v0.9.3` | 单机核心缺口补齐 II | Streams、Functions/Script、ACL、运维诊断第一批 |
| `v0.9.4` | 性能与稳定性收敛 | benchmark guard 恢复、release build 基线、长时运行、故障恢复 |
| `v0.9.5`, `v0.9.6`, ... | 单机封版候选迭代 | 核心命令矩阵、文档、性能、运维边界综合收口 |
| `v1.0.0` | 单机版封版 | Redis Open Source 单机核心功能完整、性能达标、文档齐全 |
| `v1.1.0+` | 模块与集群后续规划 | 模块命令、集群语义、gossip、failover、resharding |

完整计划见 [开发 TODO](docs/redis-uya-todo.md)。

## 设计原则

- **技术可行性优先**：复杂泛型、async、fork、后台重写等路径必须先做最小验证。
- **测试先行**：新增能力先有失败测试或 smoke，再写最小实现，再重构。
- **完整性强约束**：正常路径、错误路径、释放路径、恢复路径不能只实现一半。
- **相对路径优先**：源码、脚本和文档命令不写工程绝对路径。
- **性能数据可复现**：性能结论必须记录硬件、命令、并发、数据规模、Redis 对照版本和统计口径。

## 文档

- [文档索引](docs/README.md)
- [详细设计](docs/redis-uya-design.md)
- [方案评审](docs/redis-uya-review.md)
- [开发 TODO](docs/redis-uya-todo.md)
- [Command Scope](docs/redis-uya-command-scope.md)
- [Command Matrix](docs/redis-uya-command-matrix.md)
- [开发规范](docs/redis-uya-development.md)
- [Definition of Done](docs/redis-uya-definition-of-done.md)
- [Benchmark 输出格式](docs/redis-uya-benchmark-format.md)
- [SDS 内存布局](docs/redis-uya-sds-layout.md)
- [QUICKSTART](docs/redis-uya-quickstart.md)
- [API](docs/redis-uya-api.md)
- [ARCHITECTURE](docs/redis-uya-architecture.md)
- [release-v0.1.0](docs/redis-uya-release-v0.1.0.md)
- [release-v0.2.0](docs/redis-uya-release-v0.2.0.md)
- [release-v0.3.0](docs/redis-uya-release-v0.3.0.md)
- [release-v0.4.0](docs/redis-uya-release-v0.4.0.md)
- [release-v0.5.0](docs/redis-uya-release-v0.5.0.md)
- [release-v0.6.0](docs/redis-uya-release-v0.6.0.md)
- [release-v0.7.0](docs/redis-uya-release-v0.7.0.md)
- [release-v0.8.0](docs/redis-uya-release-v0.8.0.md)
- [release-v0.8.1](docs/redis-uya-release-v0.8.1.md)
- [test-report-v0.1.0](docs/redis-uya-test-report-v0.1.0.md)
- [test-report-v0.6.0](docs/redis-uya-test-report-v0.6.0.md)
- [test-report-v0.7.0](docs/redis-uya-test-report-v0.7.0.md)
- [test-report-v0.8.0](docs/redis-uya-test-report-v0.8.0.md)
- [test-report-v0.8.1](docs/redis-uya-test-report-v0.8.1.md)

## 目录结构

```text
redis-uya/
├── .gitignore
├── Makefile
├── build.uya
├── readme.md
├── benchmarks/
│   ├── v0.1.0.md
│   ├── v0.3.0-persistence.md
│   ├── v0.4.0-replication.md
│   ├── v0.8.0-performance.md
│   ├── v0.8.0-io-uring.md
│   ├── v0.8.0-gap-report.md
│   └── v0.8.1-performance.md
├── src/
│   ├── async_rt/
│   ├── config.uya
│   ├── main.uya
│   ├── command/
│   ├── persistence/
│   ├── memory/
│   ├── network/
│   ├── replication/
│   ├── storage/
│   └── util/
├── tests/
│   ├── unit/
│   │   └── fixtures/
│   ├── integration/
│   └── benchmark/
├── scripts/
│   ├── benchmark_v0_1_0.py
│   ├── benchmark_persistence_v0_3_0.py
│   ├── benchmark_replication_v0_4_0.py
│   ├── benchmark_v0_8_0.py
│   ├── evaluate_io_uring_v0_8_0.py
│   ├── report_v0_8_0_gaps.py
│   └── verify_definition_of_done.sh
├── docs/
│   ├── redis-uya-design.md
│   ├── redis-uya-review.md
│   ├── redis-uya-todo.md
│   ├── redis-uya-development.md
│   ├── redis-uya-definition-of-done.md
│   ├── redis-uya-quickstart.md
│   ├── redis-uya-api.md
│   ├── redis-uya-architecture.md
│   └── redis-uya-release-v0.*.md
├── lib/
└── uya/
```

## 开发规则

进入开发前先确认：

```bash
make build
make test
```

任务完成必须满足：

- 相关单元测试或集成测试通过
- `make build` 通过
- `make test` 通过
- 文档、TODO 和实际行为一致
- 没有新增工程绝对路径
