# redis-uya 文档

> 版本: v0.1.0-dev
> 日期: 2026-04-25

## 文档索引

- [详细设计](./redis-uya-design.md)
- [方案评审](./redis-uya-review.md)
- [开发 TODO](./redis-uya-todo.md)
- [开发规范](./redis-uya-development.md)
- [Definition of Done](./redis-uya-definition-of-done.md)
- [Benchmark 输出格式](./redis-uya-benchmark-format.md)
- [SDS 内存布局](./redis-uya-sds-layout.md)
- [QUICKSTART](./redis-uya-quickstart.md)
- [API](./redis-uya-api.md)
- [ARCHITECTURE](./redis-uya-architecture.md)
- [release-v0.1.0](./redis-uya-release-v0.1.0.md)
- [test-report-v0.1.0](./redis-uya-test-report-v0.1.0.md)

## 文档关系

1. `redis-uya-review.md` 评审方案范围、风险和版本收敛路线。
2. `redis-uya-design.md` 定义项目目标、总体架构、模块边界和关键设计决策。
3. `redis-uya-todo.md` 将设计拆分为当前里程碑、主线任务和 backlog。
4. `redis-uya-development.md` 固定开发规范、TDD 流程、版本策略和验证命令。
5. `redis-uya-definition-of-done.md` 维护验收矩阵。
6. `redis-uya-benchmark-format.md` 固定 benchmark 和 Redis 对照输出口径。
7. `redis-uya-sds-layout.md` 记录当前 SDS 字段语义、分配布局和格式化追加边界。
8. `redis-uya-quickstart.md` 提供从构建、运行到验证的最短路径。
9. `redis-uya-api.md` 记录当前命令与错误语义。
10. `redis-uya-architecture.md` 记录当前实现架构与数据路径。
11. `redis-uya-release-v0.1.0.md` 汇总当前预发布范围、验证入口与已知限制。
12. `redis-uya-test-report-v0.1.0.md` 固化 `v0.1.0` 收口阶段实际执行的测试和基准结果。

## 当前阶段

项目当前主线已完成 `v0.4.0` 规划任务，并已进入 `v0.5.0`：当前已补齐复制角色与状态机、`PSYNC / backlog`、replica 侧全量同步、定时拉取式增量同步、复制心跳和主从一致性 smoke。下一步进入 RESP3、事务、Pub/Sub 与更完整控制面。
