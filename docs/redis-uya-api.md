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
```

返回：

- 当前固定返回最小 `# Server` 段

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
