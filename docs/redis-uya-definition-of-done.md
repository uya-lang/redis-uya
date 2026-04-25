# redis-uya Definition of Done

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: 执行中

## 1. 目标

本页用于把 `redis-uya` 的阶段能力映射到明确测试、验证脚本或 benchmark 证据。

一键验证入口：

```bash
bash scripts/verify_definition_of_done.sh
```

## 2. `v0.1-alpha`

| DoD 项 | 证据 |
|--------|------|
| `PING/GET/SET/DEL/EXISTS` 可通过 TCP smoke 交互 | `tests/integration/smoke_tcp.py` |
| SDS、Dict、Object、Engine 有单元测试 | `tests/unit/*_test.uya` |
| SDS 1MB 追加与布局说明完成 | `tests/unit/storage_sds_test.uya`、`docs/redis-uya-sds-layout.md` |
| Dict 渐进 rehash 可手动推进 | `tests/unit/storage_dict_test.uya` |
| 错误路径不会崩溃 | `tests/unit/*_test.uya` 中错误路径用例 |
| 100ms server cron 可触发主动过期扫描 | `tests/unit/storage_engine_test.uya`、`tests/unit/server_test.uya` |

## 3. `v0.1-beta`

| DoD 项 | 证据 |
|--------|------|
| AOF 重启恢复正确 | `tests/integration/persistence_aof.py` |
| AOF 追加、回放、损坏文件失败路径有单元证据 | `tests/unit/persistence_aof_test.uya` |
| 连接状态机与服务循环稳定 | `tests/integration/smoke_tcp.py`、`tests/integration/idle_client.py` |
| 空闲客户端不会阻塞其他客户端 | `tests/integration/idle_client.py` |
| Python 子集集成测试通过 | `make test-integration` |

## 4. `v0.1.0`

| DoD 项 | 证据 |
|--------|------|
| benchmark 基线可复现 | `benchmarks/v0.1.0.md` |
| Redis 对照口径明确 | `docs/redis-uya-benchmark-format.md` |
| 发布文档齐全 | `docs/redis-uya-release-v0.1.0.md` |
