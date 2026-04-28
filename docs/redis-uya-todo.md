程序的真正成本不在于编写，而在于维护。
# redis-uya 开发 TODO 文档

> 版本: v0.1.0-dev
> 日期: 2026-04-28
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

当前进行中：

- [ ] `v0.5.0`：协议与控制面增强

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
| `v0.7.0` | 集群基础 | Cluster 槽位、重定向、节点元数据 | 分布式闭环 |
| `v0.8.0` 及以后 | 性能冲刺 | 零拷贝、批量解析、SIMD、io_uring、极限优化 | 核心场景逼近或超越 Redis |

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
- [ ] `CLIENT` / `CONFIG` 命令增强
- [ ] 兼容性回归测试

## 11. `v0.6.0` 详细规划

### O. 内存控制

- [ ] `maxmemory`
- [ ] `allkeys-lru`
- [ ] `allkeys-lfu`
- [ ] `volatile-*`
- [ ] 内存统计完善
- [ ] Slab allocator
- [ ] 内存压力与淘汰测试

## 12. `v0.7.0` 详细规划

### P. 集群基础

- [ ] Cluster 槽位模型
- [ ] `MOVED` / `ASK`
- [ ] 节点元数据
- [ ] 最小集群拓扑
- [ ] 集群一致性 smoke

## 13. `v0.8.0` 及以后：长期性能路线

### Q. 性能冲刺

- [ ] 零拷贝响应路径
- [ ] 批量 RESP 解析
- [ ] SIMD 字符串和 CRC64
- [ ] `io_uring` 评估与接入
- [ ] 专用对象池与布局优化
- [ ] 核心场景 Redis 对照追平
- [ ] 核心场景 Redis 对照超越

## 14. 风险登记

| 风险 ID | 描述 | 可能性 | 影响 | 缓解措施 |
|---------|------|--------|------|---------|
| R1 | Uya 编译器在复杂类型组合上继续暴露后端问题 | 中 | 高 | 先写最小复现和定向测试，必要时先修编译器再前进 |
| R2 | `Dict` 首版实现复杂度失控 | 中 | 高 | 固定键/值类型，不在首版做泛型化 |
| R3 | 首版功能面再次膨胀 | 高 | 高 | 保持全版本规划，但严格控制当前执行范围 |
| R4 | AOF 与恢复语义不稳定 | 中 | 高 | 先做 append + replay，损坏路径优先补测试 |
| R5 | 性能目标过早绑死 | 中 | 中 | 先建立 benchmark 基线，再谈追平和超越 |
| R6 | 后续版本规划过粗导致执行断档 | 中 | 中 | 所有版本先保留完整任务框架，进入执行前再细化实现步骤 |
