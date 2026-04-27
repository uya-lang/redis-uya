# redis-uya API

> 版本: v0.1.0-dev
> 日期: 2026-04-25

## 1. 协议

当前只支持 RESP2 子集。

已支持输入类型：

- Array
- Bulk String
- Simple String

已支持输出类型：

- Simple String
- Error
- Integer
- Bulk String
- Null Bulk

## 2. 命令

### `PING`

格式：

```text
PING
PING message
```

返回：

- 无参数：`+PONG`
- 有参数：Bulk String 回显

### `GET`

格式：

```text
GET key
```

返回：

- 命中：Bulk String
- 不存在：Null Bulk

### `SET`

格式：

```text
SET key value
```

返回：

- 成功：`+OK`
- 额外选项当前返回 `-ERR syntax error`

### `DEL`

格式：

```text
DEL key [key ...]
```

返回：

- 删除成功的键数量，Integer

### `EXISTS`

格式：

```text
EXISTS key [key ...]
```

返回：

- 存在的键数量，Integer

### `EXPIRE`

格式：

```text
EXPIRE key seconds
```

返回：

- 设置成功或秒数为 `0` 时删除成功：`1`
- 键不存在：`0`

语义：

- 秒数为 `0` 立即删除
- AOF 中会转换为绝对时间 `PEXPIREAT`

### `PEXPIREAT`

格式：

```text
PEXPIREAT key unix_ms
```

返回：

- 设置成功：`1`
- 键不存在：`0`

说明：

- 当前主要用于 AOF 回放保持绝对过期时间

### `TTL`

格式：

```text
TTL key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回剩余秒数

### `INFO`

格式：

```text
INFO
INFO server
INFO memory
INFO stats
INFO keyspace
```

返回：

- 支持 `server`、`clients`、`memory`、`stats`、`keyspace`
- 未带 section 时返回上述 section 组合段

### `CONFIG GET`

格式：

```text
CONFIG GET pattern
```

返回：

- 返回 RESP Array，按 `name`、`value` 成对展开
- 当前支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`maxmemory`、`save`
- 支持最小 `*` 通配模式

### `SAVE`

格式：

```text
SAVE
```

返回：

- 成功：`+OK`
- 当前仅支持把 String 键值对和绝对过期时间写入项目内最小 RDB 子集格式
- 若当前数据集中存在 Hash/List/Set/ZSet，会返回错误

### `BGREWRITEAOF`

格式：

```text
BGREWRITEAOF
```

返回：

- 成功：`+Background AOF rewrite scheduled`
- 当前是最小 skeleton：请求会被主循环调度后执行，不是独立子进程后台 rewrite
- rewrite 产物会把当前内存态规范化写成可回放 AOF

### `QUIT`

格式：

```text
QUIT
```

返回：

- `+OK`

## 3. 错误

当前已覆盖的基础错误响应：

- `-ERR unknown command`
- `-ERR wrong number of arguments`
- `-ERR syntax error`
- `-ERR invalid request`
- `-ERR protocol error`
- `-ERR value is not an integer or out of range`

协议错误会在返回错误后关闭当前连接。
