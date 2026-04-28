# redis-uya release v0.5.0

> 版本: v0.5.0
> 日期: 2026-04-28

## 1. 阶段定位

`v0.5.0` 聚焦协议与控制面增强，在 `v0.4.0` 复制基础上补齐 RESP3 最小闭环、连接级事务、Pub/Sub 最小闭环，以及 `CLIENT` / `CONFIG` 兼容子集。

## 2. 已完成能力

- RESP3 最小闭环：`HELLO 2/3`、`HELLO SETNAME`、常用 RESP3 输入类型解析、RESP3 Null 回复
- 连接级事务：`MULTI/EXEC/DISCARD`、`WATCH/UNWATCH`、观察键冲突后的 Null Array 中止
- Pub/Sub 最小闭环：`SUBSCRIBE`、`UNSUBSCRIBE`、`PUBLISH`、RESP2 Array 与 RESP3 Push 消息
- 控制面兼容子集：`CLIENT ID/GETNAME/SETNAME/INFO/LIST/SETINFO/HELP`、`CONFIG GET/HELP/RESETSTAT`
- 兼容性回归：覆盖 RESP3、事务错误、WATCH 中止、RESP3 Pub/Sub Push、CLIENT/CONFIG 组合路径

## 3. 验证入口

- `make test`
- `make build`
- `python3 tests/integration/pubsub_smoke.py`
- `python3 tests/integration/client_config_smoke.py`
- `python3 tests/integration/v0_5_compat.py`
- `bash tests/integration/redis_cli_smoke.sh`
- `make test-integration`

## 4. 已知限制

- RESP3 仍是最小输出闭环，不是完整 RESP3 客户端兼容矩阵
- 事务尚未覆盖 Redis 完整错误传播、脚本联动和复杂命令交互
- Pub/Sub 尚不支持 pattern 订阅、完整 subscribed-mode 命令限制和背压缓冲
- `CLIENT LIST` 当前只返回当前连接信息，不支持全局扫描、`KILL`、`PAUSE`、`TRACKING`
- `CONFIG` 当前不支持 `SET` 与 `REWRITE`
- 复制仍是当前项目内的最小同步模型，不是 Redis 长连接流式复制
