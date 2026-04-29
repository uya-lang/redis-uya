# Uya 测试规范

**版本**: v1.1.0
**日期**: 2026-02-15

---

## 1. 概述

本规范定义了 Uya 项目的测试编写标准，充分利用 Uya 的 `error` 类型系统。

### 1.1 核心理念

- **错误即测试失败**：测试函数返回 `!void`，失败时返回 `error`
- **自动传播**：使用 `try` 自动传播断言失败
- **资源安全**：使用 `errdefer` 确保错误时资源清理
- **统一报告**：框架自动统计并输出测试结果
- **零依赖**：测试程序完全使用 libc，不依赖 bridge.c

---

## 2. 测试框架

### 2.1 导入

```uya
// 单独导入需要的函数和宏
use std.testing.assert;
use std.testing.assert_eq_i32;
use std.testing.expect;
use std.testing.test_suite_begin;
use std.testing.test_suite_end;
use std.testing.run_test;  // 宏
```

### 2.2 核心组件

|| 组件 | 说明 |
||------|------|
|| `test_suite_begin(name)` | 开始测试套件 |
|| `run_test(name, test_fn)` | 运行单个测试 |
|| `test_suite_end()` | 结束套件，返回失败数 |
|| `skip_test(name, reason)` | 跳过测试 |

### 2.3 断言函数

#### 基本断言

```uya
// 带消息的断言
try assert(condition, "message");
try assert_eq_i32(actual, expected, "message");
try assert_eq_bool(actual, expected, "message");
try assert_ne_i32(actual, expected, "message");
try assert_gt_i32(actual, expected, "message");
try assert_lt_i32(actual, expected, "message");
try assert_ge_i32(actual, expected, "message");
try assert_le_i32(actual, expected, "message");
try assert_null(ptr, "message");
try assert_not_null(ptr, "message");
try assert_ptr_eq(actual, expected, "message");
```

#### 简写断言（无消息）

```uya
try expect(condition);
try expect_eq(actual, expected);    // i32
try expect_ne(actual, expected);    // i32
try expect_true(value);
try expect_false(value);
try expect_null(ptr);
try expect_not_null(ptr);
```

---

## 3. 测试文件结构

### 3.1 文件命名

```
tests/programs/test_<module>.uya      # 模块测试
```

### 3.2 标准模板

```uya
// test_<module>.uya - <模块描述>
// 使用 lib/std/testing.uya 测试框架
// 编译时需包含 entry.uya 入口模块

use libc.function1;
use libc.function2;
use std.testing.*;

// ============================================================
// 测试用例
// ============================================================

fn test_function1() !void {
    const result: i32 = function1(input);
    try assert_eq_i32(result, expected, "description");
}

fn test_function2_with_resource() !void {
    var resource: Resource = try create_resource();

    // 错误时清理
    errdefer {
        cleanup_on_error(resource);
    }

    // 正常结束时清理
    defer {
        cleanup(resource);
    }

    try assert_not_null(resource.data, "resource should have data");
}

// ============================================================
// 主函数（当前使用 fn main() 兼容 bridge.c）
// 未来测试脚本升级后可改为 export fn main() 配合 entry.uya
// ============================================================

fn main() i32 {
    test_suite_begin("<Module> Tests");

    run_test("function1", test_function1);
    run_test("function2 with resource", test_function2_with_resource);

    return test_suite_end();
}
```

### 3.3 入口机制

**当前状态**（兼容 bridge.c）：
```
C Runtime → bridge.c::main() → main_main()
                              └─ 用户测试代码
```

测试文件使用 `fn main()` 兼容测试脚本的 bridge.c 链接方式。

**未来规划**（使用 entry.uya）：
```
C Runtime → entry.uya::main() → main_main()
                              └─ 用户测试代码
```

|| 声明方式 | 编译结果 | 用途 |
||----------|----------|------|
|| `fn main()` | `main_main()` | 测试文件（兼容 bridge.c） |
|| `export fn main()` | `main_main()` | 应用程序入口（配合 entry.uya） |

### 3.4 编译命令

```bash
# 仅生成 C99
bin/uya build tests/programs/test_xxx.uya -o /tmp/test_xxx.c --c99

# 手动编译生成的 C（当前 bridge.c 路线）
gcc -std=c99 -no-pie /tmp/test_xxx.c tests/bridge_minimal.c -o /tmp/test_xxx -lm

# 运行测试
/tmp/test_xxx
```

如果测试依赖 `@c_import`，且你选择只输出 `.c`，则编译器还会额外写出同名 sidecar：

```bash
bin/uya build tests/test_c_import_file.uya -o /tmp/test_c_import_file.c --c99
# 额外生成：/tmp/test_c_import_file.cimports.sh
```

推荐用仓库自带脚本消费 sidecar：

```bash
CC=gcc ./tests/link_cimports_posix.sh /tmp/test_c_import_file.c /tmp/test_c_import_file
/tmp/test_c_import_file
```

说明：
- sidecar 中保存 `UYA_CIMPORT_SRC_*`、`UYA_CIMPORT_REL_*`、`UYA_CIMPORT_CFLAG_*_*` 与 `UYA_CIMPORT_LDFLAG_*`
- 脚本会先编译导入的 C object，再与主 `.c` 一起链接
- 若测试走 split-C 路径，则导入的 C object 直接进入 Makefile，不依赖 sidecar

当前更推荐直接让编译器在 `-e` 模式下调用宿主工具链完成链接：

```bash
# 原生 hosted 测试
bin/uya build tests/programs/test_xxx.uya -o /tmp/test_xxx.c --c99 -e

# 使用 zig cc 做统一工具链
TOOLCHAIN=zig ZIG=/path/to/zig \
bin/uya build tests/programs/test_xxx.uya -o /tmp/test_xxx.c --c99 -e
```

如需交叉或显式指定 C 驱动，可继续传入 `CC_DRIVER` / `CC_TARGET_FLAGS`：

```bash
CC_DRIVER="/path/to/zig cc" \
CC_TARGET_FLAGS="-target aarch64-macos-none" \
bin/uya build tests/programs/test_xxx.uya -o /tmp/test_xxx.c --c99 -e
```

---

## 4. 返回码约定

遵循 Unix 惯例：

|| 返回值 | 含义 |
||--------|------|
|| `0` | 所有测试通过 |
|| `非零` | 失败的测试数量 |

### 4.1 CI/CD 集成

```bash
# 运行测试
./test_xxx
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "All tests passed"
else
    echo "$exit_code tests failed"
    exit 1
fi
```

---

## 5. 测试编写规范

### 5.1 测试函数签名

```uya
// 正确：返回 !void
fn test_feature() !void {
    try expect(condition);
}

// 错误：旧方式返回 i32
fn test_feature() i32 {
    return 0;  // 不要这样写
}
```

### 5.2 断言使用

```uya
// 推荐：带描述消息
try assert_eq_i32(result, 5, "2 + 3 should equal 5");

// 可接受：简写形式
try expect_eq(result, 5);

// 不推荐：手动判断
if result != 5 {
    return error.TestFailed;  // 过于冗长
}
```

### 5.3 资源管理

```uya
fn test_with_file() !void {
    const file: FileHandle = try open_file("test.txt");

    // 错误时回滚
    errdefer {
        rollback(file);
    }

    // 总是关闭
    defer {
        close_file(file);
    }

    // 测试逻辑...
    try assert_not_null(file.data, "file should be open");
}
```

### 5.4 错误测试

```uya
fn test_error_case() !void {
    const result: i32 = divide(10, 0) catch |err| {
        // 验证返回了预期的错误
        try expect(@error_id(err) == @error_id(error.DivisionByZero));
        return;  // 测试通过
    };

    // 如果到这里，说明没有返回错误
    return error.TestFailed;
}
```

### 5.5 表驱动测试

```uya
struct TestCase {
    input: i32,
    expected: i32,
}

fn test_table_driven() !void {
    const cases: [TestCase: 3] = [
        TestCase{ input: 1, expected: 1 },
        TestCase{ input: 2, expected: 4 },
        TestCase{ input: 3, expected: 9 },
    ];

    var i: i32 = 0;
    while i < 3 {
        const tc: TestCase = cases[i];
        const result: i32 = square(tc.input);
        try assert_eq_i32(result, tc.expected, "square test");
        i = i + 1;
    }
}
```

---

## 6. 输出格式

### 6.1 标准输出

```
=== Test Suite: libc.string ===
  TEST: strlen ... OK
  TEST: strcmp ... OK
  TEST: strcpy ... FAILED
    ASSERT FAILED: strcpy should copy correctly
      Expected: 5
      Actual:   0
  TEST: strcat ... OK

=== Results ===
  Passed:  3
  Failed:  1
  Skipped: 0
==================
```

### 6.2 测试跳过

```
  TEST: large_file ... SKIPPED (requires > 1GB memory)
```

---

## 7. 编译与运行

### 7.1 编译命令

```bash
# 编译 Uya 测试文件（兼容 bridge.c）
bin/uya-c --c99 tests/programs/test_xxx.uya -o /tmp/test_xxx.c

# 编译 C 代码
gcc -std=c99 -no-pie /tmp/test_xxx.c tests/bridge_minimal.c -o /tmp/test_xxx -lm
```

### 7.2 运行测试

```bash
# 运行
/tmp/test_xxx

# 检查返回码
echo $?
```

---

## 8. 迁移指南

### 8.1 旧模式 vs 新模式

|| 旧模式 | 新模式 |
||--------|--------|
|| `fn test_xxx() i32` | `fn test_xxx() !void` |
|| `if x != 5 { return 1; }` | `try expect(x == 5);` |
|| `return 0;` | `return test_suite_end();` |
|| `var passed = 1; ...` | `try expect(...);` |
|| 手动计数失败 | 框架自动统计 |
|| `fn main()` | `fn main()` + test_suite_* |

### 8.2 迁移步骤

1. 添加 `use std.testing.*;`
2. 修改测试函数签名为 `!void`
3. 替换手动断言为框架断言
4. 修改 `main()` 使用 test_suite_* API
5. 删除冗余代码（passed 变量、手动输出等）

### 8.3 编译方式

```bash
# 编译测试文件（兼容 bridge.c）
bin/uya-c --c99 test.uya -o test.c
gcc -std=c99 -no-pie test.c tests/bridge_minimal.c -o test -lm
```

---

## 9. 最佳实践

### 9.1 测试命名

```uya
// 好的命名
fn test_strlen_empty_string() !void { }
fn test_strcmp_equal_strings() !void { }
fn test_malloc_zero_size() !void { }

// 不好的命名
fn test1() !void { }
fn test_strlen() !void { }  // 太笼统
```

### 9.2 测试隔离

```uya
// 每个测试应该独立
fn test_a() !void {
    // 不依赖其他测试的状态
    errno = 0;  // 重置全局状态
    try expect(errno == 0);
}

fn test_b() !void {
    errno = 0;  // 重置全局状态
    // ...
}
```

### 9.3 边界条件

```uya
fn test_boundary() !void {
    // 边界值
    try expect_eq(strlen(""), 0);      // 空字符串
    try expect_eq(strlen("a"), 1);     // 单字符
    try expect_eq(strlen("ab"), 2);    // 多字符

    // 边界条件
    try expect(abs(0) == 0);           // 零
    try expect(abs(-2147483648) >= 0); // INT_MIN
}
```

---

## 10. 附录

### 10.1 完整示例

```uya
// tests/programs/test_example.uya
// 描述：示例测试文件
// 编译：bin/uya-c --c99 test_example.uya -o test_example.c

use libc.malloc;
use libc.free;
use libc.strlen;
use std.testing.*;

// ============================================================
// 测试用例
// ============================================================

fn test_strlen_basic() !void {
    try expect_eq(strlen("hello"), 5);
    try expect_eq(strlen(""), 0);
}

fn test_malloc_free() !void {
    const ptr: *byte = malloc(100);
    try expect_not_null(ptr);

    defer {
        free(ptr);
    }

    // 使用内存...
}

fn test_error_propagation() !void {
    const ptr: *byte = malloc(0);

    // malloc(0) 可能返回 null 或有效指针
    if ptr == null as *byte {
        skip_test("malloc(0) returned null", "platform specific");
        return;
    }

    defer {
        free(ptr);
    }

    try expect_not_null(ptr);
}

// ============================================================
// 主函数（当前使用 fn main() 兼容 bridge.c）
// ============================================================

fn main() i32 {
    test_suite_begin("Example Tests");

    run_test("strlen basic", test_strlen_basic);
    run_test("malloc/free", test_malloc_free);
    run_test("error propagation", test_error_propagation);

    return test_suite_end();
}
```

### 10.2 断言函数完整列表

|| 函数 | 类型 | 说明 |
||------|------|------|
|| `assert(cond, msg)` | bool | 基本断言 |
|| `assert_eq_i32(a, e, msg)` | i32 | 相等 |
|| `assert_eq_u32(a, e, msg)` | u32 | 相等 |
|| `assert_eq_i64(a, e, msg)` | i64 | 相等 |
|| `assert_eq_u64(a, e, msg)` | u64 | 相等 |
|| `assert_eq_bool(a, e, msg)` | bool | 相等 |
|| `assert_ne_i32(a, e, msg)` | i32 | 不等 |
|| `assert_gt_i32(a, e, msg)` | i32 | 大于 |
|| `assert_lt_i32(a, e, msg)` | i32 | 小于 |
|| `assert_ge_i32(a, e, msg)` | i32 | 大于等于 |
|| `assert_le_i32(a, e, msg)` | i32 | 小于等于 |
|| `assert_null(p, msg)` | *byte | 空指针 |
|| `assert_not_null(p, msg)` | *byte | 非空指针 |
|| `assert_ptr_eq(a, e, msg)` | *byte | 指针相等 |
|| `expect(cond)` | bool | 简写断言 |
|| `expect_eq(a, e)` | i32 | 简写相等 |
|| `expect_ne(a, e)` | i32 | 简写不等 |
|| `expect_true(v)` | bool | 期望 true |
|| `expect_false(v)` | bool | 期望 false |
|| `expect_null(p)` | *byte | 简写空指针 |
|| `expect_not_null(p)` | *byte | 简写非空 |
