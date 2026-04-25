# redis-uya release-v0.1.0

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: 收口完成（仍未打正式 tag）

## 1. 范围

`v0.1.0` 的目标是交付一个可编译、可测试、可交互、可恢复、可基准化的最小单节点 Redis 内核，而不是完整 Redis。

当前版本包含：

- RESP2 子集
- String/Key 命令子集
- 单线程 epoll 多连接服务循环
- 100ms 主动过期 + 惰性过期
- AOF append + replay
- Python 集成 smoke

## 2. 支持命令

- `PING`
- `GET`
- `SET`
- `DEL`
- `EXISTS`
- `EXPIRE`
- `PEXPIREAT`
- `TTL`
- `INFO`
- `QUIT`

## 3. 验证入口

基础验证：

```bash
make build
make test
make test-integration
```

DoD 验证：

```bash
bash scripts/verify_definition_of_done.sh
```

可选验证：

```bash
make test-redis-cli
REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py
python3 scripts/benchmark_v0_1_0.py
```

## 4. 已知限制

- 当前机器未必安装 `redis-cli` / `redis-server` / `redis-benchmark`
- 如果缺少 `redis-server`，基准脚本会把 Redis 对照状态记录为 `skip`
- 长时运行 smoke 需要单独执行，不纳入默认 `make test-integration`
- 当前仍是 `v0.1.0-dev`，不是正式 tag

## 5. Validation Record

本次收口已执行：

- `make test`
- `make test-integration`
- `make test-redis-cli`
- `REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py`
- `python3 scripts/benchmark_v0_1_0.py`
- `bash scripts/verify_definition_of_done.sh`

结果摘要：

- 基础单元与集成 smoke 通过
- `redis-cli` smoke 通过
- 30 分钟长时运行 smoke 通过
- 同机 Redis 基线已生成到 `benchmarks/v0.1.0.md`

## 6. 发布物

- 入口二进制：`build/redis-uya`
- Quickstart：[redis-uya-quickstart.md](./redis-uya-quickstart.md)
- API：[redis-uya-api.md](./redis-uya-api.md)
- Architecture：[redis-uya-architecture.md](./redis-uya-architecture.md)
- DoD：[redis-uya-definition-of-done.md](./redis-uya-definition-of-done.md)
