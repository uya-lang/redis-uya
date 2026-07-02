# redis-uya API

> 版本: v0.9.1-dev
> 日期: 2026-05-09
> 当前主线口径: 本文只承诺已在 `v0.9.1-dev` 主线落地并有测试证据的语义；`v0.9.2+` 高级数据、运维、安全与可观测能力，除非对应命令章节明确写出，否则不视为当前可用

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
HELLO 2 AUTH default password
HELLO 3 AUTH default password
HELLO 2 SETNAME name
HELLO 3 SETNAME name
HELLO 2 AUTH default password SETNAME name
HELLO 3 AUTH default password SETNAME name
```

返回：

- `HELLO 2`：切回 RESP2，并返回 RESP2 Array 形式的服务信息
- `HELLO 3`：切到 RESP3，并返回 RESP3 Map 形式的服务信息
- 不支持的协议版本：`-NOPROTO unsupported protocol version`

说明：

- 当前 `HELLO` 支持 `AUTH default password` 与 `SETNAME name` 扩展参数，两个扩展可组合使用
- 启用 `requirepass` 后，未认证且未带 `AUTH` 的 `HELLO` 返回 `-NOAUTH Authentication required.`；带 `AUTH` 且密码错误时返回 `-WRONGPASS ...`，不会切换协议版本或设置客户端名
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

### `ACL`

格式：

```text
ACL CAT [category]
ACL DELUSER username [username ...]
ACL DRYRUN username command [arg ...]
ACL GENPASS [bits]
ACL GETUSER username
ACL HELP
ACL LIST
ACL LOAD
ACL LOG [count | RESET]
ACL SAVE
ACL SETUSER username [attribute ...]
ACL USERS
ACL WHOAMI
```

返回：

- `ACL CAT` 返回 Redis 兼容的 ACL category 列表；`ACL CAT category` 返回当前可见命令目录中匹配该 category 的命令名
- `ACL DELUSER missing` 当前返回 `0`；尝试删除 `default` 会返回 Redis 兼容错误
- `ACL DRYRUN default command [arg ...]` 当前会检查命令存在性、arity、默认用户命令 deny list 与分类 deny list；未知用户和未知命令返回 Redis 兼容错误，被 `ACL SETUSER default -cmd` 或 `-@category` 禁用的命令返回 `NOPERM`
- `ACL GENPASS` 返回 256-bit 口径的 64 字符十六进制口令；`ACL GENPASS bits` 返回 `ceil(bits / 4)` 个十六进制字符，`bits` 取值范围为 `1..4096`
- `ACL GETUSER default` 返回当前默认用户详情，并在 `commands` 字段中反映当前命令和分类 deny list；启用 `requirepass` 时 `flags` 不再包含 `nopass`，`passwords` 返回 `#` 开头的哈希标记而不暴露明文；未知用户名返回 null
- `ACL HELP` 返回 Redis 兼容的 ACL 子命令帮助数组
- `ACL LIST` 返回当前默认用户的 config file 格式描述；默认是 `user default on nopass ~* &* +@all`，启用 `requirepass` 时会用 `#` 开头的哈希标记替代 `nopass`，执行 `ACL SETUSER default -get` 或 `-@string` 后会追加对应 deny 规则
- `ACL LOAD` 当前按未配置 ACL 文件的 Redis 兼容错误返回，不会修改用户状态
- `ACL LOG [count]` 当前返回默认用户命令权限拒绝的进程内 ring 日志，覆盖 `ACL DRYRUN`、真实命令、事务队列前置拒绝和脚本内部命令拒绝产生的 `NOPERM`，字段包含 `reason/context/object/username/age-seconds/client-info/entry-id/timestamp-created/timestamp-last-updated/count`，其中 `client-info` 会记录拒绝发生时的真实连接 `id/addr/laddr`；`ACL LOG RESET` 会清空该日志
- `ACL SAVE` 当前按未配置 ACL 文件的 Redis 兼容错误返回，不会写入 ACL 文件
- `ACL SETUSER default [attribute ...]` 当前支持不会改变固定默认用户视图的 no-op 修饰符，例如 `on nopass ~* &* +@all resetkeys resetchannels clearselectors resetselectors`，也支持命令级 `-cmd` / `+cmd`、分类级 `-@category` / `+@category` 和 `resetcommands`；例如 `ACL SETUSER default -get` 或 `ACL SETUSER default -@string` 会让后续 `GET` 与 `ACL DRYRUN default GET ...` 返回 `NOPERM User default has no permissions to run the 'get' command`，`ACL SETUSER default +get`、`+@string`、`+@all` 或 `resetcommands` 会恢复对应拒绝
- `ACL USERS` 返回当前已知用户名数组；当前仅包含 `default`
- `ACL WHOAMI` 返回当前连接用户名；当前始终为 `default`

说明：

- 当前实现为 partial，仅暴露 `ACL CAT`、`ACL DELUSER`、`ACL DRYRUN`、`ACL GENPASS`、`ACL GETUSER`、`ACL HELP`、`ACL LIST`、`ACL LOAD`、`ACL LOG`、`ACL SAVE`、`ACL SETUSER`、`ACL USERS`、`ACL WHOAMI` 和 `COMMAND*` 可见面
- `COMMAND INFO/LIST/DOCS` 会暴露 `ACL`、`ACL|CAT`、`ACL|DELUSER`、`ACL|DRYRUN`、`ACL|GENPASS`、`ACL|GETUSER`、`ACL|HELP`、`ACL|LIST`、`ACL|LOAD`、`ACL|LOG`、`ACL|SAVE`、`ACL|SETUSER`、`ACL|USERS` 与 `ACL|WHOAMI`
- 当前不支持 ACL 用户存储、密码管理、完整 Redis 分类授权模型、key pattern 权限、selector 权限或 ACL 文件加载保存；命令级 deny list、分类级 deny list 与 ACL LOG 都是进程内状态，尚未持久化到 ACL 文件或 RDB/AOF

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
- `COMMAND GETKEYS` 当前支持当前运行时命令表里的 key 提取，覆盖多 key、成对 key、`RENAME` 双 key、`SORT ... STORE` / `BLMPOP` / `ZMPOP` / `BZMPOP` movablekeys 和错误路径
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

### `DELEX`

格式：

```text
DELEX key [IFEQ value | IFNE value | IFDEQ digest | IFDNE digest]
```

返回：

- 未带条件时：key 存在则删除并返回 `1`，key 不存在返回 `0`
- `IFEQ value`：当前 String 值等于 `value` 时删除并返回 `1`，否则返回 `0`
- `IFNE value`：当前 String 值不等于 `value` 时删除并返回 `1`，否则返回 `0`
- 条件路径中 key 不存在：`0`
- 条件路径中 key 存在且不是 String：`WRONGTYPE`
- `IFDEQ` / `IFDNE` 当前返回 `ERR DELEX digest conditions are not supported by redis-uya partial`

说明：

- 当前实现为 partial，仅支持字符串值比较条件；`DELEX` 的 digest 条件暂未接入，独立 `DIGEST` 命令已提供短字符串 XXH3_64 查询兼容面
- `COMMAND INFO/LIST/DOCS` 与 `COMMAND GETKEYS*` 会暴露 `DELEX`，key flags 标记为 `RM/delete`

### `DIGEST`

格式：

```text
DIGEST key
```

返回：

- key 不存在：Null Bulk
- key 存在且是 String，且值长度不超过 128 字节：返回 XXH3_64 digest 的 16 字节小写十六进制 Bulk String
- key 存在但不是 String：`WRONGTYPE`
- String 值长度超过 128 字节：`ERR DIGEST only supports string values up to 128 bytes in redis-uya partial`

说明：

- 当前为 partial，只覆盖独立 `DIGEST key` 的短字符串查询；暂不把该 digest 接入 `DELEX IFDEQ/IFDNE`
- `COMMAND INFO/LIST/DOCS` 与 `COMMAND GETKEYS*` 会暴露 `DIGEST`，key flags 标记为 `RO/access`

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

### `INCREX`

格式：

```text
INCREX key [BYINT increment] [LBOUND lower-bound] [UBOUND upper-bound] [SATURATE] [EX seconds|PX milliseconds|EXAT unix-time-seconds|PXAT unix-time-milliseconds|PERSIST] [ENX]
```

返回：

- RESP Array，包含两个 Integer：`[new-value, actual-increment]`

说明：

- 当前实现为 integer-mode partial；key 不存在时按 `0` 处理，默认增量为 `1`
- `BYINT`、`LBOUND`、`UBOUND` 参数必须为合法十进制整数
- 越界且未指定 `SATURATE` 时返回 `[current-value, 0]`，不写入 key，也不改变 TTL
- 指定 `SATURATE` 时会把结果钳制到上下界，第二个整数返回实际应用的增量
- 未提供过期选项时保留原 TTL；`EX/PX/EXAT/PXAT` 设置新 TTL；`PERSIST` 清理 TTL
- `ENX` 仅可与 `EX/PX/EXAT/PXAT` 同用；当前增量总会执行，只有目标 key 已有 TTL 时跳过新 TTL 设置
- `BYFLOAT` 当前返回 partial 限制错误，尚不支持浮点结果和浮点边界

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

### `HSET`

格式：

```text
HSET key field value [field value ...]
```

返回：

- 返回本次新创建的 field 数量
- 覆盖已有 field 不计入返回值

说明：

- key 不存在时会创建 hash
- key 存在但不是 hash 时返回 `WRONGTYPE`
- 参数数量必须为 key 后接一组或多组 field/value

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

### `HRANDFIELD`

格式：

```text
HRANDFIELD key [count [WITHVALUES]]
```

返回：

- 未传 `count` 时返回一个 field，key 不存在时返回 Null Bulk
- 传 `count` 时返回 field 数组，key 不存在时返回空数组
- 传 `WITHVALUES` 时返回 `field, value, field, value...` 交替展开的数组

说明：

- 当前实现为 deterministic random-field partial，按 field 字典序稳定返回
- `count > 0` 时最多返回 hash 中已有 field 数量；`count < 0` 时允许按稳定顺序循环重复

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

### `HGETDEL`

格式：

```text
HGETDEL key FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 RESP Array
- 命中 field 返回删除前的 Bulk String，并删除该 field
- 缺失 field 返回 Null Bulk
- key 不存在时，所有请求 field 都返回 Null Bulk

说明：

- `numfields` 必须为正整数，并且必须与后续 field 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`
- 删除最后一个 field 后，当前实现会直接删除整个 hash key

### `HGETEX`

格式：

```text
HGETEX key [EX seconds|PX milliseconds|EXAT unix-time-seconds|PXAT unix-time-milliseconds|PERSIST] FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 RESP Array
- 命中 field 返回 Bulk String
- 缺失 field 返回 Null Bulk
- key 不存在时，所有请求 field 都返回 Null Bulk

说明：

- 当前实现为 partial，支持 `EX` / `PX` / `EXAT` / `PXAT` / `PERSIST` 语法和整数校验，但尚未保存真实 hash field TTL 元数据，因此不会修改 field TTL 或触发 field 级过期
- `numfields` 必须为正整数，并且必须与后续 field 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`

### `HSETEX`

格式：

```text
HSETEX key [FNX|FXX] [EX seconds|PX milliseconds|EXAT unix-time-seconds|PXAT unix-time-milliseconds|KEEPTTL] FIELDS numfields field value [field value ...]
```

返回：

- 条件满足并设置所有 field 时返回 `1`
- `FNX` / `FXX` 条件不满足时返回 `0`

说明：

- 当前实现为 partial，支持 field 写入、`FNX` / `FXX` 条件、TTL option 语法和整数校验，但尚未保存真实 hash field TTL 元数据，因此不会触发 field 级过期
- `numfields` 必须为正整数，并且必须与后续 field/value 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`

### `HEXPIRE` / `HPEXPIRE` / `HEXPIREAT` / `HPEXPIREAT`

格式：

```text
HEXPIRE key seconds [NX|XX|GT|LT] FIELDS numfields field [field ...]
HPEXPIRE key milliseconds [NX|XX|GT|LT] FIELDS numfields field [field ...]
HEXPIREAT key unix-time-seconds [NX|XX|GT|LT] FIELDS numfields field [field ...]
HPEXPIREAT key unix-time-milliseconds [NX|XX|GT|LT] FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 Integer Array
- field 存在且条件允许设置过期时间：`1`
- field 存在但 `XX` / `GT` 等条件不满足：`0`
- 相对 TTL `<= 0` 或绝对时间戳已到期且条件允许时删除该 field：`2`
- field 或 key 不存在：`-2`

说明：

- 当前实现为 partial，支持 `NX` / `XX` / `GT` / `LT` 条件、相对 TTL / 绝对时间戳整数校验、field 删除和数组回复，但尚未保存真实 hash field TTL 元数据，因此未来过期时间不会触发后续 field 级过期
- 在无 field TTL 元数据场景下，存在 field 视为无过期时间：`NX` / `LT` 可以匹配，`XX` / `GT` 不匹配
- `numfields` 必须为正整数，并且必须与后续 field 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`

### `HTTL` / `HPTTL`

格式：

```text
HTTL key FIELDS numfields field [field ...]
HPTTL key FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 Integer Array
- field 存在但没有 field TTL：`-1`
- field 或 key 不存在：`-2`

说明：

- 当前实现为 partial，尚未保存真实 hash field TTL 元数据，因此不会返回正 TTL
- `numfields` 必须为正整数，并且必须与后续 field 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`

### `HEXPIRETIME` / `HPEXPIRETIME`

格式：

```text
HEXPIRETIME key FIELDS numfields field [field ...]
HPEXPIRETIME key FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 Integer Array
- field 存在但没有 field TTL：`-1`
- field 或 key 不存在：`-2`

说明：

- 当前实现为 partial，尚未保存真实 hash field TTL 元数据，因此不会返回正绝对过期时间
- `HEXPIRETIME` 与 `HPEXPIRETIME` 只覆盖无 field TTL 元数据场景的查询兼容面，不代表 `HEXPIRE/HPEXPIRE/HEXPIREAT/HPEXPIREAT` 未来过期时间已保存真实 field TTL 元数据

### `HPERSIST`

格式：

```text
HPERSIST key FIELDS numfields field [field ...]
```

返回：

- 返回与请求 field 顺序一致的 Integer Array
- field 存在但没有 field TTL：`-1`
- field 或 key 不存在：`-2`

说明：

- 当前实现为 partial，尚未保存真实 hash field TTL 元数据，因此不会返回 `1`
- `numfields` 必须为正整数，并且必须与后续 field 数量一致
- key 存在但不是 hash 时返回 `WRONGTYPE`

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

### `HMSET`

格式：

```text
HMSET key field value [field value ...]
```

返回：

- 写入成功：`OK`

说明：

- key 不存在时会创建 hash
- key 存在但不是 hash 时返回 `WRONGTYPE`
- 参数数量必须为 key 后接一组或多组 field/value

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

### `LPOP`

格式：

```text
LPOP key [count]
```

返回：

- 不带 `count` 时，成功返回头元素 Bulk String
- 带 `count` 时，返回从头部弹出的元素数组
- key 不存在或空 list 返回 Null Bulk
- `count` 为 `0` 时返回空 Array

### `RPOP`

格式：

```text
RPOP key [count]
```

返回：

- 不带 `count` 时，成功返回尾元素 Bulk String
- 带 `count` 时，返回从尾部弹出的元素数组
- key 不存在或空 list 返回 Null Bulk
- `count` 为 `0` 时返回空 Array

### `BLPOP`

格式：

```text
BLPOP key [key ...] timeout
```

返回：

- 命中时返回两段 RESP Array：`[key, element]`
- 超时返回 Null Array

说明：

- 当前支持多 key 顺序探测、秒级整数或浮点 timeout、server-side block/unblock
- 当较早 key 不存在时，会继续检查后续 key；当遇到已存在但错类型 key 时返回 `WRONGTYPE`

### `BRPOP`

格式：

```text
BRPOP key [key ...] timeout
```

返回：

- 命中时返回两段 RESP Array：`[key, element]`
- 超时返回 Null Array

说明：

- 语义与 `BLPOP` 相同，但从尾部弹出元素

### `BRPOPLPUSH`

格式：

```text
BRPOPLPUSH source destination timeout
```

返回：

- 命中时返回被搬移元素，Bulk String
- 超时返回 Null Bulk

说明：

- 当前支持 source 缺失时阻塞、source 就绪后从尾部弹出并推入 destination 头部
- AOF replay 复用相同命令序列，要求前序状态已由同一 AOF 正确重建

### `BLMOVE`

格式：

```text
BLMOVE source destination LEFT|RIGHT LEFT|RIGHT timeout
```

返回：

- 命中时返回被搬移元素，Bulk String
- 超时返回 Null Bulk

说明：

- 当前支持 source 缺失时阻塞、source 就绪后按方向从 source 弹出并按方向推入 destination
- 语义复用 `LMOVE` 的方向、同 key 搬移、错类型和目标列表创建逻辑
- AOF replay 复用相同命令序列，要求前序状态已由同一 AOF 正确重建

### `BLMPOP`

格式：

```text
BLMPOP timeout numkeys key [key ...] LEFT|RIGHT [COUNT count]
```

返回：

- 命中时返回两段 RESP Array：`[key, [element1, element2 ...]]`
- 超时返回 Null Array

说明：

- 当前支持多 key 顺序探测、`LEFT` / `RIGHT` 方向选择、可选 `COUNT` 和秒级整数或浮点 timeout
- 当前支持 server-side block/unblock，并在命中后删除已弹出的元素；key 被清空时会一并删除
- 当前 `COMMAND GETKEYS` / `COMMAND GETKEYSANDFLAGS` 已暴露 `BLMPOP` 的 movablekeys 提取结果
- 弹出语义复用 `LMPOP`，空源在连接层会先进入 blocking 状态，超时后返回 Null Array

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

### `SINTERCARD`

格式：

```text
SINTERCARD numkeys key [key ...] [LIMIT limit]
```

返回：

- 返回交集成员个数，Integer
- `LIMIT` 为正时，达到上限后直接返回上限值
- `LIMIT 0` 视为不限制

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

### `ZRANGE`

格式：

```text
ZRANGE key start stop [BYSCORE | BYLEX] [REV] [LIMIT offset count] [WITHSCORES]
```

返回：

- 返回按 score 升序排列后的索引区间成员
- 带 `REV` 时按 score 降序排列后再应用索引区间
- 带 `BYSCORE` 时把 `start` / `stop` 解释为整数 score 闭区间；`REV` 模式下 `start` 是 max、`stop` 是 min
- 带 `BYLEX` 时把 `start` / `stop` 解释为 Redis lex 边界；`REV` 模式下 `start` 是 max、`stop` 是 min
- 带 `WITHSCORES` 时返回 member / score 交错数组
- key 不存在时返回空数组

说明：

- 当前 rank 模式支持正负索引、闭区间 `[start, stop]`、`REV` 和 `WITHSCORES`
- 当前 `BYSCORE` 模式支持 `REV`、`WITHSCORES` 和 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前 `BYLEX` 模式支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`，支持 `REV` 和 `LIMIT offset count`，不支持与 `WITHSCORES` 组合
- 当前项目内 ZSet score 使用整数语义

### `ZLEXCOUNT`

格式：

```text
ZLEXCOUNT key min max
```

返回：

- 返回 member 字典序落在 `[min, max]` 内的成员个数，Integer
- key 不存在时返回 `0`

说明：

- 当前支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`
- 当前按项目内 ZSet 的 `(score, member)` 排序视图扫描并按 member 边界计数；与 Redis 一样，lex 范围命令的有效业务语义应使用同分 sorted set
- 非法边界返回 `ERR min or max not valid string range item`

### `ZRANGEBYLEX`

格式：

```text
ZRANGEBYLEX key min max [LIMIT offset count]
```

返回：

- 返回 member 字典序落在 `[min, max]` 内的成员数组
- key 不存在时返回空数组

说明：

- 当前支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`
- 当前支持 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前按项目内 ZSet 的 `(score, member)` 排序视图扫描并按 member 边界返回；与 Redis 一样，lex 范围命令的有效业务语义应使用同分 sorted set
- 新版 `ZRANGE ... BYLEX` 复合语法复用同一 lex 边界与 `LIMIT` 语义

### `ZRANGESTORE`

格式：

```text
ZRANGESTORE destination source start stop [BYSCORE | BYLEX] [REV] [LIMIT offset count]
```

返回：

- 返回写入 `destination` 的成员数量
- 写入 `source` 中 rank 落在闭区间 `[start, stop]` 内的成员，并保留原始 score
- 带 `BYSCORE` 时把 `start` / `stop` 解释为整数 score 闭区间；`REV` 模式下 `start` 是 max、`stop` 是 min
- 带 `BYLEX` 时把 `start` / `stop` 解释为 Redis lex 边界；`REV` 模式下 `start` 是 max、`stop` 是 min

说明：

- 当前 rank 模式范围语义与当前 `ZRANGE key start stop [REV]` 对齐
- 当前 `BYSCORE` 模式支持 `REV` 和 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前 `BYLEX` 模式支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`，支持 `REV` 和 `LIMIT offset count`
- `source` 缺失或结果为空时删除 `destination` 并返回 `0`
- 当前项目内 ZSet score 使用整数语义

### `ZREMRANGEBYLEX`

格式：

```text
ZREMRANGEBYLEX key min max
```

返回：

- 返回被删除的成员数量
- key 不存在时返回 `0`

说明：

- 当前支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`
- 当前按项目内 ZSet 的 `(score, member)` 排序视图扫描并按 member 边界删除；与 Redis 一样，lex 范围命令的有效业务语义应使用同分 sorted set
- 删除最后一个成员后会删除整个 key
- 非法边界返回 `ERR min or max not valid string range item`

### `ZREVRANGE`

格式：

```text
ZREVRANGE key start stop [WITHSCORES]
```

返回：

- 返回按 score 降序排列后的索引区间成员
- 带 `WITHSCORES` 时返回 member / score 交错数组

说明：

- 当前支持正负索引、闭区间 `[start, stop]` 和 `WITHSCORES`
- 当前不支持通过 `ZREVRANGE ... BYSCORE/BYLEX/LIMIT` 复用新版 `ZRANGE` 扩展语法；score 范围请使用 `ZREVRANGEBYSCORE`
- 当前项目内 ZSet score 使用整数语义

### `ZREVRANGEBYLEX`

格式：

```text
ZREVRANGEBYLEX key max min [LIMIT offset count]
```

返回：

- 返回 member 字典序落在 `[min, max]` 内的成员数组，结果按字典序反向返回
- key 不存在时返回空数组

说明：

- 当前支持 Redis lex 边界 token：`-`、`+`、`[value`、`(value`
- 当前支持 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前按项目内 ZSet 的 `(score, member)` 排序视图扫描并按 member 边界返回；与 Redis 一样，lex 范围命令的有效业务语义应使用同分 sorted set
- 参数顺序遵循 Redis 历史命令：先传 `max`，再传 `min`

### `ZRANGEBYSCORE`

格式：

```text
ZRANGEBYSCORE key min max [WITHSCORES] [LIMIT offset count]
```

返回：

- 返回 score 落在闭区间 `[min, max]` 内的成员，按 score 升序
- 带 `WITHSCORES` 时返回 member / score 交错数组
- 当前支持 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前项目内 ZSet score 使用整数语义

### `ZREVRANGEBYSCORE`

格式：

```text
ZREVRANGEBYSCORE key max min [WITHSCORES] [LIMIT offset count]
```

返回：

- 返回 score 落在闭区间 `[min, max]` 内的成员，按 score 降序
- 带 `WITHSCORES` 时返回 member / score 交错数组
- 当前支持 `LIMIT offset count`；`offset` 必须非负，`count < 0` 表示不限制数量
- 当前项目内 ZSet score 使用整数语义

### `ZRANDMEMBER`

格式：

```text
ZRANDMEMBER key [count [WITHSCORES]]
```

返回：

- 未提供 `count` 时返回一个 Bulk String；key 缺失或为空时返回 Null Bulk
- 提供 `count` 时返回成员数组；key 缺失或为空时返回空数组
- `WITHSCORES` 返回 `member, score` 交错数组

说明：

- 当前实现为 deterministic partial：按项目内 `(score, member)` 排序视图取值，不提供 Redis 原生随机分布
- 正数 `count` 去重并按集合大小封顶；负数 `count` 允许按排序视图循环重复
- 当前项目内 ZSet score 使用整数语义

### `ZDIFF`

格式：

```text
ZDIFF numkeys key [key ...] [WITHSCORES]
```

返回：

- 返回存在于第一个 zset 且不存在于后续 zset 的成员
- `WITHSCORES` 返回 `member, score` 交错数组，score 来自第一个 zset

说明：

- 当前实现为 read-only partial，按第一个 zset 的 `(score, member)` 排序视图输出
- 第一个 key 缺失时返回空数组；后续 key 缺失时按空 zset 处理
- 当前项目内 ZSet score 使用整数语义

### `ZDIFFSTORE`

格式：

```text
ZDIFFSTORE destination numkeys key [key ...]
```

返回：

- 返回写入 `destination` 的成员数量
- 写入存在于第一个 zset 且不存在于后续 zset 的成员，score 来自第一个 zset

说明：

- 当前实现为 write partial，按第一个 zset 的 `(score, member)` 排序视图生成结果
- 第一个源 key 缺失或结果为空时删除 `destination` 并返回 `0`
- 后续源 key 缺失时按空 zset 处理
- 当前项目内 ZSet score 使用整数语义

### `ZINTER`

格式：

```text
ZINTER numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX] [WITHSCORES]
```

返回：

- 返回多个 zset 的交集成员
- 交集成员 score 默认按 SUM 聚合
- `WEIGHTS` 支持每个 key 一个整数权重；`AGGREGATE` 支持 `SUM`、`MIN`、`MAX`
- `WITHSCORES` 返回 `member, score` 交错数组

说明：

- 当前实现为 read-only partial，按聚合结果的 `(score, member)` 排序视图输出
- 任一源 key 缺失时返回空数组
- 当前 `WEIGHTS` 仅支持整数权重，不支持 Redis 原生浮点权重
- 当前项目内 ZSet score 使用整数语义

### `ZINTERCARD`

格式：

```text
ZINTERCARD numkeys key [key ...] [LIMIT limit]
```

返回：

- 返回多个 zset 的交集成员数量
- `LIMIT` 大于 0 时达到限制后提前返回该限制值

说明：

- 当前实现为 read-only partial，只计算成员交集基数，不包含 `ZINTERSTORE` 的写回语义
- 任一源 key 缺失时返回 `0`
- `LIMIT` 不能为负数
- 当前项目内 ZSet score 使用整数语义

### `ZINTERSTORE`

格式：

```text
ZINTERSTORE destination numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX]
```

返回：

- 返回写入 `destination` 的成员数量
- 写入多个 zset 的交集成员
- 交集成员 score 默认按 SUM 聚合
- `WEIGHTS` 支持每个 key 一个整数权重；`AGGREGATE` 支持 `SUM`、`MIN`、`MAX`

说明：

- 当前实现为 write partial，按聚合结果写回项目内 zset
- 任一源 key 缺失或结果为空时删除 `destination` 并返回 `0`
- 当前 `WEIGHTS` 仅支持整数权重，不支持 Redis 原生浮点权重
- 当前项目内 ZSet score 使用整数语义

### `ZUNION`

格式：

```text
ZUNION numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX] [WITHSCORES]
```

返回：

- 返回多个 zset 的并集成员
- 重复成员 score 默认按 SUM 聚合
- `WEIGHTS` 支持每个 key 一个整数权重；`AGGREGATE` 支持 `SUM`、`MIN`、`MAX`
- `WITHSCORES` 返回 `member, score` 交错数组

说明：

- 当前实现为 read-only partial，按聚合结果的 `(score, member)` 排序视图输出
- 源 key 缺失时按空 zset 处理；所有源 key 缺失时返回空数组
- 当前 `WEIGHTS` 仅支持整数权重，不支持 Redis 原生浮点权重
- 当前项目内 ZSet score 使用整数语义

### `ZUNIONSTORE`

格式：

```text
ZUNIONSTORE destination numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX]
```

返回：

- 返回写入 `destination` 的成员数量
- 写入多个 zset 的并集成员
- 重复成员 score 默认按 SUM 聚合
- `WEIGHTS` 支持每个 key 一个整数权重；`AGGREGATE` 支持 `SUM`、`MIN`、`MAX`

说明：

- 当前实现为 write partial，按聚合结果写回项目内 zset
- 源 key 缺失时按空 zset 处理；结果为空时删除 `destination` 并返回 `0`
- 当前 `WEIGHTS` 仅支持整数权重，不支持 Redis 原生浮点权重
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

### `BZPOPMIN`

格式：

```text
BZPOPMIN key [key ...] timeout
```

返回：

- 命中时返回三段 RESP Array：`[key, member, score]`
- 超时返回 Null Array

说明：

- 当前支持多 key 顺序探测、秒级整数或浮点 timeout、server-side block/unblock
- 当前项目内 ZSet score 使用整数语义

### `BZPOPMAX`

格式：

```text
BZPOPMAX key [key ...] timeout
```

返回：

- 命中时返回三段 RESP Array：`[key, member, score]`
- 超时返回 Null Array

说明：

- 当前支持多 key 顺序探测、秒级整数或浮点 timeout、server-side block/unblock
- 当前项目内 ZSet score 使用整数语义

### `ZMPOP`

格式：

```text
ZMPOP numkeys key [key ...] MIN|MAX [COUNT count]
```

返回：

- 命中时返回两段 RESP Array：`[key, [[member1, score1], [member2, score2] ...]]`
- 所有 key 缺失或为空时返回 Null Array

说明：

- 当前支持多 key 顺序探测、`MIN` / `MAX` 方向选择和可选 `COUNT`
- 命中后删除已弹出的 member；key 被清空时会一并删除
- 当前 `COMMAND GETKEYS` / `COMMAND GETKEYSANDFLAGS` 已暴露 `ZMPOP` 的 movablekeys 提取结果
- 当前项目内 ZSet score 使用整数语义

### `BZMPOP`

格式：

```text
BZMPOP timeout numkeys key [key ...] MIN|MAX [COUNT count]
```

返回：

- 命中时返回两段 RESP Array：`[key, [[member1, score1], [member2, score2] ...]]`
- 超时返回 Null Array

说明：

- 当前支持多 key 顺序探测、`MIN` / `MAX` 方向选择、可选 `COUNT` 和秒级整数或浮点 timeout
- 当前支持 server-side block/unblock，并在命中后删除已弹出的 member；key 被清空时会一并删除
- 当前 `COMMAND GETKEYS` / `COMMAND GETKEYSANDFLAGS` 已暴露 `BZMPOP` 的 movablekeys 提取结果
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

### `COPY`

格式：

```text
COPY source destination [DB destination-db] [REPLACE]
```

返回：

- source 存在且复制成功：`1`
- source 不存在：`0`
- target 已存在且未指定 `REPLACE`：`0`
- source 和 destination 相同：错误

说明：

- 当前实现为单 DB partial；`DB 0` 作为当前唯一数据库兼容参数接受，非 `0` DB 返回 `ERR DB index is out of range`
- 复制会深拷贝当前对象并保留 source 的 TTL；source 没有 TTL 时会清理 destination 的旧 TTL
- 当前覆盖 String/Hash/List/Set/ZSet/Stream 等项目内对象类型的复制，`COMMAND GETKEYS*` 将 source 标记为 `RO/access`、destination 标记为 `OW/update`

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

### `RESTORE-ASKING`

格式：

```text
RESTORE-ASKING key ttl serialized-value
```

返回：

- 成功：`+OK`
- target 已存在：`-BUSYKEY ...`
- payload 非法：错误

说明：

- 当前实现为迁移兼容 partial，复用 `RESTORE` 的单 DB RDB payload 写入路径
- 当前不支持集群 ASKING 状态校验，也不支持 `REPLACE` / `ABSTTL` / `IDLETIME` / `FREQ`

### `MIGRATE`

格式：

```text
MIGRATE host port key destination-db timeout [COPY] [REPLACE] [AUTH password] [AUTH2 username password] [KEYS key [key ...]]
```

返回：

- 当前统一返回：`-ERR MIGRATE command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 单机安全 profile 不主动连接远端 Redis、不执行跨实例 `DUMP/RESTORE` 迁移
- `MIGRATE` 不写入 AOF 或复制 backlog，也不会改变本地 keyspace

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

### `SWAPDB`

格式：

```text
SWAPDB index1 index2
```

返回：

- 当前单机实现中：`index1 = 0` 且 `index2 = 0` 返回 `+OK`
- 非整数 DB 参数：`-ERR value is not an integer or out of range`
- 任一参数非 `0`：`-ERR DB index is out of range`

说明：

- 当前运行时只暴露唯一数据库，因此 `SWAPDB 0 0` 是 no-op partial，不存在真实多 DB 数据交换路径

### `LOLWUT`

格式：

```text
LOLWUT [VERSION version]
```

返回：

- 成功：Bulk String，包含 redis-uya 固定兼容文本和当前版本
- `VERSION` 参数值非整数：`-ERR value is not an integer or out of range`

说明：

- 当前实现是固定文本 partial，不生成 Redis 原版动态图形
- 未识别首参数按 Redis 7.0 兼容面退回默认输出

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

### `WAITAOF`

格式：

```text
WAITAOF numlocal numreplicas timeout
```

返回：

- 成功：返回 `[local, replicas]` 两元素 Array
- `numlocal` / `numreplicas` / `timeout` 非整数：`-ERR value is not an integer or out of range`
- `timeout < 0`：`-ERR timeout is negative`

说明：

- 当前 partial 不执行真实阻塞等待，也不等待副本 AOF ACK
- `numlocal > 0` 时返回本地确认 `1`，`numlocal <= 0` 时返回 `0`
- 副本确认当前固定返回 `0`

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

### `MSETEX`

格式：

```text
MSETEX numkeys key value [key value ...] [NX|XX] [EX seconds|PX milliseconds|EXAT unix-time-seconds|PXAT unix-time-milliseconds|KEEPTTL]
```

返回：

- 条件满足并完成写入：`1`
- `NX` 模式下任一 key 已存在，或 `XX` 模式下任一 key 不存在：`0`

说明：

- `numkeys` 必须为正整数，后续必须提供对应数量的 key/value 对
- `NX` 与 `XX` 互斥；`EX/PX/EXAT/PXAT/KEEPTTL` 互斥
- `EX/PX/EXAT/PXAT` 参数必须为正整数，成功写入时对所有 key 使用同一个过期时间
- `KEEPTTL` 成功写入时保留每个已存在 key 的原 TTL；新 key 不设置 TTL
- 条件失败时不写入，不进入 AOF/replication backlog
- 当前实现为 partial：支持 Redis 兼容面中的批量字符串写入、条件与 TTL 选项，暂不提供失败中途回滚保证

### `LCS`

格式：

```text
LCS key1 key2
LCS key1 key2 LEN
```

返回：

- 未带选项：返回两个字符串值的最长公共子序列，Bulk String
- `LEN`：返回最长公共子序列长度，Integer

说明：

- 缺失 key 按空字符串处理
- 任一 key 存在且不是 String：`WRONGTYPE`
- 当前实现为 partial：只支持基础结果和 `LEN`，`IDX` / `MINMATCHLEN` / `WITHMATCHLEN` 返回 partial 限制错误
- 为避免当前 DP 实现对大字符串造成不可控内存放大，任一输入长度超过 4096 字节时返回 partial 限制错误

### `GETRANGE`

格式：

```text
GETRANGE key start end
SUBSTR key start end
```

返回：

- 返回闭区间 `[start, end]` 的子串，支持负索引
- key 不存在或范围为空时返回空 Bulk String

说明：

- `SUBSTR` 是 `GETRANGE` 的兼容 alias，执行语义、返回和 key 提取标记一致

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

### `GETBIT`

格式：

```text
GETBIT key offset
```

返回：

- 返回指定 bit 位上的 `0` 或 `1`
- key 不存在时返回 `0`

说明：

- `offset` 必须为非负整数
- bit 编号按 Redis bitmap 约定，从首字节最高位开始计数

### `SETBIT`

格式：

```text
SETBIT key offset value
```

返回：

- 返回写入前该 bit 位上的 `0` 或 `1`

说明：

- `offset` 必须为非负整数
- `value` 当前只接受 `0` 或 `1`
- 超出当前字符串长度时，中间空洞会用 `\\0` 填充
- 写入后会保留原 key 的 TTL

### `BITCOUNT`

格式：

```text
BITCOUNT key
BITCOUNT key start end
BITCOUNT key start end BYTE
BITCOUNT key start end BIT
```

返回：

- 返回指定范围内置位 bit 的数量，Integer
- key 不存在时返回 `0`

说明：

- 默认按字节范围解释 `start/end`
- `BIT` 模式下按 bit 范围解释 `start/end`
- 范围支持负索引；空范围返回 `0`

### `BITPOS`

格式：

```text
BITPOS key bit
BITPOS key bit start
BITPOS key bit start end
BITPOS key bit start end BYTE
BITPOS key bit start end BIT
```

返回：

- 返回首个匹配 bit 的绝对位置，Integer
- key 不存在时：查找 `0` 返回 `0`，查找 `1` 返回 `-1`
- 已显式给出 `end` 且范围内未命中时返回 `-1`

说明：

- `bit` 当前只接受 `0` 或 `1`
- 默认按字节范围解释 `start/end`；`BIT` 模式下按 bit 范围解释
- 当查找 `0` 且未显式给出 `end` 时，如果从有效 `start` 到字符串结尾都没有 `0`，返回 `len * 8`
- 范围支持负索引；start-only 场景会从起始位置扫描到字符串末尾

### `BITOP`

格式：

```text
BITOP AND destkey key [key ...]
BITOP OR destkey key [key ...]
BITOP XOR destkey key [key ...]
BITOP NOT destkey key
```

返回：

- 返回结果字符串的字节长度，Integer
- 所有 source key 都为空时返回 `0`，并删除目标 key

说明：

- `AND` / `OR` / `XOR` 会把较短 source 按 `\\0` 右侧补齐到最长 source 长度
- `NOT` 当前只接受单个 source key；多 source 时返回兼容错误
- 目标 key 总是按普通字符串重写，原 TTL 会被清除
- 当前已覆盖 AOF replay、`COMMAND GETKEYS` / `GETKEYSANDFLAGS` 与客户端 smoke

### `BITFIELD`

格式：

```text
BITFIELD key [GET encoding offset] [OVERFLOW WRAP|SAT|FAIL] [SET encoding offset value] [INCRBY encoding offset increment] ...
```

返回：

- 返回一个 RESP Array；每个 `GET` / `SET` / `INCRBY` 子操作各占一个返回槽位
- `OVERFLOW` 只修改后续写子操作的溢出模式，不单独产生返回项
- `OVERFLOW FAIL` 触发时，对应写子操作返回 Null Bulk，并保持原值不变

说明：

- 当前支持 `iN` / `uN` 编码：`i1..i64`、`u1..u63`
- 当前支持绝对 bit 偏移和 `#offset` 形式的按字段宽度步进偏移
- `SET` / `INCRBY` 默认使用 `WRAP`；也支持 `SAT` / `FAIL`
- 写子操作会保留原 key 的 TTL
- key 不存在时按全 `0` 位图读取；写入时按需扩展并用 `\\0` 填充空洞

### `BITFIELD_RO`

格式：

```text
BITFIELD_RO key [GET encoding offset] ...
```

返回：

- 返回一个 RESP Array；每个 `GET` 子操作返回对应整数值

说明：

- 当前只允许 `GET` 子操作；写子操作会返回 `ERR BITFIELD_RO only supports the GET subcommand`
- 当前接受 `OVERFLOW` 语法占位，但它对只读 `GET` 没有实际效果

### `PFADD`

格式：

```text
PFADD key [element ...]
```

返回：

- 返回 `1` 表示当前 key 的近似基数被本次调用改变
- 返回 `0` 表示当前 key 的近似基数未变化

说明：

- 当前实现为 partial：内部暂用 exact set-backed cardinality 逼近 Redis 语义，不是 Redis 原生 dense/sparse HLL 字符串编码
- `PFADD key` 无元素时，若 key 不存在会创建一个空的 partial-HLL 并返回 `1`；再次调用返回 `0`

### `PFCOUNT`

格式：

```text
PFCOUNT key [key ...]
```

返回：

- 单 key：返回当前近似基数
- 多 key：返回所有输入 key 合并后的近似基数

说明：

- 当前实现为 partial，基于 exact set-backed union/count 返回精确去重计数
- key 不存在时按空 HLL 处理

### `PFMERGE`

格式：

```text
PFMERGE destkey [sourcekey ...]
```

返回：

- 成功：`+OK`

说明：

- 当前实现为 partial，内部用 exact set-backed union 结果重写目标 key
- `PFMERGE destkey` 无 source 时会把目标写成空的 partial-HLL
- 目标 key 会被重写，因此原 TTL 会被清除

### `PFSELFTEST`

格式：

```text
PFSELFTEST
```

返回：

- 成功：`+OK`

说明：

- 当前实现为 partial：在 redis-uya 的 exact set-backed HLL profile 下作为安全自检兼容面返回 `OK`
- 不读取或修改 key，不执行 Redis 原生 dense/sparse HLL 编码压力测试
- 不进入 AOF、复制 backlog 或脚本执行路径

### `PFDEBUG`

格式：

```text
PFDEBUG subcommand key
```

返回：

- 当前统一返回：`-ERR PFDEBUG command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入路由、运行时执行链和 `COMMAND*` 可见面，但不开放 Redis 内部 HyperLogLog 调试/破坏性子命令
- 不读取或修改 key，不进入 AOF、复制 backlog 或脚本执行路径

### `EVAL`

格式：

```text
EVAL script numkeys [key ...] [arg ...]
```

返回：

- 返回当前脚本内部那条 `redis.call(...)` 的原始 Redis 回复

说明：

- 当前实现为 partial：只支持单条 `return redis.call(...)` 脚本子集
- 当前支持 `KEYS[n]` / `ARGV[n]` 参数替换，脚本会自动写入脚本缓存
- AOF / 复制传播的是脚本内部实际执行的命令效果，不是原始 `EVAL`
- 当前不支持多语句 Lua、`redis.pcall` 或任意 Lua 值返回

### `EVAL_RO`

格式：

```text
EVAL_RO script numkeys [key ...] [arg ...]
```

返回：

- 返回当前脚本内部那条只读 `redis.call(...)` 的原始 Redis 回复

说明：

- 当前实现为 partial，脚本子集、脚本缓存和参数替换语义与 `EVAL` 相同
- 如果脚本内部命令带写标记，返回 `ERR Write commands are not allowed from read-only scripts`
- AOF / 复制只传播脚本内部成功执行的实际命令效果；被拒绝的写脚本不产生传播副作用

### `EVALSHA`

格式：

```text
EVALSHA sha1 numkeys [key ...] [arg ...]
```

返回：

- 返回命中脚本内部那条 `redis.call(...)` 的原始 Redis 回复
- 未命中脚本缓存时返回 `NOSCRIPT No matching script. Please use EVAL.`

说明：

- 当前实现为 partial，语义边界与 `EVAL` 相同
- `sha1` 查找大小写不敏感

### `EVALSHA_RO`

格式：

```text
EVALSHA_RO sha1 numkeys [key ...] [arg ...]
```

返回：

- 返回命中脚本内部那条只读 `redis.call(...)` 的原始 Redis 回复
- 未命中脚本缓存时返回 `NOSCRIPT No matching script. Please use EVAL.`

说明：

- 当前实现为 partial，语义边界与 `EVAL_RO` 相同
- `sha1` 查找大小写不敏感

### `FCALL` / `FCALL_RO`

格式：

```text
FCALL function numkeys [key ...] [arg ...]
FCALL_RO function numkeys [key ...] [arg ...]
```

返回：

- 当前返回 `ERR Function not found`，表示尚无已加载 function library

说明：

- 当前实现为 partial，仅提供空 function 库下的错误兼容面和 `COMMAND GETKEYS/GETKEYSANDFLAGS` 动态 key 解析
- `FCALL_RO` 的 `COMMAND GETKEYSANDFLAGS` key 标记为只读访问；`FCALL` 标记为读写访问/更新
- 当前不执行 Redis Functions，不支持 function library 存储或 Lua engine 调用

### `SCRIPT`

格式：

```text
SCRIPT HELP
SCRIPT DEBUG YES|SYNC|NO
SCRIPT LOAD script
SCRIPT EXISTS sha1 [sha1 ...]
SCRIPT FLUSH [ASYNC|SYNC]
SCRIPT KILL
```

返回：

- `HELP`：返回当前支持的子命令说明
- `DEBUG`：接受 `YES` / `SYNC` / `NO` 并返回 `+OK`
- `LOAD`：返回脚本 SHA1
- `EXISTS`：按输入顺序返回 `0/1`
- `FLUSH`：成功返回 `+OK`
- `KILL`：当前无长时间运行脚本，返回 `NOTBUSY No scripts in execution right now.`

说明：

- 当前实现为 partial：`LOAD` 只接受可由当前 `EVAL/EVALSHA` 执行的单条 `return redis.call(...)` 子集
- `FLUSH ASYNC|SYNC` 当前都走同步清空路径，只保留参数兼容
- `SCRIPT DEBUG` 当前是 no-op 兼容面，不提供 Redis Lua debugger
- `SCRIPT KILL` 当前只覆盖无运行脚本错误面

### `FUNCTION`

格式：

```text
FUNCTION HELP
FUNCTION LIST [LIBRARYNAME <pattern>] [WITHCODE]
FUNCTION STATS
FUNCTION FLUSH [ASYNC|SYNC]
FUNCTION DELETE <library-name>
FUNCTION LOAD [REPLACE] <function-code>
FUNCTION DUMP
FUNCTION RESTORE serialized-value [FLUSH|APPEND|REPLACE]
FUNCTION KILL
```

返回：

- 返回当前 `FUNCTION` 命令帮助数组
- `FUNCTION LIST` 当前返回空数组，表示尚无已加载 function library
- `FUNCTION STATS` 当前返回空库统计：`running_script = nil`、`LUA` 引擎 `libraries_count = 0`、`functions_count = 0`
- `FUNCTION FLUSH` 当前返回 `OK`，空库状态下为 no-op
- `FUNCTION DELETE` 当前返回 `ERR Library not found`，表示尚无可删除的 function library
- `FUNCTION LOAD` 当前做参数形状校验；合法的 `LOAD code` 或 `LOAD REPLACE code` 返回 `ERR FUNCTION LOAD is not supported by redis-uya partial`
- `FUNCTION DUMP` 当前返回 Redis 兼容的空库序列化 payload
- `FUNCTION RESTORE` 当前只接受 Redis 兼容空库序列化 payload，成功返回 `+OK`
- `FUNCTION KILL` 当前返回 `NOTBUSY No scripts in execution right now.`，表示没有正在运行的 function/script

说明：

- 当前实现为 partial，仅执行 `FUNCTION HELP`、空库状态的 `FUNCTION LIST`、空库统计的 `FUNCTION STATS`、no-op `FUNCTION FLUSH`、空库错误面的 `FUNCTION DELETE`、函数加载未支持错误面的 `FUNCTION LOAD`、空库序列化的 `FUNCTION DUMP`、空库 payload 的 `FUNCTION RESTORE` 和无运行脚本状态的 `FUNCTION KILL`
- `FUNCTION LIST` 支持 `LIBRARYNAME <pattern>` 与 `WITHCODE` 参数校验，但 function library 存储尚未实现，因此始终返回空数组
- `FUNCTION FLUSH` 支持 `ASYNC|SYNC` 参数校验，但 function library 存储尚未实现，因此不会清理任何真实库状态
- `FUNCTION RESTORE` 支持 `FLUSH|APPEND|REPLACE` 参数校验，但当前只接受空库 dump；非空或非法 payload 返回 `ERR DUMP payload version or checksum are wrong`
- `COMMAND INFO/LIST/DOCS` 会暴露 `FUNCTION`、`FUNCTION|HELP`、`FUNCTION|LIST`、`FUNCTION|STATS`、`FUNCTION|FLUSH`、`FUNCTION|DELETE`、`FUNCTION|LOAD`、`FUNCTION|DUMP`、`FUNCTION|RESTORE` 和 `FUNCTION|KILL`
- 当前不支持 function library 存储、非空 `FUNCTION RESTORE` 或真实 `FCALL/FCALL_RO` 执行

### `GEOADD`

格式：

```text
GEOADD key [NX|XX] [CH] longitude latitude member [longitude latitude member ...]
```

返回：

- 默认返回新插入的 member 数量
- 带 `CH` 时，返回插入或坐标实际变化的 member 数量

说明：

- 当前实现为 partial：内部暂用 exact zset-backed packed coordinate score，而不是 Redis 原生 geohash score
- 当前支持 `NX`、`XX`、`CH`
- longitude / latitude 仍按 Redis 边界校验；越界会返回 `ERR invalid longitude,latitude pair ...`

### `GEODIST`

格式：

```text
GEODIST key member1 member2 [M|KM|FT|MI]
```

返回：

- 命中时返回距离字符串，默认单位为米
- 任一 member 不存在时返回 Null Bulk

说明：

- 当前实现为 partial，但距离计算走 exact great-circle path
- 当前支持 `M`、`KM`、`FT`、`MI`

### `GEOPOS`

格式：

```text
GEOPOS key member [member ...]
```

返回：

- 按请求顺序返回每个 member 的坐标数组
- member 不存在或 key 不存在时，对应位置返回 Null Bulk

说明：

- 当前实现为 partial，坐标来自 exact zset-backed packed coordinate score
- 返回坐标会按当前 packed score 解码并量化到 `1e-6` 的经纬度字符串
- key 存在但不是 Geo/ZSet 类型时返回 `WRONGTYPE`

### `GEOHASH`

格式：

```text
GEOHASH key member [member ...]
```

返回：

- 按请求顺序返回每个 member 的 11 字节 geohash 字符串
- member 不存在或 key 不存在时，对应位置返回 Null Bulk

说明：

- 当前实现为 partial，坐标来自 exact zset-backed packed coordinate score
- geohash 字符串基于当前解码坐标生成，前 10 字符按标准 base32 geohash 网格编码，最后 1 字符按 Redis 兼容面固定补 `0`
- 因当前内部不是 Redis 原生 geohash score，极靠近 geohash cell 边界的结果可能与 Redis 原生编码有细微差异
- key 存在但不是 Geo/ZSet 类型时返回 `WRONGTYPE`

### `GEOSEARCH`

格式：

```text
GEOSEARCH key FROMMEMBER member BYRADIUS radius unit [ASC|DESC] [COUNT count [ANY]] [WITHDIST] [WITHCOORD] [WITHHASH]
GEOSEARCH key FROMLONLAT longitude latitude BYRADIUS radius unit [ASC|DESC] [COUNT count [ANY]] [WITHDIST] [WITHCOORD] [WITHHASH]
GEOSEARCH key FROMMEMBER member BYBOX width height unit [ASC|DESC] [COUNT count [ANY]] [WITHDIST] [WITHCOORD] [WITHHASH]
GEOSEARCH key FROMLONLAT longitude latitude BYBOX width height unit [ASC|DESC] [COUNT count [ANY]] [WITHDIST] [WITHCOORD] [WITHHASH]
```

返回：

- 默认返回 member 数组
- 带附加选项时返回嵌套数组，顺序为 `member`, `dist`, `hash`, `coord`

说明：

- 当前实现为 partial，内部使用 exact zset-backed packed coordinate score
- 当前 `WITHHASH` 返回当前 packed score 整数，不是 Redis 原生 geohash 整数
- 当前 `WITHCOORD` 返回量化到 `1e-6` 的经纬度字符串
- 当前接受 `COUNT ... ANY` 语法，但不会像 Redis 原生实现那样做提早截断优化

### `GEOSEARCHSTORE`

格式：

```text
GEOSEARCHSTORE destination source FROMMEMBER member BYRADIUS radius unit [ASC|DESC] [COUNT count [ANY]] [STOREDIST]
GEOSEARCHSTORE destination source FROMLONLAT longitude latitude BYRADIUS radius unit [ASC|DESC] [COUNT count [ANY]] [STOREDIST]
GEOSEARCHSTORE destination source FROMMEMBER member BYBOX width height unit [ASC|DESC] [COUNT count [ANY]] [STOREDIST]
GEOSEARCHSTORE destination source FROMLONLAT longitude latitude BYBOX width height unit [ASC|DESC] [COUNT count [ANY]] [STOREDIST]
```

返回：

- 返回写入 `destination` 的 member 数量，Integer
- 没有匹配结果时删除 `destination` 并返回 `0`

说明：

- 当前实现为 partial，复用 `GEOSEARCH` 的 `FROMMEMBER/FROMLONLAT`、`BYRADIUS/BYBOX`、`ASC/DESC`、`COUNT` 查询语义
- 默认写入的 zset score 为当前 packed coordinate score，不是 Redis 原生 geohash score
- `STOREDIST` 会按请求单位写入截断后的整数距离 score；由于 redis-uya 当前 zset score 是 `i64`，暂不保存 Redis 原生浮点距离
- 当前接受 `COUNT ... ANY` 语法，但不会像 Redis 原生实现那样做提早截断优化
- 当前不支持 `WITHDIST`、`WITHCOORD` 或 `WITHHASH`，这些只读返回修饰符会返回语法错误
- source key 不存在且使用 `FROMLONLAT` 时删除 `destination` 并返回 `0`；使用 `FROMMEMBER` 且 source/member 不存在时返回 `ERR could not decode requested zset member`

### `GEORADIUS`

格式：

```text
GEORADIUS key longitude latitude radius M|KM|FT|MI [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count [ANY]] [ASC|DESC]
```

返回：

- 默认返回 member 数组
- 带附加选项时返回嵌套数组，顺序为 `member`, `dist`, `hash`, `coord`

说明：

- 当前实现为 partial，复用 `GEOSEARCH key FROMLONLAT longitude latitude BYRADIUS radius unit ...` 的执行路径
- 当前只覆盖未带 `STORE` / `STOREDIST` 的 legacy 查询兼容面；`STORE` 或 `STOREDIST` 会返回语法错误，暂不写入目标 key
- 当前 `WITHHASH` 返回当前 packed score 整数，不是 Redis 原生 geohash 整数
- 当前 `WITHCOORD` 返回量化到 `1e-6` 的经纬度字符串

### `GEORADIUS_RO`

格式：

```text
GEORADIUS_RO key longitude latitude radius M|KM|FT|MI [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count [ANY]] [ASC|DESC]
```

返回：

- 默认返回 member 数组
- 带附加选项时返回嵌套数组，顺序为 `member`, `dist`, `hash`, `coord`

说明：

- 当前实现为 partial，复用 `GEOSEARCH key FROMLONLAT longitude latitude BYRADIUS radius unit ...` 的执行路径
- 当前为只读兼容面，不支持 `STORE` 或 `STOREDIST`
- 当前 `WITHHASH` 返回当前 packed score 整数，不是 Redis 原生 geohash 整数
- 当前 `WITHCOORD` 返回量化到 `1e-6` 的经纬度字符串

### `GEORADIUSBYMEMBER`

格式：

```text
GEORADIUSBYMEMBER key member radius M|KM|FT|MI [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count [ANY]] [ASC|DESC]
```

返回：

- 默认返回 member 数组
- 带附加选项时返回嵌套数组，顺序为 `member`, `dist`, `hash`, `coord`

说明：

- 当前实现为 partial，复用 `GEOSEARCH key FROMMEMBER member BYRADIUS radius unit ...` 的执行路径
- 当前只覆盖未带 `STORE` / `STOREDIST` 的 legacy 查询兼容面；`STORE` 或 `STOREDIST` 会返回语法错误，暂不写入目标 key
- center member 不存在时返回 `ERR could not decode requested zset member`
- 当前 `WITHHASH` 返回当前 packed score 整数，不是 Redis 原生 geohash 整数
- 当前 `WITHCOORD` 返回量化到 `1e-6` 的经纬度字符串

### `GEORADIUSBYMEMBER_RO`

格式：

```text
GEORADIUSBYMEMBER_RO key member radius M|KM|FT|MI [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count [ANY]] [ASC|DESC]
```

返回：

- 默认返回 member 数组
- 带附加选项时返回嵌套数组，顺序为 `member`, `dist`, `hash`, `coord`

说明：

- 当前实现为 partial，复用 `GEOSEARCH key FROMMEMBER member BYRADIUS radius unit ...` 的执行路径
- 当前为只读兼容面，不支持 `STORE` 或 `STOREDIST`
- center member 不存在时返回 `ERR could not decode requested zset member`
- 当前 `WITHHASH` 返回当前 packed score 整数，不是 Redis 原生 geohash 整数
- 当前 `WITHCOORD` 返回量化到 `1e-6` 的经纬度字符串

### Streams 第一批

格式：

```text
XACK key group id [id ...]
XACKDEL key group [KEEPREF|DELREF|ACKED] IDS numids id [id ...]
XADD key id field value [field value ...]
XCFGSET key [IDMP-DURATION seconds] [IDMP-MAXSIZE size]
XAUTOCLAIM key group consumer min-idle-time start [COUNT count] [JUSTID]
XCLAIM key group consumer min-idle-time id [id ...] [IDLE ms] [TIME ms-unix-time] [RETRYCOUNT count] [FORCE] [JUSTID]
XDEL key id [id ...]
XDELEX key [KEEPREF|DELREF|ACKED] IDS numids id [id ...]
XGROUP CREATE key groupname id-or-$ [MKSTREAM]
XGROUP CREATECONSUMER key groupname consumer
XGROUP DELCONSUMER key groupname consumer
XGROUP DESTROY key groupname
XGROUP HELP
XGROUP SETID key groupname id-or-$ [ENTRIESREAD entries-read]
XIDMPRECORD key pid iid stream-id
XINFO HELP
XINFO CONSUMERS key groupname
XINFO GROUPS key
XINFO STREAM key [FULL [COUNT count]]
XLEN key
XNACK key group SILENT|FAIL|FATAL IDS numids id [id ...] [RETRYCOUNT count] [FORCE]
XPENDING key group [IDLE min-idle-time] start end count [consumer]
XRANGE key start end [COUNT count]
XREVRANGE key end start [COUNT count]
XREAD [COUNT count] STREAMS key [key ...] id [id ...]
XREADGROUP GROUP group consumer [COUNT count] [NOACK] STREAMS key [key ...] id [id ...]
XSETID key last-id [ENTRIESADDED entries-added] [MAXDELETEDID max-deleted-id]
XTRIM key MAXLEN [=|~] count
```

返回：

- `XACK`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XACKDEL`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XADD`：成功时返回新增 entry id；`*` 会按当前毫秒时间和单毫秒递增序列生成 id
- `XCFGSET`：对现有 stream key 返回 `OK`；当前仅校验 `IDMP-DURATION` / `IDMP-MAXSIZE` 参数，不保存 IDMP 配置
- `XAUTOCLAIM`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XCLAIM`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XDEL`：返回被删除的 entry 数量；key 不存在返回 `0`
- `XDELEX`：返回每个 id 的删除状态数组；`KEEPREF` / `DELREF` 对现有 entry 返回 `1` 并删除、不存在返回 `-1`，`ACKED` 在无 consumer group 状态下返回 `2`
- `XGROUP CREATE`：当前没有 consumer group 模型，因此只校验参数、stream key 与类型；对现有 stream key 返回 `ERR XGROUP CREATE is not supported yet`
- `XGROUP CREATECONSUMER` / `XGROUP DELCONSUMER`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XGROUP DESTROY`：当前没有 consumer group 模型，因此对 stream key 或缺失 key 返回 `0`
- `XGROUP HELP`：返回当前 XGROUP 兼容面帮助数组
- `XGROUP SETID`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XIDMPRECORD`：对现有 stream entry 返回 `OK`；当前仅校验 `pid` / `iid` 非空、stream id 格式和 entry 存在，不保存 IDMP 记录
- `XINFO HELP`：返回当前 XINFO 兼容面帮助数组
- `XINFO CONSUMERS`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XINFO GROUPS`：当前没有 consumer group 模型，因此对 stream key 返回空数组；key 不存在返回 `ERR no such key`
- `XINFO STREAM`：返回基础 stream 元数据，包括 `length`、`last-generated-id`、`groups=0`、`first-entry` 与 `last-entry`；`FULL [COUNT count]` 返回基础元数据、entry 明细和空 `groups`；key 不存在返回 `ERR no such key`
- `XLEN`：返回 stream entry 数量；key 不存在返回 `0`
- `XNACK`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XPENDING`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XRANGE` / `XREVRANGE`：返回 `[id, [field, value, ...]]` 形式的嵌套数组，支持 `-` / `+` 边界和 `COUNT`
- `XREAD`：命中时返回 stream 名与 entry 数组；无新 entry 时返回 Null Array
- `XREADGROUP`：当前没有 consumer group 模型，因此对现有 stream key 返回 `NOGROUP No such consumer group`
- `XSETID`：当前只校验参数、stream key 与类型；对现有 stream key 返回 `ERR XSETID is not supported yet`
- `XTRIM`：返回被删除的 entry 数量；key 不存在返回 `0`

说明：

- 当前实现为 partial：stream 内部暂用项目内 list-backed entry 存储，不是 Redis 原生 radix-tree/listpack 编码
- `XADD` 当前只支持基础追加和显式完整 id / `*` 自动 id；不支持 `MAXLEN`、`MINID`、`LIMIT`、`NOMKSTREAM` 或 `field value` 之外的扩展选项
- `XCFGSET` 当前只提供 key/type 校验和 `IDMP-DURATION` / `IDMP-MAXSIZE` 范围校验；不维护或持久化 stream IDMP 配置
- `XREAD` 当前只支持非阻塞读取；`BLOCK` 会返回明确错误，consumer group 相关语义仍未实现
- `XREADGROUP` 当前只支持非阻塞语法校验和无 group 时的 `NOGROUP` 错误面；`BLOCK` 会返回明确错误，不维护 consumer group PEL
- `XSETID` 当前只提供 key/type 校验、`last-id` / `MAXDELETEDID` stream ID 校验和 `ENTRIESADDED` 整数校验，不修改 stream 元数据
- `XACK` 当前只提供无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL
- `XACKDEL` 当前只支持 `KEEPREF`、`DELREF`、`ACKED` 与 `IDS` 语法校验和无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL，也不会删除 entry
- `XNACK` 当前只支持 `SILENT` / `FAIL` / `FATAL`、`IDS`、`RETRYCOUNT`、`FORCE` 语法校验和无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL
- `XAUTOCLAIM` 当前只提供无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL
- `XCLAIM` 当前只提供无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL
- `XDEL` 当前只做精确 ID 删除，不维护 consumer group PEL
- `XDELEX` 当前支持 `KEEPREF`、`DELREF`、`ACKED` 与 `IDS` 语法校验；由于没有 consumer group / PEL，`KEEPREF` 与 `DELREF` 行为等同于精确 entry 删除，`ACKED` 只返回未删除状态 `2`
- `XPENDING` 当前只提供无 group 时的 `NOGROUP` 错误面，不维护 consumer group PEL
- `XGROUP CREATE` 当前只提供 key/type 校验和明确未支持错误，不创建 consumer group；`XGROUP CREATECONSUMER` / `XGROUP DELCONSUMER` / `XGROUP SETID` 当前只提供无 group 时的 `NOGROUP` 错误面；`XGROUP DESTROY` 当前只提供 empty-state 返回值，不维护 group；consumer 管理和 consumer group 状态仍未实现
- `XIDMPRECORD` 当前只提供 key/type、pid/iid 非空、stream ID 与 entry 存在性校验；不维护或持久化 stream IDMP 记录，当前 no-op 校验面不进入普通 AOF/复制传播
- `XINFO STREAM` 当前支持 key-only 基础元数据和 `FULL [COUNT count]` entry 明细，`XINFO GROUPS` 当前只支持 empty-state 空数组，`XINFO CONSUMERS` 当前只提供无 group 时的 `NOGROUP` 错误面；真实 consumer group 状态仍未实现；`radix-tree-*` 字段为 list-backed partial 占位
- `XTRIM` 当前只支持 `MAXLEN` 与可选 `=` / `~` 操作符；`~` 只是语法兼容占位，仍按精确头部裁剪执行；暂不支持 `MINID` 或 `LIMIT`
- 当前不支持真实 consumer group 状态命令
- 项目内 RDB 与 AOF rewrite 会保存显式 stream ID；普通 AOF append 仍记录原始请求，因此 `XADD *` 回放会重新生成 ID，只承诺恢复条目内容与顺序

### `TYPE`

格式：

```text
TYPE key
```

返回：

- 键不存在：`+none`
- 键存在：返回 `string/hash/list/set/zset/stream`

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

### `MEMORY`

格式：

```text
MEMORY HELP
MEMORY DOCTOR
MEMORY MALLOC-STATS
MEMORY PURGE
MEMORY STATS
MEMORY USAGE key [SAMPLES count]
```

返回：

- `HELP`：返回当前支持的 `MEMORY` 子命令说明
- `DOCTOR`：返回诊断文本 Bulk String
- `MALLOC-STATS`：返回 redis-uya allocator / object-pool 计数的 Bulk String 报告
- `PURGE`：返回 `OK`；当前作为 allocator purge 的 no-op 兼容面
- `STATS`：返回交替的 `field/value` RESP Array
- `USAGE`：命中返回近似字节数；key 不存在返回 Null Bulk

说明：

- 当前实现为 partial：仅支持 `HELP`、`DOCTOR`、`MALLOC-STATS`、`PURGE`、`STATS`、`USAGE`
- `COMMAND INFO/LIST/DOCS` 会暴露 `MEMORY`、`MEMORY|DOCTOR`、`MEMORY|HELP`、`MEMORY|MALLOC-STATS`、`MEMORY|PURGE`、`MEMORY|STATS` 与 `MEMORY|USAGE`
- `USAGE` 基于 redis-uya 当前对象布局、dict entry/bucket、list node 和 SDS 容量返回近似运行时占用，不是 Redis 原生 jemalloc 口径
- `USAGE ... SAMPLES count` 当前只做参数兼容校验，不影响近似值计算
- `MALLOC-STATS` 当前不是 Redis 原生 jemalloc 统计口径；`PURGE` 不会触发 Redis jemalloc purge 级别的 allocator 行为

### `MODULE`

格式：

```text
MODULE HELP
MODULE LIST
MODULE LOAD path [arg [arg ...]]
MODULE LOADEX path [CONFIG name value ...] [ARGS arg ...]
MODULE UNLOAD name
```

返回：

- `HELP`：返回当前支持的 `MODULE` 子命令说明
- `LIST`：返回已加载模块数组；当前固定为空数组
- `LOAD` / `LOADEX`：当前统一返回 `ERR MODULE LOAD/LOADEX command not allowed by redis-uya standalone profile`
- `UNLOAD`：当前统一返回 `ERR MODULE UNLOAD command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 partial / standalone-error 组合：`HELP`、`LIST` 为 partial；`LOAD`、`LOADEX` 与 `UNLOAD` 为单机安全 profile 下的 standalone-error
- `COMMAND INFO/LIST/DOCS` 会暴露 `MODULE`、`MODULE|HELP`、`MODULE|LIST`、`MODULE|LOAD`、`MODULE|LOADEX` 与 `MODULE|UNLOAD`
- 当前不支持 module 加载、卸载或模块 API；禁用子命令不加载动态库、不修改模块列表、不写 AOF 或复制 backlog

### RedisBloom `BF.*`

格式：

```text
BF.ADD key item
BF.CARD key
BF.EXISTS key item
BF.INFO key [option]
BF.INSERT key [CAPACITY capacity] [ERROR error] [EXPANSION expansion] [NOCREATE] ITEMS item [item ...]
BF.LOADCHUNK key iterator data
BF.MADD key item [item ...]
BF.MEXISTS key item [item ...]
BF.RESERVE key error_rate capacity [EXPANSION expansion] [NONSCALING]
BF.SCANDUMP key iterator
```

返回：

- 当前统一返回：`-ERR <BF command> command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 不加载 RedisBloom 模块，也不维护 Bloom filter 编码
- `BF.*` 不读取或修改本地 keyspace，不写入 AOF 或复制 backlog

### RedisBloom `CF.*`

格式：

```text
CF.ADD key item
CF.ADDNX key item
CF.COUNT key item
CF.DEL key item
CF.EXISTS key item
CF.INFO key
CF.INSERT key [CAPACITY capacity] [NOCREATE] ITEMS item [item ...]
CF.INSERTNX key [CAPACITY capacity] [NOCREATE] ITEMS item [item ...]
CF.LOADCHUNK key iterator data
CF.MEXISTS key item [item ...]
CF.RESERVE key capacity [BUCKETSIZE bucketsize] [MAXITERATIONS maxiterations] [EXPANSION expansion]
CF.SCANDUMP key iterator
```

返回：

- 当前统一返回：`-ERR <CF command> command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 不加载 RedisBloom 模块，也不维护 Cuckoo filter 编码
- `CF.*` 不读取或修改本地 keyspace，不写入 AOF 或复制 backlog

### RedisBloom `CMS.*`

格式：

```text
CMS.INCRBY key item increment [item increment ...]
CMS.INFO key
CMS.INITBYDIM key width depth
CMS.INITBYPROB key error probability
CMS.MERGE destination numkeys source [source ...] [WEIGHTS weight [weight ...]]
CMS.QUERY key item [item ...]
```

返回：

- 当前统一返回：`-ERR <CMS command> command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 不加载 RedisBloom 模块，也不维护 Count-Min Sketch 编码
- `CMS.*` 不读取或修改本地 keyspace，不写入 AOF 或复制 backlog

### RedisBloom `TOPK.*`

格式：

```text
TOPK.ADD key item [item ...]
TOPK.COUNT key item [item ...]
TOPK.INCRBY key item increment [item increment ...]
TOPK.INFO key
TOPK.LIST key [WITHCOUNT]
TOPK.QUERY key item [item ...]
TOPK.RESERVE key topk [width depth decay]
```

返回：

- 当前统一返回：`-ERR <TOPK command> command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 不加载 RedisBloom 模块，也不维护 Top-K 编码
- `TOPK.*` 不读取或修改本地 keyspace，不写入 AOF 或复制 backlog

### RedisBloom `TDIGEST.*`

格式：

```text
TDIGEST.ADD key value [value ...]
TDIGEST.BYRANK key rank [rank ...]
TDIGEST.BYREVRANK key reverse_rank [reverse_rank ...]
TDIGEST.CDF key value [value ...]
TDIGEST.CREATE key [COMPRESSION compression]
TDIGEST.INFO key
TDIGEST.MAX key
TDIGEST.MERGE destination numkeys source [source ...] [COMPRESSION compression] [OVERRIDE]
TDIGEST.MIN key
TDIGEST.QUANTILE key quantile [quantile ...]
TDIGEST.RANK key value [value ...]
TDIGEST.RESET key
TDIGEST.REVRANK key value [value ...]
TDIGEST.TRIMMED_MEAN key low_cut_quantile high_cut_quantile
```

返回：

- 当前统一返回：`-ERR <TDIGEST command> command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 不加载 RedisBloom 模块，也不维护 t-digest 编码
- `TDIGEST.*` 不读取或修改本地 keyspace，不写入 AOF 或复制 backlog

### `SLOWLOG`

格式：

```text
SLOWLOG HELP
SLOWLOG LEN
SLOWLOG GET [count]
SLOWLOG RESET
```

返回：

- `HELP`：返回当前支持的 `SLOWLOG` 子命令说明
- `LEN`：返回当前 slowlog 条目数
- `GET`：返回最新在前的 slowlog entry 数组；未带 `count` 时默认 `10`，`-1` 表示返回全部
- `RESET`：成功返回 `+OK`

说明：

- 当前实现为 partial：slowlog 仅是 redis-uya 进程内固定容量 ring，不持久化
- 当前记录每条命令的 `id`、秒级时间戳、runtime-measured `duration_us`、命令参数数组、客户端占位地址与空 client name
- 当前 `duration_us` 基于 redis-uya 运行时时间源采样，精度受毫秒级时钟限制；客户端地址固定为占位值 `127.0.0.1:0`，不代表 Redis 原生真实客户端端点
- `CONFIG SET slowlog-log-slower-than <microseconds>` 可控制后续 slowlog 采样门限；`0` 记录全部普通命令，`-1` 禁用采样
- `CONFIG SET slowlog-max-len <count>` 可控制后续 slowlog 保留条数并立即裁剪已有 ring；当前内部固定 ring 上限为 `128`，配置值超过该上限时实际最多保留 `128` 条

### `LATENCY`

格式：

```text
LATENCY HELP
LATENCY LATEST
LATENCY HISTORY event
LATENCY RESET [event [event ...]]
LATENCY DOCTOR
LATENCY HISTOGRAM [command [command ...]]
LATENCY GRAPH event
```

返回：

- `HELP`：返回当前支持的 `LATENCY` 子命令说明
- `LATEST`：返回 latest event 数组；当前记录 `command` 事件
- `HISTORY`：返回指定 event 的历史数组；当前支持 `command` 事件
- `RESET`：返回已清除 event 数；无参数时清空全部事件，也可按 event 名清理
- `DOCTOR`：返回 minimal 诊断文本 Bulk String
- `HISTOGRAM [command ...]`：返回命令延迟直方图数组；当前按 top-level 命令名记录 `calls` 与 `histogram_usec` 累计桶，可按命令名过滤
- `GRAPH`：返回指定 event 的 ASCII graph 文本；当前对有历史的 `command` 事件返回最小文本说明

说明：

- 当前实现为 partial：按 `latency-monitor-threshold` 采样普通命令执行耗时并写入 `command` 事件的进程内历史，同时写入 top-level 命令名直方图；`LATENCY` 自身不写入 latency 历史或直方图
- 当前 `command` 事件耗时基于 redis-uya 运行时时间源，精度受毫秒级时钟限制
- `LATENCY RESET` 只清理 event 历史；命令直方图按 Redis 习惯由 `CONFIG RESETSTAT` 清理
- `CONFIG SET latency-monitor-threshold <milliseconds>` 可控制后续 `LATENCY LATEST/HISTORY/GRAPH` 的 `command` 事件采样；`0` 禁用事件采样，正数表示记录大于等于该毫秒门限的命令事件
- 当前直方图使用 Redis 兼容的 RESP2 map-as-array 形状和固定微秒桶，但只按 top-level 命令名聚合；`CONFIG SET latency-tracking yes|no` 可控制后续命令直方图采样，尚未实现子命令名粒度直方图

### `MONITOR`

格式：

```text
MONITOR
RESET
QUIT
```

返回：

- `MONITOR`：成功后返回 `+OK`，当前连接进入 monitor 流式观测模式
- monitor 模式下，其他客户端后续成功执行的普通命令会以 RESP Simple String 行推送给 monitor 客户端
- `RESET`：退出 monitor 模式并返回 `+RESET`
- `QUIT`：关闭 monitor 连接

说明：

- 当前实现为 partial：覆盖单机流式命令观测入口、跨连接推送、连接关闭清理和 `RESET` 退出
- 当前监控行格式为 redis-uya 兼容占位格式，包含时间戳、固定 DB/端点占位和双引号参数列表；尚不提供 Redis 原生客户端地址、DB 切换真值或微秒精度时间
- 当前只在普通命令成功执行后推送；脚本内部实际命令、事务队列展开和控制面特殊分支不会完整等价 Redis 原生 `MONITOR`
- monitor 模式下同一连接只允许 `RESET` / `QUIT`

### `DEBUG`

格式：

```text
DEBUG subcommand [arg ...]
```

返回：

- 当前所有带子命令形式统一返回：`-ERR DEBUG command not allowed by redis-uya standalone profile`

说明：

- 当前实现为 `standalone-error`：`DEBUG` 已进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 单机安全 profile 不开放 Redis 内部调试/破坏性子命令
- `DEBUG` 不写入 AOF 或复制 backlog，也不会改变运行时状态
- 后续如需要开发态内部调试能力，必须先引入显式配置开关、权限边界和独立测试矩阵

### `HOTKEYS`

格式：

```text
HOTKEYS HELP
HOTKEYS GET
HOTKEYS RESET
HOTKEYS START [arg ...]
HOTKEYS STOP
```

返回：

- `HELP`：返回当前支持的 `HOTKEYS` 子命令说明
- `GET`：当前返回空数组
- `RESET` / `START` / `STOP`：当前返回 `+OK`

说明：

- 当前实现为 standalone 诊断兼容 partial：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 尚未实现热 key 采样器
- `START/STOP/RESET` 为 no-op，不启动后台采样、不维护热 key 状态
- `HOTKEYS` 不写入 AOF 或复制 backlog

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
- 当前支持 `port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`replicaof`、`masterauth`、`maxmemory`、`maxmemory-policy`、`maxclients`、`databases`、`timeout`、`save`、`latency-tracking`、`latency-monitor-threshold`、`slowlog-log-slower-than`、`slowlog-max-len`
- 支持最小 `*` 通配模式
- `CONFIG SET` 当前支持运行时子集：`port`、`bind`、`dir`、`dbfilename`、`appendfilename`、`requirepass`、`replicaof`、`masterauth`、`maxmemory`、`maxmemory-policy`、`maxclients`、`databases`、`timeout`、`save`、`latency-tracking`、`latency-monitor-threshold`、`slowlog-log-slower-than`、`slowlog-max-len`
- `CONFIG REWRITE` 当前会把运行时有效配置写到 `<appendfilename>.conf`，成功返回 `+OK`；当前已覆盖 `maxclients`、`databases` 等第二批运行时字段的落盘
- `CONFIG HELP` 返回当前支持的 CONFIG 子命令列表
- `CONFIG RESETSTAT` 当前返回 `+OK`，并清理 `LATENCY HISTOGRAM` 的命令直方图状态
- `timeout` 当前会由 server cron 关闭普通空闲连接；阻塞等待、Pub/Sub 和 MONITOR 连接不按该值主动关闭
- `CONFIG REWRITE` 当前是最小实现：目标文件路径按当前 AOF 路径派生，不保留原始配置文件注释/顺序；其余更高风险的 `CONFIG SET` 字段热更新仍不支持

### `CLIENT`

格式：

```text
CLIENT ID
CLIENT GETNAME
CLIENT GETREDIR
CLIENT REPLY ON|OFF|SKIP
CLIENT CACHING YES|NO
CLIENT SETNAME name
CLIENT NO-EVICT ON|OFF
CLIENT NO-TOUCH ON|OFF
CLIENT INFO
CLIENT LIST
CLIENT KILL ID id [SKIPME yes|no]
CLIENT UNBLOCK id [TIMEOUT|ERROR]
CLIENT PAUSE timeout-ms [WRITE|ALL]
CLIENT UNPAUSE
CLIENT TRACKING ON [REDIRECT id] [BCAST] [PREFIX prefix ...] [OPTIN] [OPTOUT] [NOLOOP]
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
- `CLIENT REPLY`：`ON` 重新开启回复并返回 `+OK`；`OFF` 关闭后续命令回复，`SKIP` 跳过紧随其后的一个命令回复；`OFF` 与 `SKIP` 自身不回包
- `CLIENT CACHING`：保存当前连接的 caching 标志，成功返回 `+OK`
- `CLIENT SETNAME`：保存连接级客户端名，成功返回 `+OK`
- `CLIENT NO-EVICT`：保存当前连接的 no-evict 标志，成功返回 `+OK`
- `CLIENT NO-TOUCH`：保存当前连接的 no-touch 标志，成功返回 `+OK`
- `CLIENT INFO`：返回当前连接的最小客户端信息行，包含 `id/name/resp/multi/sub/lib-name/lib-ver`
- `CLIENT LIST`：返回当前活跃连接的最小信息行快照，每行包含 `id/name/resp/multi/sub/lib-name/lib-ver`
- `CLIENT KILL ID id [SKIPME yes|no]`：按连接 ID 关闭活跃连接；默认 `SKIPME yes` 不关闭当前连接，显式 `SKIPME no` 可关闭当前连接，返回整数 `0/1`
- `CLIENT UNBLOCK id [TIMEOUT|ERROR]`：解除处于阻塞 pop 等待中的其他连接；默认 `TIMEOUT` 向目标连接返回对应阻塞命令的空结果，`ERROR` 向目标连接返回 `UNBLOCKED` 错误，当前命令返回整数 `0/1`
- `CLIENT PAUSE timeout-ms [WRITE|ALL]`：暂停其他连接的命令处理；`ALL` 阻塞后续命令，`WRITE` 只阻塞写命令并允许读命令继续执行，返回 `+OK`
- `CLIENT UNPAUSE`：提前解除当前 pause 状态，返回 `+OK`
- `CLIENT TRACKING`：当前支持连接级 `ON/OFF`、`REDIRECT`、`BCAST`、`PREFIX`、`OPTIN`、`OPTOUT`、`NOLOOP` 状态存储，返回 `+OK`；`PREFIX` 仅在 `BCAST` 模式下接受
- `CLIENT TRACKINGINFO`：RESP2 下返回 flatten array，RESP3 下返回 map，暴露当前连接的 tracking flags、redirect 和 prefixes
- `CLIENT SETINFO`：保存客户端库名/版本元数据，成功返回 `+OK`
- `CLIENT HELP`：返回当前支持的 CLIENT 子命令列表

说明：

- 客户端名和 `SETINFO` 元数据存放在连接级 `ConnectionTransaction`
- `CLIENT GETREDIR` 直接读取当前连接的 `tracking_redirect_id`
- `CLIENT REPLY` 当前按连接维护 `OFF`/`SKIP` 状态，覆盖普通命令、事务控制命令和 `CLIENT` 子命令回复抑制；Pub/Sub push 与 monitor 推送不受影响
- `CLIENT KILL` 当前只支持 `ID <id>` 和 `SKIPME yes|no` 过滤，不支持更完整的 addr/type/user/maxage 组合
- `CLIENT UNBLOCK` 当前支持阻塞 pop 等待路径的 `TIMEOUT` / `ERROR` 解除，不支持更复杂的模块阻塞客户端类型
- `CLIENT PAUSE` 当前保留发起暂停的控制连接可继续发送 `CLIENT UNPAUSE`；`WRITE` 基于命令目录的写标志和当前已解析 batch 判断，不实现 Redis 原生跨线程 pause 协调
- `CLIENT TRACKING` 当前只保存连接级状态和 `BCAST PREFIX` 列表，不发送 invalidation push
- `CLIENT CACHING` 当前只保存连接级兼容标志，尚未提供 server-assisted client-side caching invalidation
- `CLIENT NO-EVICT` 当前只保存连接级兼容标志，尚未接入 `maxmemory` 淘汰候选保护
- `CLIENT NO-TOUCH` 当前只保存连接级兼容标志，尚未接入对象访问路径的 LRU/LFU touch 抑制

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

### `ASKING` / `READONLY` / `READWRITE`

格式：

```text
ASKING
READONLY
READWRITE
```

返回：

- 当前实现为 `standalone-error`：命令进入运行时路由和 `COMMAND*` 可见面，但 redis-uya 尚未实现 Redis Cluster 客户端连接态
- 统一返回：`-ERR This instance has cluster support disabled`

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
- `SHARDCHANNELS`：当前存在 shard 订阅的频道数组；带 `pattern` 时按 glob 过滤
- `SHARDNUMSUB`：扁平数组 `[shardchannel, subscriber_count, ...]`

说明：

- `CHANNELS` 只统计直连频道订阅，不把 pattern 订阅投影为频道
- `NUMPAT` 统计当前连接注册表里的 pattern 订阅项总数
- `SHARDCHANNELS/SHARDNUMSUB` 只统计 `SSUBSCRIBE` 注册的 shard 频道
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

### `SSUBSCRIBE`

格式：

```text
SSUBSCRIBE shardchannel [shardchannel ...]
```

返回：

- 每个 shard channel 返回一个订阅确认：`["ssubscribe", shardchannel, count]`

说明：

- 当前实现为 standalone 连接级 shard 订阅注册表，不做 Cluster slot 路由
- RESP2 订阅态下允许继续执行 `SSUBSCRIBE/SUNSUBSCRIBE`

### `SUNSUBSCRIBE`

格式：

```text
SUNSUBSCRIBE
SUNSUBSCRIBE shardchannel [shardchannel ...]
```

返回：

- 每个 shard channel 返回一个取消订阅确认：`["sunsubscribe", shardchannel, remaining_count]`

### `SPUBLISH`

格式：

```text
SPUBLISH shardchannel message
```

返回：

- 收到消息的 shard 订阅者数量，Integer

说明：

- 订阅者会收到 `["smessage", shardchannel, message]`
- `SPUBLISH` 只投递给 `SSUBSCRIBE` 订阅者，不投递给普通 `SUBSCRIBE/PSUBSCRIBE`
- 当前不把 `SPUBLISH` 追加到 AOF，也不复制到 backlog

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
SLAVEOF host port
SLAVEOF NO ONE
```

返回：

- 成功：`+OK`
- `SLAVEOF` 当前作为 `REPLICAOF` alias 进入同一执行路径
- 当前已完成复制角色切换、`PSYNC` 全量同步、轮询式增量同步和基础心跳；仍不支持 Redis 原生长连接流式增量推送、真实 ACK/GETACK 等完整复制协议

### `REPLCONF`

格式：

```text
REPLCONF [option [value ...]]
```

返回：

- 当前 partial 对任意参数形态返回 `+OK`

说明：

- 用作复制握手兼容面；当前不记录 replica 端口、能力、ACK offset，也不触发 `GETACK` 推送
- 不进入 AOF 或 replication backlog

### `FAILOVER`

格式：

```text
FAILOVER [TO host port [FORCE]] [ABORT] [TIMEOUT milliseconds]
```

返回：

- 当前统一返回：`-ERR FAILOVER requires connected replicas.`

说明：

- 当前实现为 `standalone-error`：命令已进入运行时路由、命令矩阵和 `COMMAND*` 可见面，但 redis-uya 尚未实现 Redis 自动 failover / controlled failover 状态机
- 当前不会提升 replica、切换复制角色、等待同步 offset、关闭 master 客户端或修改复制配置
- 不进入 AOF 或 replication backlog

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

### `SYNC`

格式：

```text
SYNC
```

返回：

- 当前实现为 legacy full-sync partial：master 角色返回一份 RESP Bulk String 包裹的项目内 RDB 快照
- replica 角色返回：`-ERR SYNC is only valid for master role`

说明：

- `SYNC` 复用当前 RDB dump 路径，不返回 `PSYNC` 的 `+FULLRESYNC` 头，也不进入 AOF 或 replication backlog
- 当前不实现 Redis 原生复制连接的后续长连接命令流；真实 replica 仍优先使用 `PSYNC`

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
