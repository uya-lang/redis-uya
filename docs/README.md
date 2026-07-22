# redis-uya 文档

> 版本: v0.9.3-dev
> 日期: 2026-07-11

## 文档索引

- [详细设计](./redis-uya-design.md)
- [方案评审](./redis-uya-review.md)
- [审计报告（2026-05-16）](./redis-uya-audit-2026-05-16.md)
- [开发 TODO](./redis-uya-todo.md)
- [Command Scope](./redis-uya-command-scope.md)
- [Command Matrix](./redis-uya-command-matrix.md)
- [开发规范](./redis-uya-development.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [Uya 1.0 同步报告（2026-07-22）](./redis-uya-uya-sync-2026-07-22.md)
- [Benchmark 输出格式](./redis-uya-benchmark-format.md)
- [SDS 内存布局](./redis-uya-sds-layout.md)
- [QUICKSTART](./redis-uya-quickstart.md)
- [API](./redis-uya-api.md)
- [ARCHITECTURE](./redis-uya-architecture.md)
- [release-v0.1.0](./redis-uya-release-v0.1.0.md)
- [release-v0.2.0](./redis-uya-release-v0.2.0.md)
- [release-v0.3.0](./redis-uya-release-v0.3.0.md)
- [release-v0.4.0](./redis-uya-release-v0.4.0.md)
- [release-v0.5.0](./redis-uya-release-v0.5.0.md)
- [release-v0.6.0](./redis-uya-release-v0.6.0.md)
- [release-v0.7.0](./redis-uya-release-v0.7.0.md)
- [release-v0.8.0](./redis-uya-release-v0.8.0.md)
- [release-v0.8.1](./redis-uya-release-v0.8.1.md)
- [release-v0.9.0](./redis-uya-release-v0.9.0.md)
- [test-report-v0.1.0](./redis-uya-test-report-v0.1.0.md)
- [test-report-v0.6.0](./redis-uya-test-report-v0.6.0.md)
- [test-report-v0.7.0](./redis-uya-test-report-v0.7.0.md)
- [test-report-v0.8.0](./redis-uya-test-report-v0.8.0.md)
- [test-report-v0.8.1](./redis-uya-test-report-v0.8.1.md)
- [test-report-v0.9.0](./redis-uya-test-report-v0.9.0.md)
- [performance-v0.9.3](../benchmarks/v0.9.3-performance.md)
- [release-performance-v0.9.3](../benchmarks/v0.9.3-release-performance.md)
- [performance-analysis-v0.9.3](../benchmarks/v0.9.3-performance-analysis.md)

## 文档关系

1. `redis-uya-review.md` 评审方案范围、风险和版本收敛路线。
2. `redis-uya-audit-2026-05-16.md` 固化当前 `HEAD` 的实测结论、证据链和整改优先级。
3. `redis-uya-design.md` 定义项目目标、总体架构、模块边界和关键设计决策。
4. `redis-uya-todo.md` 将设计拆分为当前里程碑、主线任务和 backlog。
5. `redis-uya-command-scope.md` 定义单机版 `v1.0.0` 的命令封版边界、模块命令追踪边界和兼容矩阵状态。
6. `redis-uya-development.md` 固定开发规范、TDD 流程、版本策略和验证命令。
7. `redis-uya-definition-of-done.md` 维护历史里程碑证据，并注明当前 `HEAD` 是否已重新验证。
8. `redis-uya-uya-sync-2026-07-22.md` 记录 Uya 1.0 工具链同步、上游修复、产物哈希和兼容验证。
9. `redis-uya-benchmark-format.md` 固定 benchmark 和 Redis 对照输出口径。
10. `redis-uya-sds-layout.md` 记录当前 SDS 字段语义、分配布局和格式化追加边界。
11. `redis-uya-quickstart.md` 提供从构建、运行到验证的最短路径。
12. `redis-uya-api.md` 记录当前命令与错误语义。
13. `redis-uya-architecture.md` 记录当前实现架构与数据路径。
14. `redis-uya-release-v0.1.0.md` 固化 `v0.1.0` 的发布边界、验证入口与已知限制。
15. `redis-uya-release-v0.2.0.md`、`redis-uya-release-v0.3.0.md`、`redis-uya-release-v0.4.0.md`、`redis-uya-release-v0.5.0.md`、`redis-uya-release-v0.6.0.md`、`redis-uya-release-v0.7.0.md`、`redis-uya-release-v0.8.0.md`、`redis-uya-release-v0.8.1.md`、`redis-uya-release-v0.9.0.md` 固化各阶段收口时的版本边界。
16. `redis-uya-test-report-v0.1.0.md`、`redis-uya-test-report-v0.6.0.md`、`redis-uya-test-report-v0.7.0.md`、`redis-uya-test-report-v0.8.0.md`、`redis-uya-test-report-v0.8.1.md`、`redis-uya-test-report-v0.9.0.md` 固化对应阶段实际执行的测试和基准结果。

## 当前阶段

截至 2026-05-16 审计、2026-05-17 复跑、2026-05-19 复核、2026-07-11 性能复测、2026-07-20 当前验证与 2026-07-22 Uya 1.0 同步，项目当前口径应为：

- `v0.9.0` 的历史收口文档仍然保留，但不能直接代表当前 `HEAD`。
- 当前开发工具链已同步到 Uya `1.0` 分支 `337a0edd` / v0.9.9；启动器与实际 build 编译器均由上游源码重新生成并成套同步，产物哈希、上游测试边界和项目验证见 `redis-uya-uya-sync-2026-07-22.md`。
- 当前 `HEAD` 的完整单测、完整集成和 redis-cli smoke 已通过；release 矩阵见 `benchmarks/v0.9.3-release-performance.md`。常见三参数内扁平命令数组借用连接栈 `RespValue` 描述符，默认用户和 named user 还分别维护活跃命令拒绝规则计数，空 deny list 不再逐命令扫描固定表；固定 CPU 200K `PING` 对父提交吞吐提升 `2.4%`、server cycles 下降 `1.35%`、instructions 下降 `1.46%`，当前五项绝对吞吐与 p99 回归 guard 通过。
- 当前主线的第一优先级已从 `v0.9.1` 的真实性修复转入 `v0.9.3` 的 Redis Open Source 单机核心缺口补齐，并持续保持控制面真值、版本口径与统计分层不回退。
- `v1.0.0` 的命令封版门槛先收敛 Redis Open Source 单机核心；JSON/Search/Time Series/概率结构/Vector 等模块命令继续追踪，但不再作为当前阶段完成度的包装材料。

当前执行路线见：

- [审计报告（2026-05-16）](./redis-uya-audit-2026-05-16.md)
- [开发 TODO](./redis-uya-todo.md)
- [Definition of Done](./redis-uya-definition-of-done.md)

当前主线目标也需要按层理解：

- 长期目标：性能在核心场景上超过 Redis。
- `v1.0.0` 目标：先把单机核心做真、做稳、做快。

仍待继续收口的问题：

- 当前 `v0.9.3` 功能回归为绿态；最新正式 release 比例为 `PING 1.02x`、`SET 16B 1.25x`、`GET 16B 1.08x`、`SET 1KiB 1.33x`、`GET 1KiB 1.00x`。短矩阵中的同机 Redis 波动明显，严格的 1.10x 全场景超越目标尚未达成，后续优先收敛 PING/GET 的小读事件循环与命令分发、pipeline/并发矩阵和内存占用。
