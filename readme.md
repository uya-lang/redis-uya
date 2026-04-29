# redis-uya

> 使用 Uya 从零实现 Redis 兼容内存数据库
> 零 GC 路线 · 显式错误处理 · 可测试演进 · 长期性能目标超过 Redis

> 版本: v0.8.0-dev
> 日期: 2026-04-29

## 简介

`redis-uya` 是一个使用 **Uya 编程语言** 从零实现的生产级高性能内存数据库系统。项目长期目标是兼容 Redis 6.2+ 协议，覆盖核心数据结构、持久化、复制、基础集群与性能工程，并在同条件核心场景上超过 Redis。

当前项目已完成 `v0.7.0` 集群基础，并进入 `v0.8.0` 核心路径性能基线：在 `v0.1.0` 发布闭环、`v0.2.0` 数据结构扩展、`v0.3.0` 持久化增强、`v0.4.0` 复制基础、`v0.5.0` 协议与控制面增强、`v0.6.0` 内存与性能控制、`v0.7.0` Cluster 基础之上，新增核心 benchmark 矩阵、同机 Redis 对照、吞吐/p99 回归阈值、`GET` bulk string 零拷贝发送路径、RESP2/RESP3 顶层批量解析 API、`@vector` byte-slice 比较、表驱动 CRC64、`io_uring` 主机能力评估报告，以及 `RedisObject` / `ListNode` 专用对象池与 `INFO memory` 布局观测。后续继续推进 Redis 对照差距报告与优化队列。

## 核心目标

- **协议兼容**：从 RESP2 子集起步，逐步扩展到 RESP3 与更完整的 Redis 命令语义。
- **数据结构完整**：按版本推进 String、Hash、List、Set、ZSet、过期键、SCAN 与对象编码。
- **可靠持久化**：首版优先 AOF append/replay，后续补齐 RDB、AOF rewrite、BGSAVE/BGREWRITEAOF。
- **高性能路线**：建立 Redis 同机对照基线，再优化解析、字典、内存分配、零拷贝、批处理和事件循环。
- **工程可控**：所有能力必须有测试、错误路径、释放路径、恢复路径或 benchmark 证据。

## 当前状态

已完成：

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
- String/Key/Control 命令执行：`PING`、`GET`、`SET`、`DEL`、`EXISTS`、`EXPIRE`、`TTL`、`INFO` 多 section、`CONFIG GET/HELP/RESETSTAT`、`CLIENT` 兼容子集、`SAVE`
- Hash 最小对象：基于项目内 `Dict` 的最小 hash value 容器
- Hash 命令子集：`HSET`、`HGET`
- List 最小对象：基于双向链表的最小 list value 容器
- List 命令子集：`LPUSH`、`LPOP`、`LRANGE`
- Set 最小对象：基于项目内 `Dict` 的最小 set value 容器
- Set 命令子集：`SADD`、`SREM`、`SMEMBERS`
- ZSet 最小对象：基于项目内 `Dict` 的最小 zset value 容器，支持按 score 排序范围读取
- ZSet 命令子集：`ZADD`、`ZRANGE`、`ZREM`
- Key 迭代子集：`SCAN`，支持 cursor 返回与 `COUNT` 最小参数
- TCP 服务闭环：loopback 监听、连接读写缓冲、请求解析执行写回、`QUIT`、`maxclients`、Python socket smoke
- 服务运行循环：单线程 epoll 多连接、100ms cron 主动过期采样循环、空闲连接不阻塞其他客户端
- RDB 当前类型闭环：项目内 RDB 子集已覆盖 String/Hash/List/Set/ZSet + 绝对过期时间 save/load、`SAVE`
- `BGSAVE`：真实 `fork/waitpid` 子进程落盘，支持去掉 AOF 后仅靠 RDB 恢复
- AOF 最小闭环：写命令追加、启动回放、截断损坏安全失败、SET/DEL 重启恢复 smoke
- 启动恢复顺序：先加载最小 RDB，再回放 AOF
- AOF TTL 语义：`EXPIRE` 追加时转换为 `PEXPIREAT`，回放保持绝对过期时间
- `BGREWRITEAOF`：真实子进程后台 rewrite + 父进程增量缓冲合并，可把当前内存态规范化重写为可回放 AOF
- 复制角色与状态机：支持 master/slave 角色切换、`REPLICAOF` 控制入口、`INFO replication` 与复制配置可观测
- `PSYNC / backlog`：master 维护复制积压缓冲区，支持 `FULLRESYNC` / `CONTINUE` 最小握手判断
- 全量同步：replica 可通过 `REPLICAOF -> PSYNC ? -1` 拉取 master 当前 RDB 快照并落库
- 增量同步：replica 在 connected 状态下周期性 `PSYNC replid offset` 拉取 backlog delta 并回放
- 复制心跳：replica 周期性 `PING` master，链路失败时回到 `configured` 并等待重同步
- 主从一致性：当前五类对象已有 full sync + incremental smoke
- 事务控制最小子集：连接级 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，支持 `QUEUED`、`EXEC` 数组回复、观察键变更后的 Null Array 中止和 `DISCARD` 丢弃
- Pub/Sub 最小子集：`SUBSCRIBE` 注册连接订阅、`PUBLISH` 跨连接推送 message 并返回订阅者数量、`UNSUBSCRIBE` 取消订阅
- 控制面兼容子集：`CLIENT ID/GETNAME/SETNAME/INFO/LIST/SETINFO/HELP`、`HELLO SETNAME`、`CONFIG GET/HELP/RESETSTAT`
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

下一阶段：

- `v0.8.0`：核心路径性能基线，继续输出 Redis 对照差距报告与后续优化队列

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

`make test-integration` 当前覆盖基础 TCP smoke、空闲连接不阻塞其他客户端、持久化/复制/事务/Pub/Sub/控制面兼容路径，v0.6.0 的 `maxmemory`、淘汰策略、内存统计和压力回归，以及 v0.7.0 的集群 smoke 与一致性 smoke。

v0.8.0 核心性能基线：

```bash
make benchmark-v0.8.0
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
- 当前版本：`v0.9.4` 本地修复快照
- C 宿主工具链：`cc`、`gcc` 或 `clang`
- 目标平台：Linux x86_64 / ARM64

说明：当前不会依赖未发布的 `v0.9.5` 特性。`v0.9.5` 正式发布后，再评估是否切换内置工具链。

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

当前仓库主线已完成 `v0.7.0`，已经包含：

- 单节点、单进程服务模型
- RESP2 子集
- RESP3 最小闭环：`HELLO 2/3`、常用 RESP3 输入类型解析、RESP3 Null 回复
- String / Hash / List / Set / ZSet / `SCAN`
- AOF append/replay、RDB 子集、`SAVE`、`BGSAVE`、`BGREWRITEAOF`
- 主从复制最小闭环：`REPLICAOF`、`PSYNC / backlog`、全量同步、定时拉取式增量同步、复制心跳
- 事务最小子集：`MULTI/EXEC/DISCARD/WATCH/UNWATCH`
- Pub/Sub 最小子集：`PUBLISH/SUBSCRIBE/UNSUBSCRIBE`
- `CLIENT` / `CONFIG` 控制面兼容子集
- v0.5 协议与控制面兼容性回归
- `maxmemory` noeviction、`allkeys-*` 与 `volatile-*` 基线
- `INFO memory` allocator 与对象池统计观测：当前使用、峰值、累计分配/释放、活跃块数、Slab、对象池和布局大小
- Slab 小对象缓存基线：16B 到 1KB 分级 freelist，缓存与复用统计可观测
- 内存压力与淘汰回归：noeviction OOM、allkeys-lru、allkeys-lfu、volatile-ttl
- 基础集群：Cluster 槽位模型、节点元数据、单节点最小拓扑、`CLUSTER` 最小控制面、`MOVED/ASK` 基础重定向和一致性 smoke
- `redis-cli` smoke、Python 集成 smoke、持久化与复制 benchmark

当前主线仍未包含：

- 完整 RESP3 类型覆盖与客户端兼容矩阵
- 完整 Redis RDB 二进制兼容
- Redis 风格长连接流式复制
- Pub/Sub 模式下的完整命令限制、pattern 订阅与背压处理
- 完整 `CONFIG SET/REWRITE` 与全局 `CLIENT LIST/KILL/PAUSE/TRACKING`
- LFU 衰减、采样池与正式内存 benchmark
- 完整 Redis Cluster gossip、failover、resharding、`ASKING` 一次性放行和多 key 同槽校验
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
| `v0.7.0` | 集群基础 | Cluster 槽位、重定向、节点元数据 |
| `v0.8.0` | 核心路径性能基线 | 零拷贝、批量解析、SIMD、对象布局、回归护栏 |

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
- [test-report-v0.1.0](docs/redis-uya-test-report-v0.1.0.md)
- [test-report-v0.6.0](docs/redis-uya-test-report-v0.6.0.md)
- [test-report-v0.7.0](docs/redis-uya-test-report-v0.7.0.md)

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
│   └── v0.4.0-replication.md
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
