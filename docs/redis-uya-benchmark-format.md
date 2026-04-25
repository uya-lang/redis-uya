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
