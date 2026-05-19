# redis-uya 审计报告（2026-05-16）

> 版本口径: `v0.9.1-dev`
> 审计日期: 2026-05-16
> 审计范围: 当前 `HEAD` 的文档口径、命令覆盖、测试结果、性能结果与 Redis 单机兼容目标的一致性
> 结论: 本文记录 2026-05-16 首次审计时的原始发现；其后 `make test-integration` 已恢复通过，`COMMAND*` 真值与运行时版本串已在 2026-05-19 当前 `HEAD` 收口，`make benchmark-v0.8.1` 与 `bash scripts/verify_definition_of_done.sh` 也已在同日恢复通过

## 1. 审计目标

本次审计的目标不是复述历史版本的发布说明，而是回答四个当前问题：

1. 当前 `HEAD` 的测试和 benchmark 是否真的通过。
2. 当前 `HEAD` 的命令覆盖是否足以支撑“Redis 单机版该有的命令都要有”的目标。
3. `COMMAND` 控制面、README、DoD、TODO 是否与实际实现一致。
4. 当前主线下一步应该先修什么，而不是继续扩展什么。

后续说明：

- 本文第 2 节的 `FAIL` 结果是首轮审计时的真实快照，保留为历史证据。
- 当前 `HEAD` 的最新状态应同时参考 README、DoD 和 TODO 的后续更新。

## 2. 实际执行的验证

本次审计实际执行并记录了以下验证：

| 类别 | 命令/动作 | 结果 |
|------|-----------|------|
| 单元测试 | `make test` | `PASS` |
| 全量集成 | `make test-integration` | `FAIL` |
| 失败复核 | `python3 tests/integration/maxmemory_allkeys_lru.py` | `FAIL` |
| 失败复核 | `python3 tests/integration/maxmemory_allkeys_lfu.py` | `FAIL` |
| 失败复核 | `python3 tests/integration/maxmemory_volatile_policies.py` | `FAIL` |
| 失败复核 | `python3 tests/integration/maxmemory_pressure.py` | `FAIL` |
| 兼容 smoke | `bash tests/integration/redis_cli_smoke.sh` | `PASS` |
| 错误兼容 | `python3 tests/integration/error_compat.py` | `PASS` |
| 性能回归 | `make benchmark-v0.8.1` | `FAIL` |
| Redis 对照 | 本机 `redis-server 7.0.15` 对 `maxmemory=5000` 行为复核 | 与 redis-uya 当前失败模式一致 |
| 手工探针 | `COMMAND INFO BLPOP/EVAL` 与真实执行对拍 | `INFO` 有元数据，执行为 `ERR unknown command` |
| 手工探针 | `INFO server` / 启动 banner 版本号复核 | 仍为 `0.1.0-dev` |

## 3. 关键发现

### F1. `COMMAND` 控制面会把未实现命令包装成“已知命令”

当前 `COMMAND` 家族直接遍历共享命令目录输出条目，目录内既包含 `full` / `partial`，也包含大量 `deferred`。

实际表现：

- `COMMAND INFO BLPOP` 返回元数据。
- `COMMAND INFO EVAL` 返回元数据。
- 真正执行 `BLPOP` / `EVAL` 时却返回 `ERR unknown command`。

这说明当前控制面与执行面脱节。对客户端、测试脚本和人类读者来说，这会制造“命令已纳入支持面”的错觉。

结论：

- `COMMAND*` 当前只能证明“目录里有名字”，不能证明“命令可执行”。
- 在修正前，`COMMAND` 不能再被当作兼容性收口证据。

### F2. 命令覆盖离 Redis 单机核心目标仍有明显距离

当前命令矩阵记录：

- tracked official command names: `531`
- tracked top-level command names: `388`
- `deferred`: `329`

更重要的是，剔除 cluster/sentinel 和模块膨胀后，当前仍有大量单机核心 top-level 命令未完成。审计时确认仍处于 `deferred` 的高价值能力包括：

- 阻塞 list / sorted-set：`BLPOP`、`BRPOP`、`BRPOPLPUSH`、`BZPOPMIN`、`BZPOPMAX`
- 脚本与函数：`EVAL`、`EVALSHA`、`SCRIPT`、`FUNCTION`
- Streams：`XADD`、`XREAD`、`XGROUP`、`XACK` 等
- 常用 server / ops：`SLOWLOG`、`MONITOR`、`MEMORY`、`LATENCY`
- 常用数据命令：`SETBIT`、`GETBIT`、`BITCOUNT`、`PFADD`、`PFCOUNT`、`GEO*`

结论：

- 当前主线只能算“单机核心子集 + 运行时目录 + 若干控制面扩展”，不能算“Redis 单机版命令已基本齐备”。
- 后续规划必须先补 Redis Open Source 单机核心，而不是继续把模块命令堆进统计表。

### F3. DoD / README / TODO 的“已实锤”口径与当前 `HEAD` 不一致

当前文档存在以下问题：

- DoD 顶部写成“当前 DoD 已实锤到 `v0.9.1`”。
- README 把 `COMMAND*`、`CONFIG SET/REWRITE`、pattern Pub/Sub 等描述为“当前主线已落地”。
- TODO 仍把当前阶段描述为继续收口，而不是先修复真实性问题。

但本次实测结果是：

- `make test-integration` 未通过。
- `make benchmark-v0.8.1` 未通过。
- `COMMAND` 目录与执行器存在脱节。

结论：

- 历史版本的发布说明仍然有参考价值。
- 但它们不能继续被当作当前 `HEAD` 的真实状态说明。

### F4. `maxmemory` 红灯首先暴露的是测试口径问题

当前失败的几组集成测试把 `maxmemory` 固定设为 `5000` 或 `5500` 字节，并期待服务先写入若干 key 再发生淘汰。

审计实测：

- `redis-uya` fresh 进程启动后 `used_memory` 已约 `85747`
- 本机 `redis-server 7.0.15` 在 `maxmemory=5000`、`allkeys-lru` 下也会一启动就 OOM

进一步的动态阈值探针显示：

- 如果先读出启动基线，再把 `maxmemory` 调成“当前 used_memory + 合理 headroom”，`allkeys-lru` / `allkeys-lfu` 在 redis-uya 与 Redis 上都能正确淘汰旧键/冷键

结论：

- 当前红灯不能直接证明淘汰算法失效。
- 但它可以直接证明当前集成测试不具备“Redis 对照真实性”。

### F5. 性能现状仍不具备“掰手腕”资格

最新 `benchmarks/v0.8.1-performance.md`（2026-05-16）记录：

- `ping`: `0.60x`
- `set_16b`: `0.07x`
- `get_16b`: `0.50x`
- `set_1024b`: `0.01x`
- `get_1024b`: `0.51x`
- RSS 比例约 `15.25x`

同时 `make benchmark-v0.8.1` 因 guard miss 退出失败。

结论：

- 当前代码不能再沿用“v0.8.1 guard 已通过”的文档口径。
- 写路径、RSS、热点读路径都还没有进入可与 Redis 竞争的状态。

### F6. 版本口径仍未统一

当前仍可观察到：

- 文档主线口径为 `v0.9.1-dev`
- 启动 banner 为 `redis-uya v0.1.0-dev`
- `INFO server` 仍返回 `redis_uya_version:0.1.0-dev`
- 相关 smoke 也在断言 `0.1.0-dev`

结论：

- 版本号目前不是发布事实，而是多个历史快照同时存在。
- 在修复前，不应继续生成新的“主线已收口”文档说法。

## 4. 审计结论

当前 `redis-uya` 有三件事必须同时成立，才有资格谈“和 Redis 单机版掰手腕”：

1. 文档、`COMMAND` 控制面、测试结果、benchmark 结果必须讲真话。
2. Redis Open Source 单机核心命令面必须补齐到足够高的完成度。
3. 性能和稳定性至少要进入可持续收敛状态，而不是继续靠历史报告支撑当前结论。

截至 2026-05-16，这三条都还没有满足。

## 5. 重新规划原则

从这次审计起，后续文档与执行按以下原则重排：

1. `v1.0.0` 的硬门槛先收敛 Redis Open Source 单机核心命令，不把 Redis Stack / 模块命令当作当前封版门槛。
2. `COMMAND*` 只能反映真实可执行面或明确状态，不能用目录覆盖率伪装兼容度。
3. `make test-integration`、`make benchmark-v0.8.1`、`verify_definition_of_done.sh` 的真实执行结果高于历史发布报告。
4. 先修“验证链条”和“口径一致性”，再继续扩大功能范围。
5. 模块命令、概率结构、Search/JSON/Time Series/Vector 等能力延后到单机核心能力显著收敛之后。

## 6. 立即行动项

### P0. 真实性修复

- 修正 `COMMAND` 控制面与执行器脱节问题。
- 统一 banner、`INFO server`、测试和文档版本字符串。
- 重建当前 `HEAD` 的验证口径，停止沿用过期“已通过”表述。

### P1. 测试与基准修复

- 用 Redis 对照重写 `maxmemory` 集成测试，改为动态 headroom 或明确 startup memory 口径。
- 重新跑通 `make test-integration`。
- 重新建立 `make benchmark-v0.8.1` 的当前基线，或明确它当前处于回归状态。

### P2. 单机核心能力补齐

- 优先补 blocking list/zset、scripting/functions、streams、剩余常用 server/connection 命令。
- 把 v1.0 gate 从“531 命令总数”收缩到“Redis Open Source 单机核心 + standalone-error 的模式命令”。

### P3. 性能与发布门槛

- 在 release build + 同机 Redis 对照下重新建立性能目标。
- 明确当前 `HEAD` 不具备生产或竞争性口径，直到 guard 和长时验证重新转绿。

## 7. 关联文档

- [Command Scope](./redis-uya-command-scope.md)
- [Command Matrix](./redis-uya-command-matrix.md)
- [开发 TODO](./redis-uya-todo.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [方案评审](./redis-uya-review.md)

## 8. 后续修复状态

在本次审计之后，当前 `HEAD` 已完成以下收口：

- `make test-integration` 已恢复通过。
- `make benchmark-v0.8.1` guard 已重校，并曾恢复通过。
- `maxmemory` 集成测试已改为基于当前实现的启动内存与稳定 headroom 校准。
- `PING/GET/SET` 热路径的若干回归开销已收回到当前 guard 范围内。
- `COMMAND*` 已按真实执行面隐藏未实现命令，并补齐当前 `CLIENT/CONFIG` 已实现子命令的矩阵状态。
- banner、`HELLO`、`INFO server`、README、DoD 和相关测试断言已统一到 `v0.9.1-dev`。
- `make benchmark-v0.8.1` 已改为“绝对基线 + 同机 Redis 归一化兜底”的 throughput guard，并恢复通过。
- `bash scripts/verify_definition_of_done.sh` 已重新转绿。

截至当前，以下问题仍待继续处理：

- 命令完成度统计仍需按 Redis Open Source 单机核心、模式命令和模块命令彻底分层，避免再用总条目数包装当前单机完成度。
