# redis-uya 文档

> 版本: v0.9.1-dev
> 日期: 2026-05-09

## 文档索引

- [详细设计](./redis-uya-design.md)
- [方案评审](./redis-uya-review.md)
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
2. `redis-uya-design.md` 定义项目目标、总体架构、模块边界和关键设计决策。
3. `redis-uya-todo.md` 将设计拆分为当前里程碑、主线任务和 backlog。
4. `redis-uya-command-scope.md` 定义单机版要覆盖的 Redis 官方命令全集、兼容矩阵状态和封版标准。
5. `redis-uya-development.md` 固定开发规范、TDD 流程、版本策略和验证命令。
6. `redis-uya-definition-of-done.md` 维护验收矩阵。
7. `redis-uya-benchmark-format.md` 固定 benchmark 和 Redis 对照输出口径。
8. `redis-uya-sds-layout.md` 记录当前 SDS 字段语义、分配布局和格式化追加边界。
9. `redis-uya-quickstart.md` 提供从构建、运行到验证的最短路径。
10. `redis-uya-api.md` 记录当前命令与错误语义。
11. `redis-uya-architecture.md` 记录当前实现架构与数据路径。
12. `redis-uya-release-v0.1.0.md` 固化 `v0.1.0` 的发布边界、验证入口与已知限制。
13. `redis-uya-release-v0.2.0.md`、`redis-uya-release-v0.3.0.md`、`redis-uya-release-v0.4.0.md`、`redis-uya-release-v0.5.0.md`、`redis-uya-release-v0.6.0.md`、`redis-uya-release-v0.7.0.md`、`redis-uya-release-v0.8.0.md`、`redis-uya-release-v0.8.1.md`、`redis-uya-release-v0.9.0.md` 固化各阶段收口时的版本边界。
14. `redis-uya-test-report-v0.1.0.md`、`redis-uya-test-report-v0.6.0.md`、`redis-uya-test-report-v0.7.0.md`、`redis-uya-test-report-v0.8.0.md`、`redis-uya-test-report-v0.8.1.md`、`redis-uya-test-report-v0.9.0.md` 固化对应阶段实际执行的测试和基准结果。

## 当前阶段

项目当前已完成 `v0.9.0` 单机核心命令补齐：String / Hash / List / Set / ZSet / Key / Server / Security 计划内命令批次已经全部收口，并补齐发布说明、测试报告和 DoD 验证证据。当前主线执行版本是 `v0.9.1`，已落地官方命令全集矩阵、共享运行时目录和 `COMMAND*` 控制面，补齐 `CONFIG SET` 第二批运行时字段与 `CONFIG REWRITE` 对应落盘验证，并完成 pattern Pub/Sub 第一批和 `PUBSUB` 管理面第一批；`v0.9.2` 预留高级数据能力，`v0.9.3` 预留运维、安全与可观测。
