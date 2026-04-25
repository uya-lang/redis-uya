# redis-uya Test Report v0.1.0

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: 已验证

## 1. 目标

本报告汇总 `v0.1.0` 收口阶段已实际执行的测试、smoke、长时运行验证和基准结果，作为独立于命令行输出的持久化验证记录。

## 2. 已执行验证

| 类别 | 命令 | 结果 |
|------|------|------|
| 构建 | `make build` | `PASS` |
| 单元测试 | `make test` | `PASS` |
| Python 集成测试 | `make test-integration` | `PASS` |
| `redis-cli` smoke | `make test-redis-cli` | `PASS` |
| 长时运行 smoke | `REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py` | `PASS` |
| benchmark 报告生成 | `python3 scripts/benchmark_v0_1_0.py` | `PASS` |
| DoD 验证 | `bash scripts/verify_definition_of_done.sh` | `PASS` |

## 3. 集成覆盖

`make test-integration` 本次实际覆盖：

- `tests/integration/smoke_tcp.py`
- `tests/integration/idle_client.py`
- `tests/integration/slow_reader.py`
- `tests/integration/persistence_aof.py`
- `tests/integration/error_compat.py`

单独补充执行：

- `tests/integration/redis_cli_smoke.sh`
- `tests/integration/long_run_smoke.py`

## 4. benchmark 摘要

详细原始输出见 [benchmarks/v0.1.0.md](../benchmarks/v0.1.0.md)。

### redis-uya

| case | p50_us | p95_us | p99_us | req_per_s | floor | target | stretch |
|------|--------|--------|--------|-----------|-------|--------|---------|
| `PING` | `33` | `59` | `92` | `24329` | `pass` | `miss` | `miss` |
| `SET` | `66` | `107` | `177` | `13112` | `pass` | `miss` | `miss` |
| `GET` | `48` | `77` | `103` | `17990` | `pass` | `miss` | `miss` |

### Redis baseline

| case | p50_us | p95_us | p99_us | req_per_s |
|------|--------|--------|--------|-----------|
| `PING` | `29` | `45` | `57` | `31970` |
| `SET` | `34` | `54` | `61` | `25818` |
| `GET` | `38` | `65` | `114` | `20825` |

## 5. 结论

- `v0.1.0` 的代码、文档、测试和基准脚本已收口。
- `redis-uya` 已满足当前项目对 `v0.1.0` 的可编译、可测试、可恢复、可基准化要求。
- 当前性能状态达到 `floor`，尚未达到 `target`。

## 6. 相关文档

- [release-v0.1.0](./redis-uya-release-v0.1.0.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [Benchmark 输出格式](./redis-uya-benchmark-format.md)
