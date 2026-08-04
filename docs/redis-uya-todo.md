程序的真正成本不在于编写，而在于维护。
# redis-uya 开发 TODO 文档

> 版本: v0.9.3-dev
> 日期: 2026-07-31
> 配套设计文档: `redis-uya-design.md`
> 配套评审文档: `redis-uya-review.md`
> 审计基线: `redis-uya-audit-2026-05-16.md`
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
- 当前 `HEAD` 的真实性高于历史报告：`README`、`DoD`、`COMMAND*`、测试结果和 benchmark 结果必须互相一致。
- 2026-07-31 当前 `HEAD`：源码契约、完整单元和 33 项集成已通过；GET 在命中对象后直接检查字符串类型并构造 value slice，不再调用返回错误联合的通用字符串 helper。两组相反顺序固定 CPU 200K `perf stat` 共 8 次测量中吞吐提升 1.04%，cycles/instructions/branches 分别下降 0.66%/1.02%/1.02%；零丢样复采样中目标 helper 已无样本。不可变与 current 50K 的五项绝对吞吐、normalized 和 p99 guard 均通过；current Redis 比值为 `1.07x/1.29x/1.07x/1.33x/0.97x`，PING 与两项 GET 仍未达到严格稳定 1.10x 全场景超越要求。
- 2026-07-23 已将 `../uya` `1.0` 分支直接回退到与远端一致的 `f54bd7bf`，删除未推送且违反 `export const/var` 裸 C ABI 规范的两个本地提交；redis-uya 将内部全局量改为私有并通过 `export fn` 跨模块访问，构建、完整单测、完整集成、redis-cli、release 和性能 guard 均通过。
- `v0.9.4` 用于性能与稳定性收敛；`v0.9.5` 是首个单机封版候选，如未达到 `v1.0.0` 封版条件，继续使用 `v0.9.6` 等 patch 版本顺序迭代。
- 单机版必须先覆盖 Redis Open Source 单机核心命令面；模块命令可以继续追踪，但不能与 `v1.0.0` 单机封版门槛混算。命令全集、状态定义和封版标准见 `redis-uya-command-scope.md`。
- `v1.0.0` 是单机版封版发布点；只有单机版功能和性能达标后才发布。
- `v1.0.0` 之后才重新规划集群版；`v0.7.0` 已有集群基础作为历史实验能力保留，但不作为 `v0.9.0` 起的后续主线继续扩展。

## 2. 当前状态

当前已完成：

- [x] 工程骨架、`Makefile`、文档入口
- [x] 内置 Uya 工具链同步
- [x] Uya `1.0` / `v0.9.9` 工具链同步：标准库、文档、静态启动器与 `cmd/build` 成套更新；规范复核后基线固定为 `f54bd7bf`，项目侧使用私有全局量与导出函数完成兼容
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

- [x] `v0.9.0`：单机核心命令补齐与安全基线收口完成
- [x] `v0.9.1`：审计整改与真实性修复完成，测试 / benchmark / DoD 校验已恢复绿态，控制面真值、版本串与命令完成度统计分层已收口
- [x] 写路径性能修复：复制 backlog 超限后改为逻辑前移并按阈值压缩，避免达到 1MiB 后每条写命令复制整个 backlog；release 短测 `SET 1KiB` 从 1468 提升到 4078 req/s
- [x] RESP batch 顶层容量按需增长：单条大请求不再按 64 帧上限预分配并重解析；正式 `SET 1KiB` 从 2811 提升到 6545 req/s，独立确认轮达到 6884 req/s
- [x] 空闲 MONITOR 快速路径：活动订阅计数为零时跳过监控行构造，正式 `SET 1KiB` 从 6545 提升到 14386 req/s，独立确认轮达到 15848 req/s 和 Redis 的 1.29x
- [x] 空闲阻塞客户端扫描快速路径：仅在存在已保存的 blocking 请求时扫描客户端槽；正式 `SET 1KiB` 达到 15463 req/s 和 Redis 的 1.14x，profile 中空闲扫描已消失
- [x] 空闲 buffered-client 扫描快速路径：维护持有输入字节的客户端数，计数为零时不扫描 64 个槽；半包、流水线、暂停与阻塞恢复回归通过，profile 中原 2.20% 扫描已低于 0.5%
- [x] 无效回复配置占位优化：仅 `CONFIG SET` 传播完整 `config_after`，普通回复和批处理结果改用零占位；profile 中原 3.25% `default_config` 构造已低于 0.5%
- [x] 单线程 async allocator 快速模式：保留默认 pthread TSD 语义，server loop 显式使用直达 allocator 指针；profile 中原 2.24% pthread registry/TSD 查找已低于 0.5%
- [x] 事件批次时间缓存：server loop 统一刷新 `event_time_ms`，同一批次的命令、暂停和客户端交互时间复用缓存；完整单测/集成/redis-cli 通过，正式 `PING` 达 Redis 0.97x，20K `SET 1KiB` profile 中时钟调用栈样本占比从 5.66% 降到 4.80%
- [x] 1KiB 字符串值 arena：1025B SDS payload 由 1032B 专用 class 按 62 块页批量分配；完整单测/集成/redis-cli 通过，20K `SET 1KiB` profile 中 `find_chunk` 从 6.69% 降到 2.50%、`owns_ptr` 从 3.03% 降到 0.5% 报告阈值以下，采样吞吐从 11287 提升到 11621 req/s
- [x] 命令 runtime 元数据缓存：`RedisServer` 持久保存 `CommandRuntimeInfo`，动态字段逐请求刷新，完整配置仅在启动参数、`CONFIG SET` 和复制角色切换时同步；完整单测/集成/redis-cli 通过，20K `SET 1KiB` 从 11621 提升到 12853 req/s，原 0.61% `server_runtime_info` 低于 0.5% 报告阈值
- [x] 空闲 AOF rewrite 大栈门控：server loop 仅在 rewrite 已请求或进行中时进入约 321KiB 栈帧的状态机；完整单测/集成/redis-cli 通过，GET 16B/1KiB profile 中原 2.15%/2.62% 热点低于 0.4%，1KiB 采样周期下降 5.6%，正式五项吞吐均超过同机 Redis
- [x] 命令回复配置状态缩窄：`CommandReply` 从 1176B 降到 192B，执行器栈帧从 `0x4a8` 降到 `0xd8`；`CONFIG SET` 候选值改由 persistent runtime 暂存并在响应编码成功后提交，同批 `CONFIG GET` 可见且输出缓冲失败不提交；GET 16B 匹配 profile 周期下降 3.4%，GET 1KiB 相关回复 helper 均低于 0.4%
- [x] backlog 物理压缩原地复用：SDS 新增保留容量的前缀丢弃操作，backlog 达阈值后原地前移有效窗口，不再 `sds_range` 分配新缓冲；长周期单测确认跨压缩阈值零新增 allocator 分配，PSYNC/full/incremental/consistency 集成通过；固定 key 100K `SET 1KiB` 对父提交吞吐提升 10.0%、server cycles 下降 12.8%，`find_chunk` 从 8.44% 降到 0.10%
- [x] 常见 RESP 命令数组借用解析：三参数内的扁平 Bulk/Simple String 数组直接写入连接栈 `RespValue` 槽，解析结果显式记录 elements 所有权，复杂类型和更大 argc 回退通用 parser；`PING` 连接单测确认零 parser allocator 分配，固定 CPU 200K 父提交对比吞吐提升 3.1%、cycles 下降 3.4%、instructions 下降 2.3%
- [x] ACL 命令拒绝空表快速路径：默认用户和 named user 维护活跃 `-command` 规则计数，新增、`+command` 删除、`resetcommands` 与用户重置保持同步，计数为零时跳过固定 deny 表扫描；默认/命名用户计数单测、完整集成和 redis-cli 通过，固定 CPU 200K `PING` 对父提交吞吐提升 2.4%、cycles 下降 1.35%、instructions 下降 1.46%
- [x] 全小对象 class arena：16B 到 1032B 的 Slab class 在 freelist 为空时按接近 64KiB 的页批量补充，持续唯一 key 的 `SET 16B` 不再为 key/value/dict entry 逐块进入底层 allocator；同条件 20K 父提交对比吞吐从 14703 提升到 19558 req/s（+33.0%），p99 从 238us 降到 106us（-55.5%），RSS 从 144452KiB 降到 119784KiB（-17.1%），完整单测/集成/redis-cli 与正式 guard 通过
- [x] ACL 完全开放用户快速路径：主命令入口只解析一次当前用户名；当 deny command/category 计数均为零且 `allkeys/allchannels` 开启时，直接跳过命令、key、channel 三组详细 ACL 检查，有任一限制时保持原拒绝语义；两轮 50K 父提交 A/B 均值中 SET16/GET16/SET1K/GET1K 吞吐分别提升 6.7%/4.0%/6.1%/4.0%，PING 的 Redis 归一化比值提升 0.3%，完整单测、33 项集成、redis-cli 和 50K 正式 guard 通过
- [x] 隐式默认用户 ACL 选择快速路径：事务为空或用户名长度为零时直接读取默认用户 deny 计数及 `allkeys/allchannels` 状态，不再构造用户名切片并比较 `default`；两轮固定 CPU 200K `PING` 中 instructions/branches/cycles 均值分别下降 4.0%/5.6%/3.1%，完整单测、33 项集成、redis-cli 和两轮 50K 正式 guard 通过
- [x] 空 `requirepass` 认证门禁快速路径：普通命令用 NUL 终止密码缓冲首字节判断是否启用认证，不再构造并扫描完整 128B C 字符串切片；AUTH/HELLO AUTH 保持完整密码比较，两轮固定 CPU 200K `PING` 中 instructions/branches/cycles 均值分别下降 0.69%/0.74%/3.73%，完整单测、33 项集成、redis-cli 和正式 guard 通过
- [x] 默认 master 复制维护角色门控：server loop 仅在 `role_replica` 时调用 full sync、incremental sync 和 heartbeat 三个状态机，各函数内部防御性角色检查与副本时序保持不变；固定 CPU 200K `GET 1KiB` 父提交 A/B 吞吐提升 2.17%、p99 从 81.5us 降到 77.0us，cycles/instructions/branches 分别下降 0.25%/0.36%/0.29%，复采样中三个目标函数均无样本，源码契约、单元、复制心跳和正式 50K 总体 guard 通过
- [x] RESP2 Pub/Sub 模式判断调用点内联：唯一调用点直接短路检查事务、订阅计数和 RESP 版本，普通未订阅命令不再进入 29 字节 helper；RESP2 已订阅命令限制、允许 PING/退订和 RESP3 已订阅普通 GET 的单元与 TCP Pub/Sub smoke 通过。两组相反顺序固定 CPU 200K `GET 1KiB` A/B 合并吞吐提升 2.34%，`perf stat` instructions/branches 下降 0.17%/0.20%，不可变与 current 50K 总体 guard 通过
- [x] Dict key 等值包装层删除：桶查找和删除在 hash 命中后直接把 entry SDS slice 交给 `bytes_eq`，不再调用 28 字节尾跳 helper；碰撞链和渐进 rehash 语义由完整单元覆盖。固定 CPU 200K `GET 1KiB` 的 8 轮墙钟合并仅提升 0.67%，`perf stat` cycles/instructions/branches 下降 2.48%/0.09%/0.09%，不可变与 current 50K 总体 guard 通过
- [x] 固定空回复嵌套构造删除：`connection_empty_reply` 直接写出与通用构造器相同的全部字段，不再额外调用 `connection_make_reply` 构造并复制 200 字节临时对象；release 文本段缩小 208 字节，四组反向固定 CPU 200K `GET 1KiB` 的 instrumented throughput 提升 0.56%，cycles/instructions/branches 下降 0.71%/0.20%/0.11%，完整单测、33 项集成和正式 50K 总体 guard 通过
- [x] 事件循环等待前时间复用：维护阶段前已刷新的 `now_ms` 直接用于 cron/epoll timeout 计算，epoll 返回后仍刷新事件时间；完整单元、33 项集成和时间敏感 smoke 通过。两组反向顺序固定 CPU 200K `GET 1KiB` 中吞吐提升 0.71%，cycles/instructions/branches 下降 3.07%/2.39%/2.53%，不可变与 current 50K 总体 guard 通过
- [x] RESP 连续写入容量预检：`connection_append_bytes`、`connection_append_crlf` 和非零 `connection_append_u64` 先校验完整剩余容量，再直接写入并一次更新位置；19 位 i64 精确容量和不足容量单测、完整 33 项集成通过。两组反向 100K 墙钟吞吐提升 1.10%；四组反向固定 CPU 200K `perf stat` 吞吐提升 0.73%，cycles/instructions/branches/branch-misses 下降 0.99%/0.34%/0.51%/1.05%，p99 下降 0.39%，复采样中原 0.36% `connection_append_byte` 热点消失；不可变与复跑 current 50K 总体 guard 通过
- [x] 零拷贝结果包装层删除：server 直接调用 `connection_process_input_with_runtime_with_aof_and_rewrite_and_transaction_zero_copy_at`，成功解包后同步关闭标志，删除唯一调用且逐字段重建结果的 wrapper；release 文本段净减 72 字节，两组相反顺序固定 CPU 200K 合并 instructions/branches 下降 0.251%/0.231%，完整单元、33 项集成和两轮正式 50K 总体 guard 通过
- [x] 空 expires 惰性检查快速路径：expires 主表和 rehash 表均无元素时，`key_is_expired` 在 CRC64 与字典查找前直接返回；保留真实 TTL、rehash 与清空后空表语义。两组反向固定 CPU 100K `GET 1KiB` 墙钟吞吐提升 7.80%，两组反向 200K `perf stat` 的 cycles/instructions/branches 分别下降 9.47%/4.63%/2.26%，完整单元、33 项集成和不可变/current 50K 总体 guard 通过
- [x] GET 字符串结果直达：命中对象后在 GET 调用点直接校验 `object_string` 并构造 value slice，保留 missing Null Bulk 和非字符串 WRONGTYPE，不再调用通用错误联合 helper；release 的 GET 函数从 702 字节降到 691 字节。两组相反顺序固定 CPU 200K `perf stat` 共 8 次测量中吞吐提升 1.04%，cycles/instructions/branches 下降 0.66%/1.02%/1.02%，完整单元、33 项集成、零丢样 profile 和不可变/current 50K 全部 guard 通过
- [x] GET AOF 判定门控：普通顶层 GET 在 AOF writer 存在时直接按 `command_get` 跳过完整 AOF 决策 helper，脚本、事务、写命令与 `SORT ... STORE` 保持原路径；单测断言 GET 不增长 AOF buffer，并验证连接层 RPUSH + SORT STORE 可回放。8 轮反向固定 CPU 200K 墙钟吞吐提升 2.48%、p99 下降 7.63%，`perf stat` instructions/branches 下降 0.64%/0.68%，零丢样 11K profile 中目标 helper 消失，不可变/current 50K 三类 guard 全部通过
- [x] 零拷贝 writev 首次直写：大 bulk GET 先直接运行共享非阻塞 writev 进度 helper，完整首写不再构造 Future，部分写/EAGAIN 才携带精确 head/body/tail offset 进入 async continuation；8 轮反向固定 CPU 200K 吞吐提升 1.51%、p99 下降 4.01%，cycles/instructions/branches 下降 1.25%/2.94%/3.62%，慢读 EAGAIN 集成与不可变/current 50K 三类 guard 全部通过
- [ ] `v0.9.3` 起：在真实性问题收敛后，继续补 Redis Open Source 单机核心缺口，而不是先扩模块命令

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
| `v0.9.1` | 审计整改与真实性修复 | 修正文档/控制面/测试/benchmark 口径，统一版本号，恢复当前 `HEAD` 可复核性 | 讲真话、能复核 |
| `v0.9.2` | 单机核心缺口补齐 I | blocking list/zset、常用 server/connection 缺口、脚本基础、命令真值模型 | 核心命令不再“有名无实” |
| `v0.9.3` | 单机核心缺口补齐 II | Streams、Functions/Script 收口、ACL/运维面第一批、复制/持久化边界深化 | Redis Open Source 单机功能面继续收敛 |
| `v0.9.4` | 性能与稳定性收敛 | benchmark guard 恢复、release build 基线、长时运行、故障恢复 | 当前 `HEAD` 再次可量化 |
| `v0.9.5` | 首个单机封版候选 | 核心命令矩阵、文档、性能、运维边界综合收口 | v1.0.0 发布候选 |
| `v0.9.6`, ... | 后续封版候选迭代 | 未达 v1.0.0 条件时继续 patch 位递增 | 补缺口、不扩范围 |
| `v1.0.0` | 单机版封版 | Redis Open Source 单机核心功能完整、性能达标、文档齐全 | 可发布、可生产评估 |
| `v1.1.0+` | 模块与集群后续规划 | 模块命令、集群语义、gossip、failover、resharding | `v1.0.0` 之后启动 |

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
- [x] `REPLCONF` no-op 握手兼容面
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
- [x] AOF 分层写入：不超过 64KiB 的追加批次统一进入写缓冲，由容量或 server cron 触发 flush；超过 64KiB 的聚合批次先 flush 再直接写，避免 1KiB SET 每条触发 `write(2)`
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

- [x] 以 Redis 官方 Commands Reference 建立命令全集基线，记录命令名、功能组、arity、flags、key spec、ACL category、是否模式相关
- [x] 每个命令标记为 `full`、`partial`、`standalone-error`、`alias` 或 `deferred`
- [x] `deferred` 命令必须绑定目标版本；不能进入 `v1.0.0` 封版状态
- [ ] Cluster/Sentinel 等模式相关命令在 `v1.0.0` 前至少实现 standalone 兼容行为或明确错误，完整分布式语义进入 `v1.1.0+`
- [x] 兼容矩阵必须由 `COMMAND` / `COMMAND DOCS` / `COMMAND INFO` 等控制面命令共享，避免文档和运行时命令表分叉

非目标：

- [ ] `v1.0.0` 之前不继续扩展 Redis Cluster gossip、failover、resharding、正式集群 benchmark
- [ ] `v1.0.0` 之前不把已有 `src/cluster/*` 作为主线能力继续放大；只做必要兼容维护和 standalone 兼容命令响应，避免破坏现有测试

## 16. `v0.9.0`：单机核心命令补齐

### T. 基础类型与管理命令

- [x] String 第一批：`APPEND`、`STRLEN`、`GETDEL`、`DELEX`（`IFEQ/IFNE` value 条件与 `IFDEQ/IFDNE` 短字符串 digest 条件）
- [x] String 第二批计数：`INCR`、`DECR`、`INCRBY`、`DECRBY`
- [x] String 第三批原子写入：`GETSET`、`SETNX`、`SETEX`
- [x] String 第四批多 key：`MGET`、`MSET`、`MSETNX`
- [x] String 多 key TTL partial：`MSETEX`（`NX/XX`、`EX/PX/EXAT/PXAT/KEEPTTL`）
- [x] String LCS partial：`LCS key1 key2 [LEN|IDX [MINMATCHLEN n] [WITHMATCHLEN]]`，大输入保留 4096 字节 partial guard
- [x] String 第五批范围读写：`SETRANGE`、`GETRANGE`、`SUBSTR` alias
- [x] String 第六批浮点计数：`INCRBYFLOAT`
- [x] String INCREX partial：整数模式支持 `BYINT`、浮点模式支持 `BYFLOAT`，覆盖 `LBOUND/UBOUND`、`SATURATE`、`EX/PX/EXAT/PXAT/PERSIST` 与 `ENX`
- [x] String DIGEST partial：`DIGEST key` 支持 128 字节以内 String 的 XXH3_64 十六进制 digest，missing 返回 Null Bulk，错类型返回 `WRONGTYPE`；`DELEX IFDEQ/IFDNE` 复用同一短字符串 digest 口径
- [x] Hash 第一批数值：`HINCRBY`、`HINCRBYFLOAT`
- [x] Hash 第二批视图：`HKEYS`、`HVALS`、`HGETALL`、`HRANDFIELD`
- [x] Hash 第三批扫描：`HSCAN`
- [x] Hash 字段扩展：`HGETDEL`
- [x] Hash legacy alias：`HMSET` 多 field 写入返回 `OK`，覆盖错类型、参数数量、`COMMAND*` 和 redis-py/redis-cli smoke
- [x] Hash field TTL 运行期、持久化与复制传播语义：`HGETEX`、`HSETEX`、`HEXPIRE`、`HPEXPIRE`、`HEXPIREAT`、`HPEXPIREAT`、`HTTL`、`HPTTL`、`HEXPIRETIME`、`HPEXPIRETIME`、`HPERSIST` 已补 field 级绝对毫秒过期元数据、`NX/XX/GT/LT` 条件、`KEEPTTL/PERSIST`、正 TTL/过期时间查询、`HPERSIST` 清理、到期 field lazy expire、普通 hash 写入清理目标 field TTL、RDB save/load、DUMP/RESTORE bytes、AOF append、AOF rewrite 与复制 backlog 保存 field TTL
- [x] List 第一批基础：`RPUSH`、`RPOP`、`LINDEX`、`LSET`、`LLEN`
- [x] List 第二批：`LINSERT`、`LTRIM`、`LREM`
- [x] List 第三批条件写入与定位：`LPUSHX`、`RPUSHX`、`LPOS`
- [x] Set 第一批随机取值：`SPOP`、`SRANDMEMBER`
- [x] Set 第二批集合运算：`SINTER`、`SDIFF`、`SUNION`
- [x] Set 第三批集合写回：`SINTERSTORE`、`SDIFFSTORE`、`SUNIONSTORE`
- [x] Set 第四批读路径：`SCARD`、`SISMEMBER`、`SMISMEMBER`、`SSCAN`
- [x] ZSet 第一批数值与计数：`ZINCRBY`、`ZCARD`、`ZCOUNT`
- [x] ZSet 第二批范围读取：`ZRANGE REV/WITHSCORES/BYSCORE/BYLEX`、`ZLEXCOUNT`、`ZRANGEBYLEX`、`ZREVRANGE WITHSCORES/BYSCORE/BYLEX/LIMIT`、`ZREVRANGEBYLEX`、`ZRANGEBYSCORE WITHSCORES/LIMIT`、`ZREVRANGEBYSCORE WITHSCORES/LIMIT`
- [x] ZSet 第三批范围删除、扫描与读/写路径补齐：`ZREMRANGEBYLEX`、`ZREMRANGEBYRANK`、`ZREMRANGEBYSCORE`、`ZRANGESTORE REV/BYSCORE/BYLEX/LIMIT`、`ZSCAN`、`ZRANDMEMBER`、`ZDIFF`、`ZDIFFSTORE`、`ZINTER`、`ZINTERCARD`、`ZINTERSTORE`、`ZUNION`、`ZUNIONSTORE`，其中多 key 聚合命令支持整数 `WEIGHTS` 与 `AGGREGATE SUM|MIN|MAX`
- [x] Key/Server 第一批：`ECHO`、`TYPE`、`DBSIZE`
- [x] Key/Server 第二批过期毫秒语义：`PEXPIRE`、`PERSIST`、`PTTL`
- [x] Key/Server 第三批：`RENAME`、`RENAMENX`、`LASTSAVE`
- [x] Key/Server 第四批：`FLUSHDB`、`FLUSHALL`
- [x] Key/Server 第五批：`PEXPIREAT`
- [x] Key/Server 第六批：`DUMP`、`RESTORE`
- [x] Key/Server 第七批：`SELECT`、`OBJECT`
- [x] Key/Server 第八批：`MOVE`、`SWAPDB`
- [x] Key/Server 第九批：`WAIT`、`WAITAOF`
- [x] Key/Server 第十批通用 key 管理：`TOUCH`、`UNLINK`
- [x] Key/Server 第十一批模式读取：`KEYS`
- [x] Key/Server 第十二批只读排序：`SORT_RO`
- [x] Key/Server 第十批：`SORT`
- [x] Key/Server 第十三批复制：`COPY`
- [x] Key/Server 第十四批恢复迁移入口：`RESTORE-ASKING`
- [x] Key/Server 第十五批诊断：`LOLWUT`
- [x] Security baseline：`AUTH`、`requirepass`、`SHUTDOWN`

验收项：

- 新增命令必须有单元测试、错误路径测试和 redis-py/redis-cli 兼容 smoke
- 新增写命令必须覆盖 AOF、RDB、复制 backlog、WATCH 版本推进和 maxmemory 边界
- 现有 `make test`、`make test-integration`、`make benchmark-v0.8.1` 回归护栏不退化

## 17. `v0.9.1`：审计整改与真实性修复

### U1. 审计确认的历史沉淀

- [x] 共享命令目录、`COMMAND*` 第一批、TTL 扩展、Hash/Set/Key/ROLE/PubSub/CONFIG/CLIENT/RESET 等代码已经在主线落地
- [x] `v0.9.0` 与 `v0.9.1` 前三批的历史里程碑文档和测试脚本已经积累起来
- [x] 当前工程仍有可复用的 unit / integration / benchmark 基础设施

### U2. 当前必须先修的 P0 问题

- [x] `COMMAND` 真值修复：`COMMAND` / `INFO` / `DOCS` / `LIST` 已按真实执行面隐藏未实现命令，并补齐当前 `CLIENT/CONFIG` 已实现子命令的矩阵状态
- [x] 目录统计分层：已把 Redis Open Source 单机核心、模式命令、模块命令分开统计，不再用总条目数代表当前单机完成度
- [x] 版本统一：banner、`HELLO`、`INFO server`、README、DoD、测试断言已统一到 `v0.9.3-dev`
- [x] `make test-integration` 恢复：修正 `maxmemory` 相关测试口径，使其与 Redis startup memory 语义对齐
- [x] `make benchmark-v0.8.1` 稳定：性能 guard 已升级为“绝对基线 + 同机 Redis 归一化兜底”，当前复跑已恢复稳定通过
- [x] `verify_definition_of_done.sh` 重新转绿，确保一键验证再次可用
- [x] README / TODO / DoD / 审计报告交叉引用完成，停止继续沿用“当前已实锤到 v0.9.1”的旧表述

验收项：

- 审计报告中的 P0 问题全部转为有代码/测试/文档证据的已关闭项
- `COMMAND INFO <deferred-command>` 与真实执行结果不再互相矛盾
- 当前 `HEAD` 的测试和 benchmark 结果能被 README 与 DoD 原样复述，不需要靠历史报告兜底

## 18. `v0.9.2`：单机核心缺口补齐 I

### U3. 先补 Redis Open Source 核心，而不是先扩模块

- [x] Blocking list / zset：已补 `BLPOP`、`BRPOP`、`BRPOPLPUSH`、`BLMOVE`、`BLMPOP`、`BZPOPMIN`、`BZPOPMAX`、`BZMPOP`
- [x] 常用 list / zset 缺口：已补 `LMOVE`、`LMPOP`、`RPOPLPUSH`、`ZRANK`、`ZREVRANK`、`ZSCORE`、`ZMSCORE`、`ZPOPMIN`、`ZPOPMAX`、`ZMPOP`、`ZLEXCOUNT`、`ZRANGEBYLEX`、`ZRANGESTORE REV/BYSCORE/BYLEX/LIMIT`、`ZREMRANGEBYLEX`、`ZREVRANGE`、`ZREVRANGEBYLEX`、`ZRANDMEMBER`、`ZDIFF`、`ZDIFFSTORE`、`ZINTER`、`ZINTERCARD`、`ZINTERSTORE`、`ZUNION`、`ZUNIONSTORE`，多 key 聚合命令支持整数 `WEIGHTS` 与 `AGGREGATE SUM|MIN|MAX`
- [x] 常用 bitmap / bitfield：已补 `SETBIT`、`GETBIT`、`BITCOUNT`、`BITPOS`、`BITOP`、`BITFIELD`、`BITFIELD_RO`，并收口 `BITOP NOT` 多 source 的完整错误文本
- [x] 常用 HLL / GEO / Key：已补 `PFADD`、`PFCOUNT`、`PFMERGE`（exact set-backed partial）、`PFSELFTEST`（no-op self-test partial）、`PFDEBUG`（standalone-error），以及 `GEOADD`、`GEODIST`、`GEOHASH`、`GEOPOS`、`GEOSEARCH`、`GEOSEARCHSTORE`、`GEORADIUS`、`GEORADIUS_RO`、`GEORADIUSBYMEMBER`、`GEORADIUSBYMEMBER_RO`（exact zset-backed partial；`GEOSEARCHSTORE` 和写型 legacy radius 的 `STOREDIST` 当前写入整数距离 score；missing center member 完整错误文本已收口），`COPY`（当前单 DB 深拷贝 partial，支持 `REPLACE`、`DB 0` 与 TTL 保留），`RESTORE-ASKING`（复用 `RESTORE` 的单 DB RDB payload 写入 partial，支持 `REPLACE` 覆盖、`ABSTTL` 与 `IDLETIME`/`FREQ` 元数据）
- [x] Scripting 第一批：已补 `EVAL`、`EVALSHA`、`SCRIPT LOAD/EXISTS/FLUSH`，当前为 single-call script subset partial
- [x] Server / Connection 缺口第一批：已补 `MEMORY HELP/STATS/USAGE/DOCTOR/MALLOC-STATS/PURGE`（runtime-approx/no-op partial）、`SLOWLOG HELP/LEN/GET/RESET`（in-process ring partial）、`LATENCY HELP/LATEST/HISTORY/RESET/DOCTOR/HISTOGRAM/GRAPH`（command-event history + top-level command histogram partial）与 `MONITOR`（流式命令观测 partial）

验收项：

- 每个新增命令都要覆盖正常路径、参数错误、错类型、空结果、TTL、AOF/RDB、复制、事务和 `maxmemory` 边界
- 新命令必须进入“真实可执行面”统计；不允许只改命令目录状态
- 新命令默认先做 Redis Open Source 单机核心，不把 JSON/Search/Time Series/Vector 等模块命令插队到当前主线

## 19. `v0.9.3`：单机核心缺口补齐 II 与运维第一批

### U4. Streams、Functions、安全与运维面

- [x] Streams 第一批：已补 `XADD`、`XLEN`、`XRANGE`、`XREVRANGE`、`XREAD`，当前为 list-backed、非阻塞基础 stream partial；`XADD` 支持 `NOMKSTREAM` 与 `MAXLEN|MINID [=|~] threshold [LIMIT count]` 追加后头部裁剪；普通 AOF append 对 `XADD *` 回放会重新生成 ID，RDB 与 AOF rewrite 保存显式 ID
- [x] Streams 第二批：`XTRIM` 已补 `MAXLEN|MINID [=|~] threshold [LIMIT count]` 基础裁剪 partial，`XDEL` 已补精确 ID 删除 partial，`XCFGSET` 已补 `IDMP-DURATION` / `IDMP-MAXSIZE` no-op 配置校验 partial，`XIDMPRECORD` 已补 entry IDMP 记录 no-op 校验 partial，`XDELEX` 已补 `KEEPREF` / `DELREF` / `ACKED` 与 `IDS` per-id 状态 partial，`XGROUP HELP` / `XINFO HELP` 已补帮助兼容面，`XACK` / `XACKDEL` / `XNACK` / `XAUTOCLAIM` / `XCLAIM` / `XPENDING` 已补无 group 时的 `NOGROUP` 错误面 partial，`XREADGROUP` 已补非阻塞语法校验与无 group 时的 `NOGROUP` 错误面 partial，`XGROUP CREATE` 已补 key/type 校验与明确未支持错误 partial，`XGROUP CREATECONSUMER` / `XGROUP DELCONSUMER` 已补无 group 时的 `NOGROUP` 错误面 partial，`XGROUP DESTROY` 已补 empty-state 返回 `0` partial，`XGROUP SETID` 已补无 group 时的 `NOGROUP` 错误面 partial，`XSETID` 已补 key/type/ID 校验、`last-generated-id` 写入与倒退 ID 拒绝 partial，`XINFO STREAM` 已补 key-only 基础元数据和 `FULL [COUNT count]` entry 明细 partial，`XINFO GROUPS` 已补 empty-state 空数组 partial，`XINFO CONSUMERS` 已补无 group 时的 `NOGROUP` 错误面 partial，并已收口非法 ID、倒退 ID、缺失 key 与 `XGROUP CREATE` arity 的完整错误文本；真实 consumer group 状态仍待后续批次补齐
- [ ] Functions / Script 收口：只读脚本第一批已补 `EVAL_RO` / `EVALSHA_RO` single-call subset partial，并补齐 `SORT ... STORE` 等参数驱动写路径拒绝，`SCRIPT DEBUG` 已补 no-op 兼容面，`SCRIPT KILL` 已补无运行脚本 `NOTBUSY` 错误面 partial，脚本缓存、错误中止与实际数据命令的 AOF/复制传播边界已补；Functions 第一批已补 `FUNCTION HELP/LIST/STATS/FLUSH/DELETE/LOAD/DUMP/RESTORE/KILL`，并完成单 library/最多 8 个位置参数或 table 形式 `redis.register_function(... return redis.call(...))` 子集的进程内存储与 `FCALL/FCALL_RO` 执行，table 注册支持 bounded description、`no-writes` flag、`LIST` 元数据真值和运行时拒写，其他 flags、library 元数据 RDB/AOF/复制持久化和完整 Lua engine 仍待后续批次；Hash field TTL 运行期、持久化与复制传播语义已补 `HGETEX/HSETEX/HEXPIRE/HPEXPIRE/HEXPIREAT/HPEXPIREAT/HTTL/HPTTL/HEXPIRETIME/HPEXPIRETIME/HPERSIST`
- [ ] ACL 第一批：`ACL CAT/DELUSER/DRYRUN/GENPASS/GETUSER/HELP/LIST/LOAD/LOG/SAVE/SETUSER/USERS/WHOAMI` 默认用户控制面 partial 已补，默认用户命令级 `+cmd/-cmd` deny list、分类级 `+@category/-@category` deny list、`resetcommands` 默认命令规则恢复、`allkeys/resetkeys/~pattern` 固定 key range 权限 partial、`allchannels/resetchannels/&pattern` Pub/Sub channel 权限 partial、`clearselectors/resetselectors` 兼容 no-op、`requirepass` 只读哈希标记回显、真实连接 `NOPERM` 最小权限拒绝路径、命令/key/channel 权限拒绝 `ACL LOG [count]/RESET` 基础审计字段与真实 client id/addr/laddr、named user 进程内元数据创建/列出/详情/dry-run 存在性检查/删除、named user 命令级 `+cmd/-cmd` 与分类级 `+@category/-@category` deny list、named user key/channel pattern partial、`>password` 口令写入、`AUTH username password` / `HELLO ... AUTH username password` 认证和 `ACL WHOAMI` 当前用户名回显已补，后续继续补 selector 权限、ACL 文件加载保存和 Redis 动态 key spec / movablekeys 完整 key 解析
- [ ] 运维与诊断第一批：`CONFIG` 余量（`timeout` 已补运行时回读、重写和普通空闲连接关闭，`latency-tracking` 运行时开关、`latency-monitor-threshold` 事件门限、`slowlog-log-slower-than` 慢日志门限和 `slowlog-max-len` 保留长度已补）、`CLIENT` 余量（`KILL ID ... SKIPME yes|no` partial、`REPLY` 命令回复抑制 partial、`UNBLOCK` 阻塞 pop 等待解除 partial、`PAUSE WRITE` 读写区分及非法 timeout 完整错误文本、`TRACKING` 连接级 flags/redirect/`BCAST PREFIX` 状态、`CACHING` / `NO-EVICT` 连接级兼容标志与 `NO-TOUCH` 对象访问 LRU/LFU touch 抑制已补）、`MEMORY` 观测（`MALLOC-STATS` runtime-approx、`PURGE` no-op 兼容面与容器 arity 完整错误文本已补）、`SLOWLOG` 容器 arity 完整错误文本、`LATENCY`（含 top-level 与容器子命令直方图）、`MONITOR`、`MODULE HELP/LIST` 空模块兼容面及容器 arity 完整错误文本已补，`MODULE LOAD/LOADEX/UNLOAD` 与 Redis Array `AR*`、RediSearch `FT.*`、RedisJSON `JSON.*`、Redis Vector Set `V*`、RedisBloom `BF.*` / `CF.*` / `CMS.*` / `TOPK.*` / `TDIGEST.*`、RedisTimeSeries `TS.*` 已按单机安全 profile 收口为 `standalone-error`，`DEBUG` 已按单机安全 profile 收口为 `standalone-error`，`HOTKEYS HELP/GET/RESET/START/STOP` 已补空采样/no-op 诊断兼容面 partial，Sharded Pub/Sub 已补 `SSUBSCRIBE/SUNSUBSCRIBE/SPUBLISH` standalone 连接级 partial 与 `PUBSUB SHARDCHANNELS/SHARDNUMSUB` 真值，后续继续补配置、客户端与观测真值
- [ ] 复制/持久化深化：RDB 二进制兼容推进、AOF rewrite 压测、复制断线重连、`SYNC` legacy full-sync bulk snapshot partial 已补、`REPLCONF` 真实 ACK/GETACK 语义、`WAIT` / `WAITAOF` 真实等待语义、`MIGRATE` 当前已按单机安全 profile 收口为 `standalone-error`，`FAILOVER` 当前已收口为无副本/未支持 controlled failover 错误面，后续再补真实 failover 状态机、只读副本限制

验收项：

- Streams / Script / ACL / 运维命令必须给出清楚的“当前支持边界”与“不支持边界”
- 不允许只做 happy path；必须补错误语义、持久化、复制和权限边界
- 完成后，Redis Open Source 单机核心缺口应显著收敛，模块能力继续后置

## 20. `v0.9.4` 起：性能、稳定性收敛与后续封版候选

### V. `v1.0.0` 前置收敛

- [ ] release build benchmark 模式，固定硬件、Redis 对照版本、持久化配置、并发、pipeline 和数据集
- [ ] 核心命令吞吐、p95/p99、RSS 至少恢复到当前 guard 要求之上，并持续向 Redis 对照靠近
- [ ] `SET`/写路径、RDB/AOF rewrite、复制增量、Streams 等重路径单独 benchmark
- [ ] 长时间运行、内存泄漏、慢客户端、半包/粘包、崩溃恢复和磁盘损坏矩阵
- [ ] API、部署、运维、安全、性能、已知限制和迁移指南文档齐全
- [ ] Redis Open Source 单机核心矩阵中不再存在“文档说有、执行没有、测试没覆盖”的真值裂缝

如果 `v0.9.4` 未达到 `v1.0.0` 封版条件，继续按最后一位顺序增加版本号，使用 `v0.9.5`、`v0.9.6` 等版本补齐缺口；这些版本不新增集群主线，也不把模块能力重新塞回当前核心封版门槛。

`v1.0.0` 封版条件：

- [ ] 单机计划内功能已完成并有测试证据
- [ ] Redis Open Source 单机核心兼容矩阵无 `deferred`；模式相关命令达到 `full` 或 `standalone-error`
- [ ] 模块命令若仍处于 `deferred`，必须与单机封版结论分开统计和说明
- [ ] 兼容矩阵清楚标记所有 Redis 差异，不存在未说明的核心语义缺口
- [ ] 性能达到当前 target，且没有 P0/P1 稳定性缺陷
- [ ] 发布说明、DoD、benchmark 和测试报告齐全

## 21. `v1.1.0+`：模块与集群后续规划

`v1.0.0` 发布前不启动新的集群主线，也不把模块能力重新塞回当前单机封版门槛。发布后再基于稳定单机内核重新评审以下方向：

- [ ] 模块能力：JSON / Search / Time Series / Bloom / Cuckoo / CMS / Top-K / t-digest / Vector 的独立设计与实现
- [ ] 集群语义：多 key 同槽校验、`CROSSSLOT`、`ASKING`、`MOVED/ASK` 完整边界
- [ ] 集群成员：cluster bus、节点握手、gossip、拓扑传播、`PFAIL/FAIL`
- [ ] 集群故障转移：replica 归属、config epoch、failover 选择、旧 master 恢复处理
- [ ] 集群重分片：`ADDSLOTS/DELSLOTS`、迁移状态机、key 迁移闭环、正式集群 benchmark

## 22. 风险登记

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
| R9 | 文档、`COMMAND*`、测试与 benchmark 再次脱节 | 高 | 高 | 把真实性检查纳入默认回归，任何“当前状态”表述都以当前 `HEAD` 实测结果为准 |
