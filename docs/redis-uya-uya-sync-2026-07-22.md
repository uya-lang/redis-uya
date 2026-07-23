# redis-uya Uya 1.0 同步及规范回退报告（2026-07-22，2026-07-23 修订）

## 1. 同步基线

- 上游仓库：`../uya`
- 上游分支：`1.0`
- 当前同步 HEAD：`f54bd7bfe3f4fa643045c56bf631c791866db4a2`
- 远端关系：与 `origin/1.0` 一致，本地领先提交数为 0
- 编译器版本：`v0.9.9`
- 同步范围：`uya/lib`、既有 `uya/docs`、`uya/bin/uya`、`uya/bin/cmd/build`
- redis-uya 本地扩展：保留 `std.async` 单线程 allocator 快速路径及对应文档标记

同步流程不是直接复制已有二进制，而是在 `../uya` 中从源码重新构建，再复制生成物。`bin/uya` 只是命令启动器，缺少 `bin/cmd/build` 时无法执行 `uya build`，因此两者必须成套同步。

## 2. 规范复核与回退

初次同步时曾在本地 Uya `1.0` 分支产生两个提交，尝试将普通 `export const/var` 的生成 C 符号统一改为模块前缀：

- `13d7c784 fix(c99): keep exported global symbol names consistent`
- `337a0edd fix(c99): prefix split mirror global declarations`

复核 `docs/uya.md` 后确认，现行语言规范要求普通 `export const/var` 导出同名裸 C 全局符号。上述提交虽然解决了内部符号不一致，却改变了既有 C ABI，且未同步升级语言规范，因此不能保留。

这两个提交从未推送到远端。2026-07-23 已将 `../uya` 的 `1.0` 分支直接重置到 `f54bd7bf`，分支重新与 `origin/1.0` 对齐，不增加 revert 提交。

## 3. 编译器产物

| 产物 | 作用 | 类型 | 大小 | SHA256 |
|------|------|------|------|--------|
| `uya/bin/uya` | 命令启动器 | x86_64 静态 ELF | 188,776 B | `8ad1e481e45a65907b4ff02cac48646799d804e90ce794e9445680fc5e6359cf` |
| `uya/bin/cmd/build` | 实际 build 编译器 | x86_64 动态链接 PIE | 6,924,448 B | `883f369402b0f6a2eed5fbad08b5d5d4221108c355a42f54b2657513f6a8332d` |

验证结果：

```text
./uya/bin/uya --version       -> Uya 编译器版本 v0.9.9
./uya/bin/cmd/build --version -> v0.9.9
```

`make b` 能生成静态启动器，但其末尾仍调用已移除的隐式编译入口进行自比较，当前会打印跳过比较信息并以 0 退出。实际编译器使用 `make cmd-build-current` 从当前源码重新生成。

## 4. redis-uya 规范兼容调整

- 项目源码不再使用 `export const/var` 表达内部模块 API；cluster、command、allocator 和 log 的内部全局量改为私有。
- 跨模块读取改用 `export fn`，包括 cluster slot/node/topology 常量、command flag、latency bucket 数、catalog 计数和日志级别。
- `scripts/generate_command_catalog.py` 同步生成私有计数常量和公开计数函数，生成文件与生成源保持一致。
- `make verify-uya-source-contract` 扫描全部项目 Uya 源码并拒绝重新引入导出全局量，且已接入 `make test`。
- 上述调整不改变 Redis 命令、协议、持久化、内存统计或运行时语义，也不新增项目对外 C 全局 ABI。

## 5. 验证结果

### 上游 Uya

| 命令 | 结果 |
|------|------|
| `make cmd-build-current` | 通过，重新生成启动器和 `cmd/build` |
| `./tests/run_programs_parallel.sh tests/multifile` | 通过，1/1 多文件任务通过 |
| `./bin/uya build tests/extern_var_test.uya ...` + `nm` | 通过，规范样例导出裸 C 符号 `debug_mode` |

本次修订没有执行并宣称 Uya 上游全量测试为绿；同步结论仅覆盖源码重建、规范样例和既有多文件回归。上游全量状态必须继续独立验证，不能由 redis-uya 项目测试代替。

### redis-uya

| 命令 | 结果 |
|------|------|
| `make verify-uya-source-contract` | 通过，项目源码不存在 `export const/var` |
| `make build` | 通过，无 C 编译警告 |
| `make test` | 通过，完整单元测试全部通过 |
| `make test-integration` | 通过，33 项集成场景全部通过 |
| `make test-redis-cli` | 通过 |
| `make build-release` | 通过 |
| `make benchmark-v0.9.3-release` | 通过，五项吞吐和 p99 回归 guard 全部通过 |

release 产物 `build/redis-uya` 为动态链接 x86_64 PIE，大小 1,597,064 B，SHA256 为 `741780d373ee40f19fe3954f261ed98b6dadd43b764ec3307696c234e355c211`，运行时依赖 glibc 和 ELF 动态加载器。

## 6. 结论与边界

Uya 1.0 / v0.9.9 工具链已回到远端 `f54bd7bf` 规范基线并完成源码构建、成套同步和 redis-uya 全链路验证。redis-uya 通过私有全局量与导出函数适配当前语言规范，不再依赖改变 `export const/var` C ABI 的编译器补丁。当前通过的是 hosted C99/split-C 项目路径，不代表上游所有后端和运行时均已完成。
