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

报告正文会先输出 `Case Matrix` Markdown 表格，便于人工直接对比 redis-uya 与 Redis：

```text
| Case | redis-uya req/s | Redis req/s | Throughput ratio | redis-uya p99 us | Redis p99 us | p99 ratio | RSS ratio | Status |
```

表格中的 `Status` 面向 Redis 对照阅读：吞吐达到 Redis 且 p99 不高于 Redis 时为 `target`；吞吐低于 Redis `0.25x` 或 p99 高于 Redis `4.0x` 时为 `critical`；其他未达标但非极端差距为 `watch`。

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

基线报告通过 `REDIS_UYA_BENCH_BASELINE` 指定。未指定基线时，guard 状态记录为 `skip`，用于生成首次基线报告。报告标题版本可通过 `REDIS_UYA_BENCH_REPORT_VERSION` 覆盖，`make benchmark-v0.8.1` 使用同一脚本输出 `v0.8.1` 标题并默认以 `benchmarks/v0.8.0-performance.md` 为 guard 基线。

## 9. v0.8.0 io_uring 评估输出

`v0.8.0` 的 `io_uring` 项只做能力评估，不绑定生产路径。评估脚本输出 `IO_URING_EVAL_RESULT`：

```text
IO_URING_EVAL_RESULT version=1 host_os=linux host_arch=x86_64 kernel_release=... \
io_uring_disabled=0 io_uring_max_entries=... io_uring_max_workers=... \
liburing_status=unknown syscall_status=yes recommendation=prototype-only production_binding=no
```

字段约定：

- `production_binding` 必须为 `no`，表示当前事件循环仍使用 epoll。
- `syscall_status` 记录 `io_uring_setup` 的实际探测结果：`yes`、`no`、`blocked`、`skip` 或 `error`。
- `liburing_status` 记录 `pkg-config liburing` 探测结果：`yes`、`no` 或 `unknown`。
- `recommendation` 只用于后续路线判断，不作为生产路径开关。

## 10. v0.8.0 Redis 差距报告输出

`v0.8.0` 的 Redis 对照差距报告由 `scripts/report_v0_8_0_gaps.py` 从 `BENCH_RESULT` 生成，默认输出 `benchmarks/v0.8.0-gap-report.md`。报告额外记录 `PERF_GAP_RESULT` 与 `PERF_DEBT_RESULT`：

```text
PERF_GAP_RESULT version=1 case_name=get_16b redis_uya_req_per_s=... redis_req_per_s=... \
throughput_ratio=... redis_uya_p99_us=... redis_p99_us=... p99_ratio=... \
redis_uya_rss_kib=... redis_rss_kib=... rss_ratio=... status=watch

PERF_DEBT_RESULT version=1 priority=P0 area=set_write_path cases=set_16b,set_1024b \
evidence="..." next="..."
```

字段约定：

- `throughput_ratio` 表示 `redis-uya req/s / Redis req/s`，越高越好。
- `p99_ratio` 表示 `redis-uya p99 / Redis p99`，越低越好。
- `rss_ratio` 表示 `redis-uya RSS / Redis RSS`，用于标记常驻内存差距。
- `status` 当前取值为 `pass`、`watch`、`high`、`critical` 或 `skip`。
- `PERF_DEBT_RESULT` 是后续优化队列，不作为 `v0.8.0` 单版硬门槛。
