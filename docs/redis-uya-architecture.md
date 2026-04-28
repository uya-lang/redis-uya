# redis-uya ARCHITECTURE

> 版本: v0.1.0-dev
> 日期: 2026-04-28

## 1. 总体结构

`redis-uya` 当前是单进程、单线程、单节点的最小 Redis 内核。

主数据路径：

```text
TCP listener
-> epoll event loop
-> per-client input buffer
-> RESP2 / RESP3 parser
-> command router
-> command executor
-> storage engine
-> reply encode
-> nonblocking socket write
```

写命令旁路：

```text
command executor
-> AOF append
```

启动恢复路径：

```text
server open
-> load minimal RDB snapshot if present
-> open AOF
-> replay AOF
-> start listener
```

## 2. 模块分工

### `src/network/`

- `listener.uya`：loopback TCP 监听、accept、listener 级 epoll fd
- `connection.uya`：RESP 请求处理、连接级 RESP2/RESP3 模式、回复编码、非阻塞读写、待发送缓冲
- `protocol.uya`：RESP2 与 RESP3 最小解析

### `src/command/`

- `router.uya`：命令表、命令名匹配、参数数量校验
- `executor.uya`：String/Key 命令执行

### `src/storage/`

- `sds.uya`：动态字符串
- `dict.uya`：项目内专用字典，支持渐进 rehash
- `object.uya`：最小 `RedisObject`
- `engine.uya`：键空间、TTL、主动/惰性过期

### `src/persistence/`

- `aof.uya`：写命令追加、流式回放、损坏安全失败
- `rdb.uya`：项目内最小 RDB 子集 save/load
- `rewrite.uya`：离线 AOF rewrite 原型

### `src/server.uya`

- 维护全局 `RedisServer`
- 驱动单线程 epoll 事件循环
- 维护客户端槽位、输入缓冲、待发送输出
- 驱动 100ms `cron`

## 3. 当前事件循环

每个客户端槽位维护：

- `input`：读缓冲
- `input_len`：当前已读字节数
- `output`：待发送响应
- `output_len` / `output_sent`：发送进度
- `close_after_write`：`QUIT` 等命令的延迟关闭标志
- `transaction`：连接级事务队列、WATCH 集合、RESP 协议版本与 Pub/Sub 订阅计数状态

调度规则：

- 默认关注 `EPOLLIN`
- 当写回遇到 `EAGAIN` 时，保留剩余输出并切换到 `EPOLLOUT`
- 输出全部发完后恢复到 `EPOLLIN`
- 空闲客户端不再阻塞活跃客户端

## 4. Pub/Sub 最小闭环

- `connection.uya` 维护固定容量订阅注册表，记录 `fd -> channel` 与连接协议版本
- `SUBSCRIBE` / `UNSUBSCRIBE` 在连接层更新注册表并返回确认消息
- `PUBLISH` 在连接层按频道扫描订阅表，向匹配 fd 推送 `message` 事件，并向发布者返回订阅者数量
- 客户端关闭时，`server.uya` 会清理该 fd 的订阅项

当前 Pub/Sub 是最小闭环，不包含 pattern 订阅、完整 subscribed-mode 命令限制和高水位背压队列。

## 5. 过期策略

当前同时有两条路径：

- 惰性过期：访问键时检查 TTL
- 主动过期：100ms `cron` 内做受限扫描

## 6. AOF 语义

- 写命令直接追加 RESP2 原始请求
- `EXPIRE` 追加时重写成绝对时间 `PEXPIREAT`
- 回放按流式解析逐条执行
- `BGREWRITEAOF` 使用子进程写出规范化 AOF 快照，父进程继续追加旧 AOF 并记录 rewrite 增量缓冲，子进程结束后合并并原子替换
- 截断、非法协议、非法命令、执行错误都会安全失败

## 7. 当前限制

- 单线程
- `BGSAVE` / `BGREWRITEAOF` 已有最小子进程后台路径，但仍未做更细粒度的后台资源隔离与吞吐优化
- RDB 已覆盖当前五类对象和绝对过期时间，但仍不是 Redis 完整二进制兼容
- 复制当前已覆盖角色与状态机、`PSYNC / backlog`、replica 侧全量同步、定时拉取式增量同步与心跳；仍不是 Redis 那种长连接流式推送复制
- 无集群
- 事务当前已覆盖连接级最小 `MULTI/EXEC/DISCARD/WATCH/UNWATCH`，但仍没有更完整的 Redis 事务中止传播、脚本联动和控制面扩展
- RESP3 当前是 `HELLO 2/3` 驱动的最小闭环，仍不是完整 RESP3 类型输出与客户端兼容矩阵
- Pub/Sub 当前是固定容量最小闭环，仍没有 pattern 订阅、完整 subscribed-mode 命令限制和背压缓冲
