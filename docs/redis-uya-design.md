# redis-uya 详细设计文档

> 版本: v0.9.0-planning
> 日期: 2026-04-30
> 当前开发工具链: Uya v0.9.4（本地修复快照）
> 目标平台: Linux x86_64 / ARM64

---

## 目录

1. [项目概述](#1-项目概述)
2. [总体架构](#2-总体架构)
3. [核心模块设计](#3-核心模块设计)
4. [数据结构与存储引擎](#4-数据结构与存储引擎)
5. [网络通信层](#5-网络通信层)
6. [持久化子系统](#6-持久化子系统)
7. [并发与异步模型](#7-并发与异步模型)
8. [内存管理策略](#8-内存管理策略)
9. [命令处理流水线](#9-命令处理流水线)
10. [错误处理与监控](#10-错误处理与监控)
11. [模块接口定义](#11-模块接口定义)
12. [代码规范与约定](#12-代码规范与约定)
13. [附录：uya 语言关键特性映射](#13-附录uya-语言关键特性映射)

---

## 1. 项目概述

### 1.1 项目目标

`redis-uya` 是一个使用 **Uya 编程语言** 从零实现的生产级高性能内存数据库系统，目标兼容 Redis Open Source，长期在核心场景上超过 Redis。

规划更新：`v0.9.0` 起后续主线只迭代单机版，补齐 Redis Open Source 官方命令参考中的全部命令名，以及单机功能、兼容性、性能和稳定性；功能和性能达标后封版为 `v1.0.0`。`v0.9.4` 是首个单机封版候选，未达标时继续 `v0.9.5`、`v0.9.6` 等 patch 版本。集群版在 `v1.0.0` 之后重新规划，`v0.7.0` 已有集群基础作为历史能力保留。

项目以 Redis 兼容性、低延迟、高吞吐、可观测性和可维护性为核心目标。实现上优先选择可验证的简单架构：单线程事件循环作为基础性能路径，显式内存管理避免 GC 暂停，后台任务只在收益明确时逐步引入，避免首版被并发复杂度拖垮。

性能目标分层管理：`floor` 用于阶段验收，`target` 用于追平 Redis，`stretch` 用于在同条件下超过 Redis。比较口径必须固定硬件、命令集、持久化策略、客户端并发和统计窗口。

### 1.2 设计哲学

| 维度 | 策略 | uya 语言支撑 |
|------|------|-------------|
| **安全** | 编译期消除所有内存竞争与 UB | `atomic T` 零数据竞争、编译期安全证明 |
| **性能** | 零 GC 暂停、无锁数据结构、SIMD 加速 | 零 GC 运行时、无隐式控制、@vector SIMD |
| **简洁** | 单页纸可记完的模块 API | uya 极简语法、显式控制流 |
| **可靠** | 任何错误必须显式处理 | `!T` 错误联合类型、无隐式 panic |

### 1.3 首版非目标

`v0.1.0` 不包含以下内容：

- 完整 RESP3
- RDB 完整兼容
- `BGSAVE` / `BGREWRITEAOF`
- 主从复制
- 基础集群
- Lua 脚本
- 完整 Redis 模块系统
- 所有复杂类型的首版完整交付

### 1.4 `v0.1.0` 交付范围

`v0.1.0` 只承诺交付一个可运行、可测试、可 benchmark 的最小生产内核：

- 单节点、单进程服务模型
- RESP2 子集
- String 与 Key 命令子集
- 项目内专用 `Dict`
- AOF append + replay
- `redis-cli` smoke 与 Python 子集集成测试
- 同机 Redis 对照 benchmark 基线

### 1.5 实现约束

- 当前设计以 `Uya v0.9.4` 本地修复快照为准，不假设 `v0.9.5` 新能力。
- 涉及泛型容器、复杂 async、`fork()`、后台重写等路径时，必须先做最小 spike 验证。
- 数据结构和协议路径优先选择“可稳定承载”的实现，而不是一步追求最终形态。

---

## 2. 总体架构

### 2.1 模块拓扑图

```
┌─────────────────────────────────────────────────────────────┐
│                        redis-uya Server                      │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│   Client    │   Client    │   Client    │      Monitor        │
│  Connection │  Connection │  Connection │     / Admin        │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │                 │
       └─────────────┴─────────────┴─────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Network Layer    │  ← std.net / epoll / async
              │   (TCP Server)      │     Connection Pool
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   RESP Protocol     │  ← Protocol Parser
              │     Parser          │     (Zero-Copy where possible)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   Command Router    │  ← Command Table
              │   & Validator       │     (HashMap<cmd_name, handler>)
              └──────────┬──────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
┌──────▼──────┐  ┌───────▼───────┐  ┌──────▼──────┐
│  Storage    │  │  Persistence  │  │  Replication │
│   Engine    │  │    (RDB/AOF)  │  │  (Master/Slave)│
│             │  │               │  │              │
│ • String    │  │ • Snapshot    │  │ • PSYNC     │
│ • Hash      │  │ • Append Log  │  │ • Backlog   │
│ • List      │  │ • Rewrite     │  │ • Heartbeat │
│ • Set       │  │               │  │              │
│ • ZSet      │  │               │  │              │
└─────────────┘  └───────────────┘  └──────────────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Memory Manager    │  ← SlabAllocator / jemalloc FFI
              │   (Eviction/Expiry) │     LRU/LFU/TTL
              └─────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Async Runtime     │  ← std.async / epoll / io_uring(后期)
              │   (Event Loop)      │     Future / Task / Waker
              └─────────────────────┘
```

### 2.2 目录结构

```
redis-uya/
├── src/
│   ├── main.uya              # 入口：配置解析、启动流程
│   ├── server.uya            # Server 主结构体与生命周期
│   ├── config.uya            # 配置管理
│   ├── network/
│   │   ├── listener.uya      # TCP 监听与连接接纳
│   │   ├── connection.uya    # 客户端连接状态机
│   │   └── protocol.uya      # RESP2/RESP3 编解码器
│   ├── command/
│   │   ├── router.uya        # 命令路由表
│   │   ├── validator.uya     # 参数校验
│   │   ├── string.uya        # String 命令集
│   │   ├── hash.uya          # Hash 命令集
│   │   ├── list.uya          # List 命令集
│   │   ├── set.uya           # Set 命令集
│   │   ├── zset.uya          # ZSet 命令集
│   │   ├── key.uya           # Key 管理命令
│   │   ├── server.uya        # Server 管理命令
│   │   └── transaction.uya   # MULTI/EXEC/DISCARD
│   ├── storage/
│   │   ├── engine.uya        # 存储引擎总控
│   │   ├── dict.uya          # 哈希表（核心索引）
│   │   ├── sds.uya           # Simple Dynamic String
│   │   ├── string_obj.uya    # String 对象实现
│   │   ├── hash_obj.uya      # Hash 对象实现
│   │   ├── list_obj.uya      # List 对象实现 (QuickList)
│   │   ├── set_obj.uya       # Set 对象实现 (IntSet/HashTable)
│   │   ├── zset_obj.uya      # ZSet 对象实现 (SkipList+HashTable)
│   │   ├── expire.uya        # 过期键管理
│   │   └── object.uya        # 统一对象包装器
│   ├── persistence/
│   │   ├── rdb.uya           # RDB 序列化/反序列化
│   │   ├── aof.uya           # AOF 写入与回放
│   │   └── rewrite.uya       # AOF 重写与 RDB 后台保存
│   ├── replication/
│   │   ├── master.uya        # 主节点逻辑
│   │   ├── slave.uya         # 从节点逻辑
│   │   ├── sync.uya          # 全量/增量同步
│   │   └── backlog.uya       # 复制积压缓冲区
│   ├── memory/
│   │   ├── allocator.uya     # 内存分配器封装
│   │   ├── slab.uya          # Slab 分配器
│   │   ├── pool.uya          # 对象池
│   │   └── eviction.uya      # 淘汰策略 (LRU/LFU)
│   ├── async_rt/
│   │   ├── runtime.uya       # 事件循环封装
│   │   ├── handler.uya       # 请求处理器 Future
│   │   └── timer.uya         # 定时器队列 (TTL/定期任务)
│   └── util/
│       ├── log.uya           # 日志
│       ├── crc64.uya         # CRC64 校验
│       ├── endian.uya        # 字节序处理
│       └── time.uya          # 时间戳与单调时钟
├── lib/
│   └── (uya 标准库引用)
├── tests/
│   ├── unit/                 # 单元测试 (*.uya)
│   ├── integration/          # 集成测试 (Python 驱动)
│   └── benchmark/            # 性能基准
├── docs/
│   └── (本文件及 API 文档)
└── build.uya                 # 构建脚本
```

---

## 3. 核心模块设计

### 3.1 Server 主结构体

```uya
// src/server.uya
use std.collections.HashMap;
use std.collections.LinkedList;
use std.time;
use std.async;
use std.net;
use std.io;

use redis.network.Connection;
use redis.storage.Engine;
use redis.persistence.RdbConfig;
use redis.persistence.AofConfig;
use redis.memory.EvictionPolicy;
use redis.replication.ReplicationRole;
use redis.async_rt.Runtime;

/// Redis 服务器全局状态
export struct RedisServer {
    // --- 网络层 ---
    listener: std.net.TcpListener,
    connections: HashMap<i32, Connection>,     // fd -> Connection
    maxclients: i32,
    
    // --- 存储层 ---
    db: Engine,                                  // 核心存储引擎
    dbnum: i32,                                  // 数据库数量 (默认 16)
    
    // --- 持久化 ---
    rdb_config: RdbConfig,
    aof_config: AofConfig,
    
    // --- 复制 ---
    role: ReplicationRole,                     // Master | Slave
    
    // --- 内存管理 ---
    maxmemory: usize,                           // 最大内存限制 (字节)
    eviction: EvictionPolicy,                    // 淘汰策略
    
    // --- 运行时 ---
    rt: Runtime,                                // 异步运行时
    running: atomic bool,                       // 运行状态标志
    
    // --- 统计 ---
    stat: ServerStat,
}

/// 服务器统计信息
struct ServerStat {
    total_commands_processed: atomic u64,
    total_connections_received: atomic u64,
    expired_keys: atomic u64,
    evicted_keys: atomic u64,
    start_time: i64,                            // UNIX 时间戳 (秒)
}

export interface IServer {
    fn start(self: &Self) !void;
    fn stop(self: &Self) void;
    fn cron(self: &Self) void;                  // 定时任务入口
}

RedisServer : IServer {
    fn start(self: &Self) !void {
        // 1. 初始化存储引擎
        self.db.init(self.dbnum) catch |e| {
            return error.EngineInitFailed;
        };
        
        // 2. 加载 RDB/AOF
        if self.rdb_config.enabled {
            self.load_rdb() catch |e| {
                // RDB 损坏时仍可启动，记录警告
                log.warn("RDB load failed: {}", e);
            };
        }
        
        // 3. 启动网络监听 (异步)
        self.listener.bind(self.bind_addr, self.port) catch |e| {
            return error.BindFailed;
        };
        
        // 4. 启动事件循环
        self.rt.run(self) catch |e| {
            return error.RuntimeError;
        };
    }
    
    fn stop(self: &Self) void {
        self.running = false;
        self.rt.shutdown();
        self.listener.close();
    }
    
    fn cron(self: &Self) void {
        // 每 100ms 执行一次的定时任务
        // 1. 处理过期键 (主动 + 随机采样)
        self.db.active_expire_cycle(100);
        
        // 2. 检查内存并执行淘汰
        if self.maxmemory > 0 {
            self.perform_eviction();
        }
        
        // 3. 持久化后台检查
        self.rdb_check_save();
        
        // 4. 复制心跳
        if self.role == ReplicationRole.MASTER {
            self.replication_cron();
        }
    }
}
```

### 3.2 配置系统

```uya
// src/config.uya

/// 配置文件解析与默认值管理
export struct ServerConfig {
    // 网络
    bind: &[u8: 64] = "0.0.0.0",
    port: i32 = 6379,
    tcp_backlog: i32 = 511,
    timeout: i32 = 0,                          // 客户端空闲超时 (秒), 0=无限制
    tcp_keepalive: i32 = 300,
    
    // 通用
    daemonize: bool = false,
    supervised: &[u8: 32] = "no",
    loglevel: LogLevel = LogLevel.NOTICE,
    logfile: &[u8: 256] = "",
    databases: i32 = 16,
    
    // RDB 持久化
    save: &[SaveCondition: 16] = [              // 触发条件数组
        SaveCondition{ seconds: 900, changes: 1 },
        SaveCondition{ seconds: 300, changes: 10 },
        SaveCondition{ seconds: 60,  changes: 10000 },
    ],
    stop_writes_on_bgsave_error: bool = true,
    rdbcompression: bool = true,
    rdbchecksum: bool = true,
    dbfilename: &[u8: 128] = "dump.rdb",
    dir: &[u8: 256] = "./",
    
    // AOF 持久化
    appendonly: bool = false,
    appendfilename: &[u8: 128] = "appendonly.aof",
    appendfsync: AofFsyncMode = AofFsyncMode.EVERYSEC,
    no_appendfsync_on_rewrite: bool = false,
    auto_aof_rewrite_percentage: i32 = 100,
    auto_aof_rewrite_min_size: usize = 64 * 1024 * 1024,  // 64MB
    
    // 内存限制
    maxmemory: usize = 0,                       // 0 = 无限制
    maxmemory_policy: &[u8: 32] = "noeviction",
    maxmemory_samples: i32 = 5,
    
    // 复制
    replicaof: &[u8: 256] = "",                 // "host port" 或空
    masterauth: &[u8: 256] = "",
    
    // 客户端输出缓冲区限制
    client_output_buffer_limit: &[BufferLimit: 3],
}

struct SaveCondition {
    seconds: i32,
    changes: i32,
}

enum LogLevel { DEBUG, VERBOSE, NOTICE, WARNING }
enum AofFsyncMode { ALWAYS, EVERYSEC, NO }
enum BufferLimitClass { NORMAL, REPLICA, PUBSUB }

struct BufferLimit {
    class: BufferLimitClass,
    hard_limit: usize,
    soft_limit: usize,
    soft_seconds: i32,
}

export fn parse_config_file(path: *byte) !ServerConfig {
    var cfg: ServerConfig = ServerConfig{};
    // 逐行解析 redis.conf 格式
    // 支持 include、关键词-值对、单位后缀 (kb, mb, gb)
    // 返回解析错误或配置结构体
    return cfg;
}
```

---

## 4. 数据结构与存储引擎

### 4.1 核心哈希表 (Dict)

Redis 的核心是哈希表，用于存储所有键值对。`redis-uya` 首版不直接依赖泛型 `HashMap<K, V>` 作为前提，而是实现项目内专用 `Dict`，先把字符串键空间和对象存储闭环跑通，再逐步增强 rehash、迭代器与采样能力。

```uya
// src/storage/dict.uya

/// 首版项目内专用字典
/// - 键固定为 Sds
/// - 值固定为 RedisObject 或对象句柄
/// - 先保证 insert/lookup/delete/len 正确
/// - 渐进式 rehash 作为第二阶段增强
export struct Dict {
    primary: DictTable,
    secondary: DictTable,
    rehashidx: i32,                             // -1 = 未在 rehash
    iterators: i32,
}

struct DictTable {
    entries: &[DictEntry],
    size: usize,
    used: usize,
}

struct DictEntry {
    key: Sds,
    value: RedisObject,
    expires_at: i64,
    lru: u32,
}

export interface IDict {
    fn insert(self: &Self, key: Sds, value: RedisObject, expires_ms: i64) !void;
    fn lookup(self: &Self, key: &Sds) ?&RedisObject;
    fn delete(self: &Self, key: &Sds) bool;
    fn len(self: &Self) i32;
    fn begin_rehash(self: &Self) void;
    fn rehash_step(self: &Self, n: i32) i32;
}
```

### 4.2 Simple Dynamic String (SDS)

Redis 的字符串不是普通 C 字符串，而是带有元数据的二进制安全字符串。

```uya
// src/storage/sds.uya

/// 二进制安全的动态字符串
/// 兼容 Redis 的 sds 设计，支持 O(1) 长度获取和预分配
export struct Sds {
    buf: &[u8],                                  // 切片引用实际数据
    // 注意：实际内存布局为 [len: i32, alloc: i32, flags: u8, buf...]
    // 使用 extern struct 保持与 C 层兼容
}

export extern struct SdsHdr {
    len: i32,                                   // 已使用长度
    alloc: i32,                                 // 已分配容量 (不含头部和空终止)
    flags: u8,                                   // 类型标记 (5/8/16/32/64 位)
    // buf 紧跟其后
    
    fn create(init: *byte) Sds {
        const initlen: i32 = strlen(init) as i32;
        return sds_new_len(init, initlen);
    }
    
    fn len(self: &Self) i32 {
        return self.len;
    }
    
    fn grow(self: &Self, addlen: i32) !Sds {
        // 若容量不足则 realloc，策略为 2x 扩容
        if self.alloc - self.len < addlen {
            const newlen: i32 = self.len + addlen;
            const reqlen: i32 = if newlen < 1024 { newlen * 2 } else { newlen + 1024 };
            // ... realloc 逻辑
        }
        return self as Sds;  // 实际返回新的引用
    }
    
    fn drop(self: &Self) void {
        // 释放 hdr+buf 连续内存块
        free(self as &void);
    }
}

/// sds 工具函数
export fn sds_new_len(init: *byte, initlen: i32) Sds;
export fn sds_cat(s: Sds, t: *byte) Sds;
export fn sds_range(s: Sds, start: i32, end: i32) Sds;  // 切片 (不拷贝)
export fn sds_cmp(a: Sds, b: Sds) i32;                  // memcmp
```

### 4.3 数据对象系统 (RedisObject)

Redis 使用统一对象包装器来存储所有类型的值。

```uya
// src/storage/object.uya

/// 对象类型标记
export enum ObjectType {
    STRING = 0,
    LIST = 1,
    SET = 2,
    ZSET = 3,
    HASH = 4,
    STREAM = 5,                                // 预留
}

/// 底层编码方式 (多种内部实现根据数据量自动切换)
export enum Encoding {
    RAW = 0,                                    // SDS 字符串
    INT = 1,                                    // 64 位整数字面量 (节省内存)
    EMBSTR = 2,                                 // 短字符串内嵌 (<=44 字节)
    
    // List
    QUICKLIST = 3,                             // 压缩列表 + 双向链表节点
    
    // Set
    INTSET = 4,                                // 整数集合 (元素全为整数且数量少)
    HT = 5,                                     // 哈希表
    
    // ZSet
    ZIPLIST = 6,                               // 压缩列表 (旧实现，后期用 listpack)
    SKIPLIST = 7,                              // 跳表 + 哈希表双索引
    
    // Hash
    ZIPMAP = 8,                                // 已废弃，保留标记
    LISTPACK = 9,                              // 新版紧凑列表格式
}

/// 统一 Redis 对象
/// 采用 uya union 特性：编译期标签跟踪，零额外开销且 100% 类型安全
export union RedisObject {
    tag: ObjectType,
    
    // String 变体
    string: struct {
        encoding: Encoding,
        ptr: union {
            raw: Sds,
            int_val: i64,
        },
    },
    
    // List 变体
    list: struct {
        encoding: Encoding,
        ptr: &QuickList,                           // 总是指针 (较大结构)
    },
    
    // Set 变体
    set: struct {
        encoding: Encoding,
        ptr: union {
            intset: &IntSet,
            ht: &HashMap<Sds, void>,               // 值用空占位 (HashSet)
        },
    },
    
    // ZSet 变体 (跳表 + 哈希表)
    zset: struct {
        encoding: Encoding,
        ptr: &ZSet,
    },
    
    // Hash 变体
    hash: struct {
        encoding: Encoding,
        ptr: union {
            listpack: &ListPack,
            ht: &HashMap<Sds, Sds>,
        },
    },
}

/// 对象创建与销毁
export fn create_string_object(ptr: *byte, len: i32) RedisObject;
export fn create_int_object(value: i64) RedisObject;
export fn create_quicklist_object() RedisObject;
export fn create_zset_object() RedisObject;
export fn object_free(o: &RedisObject) void;
```

### 4.4 存储引擎总控

```uya
// src/storage/engine.uya
use std.collections.HashMap;

/// 单个数据库 (Redis 支持多 DB，默认 16 个)
export struct RedisDb {
    dict: Dict<Sds, RedisObject>,               // 键空间
    expires: HashMap<Sds, i64>,                 // 过期字典：键 -> 过期时间 (毫秒)
    id: i32,
    
    // 阻塞客户端队列 (BLPOP/BRPOP)
    blocking_keys: HashMap<Sds, LinkedList<&Connection>>,
    ready_keys: HashMap<Sds, void>,             // 已就绪的阻塞键 (处理完即删)
    
    // WATCH 事务相关
    watched_keys: HashMap<Sds, LinkedList<&Connection>>,
}

/// 存储引擎
export struct Engine {
    dbs: &[RedisDb],                             // 数据库数组
    db_count: i32,
    
    // 全局过期策略参数
    expire_cycle_active: bool,
    expire_cycle_slow: bool,
}

export interface IEngine {
    fn init(self: &Self, dbnum: i32) !void;
    fn lookup_key(self: &Self, dbid: i32, key: Sds) ?&RedisObject;
    fn set_key(self: &Self, dbid: i32, key: Sds, val: RedisObject, expire_ms: i64) !void;
    fn delete_key(self: &Self, dbid: i32, key: Sds) bool;
    fn expire_if_needed(self: &Self, dbid: i32, key: Sds) bool;  // 惰性删除
    fn active_expire_cycle(self: &Self, timelimit_ms: i32) void; // 主动过期采样
    fn scan(self: &Self, dbid: i32, cursor: u64) ScanResult;
}
```

---

## 5. 网络通信层

### 5.1 TCP 监听与连接管理

基于 uya 的 `std.net` 和 `std.async` 实现异步非阻塞 IO。

```uya
// src/network/listener.uya
use std.net.TcpListener;
use std.net.TcpStream;
use std.async;
use std.async.Future;

export struct NetworkListener {
    listener: TcpListener,
    rt: &Runtime,
    server: &RedisServer,
}

/// 接受连接的异步 Future
export struct AcceptFuture {
    listener: &TcpListener,
    
    // Future 接口实现
    fn poll(self: &Self, waker: Waker) Poll!TcpStream {
        match self.listener.accept_nonblock() {
            Ok(stream) => Poll.Ready(stream),
            Err(WouldBlock) => {
                // 注册到 epoll 等待可读事件
                self.rt.register_read(self.listener.fd(), waker);
                Poll.Pending
            },
            Err(e) => Poll.Err(e),
        }
    }
}

export fn run_accept_loop(listener: &NetworkListener) !void {
    while listener.server.running {
        // 异步等待新连接
        const stream: TcpStream = await AcceptFuture{ listener: &listener.listener } catch |e| {
            log.error("Accept failed: {}", e);
            continue;
        };
        
        // 创建连接对象并分配到 worker
        const conn: Connection = Connection.new(stream, listener.server);
        listener.rt.spawn(handle_connection(conn));
    }
}
```

### 5.2 RESP 协议解析器

```uya
// src/network/protocol.uya

/// RESP3 类型标记
export enum RespType {
    SIMPLE_STRING = '+',
    SIMPLE_ERROR = '-',
    INTEGER = ':',
    BULK_STRING = '$',
    ARRAY = '*',
    NULL = '_',                                 // RESP3
    BOOLEAN = '#',                              // RESP3
    DOUBLE = ',',                               // RESP3
    BIG_NUMBER = '(',                           // RESP3
    BULK_ERROR = '!',                           // RESP3
    VERBATIM_STRING = '=',                       // RESP3
    MAP = '%',                                  // RESP3
    SET = '~',                                  // RESP3
    ATTRIBUTE = '|',                            // RESP3 (未实现)
    PUSH = '>',                                 // RESP3
}

/// 协议值 (采用 union 实现多态，零额外指针开销)
export union RespValue {
    tag: RespType,
    
    simple_string: Sds,
    simple_error: Sds,
    integer: i64,
    bulk_string: ?Sds,                          // null 表示 nil
    array: &[RespValue],
    null_val: void,
    boolean: bool,
    double: f64,
    big_number: Sds,
    bulk_error: Sds,
    verbatim_string: struct { format: [u8: 3], text: Sds },
    map: &[struct { key: RespValue, val: RespValue }],
    set: &[RespValue],
    push: struct { kind: Sds, data: &[RespValue] },
}

/// 解析器状态机
export struct RespParser {
    buf: &[u8],                                 // 读缓冲区 (环形或线性)
    pos: usize,
    
    fn parse(self: &Self) !RespValue {
        if self.pos >= self.buf.len {
            return error.Incomplete;
        }
        const type_byte: u8 = self.buf[self.pos];
        self.pos += 1;
        
        match type_byte {
            '+' => self.parse_simple_string(),
            '-' => self.parse_simple_error(),
            ':' => self.parse_integer(),
            '$' => self.parse_bulk_string(),
            '*' => self.parse_array(),
            '_' => self.parse_null(),
            '#' => self.parse_boolean(),
            ',' => self.parse_double(),
            '%' => self.parse_map(),
            '~' => self.parse_set(),
            '>' => self.parse_push(),
            _ => error.UnknownType,
        }
    }
    
    fn parse_bulk_string(self: &Self) !RespValue {
        const len: i64 = self.read_line_parse_int() catch |e| { return e; };
        if len < 0 {
            return RespValue{ tag: RespType.NULL, null_val: {} };
        }
        const data: &[u8] = self.read_exact(len as usize) catch |e| { return e; };
        // 跳过末尾 \r\n
        self.skip_crlf();
        return RespValue{ tag: RespType.BULK_STRING, bulk_string: sds_new_len(data.ptr, len as i32) };
    }
    
    fn parse_array(self: &Self) !RespValue {
        const count: i64 = self.read_line_parse_int() catch |e| { return e; };
        if count < 0 {
            return RespValue{ tag: RespType.NULL, null_val: {} }; // null array
        }
        
        var items: &[RespValue] = allocator.alloc_array(RespValue, count as usize) catch |e| { return e; };
        for 0..count |i| {
            items[i] = self.parse() catch |e| { return e; };
        }
        return RespValue{ tag: RespType.ARRAY, array: items };
    }
}

/// 编码器：RespValue -> 字节流
export struct RespEncoder {
    output: &std.io.Writer,
    
    fn encode(self: &Self, val: &RespValue) !void {
        match val.tag {
            RespType.SIMPLE_STRING => {
                self.output.write("+");
                self.output.write(val.simple_string);
                self.output.write("\r\n");
            },
            RespType.SIMPLE_ERROR => {
                self.output.write("-");
                self.output.write(val.simple_error);
                self.output.write("\r\n");
            },
            RespType.INTEGER => {
                self.output.write(":");
                self.output.write_int(val.integer);
                self.output.write("\r\n");
            },
            RespType.BULK_STRING => {
                if val.bulk_string == null {
                    self.output.write("$-1\r\n");
                } else {
                    const s: Sds = val.bulk_string;
                    self.output.write("$");
                    self.output.write_int(s.len());
                    self.output.write("\r\n");
                    self.output.write(s);
                    self.output.write("\r\n");
                }
            },
            RespType.ARRAY => {
                self.output.write("*");
                self.output.write_int(val.array.len as i64);
                self.output.write("\r\n");
                for val.array |item| {
                    self.encode(item) catch |e| { return e; };
                }
            },
            // ... 其余类型
            _ => error.UnsupportedType,
        }
    }
}
```

### 5.3 连接状态机

```uya
// src/network/connection.uya

/// 客户端连接状态
export enum ConnState {
    CONNECTING,
    AUTH_REQUIRED,                              // 需要密码
    ACTIVE,                                     // 正常处理命令
    SUBSCRIBED,                                 // 处于 Pub/Sub 模式
    MULTI,                                      // 事务中
    BLOCKED,                                    // 阻塞等待 (BLPOP 等)
    CLOSING,
}

/// 连接对象
export struct Connection {
    fd: i32,
    stream: TcpStream,
    state: ConnState,
    
    // 读写缓冲区
    read_buf: &[u8],                            // 使用 uya 切片或 malloc
    write_buf: &[u8],
    
    // 解析状态
    parser: RespParser,
    
    // 命令队列 (MULTI 事务使用)
    cmd_queue: LinkedList<Command>,
    
    // 订阅状态
    subscriptions: HashMap<Sds, void>,
    
    // 阻塞状态
    blocking_for: ?Sds,                         // 当前阻塞等待的键
    blocking_timeout: i64,                      // 阻塞超时 (毫秒)
    
    // 统计
    last_interaction: i64,                      // 最后交互时间 (毫秒)
    dbid: i32,                                  // 当前选中的数据库
    
    // 输出缓冲限制
    output_buf_size: usize,
}

/// 命令结构体
export struct Command {
    argc: i32,
    argv: &[Sds],                               // 命令名 + 参数
    cmd_type: CommandType,                      // 解析后的命令类型
}

/// 连接生命周期
export interface IConnection {
    fn on_readable(self: &Self) !void;          // 有数据可读
    fn on_writable(self: &Self) !void;          // 可写 (处理输出缓冲)
    fn process_command(self: &Self) !void;      // 处理单条命令
    fn reply(self: &Self, val: RespValue) !void; // 发送响应
    fn close(self: &Self) void;
}
```

---

## 6. 持久化子系统

### 6.1 RDB 持久化

```uya
// src/persistence/rdb.uya

/// RDB 版本常量 (兼容 Redis 11)
const RDB_VERSION: i32 = 11;
const RDB_MAGIC: &[u8: 5] = "REDIS";

/// RDB 操作码
enum RdbOpcode {
    AUX = 0xFA,                                 // 辅助字段
    RESIZEDB = 0xFB,                            // 哈希表大小提示
    EXPIRETIME_MS = 0xFC,                       // 过期时间 (毫秒)
    EXPIRETIME = 0xFD,                          // 过期时间 (秒，旧版)
    SELECTDB = 0xFE,                            // 切换数据库
    EOF = 0xFF,                                 // 文件结束
}

/// RDB 编码/长度前缀类型
enum RdbLenType {
    U6 = 0,                                     // 00xxxxxx: 6 位无符号
    U14 = 1,                                    // 01xxxxxx xxxxxxxx: 14 位无符号
    U32 = 2,                                    // 10______ + 4 字节大端
    ENC = 3,                                    // 11xxxxxx: 特殊编码
}

/// RDB 序列化器
export struct RdbSerializer {
    writer: &std.io.Writer,
    checksum: u64,                             // CRC64 累加
    
    fn write_header(self: &Self) !void {
        self.writer.write(RDB_MAGIC);
        self.writer.write_int(RDB_VERSION);
    }
    
    fn write_aux(self: &Self, key: Sds, val: Sds) !void {
        self.writer.write_byte(RdbOpcode.AUX as u8);
        self.write_string(key);
        self.write_string(val);
    }
    
    fn write_db_header(self: &Self, dbid: i32, key_count: usize, expire_count: usize) !void {
        self.writer.write_byte(RdbOpcode.SELECTDB as u8);
        self.write_len(dbid as usize);
        self.writer.write_byte(RdbOpcode.RESIZEDB as u8);
        self.write_len(key_count);
        self.write_len(expire_count);
    }
    
    fn write_string_object(self: &Self, obj: &RedisObject) !void {
        // 根据编码选择序列化方式
        match obj.string.encoding {
            Encoding.INT => {
                // 整数编码：使用 LEN_ENC + 8/16/32 位整数
                self.write_int_encoded(obj.string.ptr.int_val);
            },
            Encoding.EMBSTR | Encoding.RAW => {
                self.write_string(obj.string.ptr.raw);
            },
            _ => error.UnsupportedEncoding,
        }
    }
    
    fn write_eof(self: &Self) !void {
        self.writer.write_byte(RdbOpcode.EOF as u8);
        // 写入 CRC64 (大端)
        if self.checksum_enabled {
            self.writer.write_u64_be(self.checksum);
        }
    }
}

/// RDB 加载器
export struct RdbLoader {
    reader: &std.io.Reader,
    checksum: u64,
    
    fn load(self: &Self, db: &RedisDb) !void {
        // 1. 校验 MAGIC
        const magic: [u8: 5] = self.reader.read_exact(5) catch |e| { return error.InvalidRdb; };
        if magic != RDB_MAGIC { return error.InvalidRdb; }
        
        // 2. 校验版本
        const version: i32 = self.reader.read_int_be(4) catch |e| { return error.InvalidRdb; };
        if version > RDB_VERSION { log.warn("RDB version newer than expected"); }
        
        // 3. 循环读取直到 EOF
        loop {
            const type: u8 = self.reader.read_byte() catch |e| { return e; };
            match type {
                RdbOpcode.EOF => break,
                RdbOpcode.SELECTDB => {
                    const dbid: i32 = self.read_len() as i32;
                    // 切换当前数据库继续加载
                },
                RdbOpcode.EXPIRETIME_MS => {
                    const expire: i64 = self.reader.read_i64_be() catch |e| { return e; };
                    // 下一条必须是键值对，设置过期时间
                },
                RdbOpcode.RESIZEDB => {
                    const db_size: usize = self.read_len();
                    const expire_size: usize = self.read_len();
                    // 可预分配字典容量
                },
                RdbOpcode.AUX => {
                    const key: Sds = self.read_string() catch |e| { return e; };
                    const val: Sds = self.read_string() catch |e| { return e; };
                    // 保存到 server 元数据
                },
                // 数据类型编码 0-5
                0..5 => {
                    const key: Sds = self.read_string() catch |e| { return e; };
                    const val: RedisObject = self.read_object(type) catch |e| { return e; };
                    db.dict.insert(key, DictEntry{ value: val, expires_at: -1, lru: 0 }) catch |e| { return e; };
                },
                _ => error.UnknownTypeCode,
            }
        }
    }
}
```

### 6.2 AOF 持久化

```uya
// src/persistence/aof.uya

/// AOF 状态
export struct AofState {
    fd: i32,                                    // AOF 文件描述符
    buf: &[u8],                                 // 累积缓冲区 (1MB 刷盘)
    current_size: u64,
    last_rewrite_size: u64,                     // 上次重写后大小
    rewrite_scheduled: bool,                    // 是否有待执行的重写
    
    // 重写期间需要同时写入旧文件和新文件
    rewrite_buf: &[u8],                         // 重写期间的增量命令
    child_pid: i32,                             // BGREWRITEAOF 子进程 (0=无)
}

export interface IAof {
    /// 将命令追加到 AOF 缓冲区
    fn append_command(self: &Self, cmd: &Command) !void;
    
    /// 强制刷盘 (根据 appendfsync 策略)
    fn flush(self: &Self) !void;
    
    /// 启动后台重写
    fn rewrite_start(self: &Self) !void;
    
    /// 完成重写，原子替换旧文件
    fn rewrite_done(self: &Self) !void;
    
    /// 加载 AOF 恢复数据
    fn load(self: &Self, db: &Engine) !void;
}

AofState : IAof {
    fn append_command(self: &Self, cmd: &Command) !void {
        // 1. 将命令转换为 RESP 数组并写入缓冲区
        const encoded: &[u8] = cmd.to_resp() catch |e| { return e; };
        
        // 2. 写入主缓冲区
        self.buf_append(encoded) catch |e| { return e; };
        
        // 3. 如果正在进行重写，同时写入 rewrite_buf
        if self.child_pid != 0 {
            self.rewrite_buf_append(encoded) catch |e| { return e; };
        }
        
        // 4. 检查是否需要自动重写
        self.check_auto_rewrite();
    }
    
    fn flush(self: &Self) !void {
        // 根据 appendfsync 策略执行
        // ALWAYS:  每次命令后 fsync
        // EVERYSEC: 每秒 fsync (后台线程)
        // NO:       依赖操作系统刷盘
        if self.buf.len > 0 {
            write(self.fd, self.buf.ptr, self.buf.len) catch |e| { return e; };
            if self.aof_config.appendfsync == AofFsyncMode.ALWAYS {
                fsync(self.fd) catch |e| { return e; };
            }
            self.buf.clear();
        }
    }
}
```

### 6.3 后台保存 (BGSAVE / BGREWRITEAOF)

由于 uya 目前不支持直接 fork()（COW 语义），采用以下策略：

1. **C 层 fork 封装**: 通过 `extern` 调用 libc fork，在子进程中执行只读遍历和写入
2. **写时复制安全**: 父进程继续服务，子进程拥有独立的内存快照视图（依赖 OS COW）
3. **增量同步**: 重写期间父进程将增量命令写入 `rewrite_buf`，完成后追加到新文件末尾

```uya
// src/persistence/rewrite.uya

use libc.unistd;

/// 后台保存控制器
export struct BackgroundSave {
    server: &RedisServer,
    
    fn bgsave(self: &Self) !pid_t {
        const pid: pid_t = fork() catch |e| {
            return error.ForkFailed;
        };
        
        if pid == 0 {
            // 子进程：关闭监听套接字，只保留 RDB 写入
            self.server.listener.close();
            
            // 打开临时 RDB 文件
            const tmpfile: &[u8: 256] = "temp-{}.rdb"; // 带 PID
            const rdb: RdbSerializer = RdbSerializer{ writer: file_writer(tmpfile), checksum: 0 };
            
            // 遍历所有数据库写入
            for self.server.dbs |db| {
                rdb.write_db_header(db.id, db.dict.size(), db.expires.size()) catch |e| {
                    _exit(1);
                };
                // ... 遍历 dict 写入键值对
            }
            
            rdb.write_eof() catch |e| { _exit(1); };
            _exit(0);  // 子进程退出
        } else {
            // 父进程：记录子进程 PID，继续服务
            self.server.rdb_child_pid = pid;
            return pid;
        }
    }
}
```

---

## 7. 并发与异步模型

### 7.1 总体并发架构

采用 **单线程事件循环 + 线程池辅助** 的经典 Redis 模型，结合 uya 的 `async` 能力实现非阻塞 IO。

```
┌─────────────────────────────────────────┐
│           Main Event Loop Thread        │
│  ┌─────────────────────────────────────┐ │
│  │   std.async Runtime (epoll-based)  │ │
│  │                                    │ │
│  │  ┌────────┐  ┌────────┐ ┌────────┐│ │
│  │  │ Timer  │  │ accept │ │  read  ││ │
│  │  │ Queue  │  │ future │ │ future ││ │
│  │  └───┬────┘  └───┬────┘ └───┬────┘│ │
│  │      └───────────┴─────────┘      │ │
│  │              Event Loop            │ │
│  │         (epoll_wait / select)      │ │
│  └─────────────────────────────────────┘ │
│                    │                     │
│                    ▼                     │
│  ┌─────────────────────────────────────┐ │
│  │      Command Processor              │ │
│  │  (单线程：无锁，零数据竞争)          │ │
│  │                                    │ │
│  │  所有命令在主线程串行执行           │ │
│  │  → 天然保证原子性                   │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐     ┌───────────────────┐
│  IO Thread    │     │  IO Thread        │
│  (AOF fsync)  │     │  (RDB 加载辅助)   │
└───────────────┘     └───────────────────┘
```

### 7.2 异步任务定义

```uya
// src/async_rt/runtime.uya
use std.async.Future;
use std.async.Waker;
use std.async.Poll;
use std.async.Task;
use std.async_scheduler;
use std.async_event;

/// Redis 运行时封装
export struct Runtime {
    scheduler: Scheduler,                        // 任务调度器
    epoll_fd: i32,                              // epoll 实例 (Linux)
    timer_heap: MinHeap<TimerEvent>,             // 最小堆定时器
    
    fn run(self: &Self, server: &RedisServer) !void {
        // 注册 listener 到 epoll
        self.register_accept(server);
        
        // 注册 cron 定时器 (100ms)
        self.timer_heap.push(TimerEvent{
            deadline: now_ms() + 100,
            callback: server.cron,
            periodic: true,
            interval: 100,
        });
        
        // 注册 AOF fsync 定时器 (若策略为 everysec)
        if server.aof_config.appendfsync == AofFsyncMode.EVERYSEC {
            self.timer_heap.push(TimerEvent{
                deadline: now_ms() + 1000,
                callback: server.aof_flush,
                periodic: true,
                interval: 1000,
            });
        }
        
        loop {
            // 1. 计算最近超时时间
            const timeout_ms: i32 = self.timer_heap.next_timeout();
            
            // 2. 等待 IO 事件或超时
            const nready: i32 = epoll_wait(self.epoll_fd, events, maxevents, timeout_ms);
            
            // 3. 处理到期的定时器
            self.process_timers();
            
            // 4. 处理 IO 事件
            for 0..nready |i| {
                const ev: &epoll_event = &events[i];
                const fd: i32 = ev.data.fd;
                const conn: &Connection = server.connections.lookup(fd);
                
                if ev.events & EPOLLIN {
                    // 读事件：解析命令并投递到主队列
                    conn.on_readable() catch |e| {
                        conn.close();
                        continue;
                    };
                }
                if ev.events & EPOLLOUT {
                    // 写事件：刷出输出缓冲
                    conn.on_writable() catch |e| {
                        conn.close();
                    };
                }
                if ev.events & (EPOLLERR | EPOLLHUP) {
                    conn.close();
                }
            }
            
            // 5. 处理就绪的命令队列
            self.process_ready_commands(server);
            
            if !server.running && server.connections.is_empty() {
                break;
            }
        }
    }
}
```

### 7.3 原子并发安全

对于需要多线程共享的统计计数器、全局配置等，使用 uya 的 `atomic T` 特性：

```uya
// 全局统计 (多线程安全，零运行时锁)
struct GlobalCounters {
    total_commands: atomic u64,
    total_connections: atomic u64,
    expired_keys: atomic u64,
    evicted_keys: atomic u64,
    keyspace_hits: atomic u64,
    keyspace_misses: atomic u64,
}

fn record_command_processed(counters: &GlobalCounters) void {
    counters.total_commands += 1;  // 编译为 lock xadd
}
```

---

## 8. 内存管理策略

### 8.1 分配器分层

```
┌─────────────────────────────────────────┐
│           Application Layer             │
│         (RedisObject / Sds)             │
├─────────────────────────────────────────┤
│           Slab Allocator                │
│   (固定大小对象：16B/32B/64B/.../1KB)  │
├─────────────────────────────────────────┤
│           jemalloc / mimalloc            │
│   (大对象、Slab 耗尽时的回退)            │
├─────────────────────────────────────────┤
│              OS mmap                     │
│   (超大对象、AOF 映射文件)               │
└─────────────────────────────────────────┘
```

```uya
// src/memory/allocator.uya

use std.mem.allocator.IAllocator;
use std.mem.allocator.HeapAllocator;

/// Redis 专用分配器
export struct RedisAllocator : IAllocator {
    small_slab: SlabAllocator,                  // <= 1KB 对象
    medium_pool: PoolAllocator,                 // 1KB - 64KB
    large_alloc: &HeapAllocator,                // > 64KB (回退到系统)
    
    fn alloc(self: &Self, size: usize) !&byte {
        if size <= 1024 {
            return self.small_slab.alloc(size);
        } else if size <= 65536 {
            return self.medium_pool.alloc(size);
        } else {
            return self.large_alloc.alloc(size);
        }
    }
    
    fn free(self: &Self, ptr: &byte, size: usize) void {
        if size <= 1024 {
            self.small_slab.free(ptr);
        } else if size <= 65536 {
            self.medium_pool.free(ptr);
        } else {
            self.large_alloc.free(ptr);
        }
    }
}
```

### 8.2 过期键管理 (Active + Lazy Expire)

```uya
// src/storage/expire.uya

/// 惰性删除：访问键时检查是否过期
export fn expire_if_needed(db: &RedisDb, key: &Sds) bool {
    const expire_time: ?i64 = db.expires.lookup(key);
    if expire_time == null {
        return false;  // 永不过期
    }
    
    if now_ms() < expire_time {
        return false;  // 未过期
    }
    
    // 已过期：从 dict 和 expires 中删除
    db.dict.delete(key);
    db.expires.delete(key);
    server.stat.expired_keys += 1;
    return true;
}

/// 主动过期：定时采样删除
export fn active_expire_cycle(db: &RedisDb, timelimit_ms: i32) void {
    const start: i64 = now_ms();
    var deleted: i32 = 0;
    
    // 每次最多扫描 20 个键，删除比例超过 25% 则继续
    loop {
        if now_ms() - start >= timelimit_ms { break; }
        
        var expired_in_sample: i32 = 0;
        for 0..20 |_| {
            const key: ?&Sds = db.dict.random_key();
            if key == null { break; }
            
            if db.expires.lookup(key) != null && db.expires.lookup(key) <= now_ms() {
                db.dict.delete(key);
                db.expires.delete(key);
                expired_in_sample += 1;
                deleted += 1;
            }
        }
        
        // 若过期率 < 25%，认为当前 DB "干净"，停止
        if expired_in_sample < 5 { break; }
    }
}
```

### 8.3 内存淘汰策略

```uya
// src/memory/eviction.uya

export enum EvictionPolicy {
    NOEVICTION,                                 // 不淘汰，写操作返回错误
    ALLKEYS_LRU,                                // 所有键 LRU
    ALLKEYS_LFU,                                // 所有键 LFU
    VOLATILE_LRU,                               // 仅设置过期时间的键 LRU
    VOLATILE_LFU,                               // 仅设置过期时间的键 LFU
    VOLATILE_TTL,                               // 仅设置过期时间的键，优先快过期的
    ALLKEYS_RANDOM,                             // 所有键随机淘汰
    VOLATILE_RANDOM,                            // 过期的键随机淘汰
}

/// 执行内存淘汰
export fn perform_eviction(server: &RedisServer) void {
    if server.memory_used() <= server.maxmemory {
        return;
    }
    
    var freed: usize = 0;
    const target: usize = server.memory_used() - server.maxmemory;
    
    loop {
        if server.memory_used() <= server.maxmemory { break; }
        
        const key: Sds = select_eviction_key(server) catch |e| {
            // 无候选键可淘汰
            if server.eviction == EvictionPolicy.NOEVICTION {
                // 返回写操作错误给客户端
                return;
            }
            break;
        };
        
        // 删除键
        const dbid: i32 = select_db_for_key(key);  // 简化：遍历所有 DB
        server.dbs[dbid].dict.delete(key);
        server.dbs[dbid].expires.delete(key);
        freed += estimate_key_size(key);
        server.stat.evicted_keys += 1;
    }
}

/// 根据策略选择淘汰键
fn select_eviction_key(server: &RedisServer) !Sds {
    match server.eviction {
        EvictionPolicy.ALLKEYS_LRU => {
            // 随机采样 5 个，选 LRU 最老的
            return lru_sample(server, 5, false);
        },
        EvictionPolicy.ALLKEYS_LFU => {
            return lfu_sample(server, 5, false);
        },
        EvictionPolicy.VOLATILE_LRU => {
            return lru_sample(server, 5, true);
        },
        EvictionPolicy.VOLATILE_LFU => {
            return lfu_sample(server, 5, true);
        },
        EvictionPolicy.ALLKEYS_RANDOM => {
            return random_key_any_db(server);
        },
        EvictionPolicy.VOLATILE_RANDOM => {
            return random_key_with_expire(server);
        },
        EvictionPolicy.VOLATILE_TTL => {
            return shortest_ttl_sample(server, 5);
        },
        EvictionPolicy.NOEVICTION => {
            return error.NoEvictionTarget;
        },
    }
}
```

---

## 9. 命令处理流水线

### 9.1 命令路由表

```uya
// src/command/router.uya
use std.collections.HashMap;

/// 命令处理函数类型
export type CommandHandler = fn (server: &RedisServer, client: &Connection, cmd: &Command) RespValue;

/// 命令元数据
export struct CommandInfo {
    name: Sds,
    handler: CommandHandler,
    arity: i32,                                 // 参数数量，负数为 "至少"
    sflags: Sds,                               // 字符串标记 "wm" "r" 等
    flags: u64,                                // 解析后的位标记
    first_key: i32,                            // 第一个 key 参数位置
    last_key: i32,
    key_step: i32,
    microseconds: atomic u64,                  // 累计执行时间 (微秒)
    calls: atomic u64,                         // 累计调用次数
}

/// 命令路由器
export struct CommandRouter {
    table: HashMap<Sds, CommandInfo>,          // 命令名 -> 元数据
    
    fn init_default_commands(self: &Self) void {
        // String
        self.register("GET", handle_get, 2, "r", 1, 1, 1);
        self.register("SET", handle_set, -3, "wm", 1, 1, 1);
        self.register("DEL", handle_del, -2, "w", 1, -1, 1);
        self.register("INCR", handle_incr, 2, "wm", 1, 1, 1);
        self.register("DECR", handle_decr, 2, "wm", 1, 1, 1);
        self.register("APPEND", handle_append, 3, "wm", 1, 1, 1);
        self.register("STRLEN", handle_strlen, 2, "r", 1, 1, 1);
        
        // Hash
        self.register("HGET", handle_hget, 3, "r", 1, 1, 1);
        self.register("HSET", handle_hset, -4, "wm", 1, 1, 1);
        self.register("HDEL", handle_hdel, -3, "w", 1, 1, 1);
        self.register("HGETALL", handle_hgetall, 2, "r", 1, 1, 1);
        
        // List
        self.register("LPUSH", handle_lpush, -3, "wm", 1, 1, 1);
        self.register("RPUSH", handle_rpush, -3, "wm", 1, 1, 1);
        self.register("LPOP", handle_lpop, 2, "w", 1, 1, 1);
        self.register("RPOP", handle_rpop, 2, "w", 1, 1, 1);
        self.register("LRANGE", handle_lrange, 4, "r", 1, 1, 1);
        self.register("BLPOP", handle_blpop, -3, "ws", 1, -2, 1);  // 阻塞
        
        // Set
        self.register("SADD", handle_sadd, -3, "wm", 1, 1, 1);
        self.register("SREM", handle_srem, -3, "w", 1, 1, 1);
        self.register("SMEMBERS", handle_smembers, 2, "r", 1, 1, 1);
        self.register("SISMEMBER", handle_sismember, 3, "r", 1, 1, 1);
        
        // ZSet
        self.register("ZADD", handle_zadd, -4, "wm", 1, 1, 1);
        self.register("ZREM", handle_zrem, -3, "w", 1, 1, 1);
        self.register("ZRANGE", handle_zrange, -4, "r", 1, 1, 1);
        self.register("ZREVRANGE", handle_zrevrange, -4, "r", 1, 1, 1);
        self.register("ZRANK", handle_zrank, 3, "r", 1, 1, 1);
        
        // Key
        self.register("EXPIRE", handle_expire, 3, "w", 1, 1, 1);
        self.register("TTL", handle_ttl, 2, "r", 1, 1, 1);
        self.register("PTTL", handle_pttl, 2, "r", 1, 1, 1);
        self.register("EXISTS", handle_exists, -2, "r", 1, -1, 1);
        self.register("KEYS", handle_keys, 2, "r", 1, 1, 1);
        self.register("SCAN", handle_scan, -2, "r", 1, 1, 1);
        self.register("TYPE", handle_type, 2, "r", 1, 1, 1);
        self.register("DBSIZE", handle_dbsize, 1, "r", 0, 0, 0);
        self.register("FLUSHDB", handle_flushdb, 1, "w", 0, 0, 0);
        self.register("FLUSHALL", handle_flushall, 1, "w", 0, 0, 0);
        
        // Server
        self.register("PING", handle_ping, -1, "rt", 0, 0, 0);
        self.register("INFO", handle_info, -1, "rt", 0, 0, 0);
        self.register("CONFIG", handle_config, -2, "rt", 0, 0, 0);
        self.register("CLIENT", handle_client, -2, "rs", 0, 0, 0);
        self.register("SHUTDOWN", handle_shutdown, -1, "rlt", 0, 0, 0);
        self.register("SAVE", handle_save, 1, "rs", 0, 0, 0);
        self.register("BGSAVE", handle_bgsave, 1, "rs", 0, 0, 0);
        self.register("LASTSAVE", handle_lastsave, 1, "r", 0, 0, 0);
        
        // Transaction
        self.register("MULTI", handle_multi, 1, "rs", 0, 0, 0);
        self.register("EXEC", handle_exec, 1, "rs", 0, 0, 0);
        self.register("DISCARD", handle_discard, 1, "rs", 0, 0, 0);
        self.register("WATCH", handle_watch, -2, "rs", 1, -1, 1);
        self.register("UNWATCH", handle_unwatch, 1, "rs", 0, 0, 0);
        
        // Pub/Sub (预留)
        self.register("PUBLISH", handle_publish, 3, "pm", 0, 0, 0);
        self.register("SUBSCRIBE", handle_subscribe, -2, "ps", 0, 0, 0);
        self.register("UNSUBSCRIBE", handle_unsubscribe, -1, "ps", 0, 0, 0);
    }
}
```

### 9.2 命令执行示例 (GET/SET)

```uya
// src/command/string.uya

/// GET key
export fn handle_get(server: &RedisServer, client: &Connection, cmd: &Command) RespValue {
    if cmd.argc != 2 {
        return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR wrong number of arguments for 'get' command") };
    }
    
    const key: Sds = cmd.argv[1];
    const db: &RedisDb = server.dbs[client.dbid];
    
    // 惰性过期检查
    if db.expire_if_needed(key) {
        return RespValue{ tag: RespType.NULL, null_val: {} };
    }
    
    const obj: ?&RedisObject = db.dict.lookup(key);
    if obj == null {
        return RespValue{ tag: RespType.NULL, null_val: {} };
    }
    
    const val: &RedisObject = obj;
    if val.tag != ObjectType.STRING {
        return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("WRONGTYPE Operation against a key holding the wrong kind of value") };
    }
    
    // 更新 LRU
    update_lru(val);
    
    // 返回
    match val.string.encoding {
        Encoding.INT => {
            return RespValue{ tag: RespType.INTEGER, integer: val.string.ptr.int_val };
        },
        Encoding.EMBSTR | Encoding.RAW => {
            return RespValue{ tag: RespType.BULK_STRING, bulk_string: val.string.ptr.raw };
        },
        _ => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR unknown encoding") };
        },
    }
}

/// SET key value [NX] [XX] [EX seconds|PX milliseconds|KEEPTTL]
export fn handle_set(server: &RedisServer, client: &Connection, cmd: &Command) RespValue {
    if cmd.argc < 3 {
        return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR wrong number of arguments for 'set' command") };
    }
    
    const key: Sds = cmd.argv[1];
    const val_str: Sds = cmd.argv[2];
    var nx: bool = false;
    var xx: bool = false;
    var expire_ms: i64 = -1;
    var keep_ttl: bool = false;
    
    // 解析选项
    var i: i32 = 3;
    while i < cmd.argc {
        const opt: Sds = cmd.argv[i];
        if sds_cmp(opt, "NX") == 0 { nx = true; }
        else if sds_cmp(opt, "XX") == 0 { xx = true; }
        else if sds_cmp(opt, "KEEPTTL") == 0 { keep_ttl = true; }
        else if sds_cmp(opt, "EX") == 0 && i + 1 < cmd.argc {
            const seconds: i64 = parse_int(cmd.argv[i + 1]) catch |e| {
                return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR value is not an integer or out of range") };
            };
            expire_ms = now_ms() + seconds * 1000;
            i += 1;
        }
        else if sds_cmp(opt, "PX") == 0 && i + 1 < cmd.argc {
            const ms: i64 = parse_int(cmd.argv[i + 1]) catch |e| {
                return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR value is not an integer or out of range") };
            };
            expire_ms = now_ms() + ms;
            i += 1;
        }
        i += 1;
    }
    
    const db: &RedisDb = server.dbs[client.dbid];
    const existing: ?&RedisObject = db.dict.lookup(key);
    
    // NX/XX 条件检查
    if nx && existing != null {
        return RespValue{ tag: RespType.NULL, null_val: {} };  // 已存在，不设置
    }
    if xx && existing == null {
        return RespValue{ tag: RespType.NULL, null_val: {} };  // 不存在，不设置
    }
    
    // 保留原有 TTL
    var final_expire: i64 = expire_ms;
    if keep_ttl && existing != null {
        final_expire = db.expires.lookup(key) catch { -1 };
    }
    
    // 创建 String 对象
    var new_obj: RedisObject;
    if try_parse_int(val_str) |int_val| {
        new_obj = create_int_object(int_val);
    } else {
        new_obj = create_string_object(val_str);
    }
    
    // 写入
    db.dict.insert(key, DictEntry{ value: new_obj, expires_at: final_expire, lru: lru_clock() }) catch |e| {
        return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR OOM") };
    };
    if final_expire > 0 {
        db.expires.insert(key, final_expire) catch |e| {};
    }
    
    // AOF 追加
    if server.aof_state != null {
        server.aof_state.append_command(cmd) catch |e| {};
    }
    
    return RespValue{ tag: RespType.SIMPLE_STRING, simple_string: sds_new("OK") };
}
```

---

## 10. 错误处理与监控

### 10.1 统一错误体系

```uya
// src/util/error.uya

/// Redis 内部错误类型
export enum RedisError {
    // 协议错误
    ProtocolIncomplete,
    ProtocolInvalid,
    UnknownCommand,
    WrongArity,
    
    // 存储错误
    OOM,                                        // Out of Memory
    KeyNotFound,
    WrongType,
    
    // 持久化错误
    RdbCorrupted,
    RdbVersionMismatch,
    AofTruncated,
    
    // 网络错误
    ConnectionClosed,
    ConnectionTimeout,
    WriteError,
    
    // 系统错误
    ForkFailed,
    FileOpenFailed,
    FileWriteFailed,
    
    // 配置错误
    InvalidConfig,
    UnsupportedOption,
}

/// 将内部错误映射到 RESP 错误回复
export fn redis_error_to_resp(err: RedisError) RespValue {
    match err {
        RedisError.UnknownCommand => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR unknown command") };
        },
        RedisError.WrongArity => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR wrong number of arguments") };
        },
        RedisError.OOM => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("OOM command not allowed when used memory > 'maxmemory'") };
        },
        RedisError.WrongType => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("WRONGTYPE Operation against a key holding the wrong kind of value") };
        },
        RedisError.KeyNotFound => {
            return RespValue{ tag: RespType.NULL, null_val: {} };
        },
        // ... 其余映射
        _ => {
            return RespValue{ tag: RespType.SIMPLE_ERROR, simple_error: sds_new("ERR internal error") };
        },
    }
}
```

### 10.2 INFO 命令输出

```uya
// src/command/server.uya

/// 生成 INFO 回复
export fn generate_info(server: &RedisServer, section: ?Sds) Sds {
    var buf: Sds = sds_empty();
    
    // Server 段
    sds_cat(buf, "# Server\r\n");
    sds_cat_fmt(buf, "redis_version:0.1.0-uya\r\n");
    sds_cat_fmt(buf, "redis_mode:standalone\r\n");
    sds_cat_fmt(buf, "os:Linux\r\n");
    sds_cat_fmt(buf, "arch_bits:64\r\n");
    sds_cat_fmt(buf, "multiplexing_api:epoll\r\n");
    sds_cat_fmt(buf, "gcc_version:0.0.0\r\n");  // uya 后端编译器
    sds_cat_fmt(buf, "process_id:{}\r\n", getpid());
    sds_cat_fmt(buf, "tcp_port:{}\r\n", server.port);
    sds_cat_fmt(buf, "server_time_usec:{}\r\n", now_us());
    sds_cat_fmt(buf, "uptime_in_seconds:{}\r\n", now_s() - server.stat.start_time);
    sds_cat_fmt(buf, "uptime_in_days:{}\r\n", (now_s() - server.stat.start_time) / 86400);
    
    // Clients 段
    sds_cat(buf, "# Clients\r\n");
    sds_cat_fmt(buf, "connected_clients:{}\r\n", server.connections.size());
    sds_cat_fmt(buf, "blocked_clients:{}\r\n", server.blocked_clients_count());
    
    // Memory 段
    sds_cat(buf, "# Memory\r\n");
    sds_cat_fmt(buf, "used_memory:{}\r\n", server.memory_used());
    sds_cat_fmt(buf, "used_memory_human:{}\r\n", format_bytes(server.memory_used()));
    sds_cat_fmt(buf, "used_memory_rss:{}\r\n", get_rss());
    sds_cat_fmt(buf, "used_memory_peak:{}\r\n", server.memory_peak());
    sds_cat_fmt(buf, "maxmemory:{}\r\n", server.maxmemory);
    sds_cat_fmt(buf, "maxmemory_policy:{}\r\n", server.eviction.to_string());
    
    // Stats 段
    sds_cat(buf, "# Stats\r\n");
    sds_cat_fmt(buf, "total_connections_received:{}\r\n", server.stat.total_connections);
    sds_cat_fmt(buf, "total_commands_processed:{}\r\n", server.stat.total_commands);
    sds_cat_fmt(buf, "expired_keys:{}\r\n", server.stat.expired_keys);
    sds_cat_fmt(buf, "evicted_keys:{}\r\n", server.stat.evicted_keys);
    sds_cat_fmt(buf, "keyspace_hits:{}\r\n", server.stat.keyspace_hits);
    sds_cat_fmt(buf, "keyspace_misses:{}\r\n", server.stat.keyspace_misses);
    
    // Replication 段
    sds_cat(buf, "# Replication\r\n");
    sds_cat_fmt(buf, "role:{}\r\n", if server.role == ReplicationRole.MASTER { "master" } else { "slave" });
    
    // Keyspace 段
    sds_cat(buf, "# Keyspace\r\n");
    for 0..server.dbnum |i| {
        const db: &RedisDb = server.dbs[i];
        if db.dict.size() > 0 {
            sds_cat_fmt(buf, "db{}:keys={},expires={},avg_ttl={}\r\n", 
                i, db.dict.size(), db.expires.size(), db.avg_ttl());
        }
    }
    
    return buf;
}
```

---

## 11. 模块接口定义

### 11.1 公共接口清单

| 模块 | 文件 | 导出接口 | 依赖 |
|------|------|----------|------|
| Server | `server.uya` | `RedisServer`, `IServer` | 所有子模块 |
| Config | `config.uya` | `ServerConfig`, `parse_config_file()` | std.io |
| Protocol | `network/protocol.uya` | `RespValue`, `RespParser`, `RespEncoder` | std.io, sds |
| Connection | `network/connection.uya` | `Connection`, `ConnState`, `Command` | protocol |
| Dict | `storage/dict.uya` | `Dict`, `DictEntry`, `IDict` | std.collections |
| SDS | `storage/sds.uya` | `Sds`, `SdsHdr`, `sds_new*()`, `sds_cat()` | libc |
| Object | `storage/object.uya` | `RedisObject`, `ObjectType`, `Encoding`, `create_*_object()` | sds, collections |
| Engine | `storage/engine.uya` | `RedisDb`, `Engine`, `IEngine` | dict, object |
| Command Router | `command/router.uya` | `CommandRouter`, `CommandInfo`, `CommandHandler` | collections |
| String Cmds | `command/string.uya` | `handle_get`, `handle_set`, ... | engine |
| Hash Cmds | `command/hash.uya` | `handle_hget`, `handle_hset`, ... | engine |
| List Cmds | `command/list.uya` | `handle_lpush`, `handle_lpop`, ... | engine |
| Set Cmds | `command/set.uya` | `handle_sadd`, `handle_srem`, ... | engine |
| ZSet Cmds | `command/zset.uya` | `handle_zadd`, `handle_zrange`, ... | engine |
| Key Cmds | `command/key.uya` | `handle_del`, `handle_expire`, ... | engine |
| Server Cmds | `command/server.uya` | `handle_ping`, `handle_info`, ... | server |
| Transaction | `command/transaction.uya` | `handle_multi`, `handle_exec`, ... | connection |
| RDB | `persistence/rdb.uya` | `RdbSerializer`, `RdbLoader` | io, object, crc64 |
| AOF | `persistence/aof.uya` | `AofState`, `IAof` | io, protocol |
| BG Save | `persistence/rewrite.uya` | `BackgroundSave` | libc.unistd |
| Replication | `replication/*.uya` | `ReplicationRole`, `MasterState`, `SlaveState` | network, protocol |
| Allocator | `memory/allocator.uya` | `RedisAllocator`, `SlabAllocator` | std.mem |
| Eviction | `memory/eviction.uya` | `EvictionPolicy`, `perform_eviction()` | engine |
| Runtime | `async_rt/runtime.uya` | `Runtime`, `TimerEvent` | std.async, epoll |
| Log | `util/log.uya` | `log.debug`, `log.info`, `log.warn`, `log.error` | std.io |
| CRC64 | `util/crc64.uya` | `crc64_update()`, `crc64_combine()` | (纯算法) |

---

## 12. 代码规范与约定

### 12.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 结构体 | PascalCase | `RedisServer`, `DictEntry` |
| 接口 | PascalCase 前缀 I | `IServer`, `IEngine` |
| 枚举 | PascalCase | `ObjectType`, `RespType` |
| 函数 | snake_case | `handle_get`, `active_expire_cycle` |
| 变量 | snake_case | `read_buf`, `max_memory` |
| 常量 | UPPER_SNAKE | `RDB_VERSION`, `RESP_TYPE_SIMPLE_STRING` |
| 模块文件 | snake_case.uya | `protocol.uya`, `string_obj.uya` |
| 类型参数 | 单大写字母 | `K`, `V`, `T` |

### 12.2 注释规范

```uya
/// 对外导出的函数/结构体使用三斜杠文档注释
/// 支持 markdown 格式和 uya 文档生成器
/// 
/// # 参数
/// - `key`: 要查找的键
/// - `dbid`: 数据库编号
/// 
/// # 返回
/// 若键存在且未过期返回对象引用，否则返回 null
export fn lookup_key(server: &RedisServer, dbid: i32, key: Sds) ?&RedisObject;

// 内部实现使用双斜杠普通注释
// 注意：此处需先检查过期再返回值
fn internal_lookup(db: &RedisDb, key: Sds) ?&RedisObject { ... }
```

### 12.3 错误处理约定

1. **所有可恢复错误使用 `!T`**：数据库操作、网络 IO、文件操作必须返回 `!T`
2. **panic 仅用于不可恢复的内部不一致**：如内存分配器元数据损坏
3. **错误日志**：所有错误路径必须记录 `log.error` 或 `log.warn`
4. **客户端可见错误**：统一使用 `RedisError -> RESP Error` 映射，禁止直接暴露内部状态

### 12.4 内存安全约定

1. **指针算术必须编译期可证明**：`ptr + offset` 需确保在分配边界内
2. **切片访问使用 `&arr[start:len]`**：编译器自动验证范围
3. **外部指针生命周期**：C FFI 返回的指针需立即包装为 uya 引用或显式管理
4. **Drop 实现**：所有持有堆内存的结构体必须实现 `drop()`

---

## 13. 附录：uya 语言关键特性映射

### 13.1 uya 特性 -> Redis 设计收益

| uya 特性 | 在 Redis 设计中的应用 | 收益 |
|----------|---------------------|------|
| `atomic T` | 全局计数器、连接统计 | 零数据竞争，无锁，编译期保证 |
| `union (tagged)` | `RedisObject`, `RespValue` | 类型安全多态，零运行时开销 |
| `!T` 错误类型 | 所有 IO/存储操作 | 显式错误传播，无隐式 panic |
| 编译期安全证明 | 缓冲区访问、指针算术 | 消除缓冲区溢出 UB |
| 零 GC | 长期运行服务 | 无暂停，预测性延迟 |
| `extern struct` | C 兼容头 (RDB 文件格式) | 100% 二进制兼容 |
| `@vector(T,N)` | CRC64 计算、批量字符串操作 | SIMD 加速 |
| 泛型 `<T>` | `Slab<T>`、测试辅助容器 | 代码复用，类型安全 |
| `async/await` | 连接处理、定时器 | 非阻塞 IO，清晰控制流 |
| 模块系统 | 目录级模块隔离 | 清晰依赖，快速编译 |
| 切片 `&arr[s:l]` | 协议解析零拷贝 | 减少内存复制 |
| 字符串插值 | 日志、INFO 输出 | 简洁格式化 |

### 13.2 uya 与 C 互操作边界

| 场景 | uya 层 | C 层 | 说明 |
|------|--------|------|------|
| 系统调用 | `libc.syscall` | 直接封装 | epoll, socket, open |
| 内存分配 | `RedisAllocator` | jemalloc FFI | 大对象回退 |
| 进程 fork | `BackgroundSave` | `unistd.fork()` | 仅 RDB/AOF 重写 |
| CRC64 | `crc64.uya` | 可选 C 加速 | 纯 uya 实现兜底 |
| 配置文件 | `parse_config_file` | 无 | 纯 uya 字符串处理 |
| 网络解析 | `RespParser` | 无 | 纯 uya 字节流处理 |

---

## 14. 兼容性矩阵

| Redis 特性 | redis-uya 支持 | 版本目标 |
|-----------|---------------|---------|
| RESP2 | 首版子集 | v0.1.0 |
| RESP3 | 后续版本 | v0.2.0 及后续 |
| String | 首版子集：`PING/GET/SET/DEL/EXISTS` 为主 | v0.1.0 |
| Hash | 后续版本 | v0.2.0 及后续 |
| List | 后续版本 | v0.2.0 及后续 |
| Set | 后续版本 | v0.2.0 及后续 |
| ZSet | 后续版本 | v0.2.0 及后续 |
| Key | 首版子集：`DEL/EXPIRE/TTL/EXISTS/INFO` | v0.1.0 |
| Transaction | 后续版本 | v0.2.0 及后续 |
| Pub/Sub | ⚠️ PUBLISH/SUBSCRIBE (基础) | v0.2.0 |
| Persistence | ✅ RDB + AOF + BGSAVE + BGREWRITEAOF | v0.1.0 |
| Replication | ⚠️ 主从同步 (PSYNC1) | v0.2.0 |
| Sentinel | ❌ 不支持 | - |
| Cluster | ❌ 不支持 | v0.3.0 |
| Lua | ❌ 不支持 | - |
| ACL | ❌ 不支持 | - |
| Streams | ❌ 不支持 | - |
| Functions | ❌ 不支持 | - |

---

> 文档结束。本设计文档为 redis-uya 的 v0.1.0 初始版本，后续迭代将在各子模块实现后更新。
