# redis-uya

> 使用 Uya 从零实现 Redis 兼容内存数据库
> 零 GC 路线 · 显式错误处理 · 可测试演进 · 长期性能目标超过 Redis

> 版本: v0.1.0-dev
> 日期: 2026-04-25

## 简介

`redis-uya` 是一个使用 **Uya 编程语言** 从零实现的生产级高性能内存数据库系统。项目长期目标是兼容 Redis 6.2+ 协议，覆盖核心数据结构、持久化、复制、基础集群与性能工程，并在同条件核心场景上超过 Redis。

当前项目已完成 `v0.1.0` 发布闭环：`v0.1.0-alpha` 的存储与协议主线、`v0.1.0-beta` 的可靠性闭环，以及 `v0.1.0` 的文档、长时运行 smoke 和同机 Redis 基线都已收口。下一步进入 `v0.2.0` 数据结构扩展阶段。

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
- 命令路由：最小命令表、大小写匹配、参数数量校验、未知命令错误、RESP Array 转命令
- String/Key 命令执行：`PING`、`GET`、`SET`、`DEL`、`EXISTS`、`EXPIRE`、`TTL`、`INFO` 最小段
- TCP 服务闭环：loopback 监听、连接读写缓冲、请求解析执行写回、`QUIT`、`maxclients`、Python socket smoke
- 服务运行循环：单线程 epoll 多连接、100ms cron 主动过期扫描、空闲连接不阻塞其他客户端
- AOF 最小闭环：写命令追加、启动回放、截断损坏安全失败、SET/DEL 重启恢复 smoke
- AOF TTL 语义：`EXPIRE` 追加时转换为 `PEXPIREAT`，回放保持绝对过期时间

当前进行中：

- `v0.2.0`：数据结构扩展与更完整控制面

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

`make test-integration` 当前覆盖基础 TCP smoke、空闲连接不阻塞其他客户端、AOF 写入、重启、恢复 smoke，以及基础错误响应兼容检查。

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

## 当前能力边界

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
- `BGSAVE` / `BGREWRITEAOF`
- 主从复制
- 基础集群
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
| `v0.8.0` 及以后 | 性能冲刺 | 零拷贝、批量解析、SIMD、io_uring、极限优化 |

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
- [test-report-v0.1.0](docs/redis-uya-test-report-v0.1.0.md)

## 目录结构

```text
redis-uya/
├── Makefile
├── build.uya
├── readme.md
├── src/
│   ├── config.uya
│   ├── main.uya
│   ├── command/
│   ├── memory/
│   ├── network/
│   ├── storage/
│   └── util/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── benchmark/
├── scripts/
├── docs/
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
