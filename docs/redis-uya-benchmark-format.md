# redis-uya Benchmark 输出格式

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: 骨架

## 1. 目标

固定 `redis-uya` 与 Redis 对照 benchmark 的环境和结果格式，避免后续数字不可横向比较。

## 2. 环境块

推荐输出一条 `BENCH_ENV`：

```text
BENCH_ENV version=1 host_os=linux host_arch=x86_64 cpu_model="..." cpu_count=... \
build_mode=release durability=aof dataset_kind=string-kv benchmark_mode=single-thread case_name=get
```

## 3. 结果块

推荐每个 case 输出一条 `BENCH_RESULT`：

```text
BENCH_RESULT version=1 case_name=get benchmark_mode=single-thread iterations=100000 \
p50_us=... p95_us=... p99_us=... req_per_s=... rss_kib=... floor_status=pass
```

## 4. 状态字段

- `floor_status`: `pass` / `miss` / `skip`
- `target_status`: `pass` / `miss` / `skip`
- `stretch_status`: `pass` / `miss` / `skip`

## 5. Redis 对照要求

与 Redis 比较时必须记录：

- 相同硬件
- 相同客户端并发
- 相同命令集合
- 相同数据规模
- 相同持久化策略
- 相同统计窗口

## 6. 持久化用例

对于 `SAVE`、重启恢复、rewrite 完成时间这类持久化场景，允许输出专用结果行：

```text
PERSIST_BENCH_RESULT version=1 impl=redis-uya case_name=save runs=3 p50_ms=... p95_ms=... p99_ms=... rss_kib=...
```

说明：

- `p50_ms/p95_ms/p99_ms` 表示毫秒级延迟分位
- `rss_kib` 记录被测进程的常驻内存
- 持久化场景默认以“更低延迟更好”为比较方向，不复用 `floor/target/stretch` 判定

## 7. 复制用例

对于 full sync、incremental sync、主从重连恢复这类复制场景，允许输出专用结果行：

```text
REPL_BENCH_RESULT version=1 impl=redis-uya case_name=full_sync runs=3 p50_ms=... p95_ms=... p99_ms=... rss_kib=...
```

说明：

- `rss_kib` 记录 master + replica 两个进程的合计 RSS
- 复制场景默认以“更低延迟更好”为比较方向，不复用 `floor/target/stretch` 判定

## 8. v0.8.0 性能回归护栏

`v0.8.0` 起，核心热路径 benchmark 额外输出 `PERF_GUARD_RESULT`：

```text
PERF_GUARD_RESULT version=1 case_name=get_16b baseline_req_per_s=... current_req_per_s=... \
min_req_per_s=... throughput_status=pass baseline_p99_us=... current_p99_us=... max_p99_us=... p99_status=pass
```

默认阈值：

- 吞吐不低于基线的 `0.90x`
- p99 不高于 `max(基线 * 1.15, 基线 + 100us)`

阈值可通过环境变量覆盖：

- `REDIS_UYA_REGRESSION_RPS_RATIO`
- `REDIS_UYA_REGRESSION_P99_RATIO`
- `REDIS_UYA_REGRESSION_P99_ABS_US`

基线报告通过 `REDIS_UYA_BENCH_BASELINE` 指定。未指定基线时，guard 状态记录为 `skip`，用于生成首次基线报告。
