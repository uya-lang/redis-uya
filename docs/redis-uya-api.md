# redis-uya API

> 版本: v0.9.1-dev
> 日期: 2026-05-09
> 当前主线口径: 本文只承诺已在 `v0.9.1-dev` 主线落地并有测试证据的语义；`v0.9.2` 高级数据能力与 `v0.9.3` 运维 / 安全 / 可观测能力，除非对应命令章节明确写出，否则不视为当前可用

## 1. 协议

当前默认使用 RESP2 子集，支持通过 `HELLO 3` 在连接级切换到 RESP3 最小闭环。

已支持输入类型：

- RESP2：Array、Bulk String、Simple String
- RESP3：Array、Blob String、Simple String、Number、Null、Boolean、Double、Big Number、Blob Error、Verbatim String、Map、Set、Push

已支持输出类型：

- Simple String
- Error
- Integer
- Bulk String
- Null Bulk
- Array
- RESP3 Null（连接通过 `HELLO 3` 切换后）
- `HELLO 3` Map 回复
- RESP3 Push（RESP3 Pub/Sub 确认与消息）

## 2. 命令

### `HELLO`

格式：

```text
HELLO
HELLO 2
HELLO 3
HELLO 2 SETNAME name
HELLO 3 SETNAME name
```

返回：

- `HELLO 2`：切回 RESP2，并返回 RESP2 Array 形式的服务信息
- `HELLO 3`：切到 RESP3，并返回 RESP3 Map 形式的服务信息
- 不支持的协议版本：`-NOPROTO unsupported protocol version`

说明：

- 当前 `HELLO` 支持 `SETNAME` 扩展参数，不支持 `AUTH`
- 启用 `requirepass` 后，当前实现要求先单独执行 `AUTH`；未认证时 `HELLO` 返回 `-NOAUTH Authentication required.`
- RESP3 模式下，不存在的 bulk 值返回 RESP3 Null：`_\r\n`

### `AUTH`

格式：

```text
AUTH password
AUTH default password
```

返回：

- 成功：`+OK`
- 密码错误 / 用户不匹配：`-WRONGPASS invalid username-password pair or user is disabled.`
- 未配置 `requirepass` 时，单参数 `AUTH` 返回错误

说明：

- 当前安全基线只支持默认用户 `default`
- 启用 `requirepass` 后，除 `AUTH` / `QUIT` / `RESET` 外的普通命令在认证前返回 `-NOAUTH Authentication required.`

### `COMMAND`

格式：

```text
COMMAND
COMMAND HELP
COMMAND COUNT
COMMAND LIST [FILTERBY MODULE module-name | ACLCAT category | PATTERN pattern]
COMMAND INFO [command-name [command-name ...]]
COMMAND DOCS [command-name [command-name ...]]
```

返回：

- `COMMAND`：返回顶层命令元数据数组；顶层容器命令会内嵌其子命令元数据
- `COMMAND COUNT`：返回当前目录里的顶层官方命令数量，Integer
- `COMMAND LIST`：返回命令名数组；支持 `FILTERBY MODULE`、`FILTERBY ACLCAT`、`FILTERBY PATTERN`
- `COMMAND INFO`：返回命令元数据数组；未知命令在 RESP2 下返回 Null Bulk，占位于原请求位置；RESP3 下返回 Null
- `COMMAND DOCS`：带命令名时，RESP2 下返回 flatten map array，RESP3 下返回 map；无参数时返回全量官方目录 docs；未知命令会被忽略

说明：

- 当前 `COMMAND` 家族与 `docs/redis-uya-command-matrix.md` 共用 `src/command/catalog_generated*` 生成目录
- 目录基线当前覆盖 Redis 8.6 官方命令页中的 `531` 个官方命令名
- `COMMAND DOCS` 当前命令名定向查询和无参数全量 docs 查询都可用；全量返回使用当前扩大的连接输出缓冲完成 RESP2/RESP3 大响应发送第一批闭环
- `COMMAND GETKEYS` 当前支持当前运行时命令表里的 key 提取，覆盖多 key、成对 key、`RENAME` 双 key、`SORT ... STORE` movablekeys 和错误路径
- `COMMAND GETKEYSANDFLAGS` 当前支持当前运行时命令表里的 key/flag 提取，覆盖 `RO/OW/RW/RM` 及 `access/update/insert/delete` 基础组合

### `PING`

格式：

```text
PING
PING message
```

返回：

- 无参数：`+PONG`
- 有参数：Bulk String 回显

### `ECHO`

格式：

```text
ECHO message
```

返回：

- Bulk String 回显

### `GET`

格式：

```text
GET key
```

返回：

- 命中：Bulk String
- 不存在：Null Bulk

### `APPEND`

格式：

```text
APPEND key value
```

返回：

- 追加后的字符串长度，Integer

语义：

- key 不存在时按空字符串处理并创建新 key

### `STRLEN`

格式：

```text
STRLEN key
```

返回：

- key 不存在：`0`
- 否则返回字符串字节长度

### `GETDEL`

格式：

```text
GETDEL key
```

返回：

- 命中：返回旧值 Bulk String，并删除 key
- 不存在：Null Bulk

### `INCR`

格式：

```text
INCR key
```

返回：

- 自增后的整数值，Integer

### `DECR`

格式：

```text
DECR key
```

返回：

- 自减后的整数值，Integer

### `INCRBY`

格式：

```text
INCRBY key increment
```

返回：

- 加法后的整数值，Integer

### `DECRBY`

格式：

```text
DECRBY key decrement
```

返回：

- 减法后的整数值，Integer

说明：

- key 不存在时按 `0` 处理
- key 必须持有可解析的十进制整数字符串，否则返回整数解析错误

### `INCRBYFLOAT`

格式：

```text
INCRBYFLOAT key increment
```

返回：

- 加法后的浮点字符串，Bulk String

说明：

- key 不存在时按 `0` 处理
- key 和 increment 都必须是合法十进制浮点文本
- 结果会归一化为最短常见十进制形态，例如 `1.5`、`3.5`

### `GETSET`

格式：

```text
GETSET key value
```

返回：

- key 不存在：Null Bulk，并写入新值
- key 存在：返回旧值 Bulk String，并写入新值

### `SETNX`

格式：

```text
SETNX key value
```

返回：

- 写入成功：`1`
- key 已存在：`0`

### `SETEX`

格式：

```text
SETEX key seconds value
```

返回：

- 成功：`+OK`

说明：

- 当前实现要求 `seconds > 0`
- AOF 中会展开为 `SET` + 绝对 `PEXPIREAT`

### `PSETEX`

格式：

```text
PSETEX key milliseconds value
```

返回：

- 成功：`+OK`

说明：

- 当前实现要求 `milliseconds > 0`
- AOF 中会展开为 `SET` + 绝对 `PEXPIREAT`

### `GETEX`

格式：

```text
GETEX key
GETEX key PERSIST
GETEX key EX seconds
GETEX key PX milliseconds
GETEX key EXAT unix-time-seconds
GETEX key PXAT unix-time-milliseconds
```

返回：

- 命中：返回 Bulk String
- 不存在：Null Bulk

说明：

- 无附加选项时只返回当前值，不改变 TTL
- `PERSIST` 会移除当前 TTL
- `EX` / `PX` 要求值大于 `0`
- `EXAT` / `PXAT` 使用绝对时间；若时间点已到或已过，会在返回当前值后删除 key
- AOF 中只写入 TTL / `PERSIST` 状态变更；相对 TTL 选项会折算成绝对 `PEXPIREAT`

### `HINCRBY`

格式：

```text
HINCRBY key field increment
```

返回：

- 加法后的整数值，Integer

说明：

- key 不存在时会创建 hash，并把 field 从 `0` 加到目标值
- field 已存在时必须持有合法十进制整数字符串

### `HINCRBYFLOAT`

格式：

```text
HINCRBYFLOAT key field increment
```

返回：

- 加法后的浮点字符串，Bulk String

说明：

- key 不存在时会创建 hash，并把 field 从 `0` 加到目标值
- field 和 increment 都必须是合法十进制浮点文本
- 返回值会归一化为最短常见十进制形态

### `HKEYS`

格式：

```text
HKEYS key
```

返回：

- 返回 hash 中全部 field 的 RESP Array
- key 不存在时返回空 Array

### `HVALS`

格式：

```text
HVALS key
```

返回：

- 返回 hash 中全部 value 的 RESP Array
- key 不存在时返回空 Array

### `HGETALL`

格式：

```text
HGETALL key
```

返回：

- 返回 `field, value, field, value...` 交替展开的 RESP Array
- key 不存在时返回空 Array

### `HDEL`

格式：

```text
HDEL key field [field ...]
```

返回：

- 返回实际删除的 field 数量，Integer

说明：

- key 不存在时返回 `0`
- 删除最后一个 field 后，当前实现会直接删除整个 hash key

### `HEXISTS`

格式：

```text
HEXISTS key field
```

返回：

- field 存在：`1`
- field 不存在或 key 不存在：`0`

### `HLEN`

格式：

```text
HLEN key
```

返回：

- key 不存在：`0`
- 否则返回 field 数量

### `HMGET`

格式：

```text
HMGET key field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 RESP Array
- 缺失 field 返回 Null Bulk
- key 不存在时，所有请求 field 都返回 Null Bulk

### `HSETNX`

格式：

```text
HSETNX key field value
```

返回：

- 新 field 写入成功：`1`
- field 已存在：`0`

说明：

- key 不存在时会创建 hash

### `HSTRLEN`

格式：

```text
HSTRLEN key field
```

返回：

- field 或 key 不存在：`0`
- 否则返回对应 value 的字节长度

### `HSCAN`

格式：

```text
HSCAN key cursor [COUNT count]
```

返回：

- 返回两段 RESP Array：`[next-cursor, [field1, value1, field2, value2...]]`
- 当前实现支持 `COUNT`
- key 不存在时返回 cursor `0` 和空 Array

### `RPUSH`

格式：

```text
RPUSH key value [value ...]
```

返回：

- 返回 list 新长度，Integer

### `RPOP`

格式：

```text
RPOP key
```

返回：

- 成功时返回尾元素 Bulk String
- key 不存在或空 list 返回 Null Bulk

### `LINDEX`

格式：

```text
LINDEX key index
```

返回：

- 返回指定位置元素，支持负索引
- 越界或 key 不存在时返回 Null Bulk

### `LSET`

格式：

```text
LSET key index value
```

返回：

- 成功：`+OK`
- key 不存在：`-ERR no such key`
- index 越界：`-ERR index out of range`

### `LLEN`

格式：

```text
LLEN key
```

返回：

- 返回 list 当前长度，Integer
- key 不存在时返回 `0`

### `LINSERT`

格式：

```text
LINSERT key BEFORE|AFTER pivot element
```

返回：

- 成功时返回插入后的 list 长度，Integer
- pivot 不存在时返回 `-1`
- key 不存在时返回 `0`

### `LTRIM`

格式：

```text
LTRIM key start stop
```

返回：

- 成功：`+OK`
- 按闭区间 `[start, stop]` 保留元素，支持负索引

### `LREM`

格式：

```text
LREM key count element
```

返回：

- 返回实际删除元素个数，Integer
- `count > 0` 从头开始删
- `count < 0` 从尾开始删
- `count = 0` 删除全部匹配元素

### `LPUSHX`

格式：

```text
LPUSHX key value [value ...]
```

返回：

- key 存在且为 list 时，返回新长度，Integer
- key 不存在时返回 `0`

### `RPUSHX`

格式：

```text
RPUSHX key value [value ...]
```

返回：

- key 存在且为 list 时，返回新长度，Integer
- key 不存在时返回 `0`

### `LPOS`

格式：

```text
LPOS key element
```

返回：

- 返回首个匹配元素位置，Integer
- 没有命中或 key 不存在时返回 Null Bulk

### `SPOP`

格式：

```text
SPOP key
```

返回：

- 返回一个被移除的成员 Bulk String
- key 不存在或空 set 返回 Null Bulk

### `SRANDMEMBER`

格式：

```text
SRANDMEMBER key
```

返回：

- 返回一个成员 Bulk String
- key 不存在或空 set 返回 Null Bulk

### `SINTER`

格式：

```text
SINTER key [key ...]
```

返回：

- 返回多个 set 的交集 RESP Array

### `SDIFF`

格式：

```text
SDIFF key [key ...]
```

返回：

- 返回第一个 set 相对后续 set 的差集 RESP Array

### `SUNION`

格式：

```text
SUNION key [key ...]
```

返回：

- 返回多个 set 的并集 RESP Array

### `SINTERSTORE`

格式：

```text
SINTERSTORE destination key [key ...]
```

返回：

- 把交集写入 `destination`
- 返回写入后的成员个数，Integer

### `SDIFFSTORE`

格式：

```text
SDIFFSTORE destination key [key ...]
```

返回：

- 把差集写入 `destination`
- 返回写入后的成员个数，Integer

### `SUNIONSTORE`

格式：

```text
SUNIONSTORE destination key [key ...]
```

返回：

- 把并集写入 `destination`
- 返回写入后的成员个数，Integer

### `SCARD`

格式：

```text
SCARD key
```

返回：

- key 不存在时返回 `0`
- 否则返回 set 成员个数，Integer

### `SISMEMBER`

格式：

```text
SISMEMBER key member
```

返回：

- 命中成员返回 `1`
- key 不存在或成员不存在返回 `0`

### `SMISMEMBER`

格式：

```text
SMISMEMBER key member [member ...]
```

返回：

- 返回与请求成员顺序一致的 RESP Array
- 每个元素都是 Integer：存在返回 `1`，否则返回 `0`

### `SSCAN`

格式：

```text
SSCAN key cursor [COUNT count]
```

返回：

- 返回 `[cursor, members-array]`
- key 不存在时返回 cursor `0` 和空数组

当前实现支持 `COUNT`

### `SMOVE`

格式：

```text
SMOVE source destination member
```

返回：

- 成员存在于 `source` 时返回 `1`，并把成员原子地从 `source` 搬到 `destination`
- `source` 不存在时返回 `0`
- `source == destination` 且成员存在时返回 `1`，集合内容保持不变
- `source` 清空后会删除源 key

### `ZINCRBY`

格式：

```text
ZINCRBY key increment member
```

返回：

- 返回递增后的 score，Bulk String
- 当前项目内 ZSet score 使用整数语义

### `ZCARD`

格式：

```text
ZCARD key
```

返回：

- 返回 zset 当前成员个数，Integer
- key 不存在时返回 `0`

### `ZCOUNT`

格式：

```text
ZCOUNT key min max
```

返回：

- 返回闭区间 `[min, max]` 内的成员个数，Integer
- 当前项目内 ZSet score 使用整数语义

### `ZRANGEBYSCORE`

格式：

```text
ZRANGEBYSCORE key min max
```

返回：

- 返回 score 落在闭区间 `[min, max]` 内的成员，按 score 升序
- 当前项目内 ZSet score 使用整数语义

### `ZREVRANGEBYSCORE`

格式：

```text
ZREVRANGEBYSCORE key max min
```

返回：

- 返回 score 落在闭区间 `[min, max]` 内的成员，按 score 降序
- 当前项目内 ZSet score 使用整数语义

### `ZREMRANGEBYRANK`

格式：

```text
ZREMRANGEBYRANK key start stop
```

返回：

- 删除 rank 落在闭区间 `[start, stop]` 内的成员
- 返回删除成员个数，Integer

### `ZREMRANGEBYSCORE`

格式：

```text
ZREMRANGEBYSCORE key min max
```

返回：

- 删除 score 落在闭区间 `[min, max]` 内的成员
- 返回删除成员个数，Integer

### `ZSCAN`

格式：

```text
ZSCAN key cursor [COUNT count]
```

返回：

- 返回两段 RESP Array：`[next-cursor, [member1, score1, member2, score2...]]`
- 当前实现支持 `COUNT`
- 当前项目内 ZSet score 使用整数语义

### `RENAME`

格式：

```text
RENAME key newkey
```

返回：

- 成功：`+OK`
- source 不存在：`-ERR no such key`
- source 和 target 相同：错误

### `RENAMENX`

格式：

```text
RENAMENX key newkey
```

返回：

- 重命名成功：`1`
- target 已存在：`0`
- source 不存在：`-ERR no such key`
- source 和 target 相同：错误

### `LASTSAVE`

格式：

```text
LASTSAVE
```

返回：

- 返回最近一次成功 `SAVE` / `BGSAVE` 的 Unix 秒时间戳，Integer

### `FLUSHDB`

格式：

```text
FLUSHDB
```

返回：

- 成功：`+OK`
- 当前单机实现中清空当前唯一数据库

### `FLUSHALL`

格式：

```text
FLUSHALL
```

返回：

- 成功：`+OK`
- 当前单机实现中等价于清空当前唯一数据库

### `DUMP`

格式：

```text
DUMP key
```

返回：

- 返回项目内 RDB 子集二进制 payload，Bulk String
- key 不存在时返回 Null Bulk

### `RESTORE`

格式：

```text
RESTORE key ttl serialized-value
```

返回：

- 成功：`+OK`
- target 已存在：`-BUSYKEY ...`
- payload 非法：错误

说明：

- `ttl` 为相对毫秒 TTL，`0` 表示不过期
- 当前实现不支持 `REPLACE` / `ABSTTL` / `IDLETIME` / `FREQ`

### `SELECT`

格式：

```text
SELECT index
```

返回：

- `index = 0`：`+OK`
- 非整数：`-ERR value is not an integer or out of range`
- 非 `0`：`-ERR DB index is out of range`

说明：

- 当前单机运行时只暴露一个数据库，`SELECT 0` 为兼容性切换，`SELECT` 到其他 DB 返回越界错误

### `OBJECT`

格式：

```text
OBJECT ENCODING key
OBJECT REFCOUNT key
OBJECT IDLETIME key
OBJECT FREQ key
OBJECT HELP
```

返回：

- `ENCODING`：返回对象当前内部编码，Bulk String
- `REFCOUNT`：返回对象引用计数，当前实现固定为 `:1`
- `IDLETIME`：返回对象近似空闲秒数，Integer；key 不存在时 Null Bulk
- `FREQ`：返回对象访问频次计数，Integer；key 不存在时 Null Bulk
- `HELP`：返回支持的 `OBJECT` 子命令列表

说明：

- `IDLETIME` / `FREQ` 查询本身不会刷新对象的 LRU/LFU 统计
- 当前实现下，LFU 淘汰策略未启用时 `OBJECT FREQ` 返回错误；LFU 淘汰策略启用时 `OBJECT IDLETIME` 返回错误

### `MOVE`

格式：

```text
MOVE key db
```

返回：

- 当前单机实现中：`db = 0` 返回 `-ERR source and destination objects are the same`
- 非整数 DB 参数：`-ERR value is not an integer or out of range`
- 非 `0`：`-ERR DB index is out of range`

说明：

- 当前运行时只暴露唯一数据库，因此 `MOVE` 只固化与单库模式一致的错误语义，不存在成功迁移路径

### `WAIT`

格式：

```text
WAIT numreplicas timeout
```

返回：

- 成功：返回 Integer
- `numreplicas` 非整数：`-ERR value is not an integer or out of range`
- `timeout` 非整数：`-ERR value is not an integer or out of range`
- `timeout < 0`：`-ERR timeout is negative`

说明：

- 当前单机实现下尚未引入副本 ACK 收敛路径，因此在参数合法时返回 `:0`
- `numreplicas <= 0` 时也直接返回 `:0`

### `SORT`

格式：

```text
SORT key [ASC|DESC] [ALPHA] [LIMIT offset count] [BY pattern] [GET pattern ...] [STORE destination]
```

返回：

- 默认返回排序后的 RESP Array
- 带 `STORE destination` 时返回写入元素个数，Integer
- 非数值排序且未指定 `ALPHA`：`-ERR One or more scores can't be converted into double`
- 选项缺参或未知选项：`-ERR syntax error`

说明：

- 当前实现支持 `list` / `set` / `zset` 作为源集合
- 支持 `BY nosort`
- 支持字符串 key pattern 与 hash field pattern，例如 `weight_*`、`user_*->score`
- 支持多次 `GET`；`GET #` 返回当前元素本身
- `GET` 缺失值在普通回复里返回 Null Bulk，在 `STORE` 路径里写入空字符串
- `LIMIT` 中 `offset < 0` 按 `0` 处理，`count < 0` 表示取到尾部
- `SORT STORE` 在当前实现中会覆盖目标 key 并清除其 TTL；结果为空时删除目标 key

### `SORT_RO`

格式：

```text
SORT_RO key [ASC|DESC] [ALPHA] [LIMIT offset count] [BY pattern] [GET pattern ...]
```

返回：

- 返回排序后的 RESP Array
- 非数值排序且未指定 `ALPHA`：`-ERR One or more scores can't be converted into double`
- 带 `STORE` 或未知/缺失选项：`-ERR syntax error`

说明：

- 当前实现复用 `SORT` 的只读路径
- 支持 `list` / `set` / `zset` 作为源集合
- 支持 `BY nosort`
- 支持字符串 key pattern 与 hash field pattern
- 不支持 `STORE destination`

### `MGET`

格式：

```text
MGET key [key ...]
```

返回：

- RESP Array，按请求顺序返回每个 key 的值或 Null Bulk

### `MSET`

格式：

```text
MSET key value [key value ...]
```

返回：

- 成功：`+OK`

### `MSETNX`

格式：

```text
MSETNX key value [key value ...]
```

返回：

- 所有 key 都不存在并完成写入：`1`
- 任一 key 已存在：`0`

### `GETRANGE`

格式：

```text
GETRANGE key start end
```

返回：

- 返回闭区间 `[start, end]` 的子串，支持负索引
- key 不存在或范围为空时返回空 Bulk String

### `SETRANGE`

格式：

```text
SETRANGE key offset value
```

返回：

- 写入后的字符串长度，Integer

说明：

- `offset` 必须为非负整数
- offset 超过当前长度时，中间空洞会用 `\\0` 填充

### `TYPE`

格式：

```text
TYPE key
```

返回：

- 键不存在：`+none`
- 键存在：返回 `string/hash/list/set/zset`

### `SET`

格式：

```text
SET key value
```

返回：

- 成功：`+OK`
- 额外选项当前返回 `-ERR syntax error`
- 当配置了 `maxmemory` 且当前策略无法腾出预算：`-OOM command not allowed when used memory > 'maxmemory'`

说明：

- `noeviction` 策略不主动淘汰，超预算增量写命令直接失败
- `allkeys-lru` 策略会按 top-level key 的最近访问时间淘汰最久未访问 key，再执行当前写命令
- `allkeys-lfu` 策略会按 top-level key 的访问计数淘汰最低频 key，同频次用 LRU 打破平局
- `volatile-lru` / `volatile-lfu` / `volatile-ttl` 只从带 TTL 的 key 中选候选；没有可淘汰 volatile key 时返回 OOM

### `DEL`

格式：

```text
DEL key [key ...]
```

返回：

- 删除成功的键数量，Integer

### `TOUCH`

格式：

```text
TOUCH key [key ...]
```

返回：

- 返回本次请求中存在且被访问到的 key 数量，Integer

### `UNLINK`

格式：

```text
UNLINK key [key ...]
```

返回：

- 返回成功移除的 key 数量，Integer

说明：

- 当前实现先提供 standalone 兼容返回值与删除闭环
- 现阶段仍按单线程同步删除完成，不做后台异步释放

### `KEYS`

格式：

```text
KEYS pattern
```

返回：

- 返回匹配当前数据库非过期 key 的 RESP Array

说明：

- 当前实现支持 `*` 与 `?` 通配
- 返回结果按字典序稳定输出
- 当前实现只覆盖最小 glob 语义，不包含更完整字符类等扩展

### `DBSIZE`

格式：

```text
DBSIZE
```

返回：

- 当前数据库中的非过期 key 数量，Integer

### `RANDOMKEY`

格式：

```text
RANDOMKEY
```

返回：

- 空库：Null Bulk
- 非空：返回一个 key 的 Bulk String

说明：

- 当前实现基于有序 key 列表和请求时间做确定性选择，用于 standalone 兼容和测试闭环；尚未追求 Redis 的随机分布特性

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

### `EXPIREAT`

格式：

```text
EXPIREAT key unix_s
```

返回：

- 设置成功：`1`
- 键不存在：`0`

说明：

- 使用 Unix 秒级绝对时间
- 若目标时间点已到或已过，会立即删除 key
- AOF 中会转换为绝对时间 `PEXPIREAT`

### `PEXPIRE`

格式：

```text
PEXPIRE key milliseconds
```

返回：

- 设置成功或毫秒数为 `0` 时删除成功：`1`
- 键不存在：`0`

语义：

- 毫秒数为 `0` 立即删除
- AOF 中会转换为绝对时间 `PEXPIREAT`

### `PERSIST`

格式：

```text
PERSIST key
```

返回：

- 成功移除过期时间：`1`
- 键不存在或本来就没有 TTL：`0`

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

### `EXPIRETIME`

格式：

```text
EXPIRETIME key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回 Unix 秒级绝对过期时间

### `PEXPIRETIME`

格式：

```text
PEXPIRETIME key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回 Unix 毫秒级绝对过期时间

### `TTL`

格式：

```text
TTL key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回剩余秒数

### `PTTL`

格式：

```text
PTTL key
```

返回：

- 键不存在：`-2`
- 无过期时间：`-1`
- 否则返回剩余毫秒数

### `TIME`

格式：

```text
TIME
```

返回：

- 两元素 RESP Array：`[unix-seconds, microseconds]`

说明：

- 当前实现由命令执行时传入的毫秒时间戳换算秒和微秒部分
- 微秒部分固定是当前毫秒余数乘以 `1000`

### `ROLE`

格式：

```text
ROLE
```

返回：

- master：`[master, replication-offset, []]`
- replica：`[slave, master-host, master-port, replication-state, replication-offset]`

说明：

- 当前 standalone 路径只覆盖 `master` / `slave` 两种返回形态，不包含 Sentinel 角色
- master 形态里的第三个元素当前固定为空数组，表示没有额外下游副本明细
- replica 形态里的 host/port/state 来自当前运行时复制配置与状态机

### `INFO`

格式：

```text
INFO
INFO server
INFO replication
INFO memory
INFO stats
INFO keyspace
```

返回：

- 支持 `server`、`clients`、`memory`、`stats`、`replication`、`keyspace`
- 未带 section 时返回上述 section 组合段
- `memory` section 当前包含 `used_memory`、`used_memory_peak`、`total_allocated`、`total_freed`、`allocator_total_allocations`、`allocator_active_allocations`、`allocator_slab_cached_blocks`、`allocator_slab_cached_bytes`、`allocator_slab_reuse_count`、`object_pool_cached_objects`、`object_pool_cached_list_nodes`、`object_pool_reuse_count`、`object_layout_size`、`list_node_layout_size`、`maxmemory`、`maxmemory_policy`

### `CONFIG`

格式：

```text
CONFIG GET pattern
CONFIG SET parameter value [parameter value ...]
CONFIG REWRITE
CONFIG HELP
CONFIG RESETSTAT
```

返回：

- 返回 RESP Array，按 `name`、`value` 成对展开
- 当前支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`replicaof`、`masterauth`、`maxmemory`、`maxmemory-policy`、`maxclients`、`databases`、`save`
- 支持最小 `*` 通配模式
- `CONFIG SET` 当前支持运行时子集：`requirepass`、`maxmemory`、`maxmemory-policy`、`save`
- `CONFIG REWRITE` 当前会把运行时有效配置写到 `<appendfilename>.conf`，成功返回 `+OK`；当前已覆盖 `maxclients`、`databases` 等第二批运行时字段的落盘
- `CONFIG HELP` 返回当前支持的 CONFIG 子命令列表
- `CONFIG RESETSTAT` 当前返回 `+OK`，用于客户端兼容；统计重置仍是最小占位语义
- `CONFIG REWRITE` 当前是最小实现：目标文件路径按当前 AOF 路径派生，不保留原始配置文件注释/顺序；其余更高风险的 `CONFIG SET` 字段热更新仍不支持

### `CLIENT`

格式：

```text
CLIENT ID
CLIENT GETNAME
CLIENT GETREDIR
CLIENT SETNAME name
CLIENT INFO
CLIENT LIST
CLIENT KILL ID id
CLIENT PAUSE timeout-ms [WRITE|ALL]
CLIENT UNPAUSE
CLIENT TRACKING ON [REDIRECT id] [BCAST] [OPTIN] [OPTOUT] [NOLOOP]
CLIENT TRACKING OFF
CLIENT TRACKINGINFO
CLIENT SETINFO LIB-NAME value
CLIENT SETINFO LIB-VER value
CLIENT HELP
```

返回：

- `CLIENT ID`：当前连接的整数 ID；服务端按连接事务分配递增 ID，测试重置后的首个连接从 `1` 开始
- `CLIENT GETNAME`：未设置时返回 Null Bulk，已设置时返回 Bulk String
- `CLIENT GETREDIR`：返回当前连接 tracking redirect 客户端 ID；未设置时返回 `-1`
- `CLIENT SETNAME`：保存连接级客户端名，成功返回 `+OK`
- `CLIENT INFO`：返回当前连接的最小客户端信息行，包含 `id/name/resp/multi/sub/lib-name/lib-ver`
- `CLIENT LIST`：返回当前活跃连接的最小信息行快照，每行包含 `id/name/resp/multi/sub/lib-name/lib-ver`
- `CLIENT KILL ID id`：按连接 ID 关闭其他活跃连接；当前只支持 `ID` 过滤，返回整数 `0/1`
- `CLIENT PAUSE timeout-ms [WRITE|ALL]`：暂停其他连接的命令处理；当前 `WRITE`/`ALL` 都按全局暂停处理，返回 `+OK`
- `CLIENT UNPAUSE`：提前解除当前 pause 状态，返回 `+OK`
- `CLIENT TRACKING`：当前支持连接级 `ON/OFF`、`REDIRECT`、`BCAST`、`OPTIN`、`OPTOUT`、`NOLOOP` 标志存储，返回 `+OK`
- `CLIENT TRACKINGINFO`：RESP2 下返回 flatten array，RESP3 下返回 map，暴露当前连接的 tracking flags、redirect 和 prefixes
- `CLIENT SETINFO`：保存客户端库名/版本元数据，成功返回 `+OK`
- `CLIENT HELP`：返回当前支持的 CLIENT 子命令列表

说明：

- 客户端名和 `SETINFO` 元数据存放在连接级 `ConnectionTransaction`
- `CLIENT GETREDIR` 直接读取当前连接的 `tracking_redirect_id`
- `CLIENT KILL` 当前只支持 `ID <id>` 过滤，不支持更完整的 addr/type/user/maxage/skipme 组合
- `CLIENT PAUSE` 当前保留发起暂停的控制连接可继续发送 `CLIENT UNPAUSE`；`WRITE` 语义还没有细分成仅写命令暂停
- `CLIENT TRACKING` 当前只保存连接级状态，不发送 invalidation push，也不支持 `PREFIX`

### `CLUSTER`

格式：

```text
CLUSTER KEYSLOT key
CLUSTER INFO
CLUSTER NODES
CLUSTER SLOTS
CLUSTER MEET ip port
CLUSTER SETSLOT slot NODE node-id
CLUSTER SETSLOT slot MIGRATING node-id
CLUSTER SETSLOT slot STABLE
CLUSTER HELP
```

返回：

- `CLUSTER KEYSLOT key`：按 Redis Cluster CRC16/hash tag 规则返回 `0..16383` 槽位
- `CLUSTER INFO`：Bulk String，包含 `cluster_enabled:1`、`cluster_state:ok`、`cluster_slots_assigned`、`cluster_known_nodes` 与 `cluster_size`
- `CLUSTER NODES`：Bulk String，返回当前最小拓扑中的本地与远端节点，包含节点地址、连接状态和已归属 slot 范围
- `CLUSTER SLOTS`：RESP Array，当前返回单个 `0..16383` 槽位范围及本地节点地址、端口和 node id
- `CLUSTER MEET ip port`：在服务端最小拓扑中注册远端 master 节点元数据
- `CLUSTER SETSLOT slot NODE node-id`：把指定 slot 的稳定 owner 设置为已知节点；若 owner 不是本节点，后续首 key 落该 slot 的命令返回 `-MOVED slot host:port`
- `CLUSTER SETSLOT slot MIGRATING node-id`：把指定 slot 标记为迁移到已知节点；后续首 key 落该 slot 的命令返回 `-ASK slot host:port`
- `CLUSTER SETSLOT slot STABLE`：清除指定 slot 的迁移态 `ASK` 标记
- `CLUSTER HELP`：返回当前支持的 CLUSTER 子命令列表

说明：

- 当前 `CLUSTER` 命令使用单节点最小拓扑，默认本节点拥有全部 16384 个槽
- 当前 `MEET/SETSLOT` 是最小控制面，不实现 Redis Cluster gossip、节点握手、故障检测和配置纪元冲突解决
- 当前 `MOVED` / `ASK` 只基于命令首个 key 判断，不实现完整多 key 同槽校验和 `ASKING` 一次性放行
- 当前不支持 `CLUSTER ADDSLOTS`、`REPLICATE`、`FAILOVER` 等拓扑变更命令

### `MULTI`

格式：

```text
MULTI
```

返回：

- 成功：`+OK`
- 嵌套调用：`-ERR MULTI calls can not be nested`

说明：

- 当前实现是连接级最小事务队列
- 进入事务态后，后续命令先返回 `+QUEUED`

### `EXEC`

格式：

```text
EXEC
```

返回：

- 成功：RESP Array，按入队顺序返回每条命令的真实回复
- 未进入 `MULTI`：`-ERR EXEC without MULTI`

说明：

- 当前按单线程顺序执行队列中的命令
- 队列中的写命令会在 `EXEC` 时真正落 AOF / replication backlog

### `DISCARD`

格式：

```text
DISCARD
```

返回：

- 成功：`+OK`
- 未进入 `MULTI`：`-ERR DISCARD without MULTI`

说明：

- 会清空当前连接已入队命令，并退出事务态

### `WATCH`

格式：

```text
WATCH key [key ...]
```

返回：

- 成功：`+OK`
- 在 `MULTI` 事务态内调用：`-ERR WATCH inside MULTI is not allowed`

说明：

- 当前按键记录观察版本
- 被观察键在 `EXEC` 前被其他写命令改动时，`EXEC` 返回 Null Array

### `UNWATCH`

格式：

```text
UNWATCH
```

返回：

- 成功：`+OK`
- 在 `MULTI` 事务态内调用：`-ERR UNWATCH inside MULTI is not allowed`

说明：

- 会清空当前连接的观察集
- `EXEC` 或 `DISCARD` 完成后也会自动清空观察集

### `SUBSCRIBE`

格式：

```text
SUBSCRIBE channel [channel ...]
```

返回：

- 每个频道返回一个订阅确认：`["subscribe", channel, count]`
- RESP3 模式下订阅确认使用 Push 形式

说明：

- 当前实现为固定容量连接级订阅注册表
- RESP2 订阅态下只允许继续执行 `SUBSCRIBE/PSUBSCRIBE/UNSUBSCRIBE/PUNSUBSCRIBE/PING/QUIT/RESET`
- RESP3 订阅态下，非 Pub/Sub 命令仍可继续执行
- 连接关闭后会自动清理该连接持有的频道订阅项

### `PUBSUB`

格式：

```text
PUBSUB HELP
PUBSUB CHANNELS [pattern]
PUBSUB NUMPAT
PUBSUB NUMSUB [channel ...]
PUBSUB SHARDCHANNELS [pattern]
PUBSUB SHARDNUMSUB [shardchannel ...]
```

返回：

- `HELP`：帮助文本数组
- `CHANNELS`：当前存在直连订阅的频道数组；带 `pattern` 时按 glob 过滤
- `NUMPAT`：当前 pattern 订阅总数，Integer
- `NUMSUB`：扁平数组 `[channel, subscriber_count, ...]`，不计 pattern 订阅
- `SHARDCHANNELS`：当前返回空数组
- `SHARDNUMSUB`：当前对每个请求 shard channel 返回 `0`

说明：

- `CHANNELS` 只统计直连频道订阅，不把 pattern 订阅投影为频道
- `NUMPAT` 统计当前连接注册表里的 pattern 订阅项总数
- 当前尚未实现 `SSUBSCRIBE/SPUBLISH`，因此 `SHARDCHANNELS/SHARDNUMSUB` 只固化空结果边界
- RESP2 订阅态下 `PUBSUB` 仍不在允许命令集合内

### `PSUBSCRIBE`

格式：

```text
PSUBSCRIBE pattern [pattern ...]
```

返回：

- 每个 pattern 返回一个订阅确认：`["psubscribe", pattern, count]`

说明：

- 匹配发布时会向订阅者推送 `["pmessage", pattern, channel, message]`

### `UNSUBSCRIBE`

格式：

```text
UNSUBSCRIBE
UNSUBSCRIBE channel [channel ...]
```

返回：

- 每个频道返回一个取消订阅确认：`["unsubscribe", channel, remaining_count]`

说明：

- 显式频道取消订阅后，后续 `PUBLISH` 不再向该连接推送对应消息
- 连接关闭后也会自动移除该连接持有的频道订阅项

### `PUNSUBSCRIBE`

格式：

```text
PUNSUBSCRIBE
PUNSUBSCRIBE pattern [pattern ...]
```

返回：

- 每个 pattern 返回一个取消订阅确认：`["punsubscribe", pattern, remaining_count]`

### `PUBLISH`

格式：

```text
PUBLISH channel message
```

返回：

- 收到消息的订阅者数量，Integer

说明：

- 订阅者会收到 `["message", channel, message]`
- RESP3 模式下消息使用 Push 形式
- 当前不把 `PUBLISH` 追加到 AOF，也不复制到 backlog

### `SAVE`

格式：

```text
SAVE
```

返回：

- 成功：`+OK`
- 当前支持把 String/Hash/List/Set/ZSet 与绝对过期时间写入项目内 RDB 子集格式

### `BGSAVE`

格式：

```text
BGSAVE
```

返回：

- 成功：`+Background saving scheduled`
- 走真实 `fork/waitpid` 子进程后台保存
- 当前写出的 RDB 子集覆盖 String/Hash/List/Set/ZSet 与绝对过期时间

### `BGREWRITEAOF`

格式：

```text
BGREWRITEAOF
```

返回：

- 成功：`+Background AOF rewrite scheduled`
- 走真实子进程后台 rewrite
- 父进程会记录 rewrite 增量缓冲，并在子进程结束后合并到新 AOF
- rewrite 产物会把当前内存态规范化写成可回放 AOF

### `REPLICAOF`

格式：

```text
REPLICAOF host port
REPLICAOF NO ONE
```

返回：

- 成功：`+OK`
- 当前仅完成复制角色与状态机切换，不包含 `PSYNC`、全量同步、增量同步和心跳

### `PSYNC`

格式：

```text
PSYNC ? -1
PSYNC replid offset
```

返回：

- 首次同步或 backlog 不命中：`+FULLRESYNC <replid> <offset>`
- backlog 命中：`+CONTINUE <master_offset>`，后跟一个 bulk payload 作为 backlog delta
- 当前支持最小全量同步：`FULLRESYNC` 后跟一份项目内 RDB 快照
- 当前 replica 侧已支持把这份快照落库
- 当前增量同步由 replica 周期性轮询 `PSYNC replid offset` 完成，不是长连接推送流

### `QUIT`

格式：

```text
QUIT
```

返回：

- `+OK`

### `RESET`

格式：

```text
RESET
```

返回：

- `+RESET`

说明：

- 清空当前连接的事务队列、WATCH、Pub/Sub 订阅、CLIENT TRACKING 状态和客户端名称/库信息
- 把 RESP3 连接切回 RESP2
- 启用 `requirepass` 时，`RESET` 后当前连接需要重新 `AUTH`

### `SHUTDOWN`

格式：

```text
SHUTDOWN
SHUTDOWN NOSAVE
SHUTDOWN SAVE
```

返回：

- 成功时不返回 RESP 内容，服务端直接关闭当前连接并退出进程
- 参数非法：`-ERR syntax error`
- 未认证：`-NOAUTH Authentication required.`

说明：

- 当前实现支持最小 `SHUTDOWN` / `NOSAVE` / `SAVE` 形状
- `SHUTDOWN` 不能在事务中使用；事务内返回 `-ERR Command not allowed inside a transaction`

## 3. 错误

当前已覆盖的基础错误响应：

- `-ERR unknown command`
- `-ERR wrong number of arguments`
- `-ERR syntax error`
- `-ERR invalid request`
- `-ERR protocol error`
- `-ERR value is not an integer or out of range`

协议错误会在返回错误后关闭当前连接。
