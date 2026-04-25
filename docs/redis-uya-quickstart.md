# redis-uya QUICKSTART

> 版本: v0.1.0-dev
> 日期: 2026-04-25

## 1. 前置条件

- Linux x86_64 / ARM64
- `cc`、`gcc` 或 `clang`
- Python 3
- 如需 `redis-cli` smoke：本机安装 `redis-cli`

## 2. 构建与运行

查看编译器版本：

```bash
make version
```

构建：

```bash
make build
```

启动服务：

```bash
make run
```

指定端口、最大连接数和 AOF 路径：

```bash
build/redis-uya 6380 8 build/dev.aof
```

参数顺序：

1. 监听端口
2. 最大客户端数，`0` 表示不限制
3. AOF 文件路径，可省略，默认 `build/appendonly.aof`

## 3. 基础验证

单元测试：

```bash
make test
```

Python 集成 smoke：

```bash
make test-integration
```

如果本机已安装 `redis-cli`：

```bash
make test-redis-cli
```

长时运行 smoke：

```bash
REDIS_UYA_LONG_RUN_SECONDS=1800 python3 tests/integration/long_run_smoke.py
```

## 4. 当前支持命令

- `PING [message]`
- `GET key`
- `SET key value`
- `DEL key [key ...]`
- `EXISTS key [key ...]`
- `EXPIRE key seconds`
- `PEXPIREAT key unix_ms`
- `TTL key`
- `INFO [section]`
- `QUIT`

## 5. 当前边界

- 单节点、单进程
- RESP2 子集
- 仅 String/Key 子集
- AOF append + replay
- 不支持 RDB、复制、集群、事务、Pub/Sub
