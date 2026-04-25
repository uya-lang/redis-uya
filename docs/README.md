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

## 文档关系

1. `redis-uya-review.md` 评审方案范围、风险和版本收敛路线。
2. `redis-uya-design.md` 定义项目目标、总体架构、模块边界和关键设计决策。
3. `redis-uya-todo.md` 将设计拆分为当前里程碑、主线任务和 backlog。
4. `redis-uya-development.md` 固定开发规范、TDD 流程、版本策略和验证命令。
5. `redis-uya-definition-of-done.md` 维护验收矩阵。
6. `redis-uya-benchmark-format.md` 固定 benchmark 和 Redis 对照输出口径。
7. `redis-uya-sds-layout.md` 记录当前 SDS 字段语义、分配布局和格式化追加边界。

## 当前阶段

项目当前处于 `v0.1.0-dev`：已完成 `v0.1-alpha` 的存储、协议与单线程 epoll 多连接服务闭环，并已完成 `v0.1-beta` 的 AOF 最小恢复闭环；下一步推进 `redis-cli` smoke、长时运行和错误响应兼容检查。
