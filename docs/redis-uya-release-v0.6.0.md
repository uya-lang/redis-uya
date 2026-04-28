# redis-uya release v0.6.0

> 版本: v0.6.0
> 日期: 2026-04-29
> 状态: 收口完成（仍未打正式 tag）

## 1. 阶段定位

`v0.6.0` 聚焦内存与性能控制，在 `v0.5.0` 协议与控制面增强基础上补齐 `maxmemory` 基线、运行时淘汰策略、allocator 统计观测、Slab 小对象缓存，以及内存压力与淘汰回归。

## 2. 已完成能力

- `maxmemory` noeviction 基线：启动参数可配置最大内存，超预算增量写命令返回 OOM 且不落库
- `allkeys-lru`：对象记录访问时间，读写触碰 LRU，超预算写入可淘汰最久未访问 key
- `allkeys-lfu`：对象记录访问计数，读写递增 LFU，同频次用 LRU 打破平局
- `volatile-lru` / `volatile-lfu` / `volatile-ttl`：只从带 TTL 的 key 中选择候选，永久 key 不被 volatile 策略淘汰
- `INFO memory` allocator 统计：当前使用、峰值、累计分配、累计释放、累计/活跃分配块数、Slab 缓存与复用计数
- Slab 小对象缓存基线：16B 到 1KB 分级 freelist，每个 class 最多缓存 64 个空闲块
- 内存压力与淘汰回归：真实 TCP 循环写入覆盖 noeviction、allkeys-lru、allkeys-lfu 与 volatile-ttl

## 3. 验证入口

- `make test`
- `make build`
- `python3 tests/integration/maxmemory_noeviction.py`
- `python3 tests/integration/maxmemory_allkeys_lru.py`
- `python3 tests/integration/maxmemory_allkeys_lfu.py`
- `python3 tests/integration/maxmemory_volatile_policies.py`
- `python3 tests/integration/memory_info_stats.py`
- `python3 tests/integration/maxmemory_pressure.py`
- `make test-integration`
- `make test-redis-cli`
- `git diff --check`

## 4. 发布前检查

- 工作区必须干净：`git status --short`
- 默认构建、单元测试、完整 Python 集成测试和 `redis-cli` smoke 必须通过
- v0.6.0 新增内存脚本必须纳入 `make test-integration`
- 发布文档、DoD、TODO、API、ARCHITECTURE、QUICKSTART 和根 README 必须保持一致
- 如需正式发布 tag，建议在干净工作区执行 `git tag -a v0.6.0 -m "redis-uya v0.6.0"`，本次收口文档未自动打 tag

## 5. 已知限制

- 当前淘汰策略仍是全量扫描基线，没有 Redis 风格采样池
- LFU 当前只有访问计数和 LRU tie-break，没有衰减周期
- 淘汰事件当前不作为独立持久化事件记录，只体现为最终数据集变化
- `used_memory` 是项目 allocator 的逻辑活跃字节统计，不等同于 OS RSS；Slab 空闲缓存通过单独字段观测
- 当前有压力回归测试，但还没有正式内存 benchmark 报告

## 6. 发布边界

`v0.6.0` 承诺：

- `v0.5.0` 协议、事务、Pub/Sub 与控制面能力继续可用
- `maxmemory` noeviction、allkeys-lru、allkeys-lfu、volatile-lru、volatile-lfu、volatile-ttl 基线
- `INFO memory` 可观测内存限制、策略、allocator 与 Slab 统计
- Slab 小对象缓存基线
- 内存压力与淘汰回归纳入 `make test-integration`

`v0.6.0` 不承诺：

- Redis 完整淘汰策略实现、采样池或 LFU 衰减
- OS RSS / jemalloc 级别统计
- 正式内存 benchmark
- 集群、Sentinel、高可用切换

## 7. 发布物

- 入口二进制：`build/redis-uya`
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
- 测试报告：[redis-uya-test-report-v0.6.0.md](./redis-uya-test-report-v0.6.0.md)
