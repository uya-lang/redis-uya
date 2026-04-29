# redis-uya release v0.8.1

> 版本: v0.8.1
> 日期: 2026-04-29
> 状态: 收口完成（仍未打正式 tag）

## 1. 阶段定位

`v0.8.1` 是 `v0.8.0` 之后的写路径性能修复版，目标是先收敛 Redis 差距报告中标记为 P0 的 `set_write_path` 债务，同时保持协议、持久化、复制、事务和集群基础语义不变。

## 2. 已完成能力

- WATCH 版本懒维护：仅在存在活跃 WATCH 客户端时维护 `watch_versions`
- Dict 覆盖写单次探测：`dict_insert_with_old()` 同时完成覆盖和旧值返回，`set_key_at()` 不再先 lookup 再 insert
- AOF 分层写入：512B 以下命令进入 64KiB buffer，较大命令 flush 小缓冲后直接写
- AOF flush 边界：server cron、客户端关闭、server close 和 BGREWRITEAOF fork 前都会 flush 当前 buffer
- v0.8.1 benchmark 入口：`make benchmark-v0.8.1` 默认以 `benchmarks/v0.8.0-performance.md` 为 guard 基线，输出 `benchmarks/v0.8.1-performance.md`

## 3. 验证入口

- `make test`
- `make test-integration`
- `make benchmark-v0.8.1`
- `bash scripts/verify_definition_of_done.sh`
- `git diff --check`

## 4. 性能结论

`benchmarks/v0.8.1-performance.md` 中五个 case 的吞吐和 p99 guard 均通过：

- `ping`: 24006 req/s，p99 62us
- `set_16b`: 1297 req/s，p99 1348us
- `get_16b`: 20347 req/s，p99 66us
- `set_1024b`: 191 req/s，p99 6959us
- `get_1024b`: 18892 req/s，p99 73us

本版仍未解决追平 Redis 的长期目标；`SET` 绝对性能仍明显落后 Redis，但相对 v0.8.0 基线已经不退化，并完成首批写路径开销削减。

## 5. 已知限制

- AOF 现在采用内存 buffer + 周期 flush；进程崩溃前尚未 flush 的小命令可能不会出现在 AOF 文件中
- benchmark 仍是 debug 构建、单线程、`client_pipeline=1`，尚未覆盖 release build、pipeline 或多连接
- 1KiB SET 仍主要受对象/SDS 分配、命令执行和 debug 构建开销限制
- Redis gap 报告仍以 `v0.8.0` 的对照矩阵为后续优化队列来源

## 6. 发布边界

`v0.8.1` 承诺：

- v0.8.0 已完成的协议、持久化、复制、内存治理和集群基础能力继续可用
- WATCH/UNWATCH 事务观察语义保持正确
- AOF replay、crash matrix、cluster consistency 和 maxmemory volatile 策略测试通过
- 相对 v0.8.0 benchmark 基线不退化

`v0.8.1` 不承诺：

- 完整 Redis 性能追平或超过
- release build benchmark、pipeline benchmark、多连接 benchmark
- Redis Cluster gossip、failover、resharding、`ASKING` 和多 key 同槽校验
- Redis RDB 二进制兼容和 Redis 风格流式复制

## 7. 发布物

- Benchmark 报告：[v0.8.1-performance.md](../benchmarks/v0.8.1-performance.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
- 测试报告：[redis-uya-test-report-v0.8.1.md](./redis-uya-test-report-v0.8.1.md)
