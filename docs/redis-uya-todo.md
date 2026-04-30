程序的真正成本不在于编写，而在于维护。
# redis-uya 开发 TODO 文档

> 版本: v0.9.0-dev
> 日期: 2026-04-30
> 配套设计文档: `redis-uya-design.md`
> 配套评审文档: `redis-uya-review.md`
> 开发规范: `redis-uya-development.md`

## 1. 规划原则

本页同时满足两个目标：

1. 给出当前正在执行的近端计划，确保开发有明确优先级。
2. 给出从 `v0.1.0` 到长期目标的全版本路线图，确保项目不会丢失最终愿景。

执行规则：

- 近端版本采用可执行粒度，任务细到可以直接开发和验收。
- 中远期版本保留完整功能范围、里程碑与验收方向，但不提前承诺每个实现细节。
- 任何阶段都必须满足技术可行性和完整性约束，不能因为规划全面而牺牲收敛。
- 最小迭代默认递增版本号最后一位：`v0.9.0`、`v0.9.1`、`v0.9.2` 依次推进；不为普通小阶段抬高第二位版本号。
- `v0.9.0` 起后续主线只迭代单机版：补齐 Redis Open Source 单机功能、兼容性、性能和稳定性。
- `v0.9.4` 是首个单机封版候选；如未达到 `v1.0.0` 封版条件，继续使用 `v0.9.5`、`v0.9.6` 等 patch 版本顺序迭代。
- 单机版必须覆盖 Redis 官方命令参考中的全部命令名；命令全集、状态定义和封版标准见 `redis-uya-command-scope.md`。
- `v1.0.0` 是单机版封版发布点；只有单机版功能和性能达标后才发布。
- `v1.0.0` 之后才重新规划集群版；`v0.7.0` 已有集群基础作为历史实验能力保留，但不作为 `v0.9.0` 起的后续主线继续扩展。

## 2. 当前状态

当前已完成：

- [x] 工程骨架、`Makefile`、文档入口
- [x] 内置 Uya 工具链同步
- [x] 工具模块：`log/time/endian/crc64`
- [x] 最小单元测试框架与 `make test`
- [x] 内存分配器封装
- [x] 配置解析：文本 + 文件读取
- [x] SDS 基础能力：创建、追加、格式化追加、比较、扩缩容、复制、范围切片、1MB 压测
- [x] 项目内专用 `Dict`：插入、查找、覆盖、删除、扩容、渐进 rehash、10k 键回归
- [x] `RedisObject` 最小 String 包装：RAW/INT 编码、类型名、释放
- [x] `Engine` 最小实现：键读写删除、覆盖释放、TTL 字段、惰性过期
- [x] RESP2 最小子集解析：Simple String、Error、Integer、Bulk String、Array、Incomplete、非法输入
- [x] 命令路由：最小命令表、参数校验、未知命令错误
- [x] String/Key 命令执行：`PING/GET/SET/DEL/EXISTS/EXPIRE/TTL/INFO`
- [x] 服务闭环：TCP 监听、连接处理、Python socket smoke
- [x] 服务运行循环：单线程 epoll 多连接、100ms cron 主动过期扫描、空闲连接不阻塞其他客户端
- [x] AOF 最小闭环：写命令追加、启动回放、截断损坏安全失败、重启恢复 smoke
- [x] `v0.3.0`：持久化增强与可靠性矩阵
- [x] `v0.4.0`：复制与高可用基础
- [x] `v0.5.0`：协议与控制面增强
- [x] `v0.6.0`：内存与性能控制
- [x] `v0.7.0`：集群基础
- [x] `v0.8.0`：核心路径性能基线
- [x] `v0.8.1`：写路径性能修复

当前进行中：

- [ ] `v0.9.0` 起：单机版完整功能、兼容性、性能和稳定性收敛，达标后封版 `v1.0.0`

## 3. 全版本路线图

| 版本 | 阶段定位 | 核心目标 | 验收关键词 |
|------|---------|---------|-----------|
| `v0.1.0-alpha` | 最小可运行内核 | 单节点、RESP2 子集、String/Key 子集 | `redis-cli` 基本交互 |
| `v0.1.0-beta` | 基础可靠性 | TCP 服务、TTL、AOF append/replay、Python 子集测试 | 重启恢复 |
| `v0.1.0` | 首版发布 | benchmark 基线、DoD、发布文档 | 可交付、可复现 |
| `v0.2.0` | 数据结构扩展 | Hash/List/Set/ZSet、SCAN、RDB 子集 | 类型面完整 |
| `v0.3.0` | 持久化增强 | RDB 完整化、AOF rewrite、BGSAVE/BGREWRITEAOF | 恢复与压缩 |
| `v0.4.0` | 复制与高可用基础 | 主从复制、PSYNC、复制积压缓冲区 | 副本同步 |
| `v0.5.0` | 协议与控制面增强 | RESP3、事务、Pub/Sub、CONFIG/CLIENT 完整化 | 协议兼容扩大 |
| `v0.6.0` | 内存与性能控制 | `maxmemory`、淘汰策略、主动过期强化、Slab | 内存可控 |
| `v0.7.0` | 集群基础实验 | Cluster 槽位、重定向、节点元数据 | 历史基础能力，后续冻结到 v1.0.0 之后 |
| `v0.8.0` | 核心路径性能基线 | 零拷贝、批量解析、SIMD、对象布局、回归护栏 | 热路径可度量、不退化 |
| `v0.8.1` | 写路径性能修复 | WATCH 懒维护、Dict 单次探测、AOF 分层写入 | 写路径首批 P0 债务收敛 |
| `v0.9.0` | 单机核心命令补齐 | String/Hash/List/Set/ZSet/Key/Server/Security 核心命令 | redis-cli/redis-py 常用命令兼容 |
| `v0.9.1` | 单机命令全集矩阵 | Redis 官方命令全集建表，补齐 Connection/Generic/Server/Transaction/Pub/Sub/Scripting/Stream 命令族 | 所有官方命令名可追踪 |
| `v0.9.2` | 单机高级数据能力 | Bitmap、Bitfield、HyperLogLog、Geo、JSON、Search、Time Series、概率结构、Vector | Redis Open Source 单机功能面覆盖 |
| `v0.9.3` | 单机运维、安全与可观测 | ACL、TLS、CLIENT/CONFIG/INFO/SLOWLOG/LATENCY/MEMORY 等管理面 | 生产运维可用 |
| `v0.9.4` | 首个单机性能与稳定性封版候选 | benchmark target、长时运行、故障恢复、兼容矩阵 | v1.0.0 发布候选 |
| `v0.9.5`, `v0.9.6`, ... | 后续封版候选迭代 | 未达 v1.0.0 条件时继续 patch 位递增 | 补缺口、不扩范围 |
| `v1.0.0` | 单机版封版 | 单机功能完整、性能达标、文档齐全 | 可发布、可生产评估 |
| `v1.1.0+` | 集群版规划与开发 | 集群语义、gossip、failover、resharding | v1.0.0 之后启动 |

## 4. 当前主线：`v0.1.0-alpha`

### A. 存储核心

#### A1. SDS 收尾

- [x] `sds_new()`
- [x] `sds_new_len()`
- [x] `sds_empty()`
- [x] `sds_dup()`
- [x] `sds_cat()`
- [x] `sds_range()`
- [x] `sds_cmp()`
- [x] `sds_casecmp()`
- [x] `sds_len()`
- [x] `sds_avail()`
- [x] `sds_grow()`
- [x] `sds_shrink()`
- [x] `sds_cat_fmt()` 最小实现
- [x] 1MB 追加压力测试
- [x] 内存布局与头部方案文档化

#### A2. 专用 `Dict`

- [x] 定义 `DictEntry`
- [x] 定义 `DictTable`
- [x] 定义 `Dict`
- [x] 实现 `insert()`
- [x] 实现 `lookup()`
- [x] 实现 `delete()`
- [x] 实现 `len()`
- [x] 单元测试：插入、覆盖、删除、缺失键
- [x] 单元测试：扩容后查找
- [x] 单元测试：10k 键规模回归
- [x] 第二阶段：`begin_rehash()` / `rehash_step()`

#### A3. `RedisObject` 最小实现

- [x] 定义 `ObjectType`
- [x] 定义 `Encoding`
- [x] 定义 `RedisObject`
- [x] 实现 String 变体
- [x] 实现 `create_string_object()`
- [x] 实现 `object_free()`
- [x] 实现 `object_type_name()`
- [x] 单元测试：String 对象创建/释放
- [x] 单元测试：整数编码与普通字符串编码

#### A4. `Engine` 最小实现

- [x] 定义 `RedisDb`
- [x] 定义 `Engine`
- [x] 实现 `lookup_key()`
- [x] 实现 `set_key()`
- [x] 实现 `delete_key()`
- [x] 实现 TTL 字段存储
- [x] 单元测试：键读写删除
- [x] 单元测试：惰性过期

### B. 协议与命令

#### B1. RESP2 最小子集

- [x] Simple String
- [x] Error
- [x] Integer
- [x] Bulk String
- [x] Array
- [x] 不完整输入返回 `Incomplete`
- [x] 单元测试：官方 RESP2 样本
- [x] 单元测试：半包输入
- [x] 单元测试：非法前缀与非法长度

#### B2. 命令路由

- [x] 定义 `Command`
- [x] 定义 `CommandInfo`
- [x] 注册最小命令表
- [x] 参数数量校验
- [x] 未知命令错误
- [x] 单元测试：查找、校验、错误路径

#### B3. String / Key 命令子集

- [x] `PING`
- [x] `GET`
- [x] `SET`
- [x] `DEL`
- [x] `EXISTS`
- [x] `EXPIRE`
- [x] `TTL`
- [x] `INFO` 最小段
- [x] 单元测试：每个命令正常路径
- [x] 单元测试：每个命令错误路径

### C. 服务闭环

#### C1. TCP 与连接

- [x] `listener` 最小 TCP 监听
- [x] `connection` 读写缓冲
- [x] 读取 -> 解析 -> 执行 -> 写回 闭环
- [x] `QUIT`
- [x] `maxclients` 最小限制

#### C2. 运行循环

- [x] Server 主循环
- [x] 100ms `cron`
- [x] 过期键惰性检查入口
- [x] 过期键主动扫描入口
- [x] 多连接 epoll 调度，空闲客户端不阻塞其他客户端
- [x] 启动/监听/响应 `PING` smoke

## 5. `v0.1.0-beta` 主线

### D. AOF 最小闭环

- [x] 写命令追加 AOF
- [x] 启动回放 AOF
- [x] `EXPIRE` AOF 转换为绝对 `PEXPIREAT`
- [x] 损坏 AOF 安全失败
- [x] 集成测试：写入 -> 重启 -> 恢复

### E. 稳定性与集成

- [x] `redis-cli` smoke：`tests/integration/redis_cli_smoke.sh`
- [x] Python 子集集成测试：`tests/integration/smoke_tcp.py`
- [x] Python 空闲连接回归测试：`tests/integration/idle_client.py`
- [x] Python 慢读客户端回归测试：`tests/integration/slow_reader.py`
- [x] Python AOF 重启恢复集成测试：`tests/integration/persistence_aof.py`
- [x] 错误响应与 Redis 基础兼容检查：`tests/integration/error_compat.py`
- [x] 长时运行 smoke（至少 30 分钟）

## 6. `v0.1.0` 发布闭环

### F. Benchmark 与基线

- [x] 同机 Redis 基线记录
- [x] `PING/SET/GET` benchmark
- [x] `floor/target/stretch` 判定
- [x] 输出到 `benchmarks/v0.1.0.md`

### G. 文档与验收

- [x] 完善 DoD 文档
- [x] 更新 `readme.md`
- [x] 新增 `QUICKSTART`
- [x] 新增 `API`
- [x] 新增 `ARCHITECTURE`
- [x] 新增 `release-v0.1.0`

## 7. `v0.2.0` 详细规划

### H. 数据结构扩展

- [x] Hash 最小对象实现
- [x] List 最小对象实现
- [x] Set 最小对象实现
- [x] ZSet 最小对象实现
- [x] 对应命令子集：`HSET/HGET`
- [x] 对应命令子集：`LPUSH/LPOP/LRANGE`
- [x] 对应命令子集：`SADD/SREM/SMEMBERS`
- [x] 对应命令子集：`ZADD/ZRANGE/ZREM`
- [x] `SCAN`
- [x] 更完整 `INFO` / `CONFIG`
- [x] 过期主动采样循环

### I. 持久化扩展

- [x] RDB 文件头/键值对子集
- [x] RDB 加载子集
- [x] AOF rewrite 预研

### J. 测试扩展

- [x] 五大类型单元测试
- [x] redis-py 子集覆盖更多命令
- [x] RDB/AOF 混合恢复测试

## 8. `v0.3.0` 详细规划

### K. 持久化增强

- [x] RDB 完整兼容推进
- [x] `BGSAVE`
- [x] `BGREWRITEAOF`
- [x] rewrite 增量缓冲
- [x] fork / 子进程路径验证

### L. 可靠性

- [x] 崩溃恢复矩阵
- [x] RDB/AOF 损坏与截断测试
- [x] 持久化 benchmark

## 9. `v0.4.0` 详细规划

### M. 主从复制

- [x] 复制角色与状态机
- [x] `PSYNC` / backlog
- [x] 全量同步
- [x] 增量同步
- [x] 复制心跳
- [x] 集成测试：主从一致性
- [x] 复制 benchmark

## 10. `v0.5.0` 详细规划

### N. 协议与控制面增强

- [x] RESP3
- [x] `MULTI/EXEC/DISCARD`
- [x] `WATCH/UNWATCH`
- [x] `PUBLISH/SUBSCRIBE`
- [x] `CLIENT` / `CONFIG` 命令增强
- [x] 兼容性回归测试

## 11. `v0.6.0` 详细规划

### O. 内存控制

- [x] `maxmemory`
- [x] `allkeys-lru`
- [x] `allkeys-lfu`
- [x] `volatile-*`
- [x] 内存统计完善
- [x] Slab allocator
- [x] 内存压力与淘汰测试

## 12. `v0.7.0` 详细规划

### P. 集群基础

- [x] Cluster 槽位模型
- [x] `MOVED` / `ASK`
- [x] 节点元数据
- [x] 最小集群拓扑
- [x] `CLUSTER` 最小命令接口
- [x] 集群一致性 smoke

## 13. `v0.8.0`：核心路径性能基线

### Q. 性能地基与回归护栏

- [x] 核心 benchmark 矩阵与回归阈值
- [x] 零拷贝响应路径
- [x] 批量 RESP 解析
- [x] SIMD 字符串和 CRC64
- [x] `io_uring` 评估，不把生产路径绑定到未验证能力
- [x] 专用对象池与布局优化
- [x] Redis 对照差距报告与后续优化队列

验收项：

- `PING/GET/SET` 热路径吞吐和 p99 延迟较 `v0.7.0` 不退化
- benchmark 报告明确硬件、构建模式、持久化配置、数据规模和 Redis 对照口径
- 性能优化不改变协议、持久化、复制、集群基础语义
- 输出明确的后续性能债务清单，不把“超越 Redis”作为 `v0.8.0` 单版硬门槛

测试证据：

- `make test`
- `make test-integration`
- `scripts/benchmark_v0_1_0.py`
- `make benchmark-v0.8.0`
- `scripts/benchmark_v0_8_0.py`
- `benchmarks/v0.8.0-performance.md`
- `make report-v0.8.0-gaps`
- `benchmarks/v0.8.0-gap-report.md`

## 14. `v0.8.1`：写路径性能修复

### R. 首批 P0 写路径债务

- [x] WATCH 版本表懒维护：没有活跃 WATCH 客户端时，普通写命令不维护 `watch_versions`
- [x] Dict 覆盖写单次探测：`dict_insert_with_old()` 同时完成插入/覆盖和旧值返回，减少 `SET` 覆盖路径重复 lookup
- [x] AOF 分层写入：512B 以下命令进入 64KiB buffer，较大命令 flush 小缓冲后直接写，避免 1KiB SET 在 debug 构建中逐字节复制
- [x] AOF flush 边界：server cron、客户端关闭、server close 和 BGREWRITEAOF fork 前都会 flush 当前 AOF buffer
- [x] 进程级测试适配 AOF 周期 flush 语义，仍断言成功写入可落盘、失败重定向写不进入 AOF

验收项：

- 相对 `benchmarks/v0.8.0-performance.md`，`PING`、16B/1KiB `SET`、16B/1KiB `GET` 的吞吐和 p99 guard 全部通过
- `SET` 写路径优化不改变命令语义、事务 WATCH 语义、AOF replay 语义、复制 backlog 和集群重定向失败写边界
- AOF 新语义明确为内存 buffer + 周期 flush；需要立即检查文件内容的集成测试必须等待 flush 完成

测试证据：

- `make test`
- `make test-integration`
- `make benchmark-v0.8.1`
- `benchmarks/v0.8.1-performance.md`

## 15. `v0.9.0` 起：单机版总目标

`v0.9.0` 起后续所有开发都服务于单机版封版。目标不是只实现五大基础类型，而是覆盖 Redis Open Source 在单机部署下可用的全部官方命令名和主要能力：命令语义、数据结构、持久化、复制、脚本、消息、搜索/高级数据结构、运维、安全、可观测和性能。

### S. 单机功能范围

- [ ] Core commands：String、Hash、List、Set、ZSet、Key、Server、Connection、Database、Pub/Sub、Transaction、Scripting、Function、Stream 等命令族
- [ ] Core data structures：String、Hash、List、Set、Sorted Set、Bitmap、Bitfield、HyperLogLog、Geo、Stream
- [ ] Advanced data structures：JSON、Search、Time Series、Bloom、Cuckoo、Count-Min Sketch、Top-K、t-digest、Vector
- [ ] Persistence：RDB、AOF、AOF rewrite、混合持久化、损坏/截断恢复、兼容性测试
- [ ] Replication：主从复制、PSYNC、backlog、WAIT、只读副本、断线恢复和一致性 smoke
- [ ] Programmability：Lua 脚本、Redis Functions、脚本缓存、原子执行边界
- [ ] Security：AUTH、ACL、TLS、命令权限、key pattern 权限、保护模式
- [ ] Operations：CONFIG、CLIENT、INFO、MEMORY、SLOWLOG、LATENCY、MONITOR、COMMAND、DBSIZE、FLUSH、SHUTDOWN、SAVE/BGSAVE
- [ ] Performance：解析、命令执行、存储结构、内存分配、网络写回、持久化写路径、长时间运行稳定性

### S1. 官方命令全集兼容矩阵

- [ ] 以 Redis 官方 Commands Reference 建立命令全集基线，记录命令名、功能组、arity、flags、key spec、ACL category、是否模式相关
- [ ] 每个命令标记为 `full`、`partial`、`standalone-error`、`alias` 或 `deferred`
- [ ] `deferred` 命令必须绑定目标版本；不能进入 `v1.0.0` 封版状态
- [ ] Cluster/Sentinel 等模式相关命令在 `v1.0.0` 前至少实现 standalone 兼容行为或明确错误，完整分布式语义进入 `v1.1.0+`
- [ ] 兼容矩阵必须由 `COMMAND` / `COMMAND DOCS` / `COMMAND INFO` 等控制面命令共享，避免文档和运行时命令表分叉

非目标：

- [ ] `v1.0.0` 之前不继续扩展 Redis Cluster gossip、failover、resharding、正式集群 benchmark
- [ ] `v1.0.0` 之前不把已有 `src/cluster/*` 作为主线能力继续放大；只做必要兼容维护和 standalone 兼容命令响应，避免破坏现有测试

## 16. `v0.9.0`：单机核心命令补齐

### T. 基础类型与管理命令

- [x] String 第一批：`APPEND`、`STRLEN`、`GETDEL`
- [ ] String 后续：`INCR/DECR/INCRBY/DECRBY/INCRBYFLOAT`、`GETSET`、`SETNX/SETEX/SETRANGE`、`GETRANGE`、`MGET/MSET/MSETNX`
- [ ] Hash：`HINCRBY/HINCRBYFLOAT`、`HKEYS/HVALS/HGETALL`、`HSCAN`
- [ ] List：`RPUSH/RPOP`、`LINDEX/LINSERT`、`LSET/LLEN/LTRIM`、`LREM`、`LPUSHX/RPUSHX`、`LPOS`
- [ ] Set：`SPOP/SRANDMEMBER`、`SINTER/SDIFF/SUNION`、`SINTERSTORE/SDIFFSTORE/SUNIONSTORE`
- [ ] ZSet：`ZINCRBY/ZCARD/ZCOUNT`、`ZRANGEBYSCORE/ZREVRANGEBYSCORE`、`ZREMRANGEBYRANK/ZREMRANGEBYSCORE`、`ZSCAN`
- [x] Key/Server 第一批：`ECHO`、`TYPE`、`DBSIZE`
- [x] Key/Server 第二批过期毫秒语义：`PEXPIRE`、`PERSIST`、`PTTL`
- [ ] Key/Server 后续：`RENAME/RENAMENX`、`MOVE`、`DUMP/RESTORE`、`PEXPIREAT`、`WAIT`、`FLUSHDB/FLUSHALL`、`SELECT`、`LASTSAVE`、`OBJECT`、`SORT`
- [ ] Security baseline：`AUTH`、`requirepass`、`SHUTDOWN`

验收项：

- 新增命令必须有单元测试、错误路径测试和 redis-py/redis-cli 兼容 smoke
- 新增写命令必须覆盖 AOF、RDB、复制 backlog、WATCH 版本推进和 maxmemory 边界
- 现有 `make test`、`make test-integration`、`make benchmark-v0.8.1` 回归护栏不退化

## 17. `v0.9.1-v0.9.3`：单机完整功能面

### U. 语义、数据结构与运维面

- [ ] 官方命令全集矩阵落地：所有 Redis Open Source 官方命令名进入命令表或兼容错误处理
- [ ] Streams 完整化：消费者组、pending、claim、trim、阻塞读取和持久化恢复
- [ ] Pub/Sub 完整化：pattern 订阅、订阅态命令限制、背压和断开清理
- [ ] Lua 与 Functions：`EVAL/EVALSHA`、脚本缓存、只读脚本、原子边界、函数加载和调用
- [ ] RESP3 与客户端兼容矩阵：push、map、set、attribute、null、HELLO/AUTH/SETNAME 组合路径
- [ ] Bitmap/Bitfield/HyperLogLog/Geo 命令族
- [ ] JSON、Search、Time Series、概率结构和 Vector 的项目内实现方案与分阶段命令覆盖
- [ ] ACL 与 TLS：用户、权限、命令类别、key pattern、证书配置和认证错误兼容
- [ ] 管理与诊断：`CONFIG SET/REWRITE`、`CLIENT LIST/KILL/PAUSE/TRACKING`、`SLOWLOG`、`LATENCY`、`MEMORY`、`MONITOR`、`COMMAND`
- [ ] 持久化与复制收敛：RDB 二进制兼容推进、AOF rewrite 压测、复制断线重连、`WAIT` 语义、只读副本限制

验收项：

- 按命令族建立兼容矩阵，明确已实现、部分实现、暂不支持的语义差异
- 每个数据类型必须覆盖正常路径、空 key、错类型、过期、持久化恢复、复制恢复、内存淘汰边界
- 高级数据结构必须先完成项目内设计评审，再进入实现，避免一次性堆入不可维护的半成品

## 18. `v0.9.4` 起：单机性能与稳定性封版候选

### V. v1.0.0 前置收敛

- [ ] release build benchmark 模式，固定硬件、Redis 对照版本、持久化配置、并发、pipeline 和数据集
- [ ] 核心命令吞吐、p95/p99、RSS 达到 floor/target，关键路径持续向 Redis 对照靠近
- [ ] SET/写路径、RDB/AOF rewrite、复制增量、Streams、Search/Vector 等重路径单独 benchmark
- [ ] 长时间运行、内存泄漏、慢客户端、半包/粘包、崩溃恢复和磁盘损坏矩阵
- [ ] API、部署、运维、安全、性能、已知限制和迁移指南文档齐全

如果 `v0.9.4` 未达到 `v1.0.0` 封版条件，继续按最后一位顺序增加版本号，使用 `v0.9.5`、`v0.9.6` 等版本补齐缺口；这些版本不新增集群主线和新的大范围目标。

`v1.0.0` 封版条件：

- [ ] 单机计划内功能已完成并有测试证据
- [ ] Redis 官方命令全集兼容矩阵无 `deferred`；非模式相关命令达到 `full`，模式相关命令达到 `full` 或 `standalone-error`
- [ ] 兼容矩阵清楚标记所有 Redis 差异，不存在未说明的核心语义缺口
- [ ] 性能达到当前 target，且没有 P0/P1 稳定性缺陷
- [ ] 发布说明、DoD、benchmark 和测试报告齐全

## 19. `v1.1.0+`：集群版规划与开发

`v1.0.0` 发布前不启动新的集群主线。发布后再基于稳定单机内核重新评审集群架构，规划以下方向：

- [ ] 集群语义：多 key 同槽校验、`CROSSSLOT`、`ASKING`、`MOVED/ASK` 完整边界
- [ ] 集群成员：cluster bus、节点握手、gossip、拓扑传播、`PFAIL/FAIL`
- [ ] 集群故障转移：replica 归属、config epoch、failover 选择、旧 master 恢复处理
- [ ] 集群重分片：`ADDSLOTS/DELSLOTS`、迁移状态机、key 迁移闭环、正式集群 benchmark

## 20. 风险登记

| 风险 ID | 描述 | 可能性 | 影响 | 缓解措施 |
|---------|------|--------|------|---------|
| R1 | Uya 编译器在复杂类型组合上继续暴露后端问题 | 中 | 高 | 先写最小复现和定向测试，必要时先修编译器再前进 |
| R2 | `Dict` 首版实现复杂度失控 | 中 | 高 | 固定键/值类型，不在首版做泛型化 |
| R3 | 首版功能面再次膨胀 | 高 | 高 | 保持全版本规划，但严格控制当前执行范围 |
| R4 | AOF 与恢复语义不稳定 | 中 | 高 | 先做 append + replay，损坏路径优先补测试 |
| R5 | 性能目标过早绑死 | 中 | 中 | 先建立 benchmark 基线，再谈追平和超越 |
| R6 | 后续版本规划过粗导致执行断档 | 中 | 中 | 所有版本先保留完整任务框架，进入执行前再细化实现步骤 |
| R7 | 单机功能范围扩大导致封版失控 | 中 | 高 | 所有 Redis 功能按命令族和数据类型分批验收，未进入当前版本的能力只保留范围，不提前实现 |
| R8 | 完整 Cluster 协议过早铺开导致状态机失控 | 中 | 高 | `v1.0.0` 前冻结集群扩展，只做现有基础能力维护；`v1.0.0` 后重新评审并分阶段实现 |
