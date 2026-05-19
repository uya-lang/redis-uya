# redis-uya 文档

> 版本: v0.9.1-dev
> 日期: 2026-05-16

## 文档索引

- [详细设计](./redis-uya-design.md)
- [方案评审](./redis-uya-review.md)
- [审计报告（2026-05-16）](./redis-uya-audit-2026-05-16.md)
- [开发 TODO](./redis-uya-todo.md)
- [Command Scope](./redis-uya-command-scope.md)
- [Command Matrix](./redis-uya-command-matrix.md)
- [开发规范](./redis-uya-development.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
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

## 文档关系

1. `redis-uya-review.md` 评审方案范围、风险和版本收敛路线。
2. `redis-uya-audit-2026-05-16.md` 固化当前 `HEAD` 的实测结论、证据链和整改优先级。
3. `redis-uya-design.md` 定义项目目标、总体架构、模块边界和关键设计决策。
4. `redis-uya-todo.md` 将设计拆分为当前里程碑、主线任务和 backlog。
5. `redis-uya-command-scope.md` 定义单机版 `v1.0.0` 的命令封版边界、模块命令追踪边界和兼容矩阵状态。
6. `redis-uya-development.md` 固定开发规范、TDD 流程、版本策略和验证命令。
7. `redis-uya-definition-of-done.md` 维护历史里程碑证据，并注明当前 `HEAD` 是否已重新验证。
8. `redis-uya-benchmark-format.md` 固定 benchmark 和 Redis 对照输出口径。
9. `redis-uya-sds-layout.md` 记录当前 SDS 字段语义、分配布局和格式化追加边界。
10. `redis-uya-quickstart.md` 提供从构建、运行到验证的最短路径。
11. `redis-uya-api.md` 记录当前命令与错误语义。
12. `redis-uya-architecture.md` 记录当前实现架构与数据路径。
13. `redis-uya-release-v0.1.0.md` 固化 `v0.1.0` 的发布边界、验证入口与已知限制。
14. `redis-uya-release-v0.2.0.md`、`redis-uya-release-v0.3.0.md`、`redis-uya-release-v0.4.0.md`、`redis-uya-release-v0.5.0.md`、`redis-uya-release-v0.6.0.md`、`redis-uya-release-v0.7.0.md`、`redis-uya-release-v0.8.0.md`、`redis-uya-release-v0.8.1.md`、`redis-uya-release-v0.9.0.md` 固化各阶段收口时的版本边界。
15. `redis-uya-test-report-v0.1.0.md`、`redis-uya-test-report-v0.6.0.md`、`redis-uya-test-report-v0.7.0.md`、`redis-uya-test-report-v0.8.0.md`、`redis-uya-test-report-v0.8.1.md`、`redis-uya-test-report-v0.9.0.md` 固化对应阶段实际执行的测试和基准结果。

## 当前阶段

截至 2026-05-16 审计、2026-05-17 最新复跑与 2026-05-19 当前复核，项目当前口径应为：

- `v0.9.0` 的历史收口文档仍然保留，但不能直接代表当前 `HEAD`。
- 当前 `HEAD` 的 `make test` 与 `make test-integration` 已恢复为通过状态，但 `make benchmark-v0.8.1` 仍有抖动，不能宣称稳定通过。
- 当前主线的第一优先级仍是收口“版本号、benchmark 稳定性、文档口径”之间的裂缝，并持续保持控制面真值不回退。
- `v1.0.0` 的命令封版门槛先收敛 Redis Open Source 单机核心；JSON/Search/Time Series/概率结构/Vector 等模块命令继续追踪，但不再作为当前阶段完成度的包装材料。

当前执行路线见：

- [审计报告（2026-05-16）](./redis-uya-audit-2026-05-16.md)
- [开发 TODO](./redis-uya-todo.md)
- [Definition of Done](./redis-uya-definition-of-done.md)

当前主线目标也需要按层理解：

- 长期目标：性能在核心场景上超过 Redis。
- `v1.0.0` 目标：先把单机核心做真、做稳、做快。

仍待继续收口的问题：

- 当前 `COMMAND*` 已按真实执行面隐藏未实现命令，且当前 `CLIENT/CONFIG` 已实现子命令的矩阵状态已补齐；后续仍需继续扩展剩余单机核心命令。
- banner、`INFO server` 与文档版本号尚未统一。
- `benchmark-v0.8.1` 最新复跑仍可能出现 guard miss。
