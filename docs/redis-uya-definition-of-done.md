# redis-uya Definition of Done

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: 骨架

## 1. 目标

本页用于把 `redis-uya` 的阶段能力映射到明确测试、验证脚本或 benchmark 证据。

## 2. `v0.1-alpha`

| DoD 项 | 证据 |
|--------|------|
| `PING/GET/SET/DEL/EXISTS` 可通过 `redis-cli` 交互 | 待补 `tests/integration` |
| SDS、Dict、Object、Engine 有单元测试 | `tests/unit/*_test.uya` |
| 错误路径不会崩溃 | 待补错误路径测试 |

## 3. `v0.1-beta`

| DoD 项 | 证据 |
|--------|------|
| AOF 重启恢复正确 | 待补 `tests/integration/test_persistence.py` |
| 连接状态机与服务循环稳定 | 待补 TCP smoke |
| Python 子集集成测试通过 | 待补集成测试报告 |

## 4. `v0.1.0`

| DoD 项 | 证据 |
|--------|------|
| benchmark 基线可复现 | `benchmarks/v0.1.0.md` |
| Redis 对照口径明确 | `docs/redis-uya-benchmark-format.md` |
| 发布文档齐全 | `docs/redis-uya-release-v0.1.0.md` |
