# redis-uya SDS 内存布局

> 版本: v0.1.0-dev
> 日期: 2026-04-25
> 状态: Phase 0 实现说明

## 1. 当前实现

当前 SDS 定义在 `src/storage/sds.uya`：

```text
Sds {
    buf: &[byte],
    len: usize,
    alloc: usize,
}
```

`buf` 指向由 `redis_malloc()` 分配的连续字节区，长度为 `alloc + 1`。最后 1 字节固定保留给 `0` 结尾，便于后续与 C/Redis 风格字符串边界交互；真实字符串长度始终以 `len` 为准，因此可以安全保存内嵌 `0` 字节。

## 2. 分配布局

内存从低地址到高地址如下：

```text
redis_malloc header: usize    由 allocator 维护，用于 used_memory 统计
payload[0 .. alloc - 1]       SDS 可写数据区
payload[alloc]                额外 NUL 结尾字节
```

`Sds.buf.ptr` 指向 `payload[0]`，不指向 allocator header。释放时必须通过 `sds_free()` 调用 `redis_free(s.buf.ptr)`，不能手动偏移释放。

## 3. 字段语义

| 字段 | 语义 |
|------|------|
| `len` | 已使用字节数，不包含 NUL 结尾 |
| `alloc` | 可用数据容量，不包含 NUL 结尾 |
| `buf.len` | 当前分配切片长度，等于 `alloc + 1` |

`sds_len()` 返回 `len`，`sds_avail()` 返回 `alloc - len`。所有读写内容应使用 `s.buf[0: s.len]`，不要依赖 NUL 结尾判断长度。

## 4. 扩容策略

`sds_grow()` 保持以下规则：

- 小字符串最小容量为 16 字节。
- 需要扩容时默认翻倍。
- 如果翻倍仍不足以容纳目标长度，则直接扩到目标长度。
- 扩容后重新写入 `buf[len] = 0`。

`sds_cat()` 先确保目标容量，再复制追加内容，最后更新 `len` 和 NUL 结尾。当前 1MB 追加压力测试覆盖 1024 次 1KB 追加、扩容、内容边界和释放统计。

## 5. 格式化追加

`sds_cat_fmt()` 采用结构化参数数组而不是可变参数，避免当前 Uya/C99 边界上的 varargs 风险。Phase 0 支持最小占位符：

| 占位符 | 参数类型 |
|--------|----------|
| `%s` | `SdsFmtArgType.sds_fmt_bytes` |
| `%i` | `SdsFmtArgType.sds_fmt_i64` |
| `%u` | `SdsFmtArgType.sds_fmt_u64` |
| `%%` | 字面量 `%`，不消耗参数 |

追加前会先校验格式串和参数类型；校验失败不会修改原 SDS。

## 6. 后续演进

当前布局优先保证当前 Uya 工具链可编译、可测试和易释放。后续若要逼近 Redis SDS，可评估压缩 header、按长度分级的 header 类型和更细粒度的预分配策略。该阶段必须重新补齐内存布局测试和 allocator 统计测试。
