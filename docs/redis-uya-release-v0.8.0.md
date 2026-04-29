# redis-uya release v0.8.0

> 版本: v0.8.0
> 日期: 2026-04-29
> 状态: 收口完成（仍未打正式 tag）

## 1. 阶段定位

`v0.8.0` 聚焦核心路径性能基线，在 `v0.7.0` 集群基础之上固定 `PING`、16B/1KiB `SET`、16B/1KiB `GET` 的 Redis 同机对照矩阵、吞吐/p99 回归护栏和后续性能债务队列，同时落地不改变协议、持久化、复制和集群语义的热路径优化。

## 2. 已完成能力

- 核心 benchmark 矩阵：`make benchmark-v0.8.0` 生成 `PING`、16B/1KiB `SET`、16B/1KiB `GET` 的 p50/p95/p99、吞吐、RSS 和同机 Redis 对照
- 性能回归护栏：支持 `REDIS_UYA_BENCH_BASELINE`，默认要求吞吐不低于基线 `0.90x`，p99 不高于 `max(1.15x, +100us)`
- `GET` bulk string 零拷贝响应：64B 及以上命中值使用 `writev` 分段发送 RESP 头、对象 value body 和 CRLF，小 body 保持原编码路径
- RESP2/RESP3 顶层批量解析 API：一次扫描可返回多个完整顶层帧、每帧消费长度和完整前缀总消费长度
- SIMD byte-slice 比较：新增 `@vector` 16 字节块比较/大小写比较工具，并接入命令路由、配置 token、SDS 比较和 Dict key 比较
- CRC64 表驱动更新：使用 256 项查表路径，同时保留标量路径用于正确性对照测试
- `io_uring` 主机能力评估：`make evaluate-io-uring-v0.8.0` 记录 syscall、sysctl、liburing 探测和 `production_binding=no` 边界
- 专用对象池与布局观测：`RedisObject` / `ListNode` 释放后进入专用 freelist，`INFO memory` 暴露缓存、复用计数和布局大小
- Redis 对照差距报告：`make report-v0.8.0-gaps` 生成吞吐、p99、RSS 比例矩阵和 P0/P1/P2 后续优化队列

## 3. 验证入口

- `make build`
- `make test`
- `make test-integration`
- `make test-redis-cli`
- `REDIS_UYA_BENCH_BASELINE=benchmarks/v0.8.0-performance.md REDIS_UYA_BENCH_OUT=build/v0.8.0-release.md make benchmark-v0.8.0`
- `make report-v0.8.0-gaps`
- `REDIS_UYA_IO_URING_OUT=build/v0.8.0-io-uring-release.md make evaluate-io-uring-v0.8.0`
- `bash scripts/verify_definition_of_done.sh`
- `git diff --check`

## 4. 发布前检查

- 工作区必须干净：`git status --short`
- 默认构建、单元测试、完整 Python 集成测试和 `redis-cli` smoke 必须通过
- v0.8.0 benchmark guard 必须在当前基线上通过，临时输出写入 `build/`，不覆盖已记录基线
- v0.8.0 gap report、io_uring 评估、DoD、TODO、API、ARCHITECTURE、Benchmark 格式、文档索引和根 README 必须保持一致
- 如需正式发布 tag，建议在干净工作区执行 `git tag -a v0.8.0 -m "redis-uya v0.8.0"`，本次收口文档未自动打 tag

## 5. 已知限制

- `v0.8.0` 只建立核心路径基线和可回归优化，不承诺单版超过 Redis
- 写路径仍是最大性能债务：`benchmarks/v0.8.0-gap-report.md` 将 `set_write_path` 标为 P0
- 当前 benchmark 矩阵是单线程、`client_pipeline=1`，尚未覆盖 pipelined、多连接或 release build 模式
- 批量 RESP 解析已经有 API 和测试，但生产连接循环仍按现有逐帧路径执行
- `io_uring` 只做能力评估，生产事件循环仍绑定 epoll
- 对象池优化限于 `RedisObject` 与 `ListNode`，没有改变对象编码或持久化格式

## 6. 发布边界

`v0.8.0` 承诺：

- `v0.7.0` 集群基础和此前协议、持久化、复制、内存治理能力继续可用
- 核心热路径 benchmark 与回归护栏可复现
- 大 bulk GET 响应具备零拷贝发送路径
- RESP2/RESP3 顶层批量解析 API 可用且错误释放路径有覆盖
- SIMD byte 比较和表驱动 CRC64 正确性有单元证据
- 对象池复用、布局大小和缓存计数可通过 `INFO memory` 观测
- Redis 对照差距报告与后续优化队列已固化

`v0.8.0` 不承诺：

- 完整 Redis 性能追平或超过
- release build benchmark、pipeline benchmark、多连接 benchmark
- `io_uring` 生产切换
- Redis Cluster gossip、failover、resharding、`ASKING` 和多 key 同槽校验
- 完整 RESP3 类型覆盖、Redis RDB 二进制兼容和 Redis 风格流式复制

## 7. 发布物

- 入口二进制：`build/redis-uya`
- Benchmark 基线：[v0.8.0-performance.md](../benchmarks/v0.8.0-performance.md)
- Redis 差距报告：[v0.8.0-gap-report.md](../benchmarks/v0.8.0-gap-report.md)
- `io_uring` 评估：[v0.8.0-io-uring.md](../benchmarks/v0.8.0-io-uring.md)
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- Benchmark 输出格式：[redis-uya-benchmark-format.md](./redis-uya-benchmark-format.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
- 测试报告：[redis-uya-test-report-v0.8.0.md](./redis-uya-test-report-v0.8.0.md)
