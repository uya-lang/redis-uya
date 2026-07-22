# redis-uya Uya 1.0 同步报告（2026-07-22）

## 1. 同步基线

- 上游仓库：`../uya`
- 上游分支：`1.0`
- 同步完成时 HEAD：`337a0edde4b69ae439bb8c33e5253b81c23fbe60`
- 编译器版本：`v0.9.9`
- 同步范围：`uya/lib`、既有 `uya/docs`、`uya/bin/uya`、`uya/bin/cmd/build`
- redis-uya 本地扩展：保留 `std.async` 单线程 allocator 快速路径及对应文档标记

同步流程不是直接复制已有二进制，而是在 `../uya` 中从源码重新构建，再复制生成物。`bin/uya` 只是命令启动器，缺少 `bin/cmd/build` 时无法执行 `uya build`，因此两者必须成套同步。

## 2. 上游修复

redis-uya 首次使用新编译器时暴露了 split-C 跨模块导出全局符号不一致：定义、引用和镜像 extern 声明使用了不同 C 名称。修复已先提交到上游 `1.0` 分支：

- `13d7c784 fix(c99): keep exported global symbol names consistent`
- `337a0edd fix(c99): prefix split mirror global declarations`

上游增加了 `tests/verify_c99_exported_global_split.sh`，覆盖导出常量和可变全局量的跨模块读写、镜像头符号检查、split-C 链接与运行。

## 3. 编译器产物

| 产物 | 作用 | 类型 | 大小 | SHA256 |
|------|------|------|------|--------|
| `uya/bin/uya` | 命令启动器 | x86_64 静态 ELF | 188,776 B | `8ad1e481e45a65907b4ff02cac48646799d804e90ce794e9445680fc5e6359cf` |
| `uya/bin/cmd/build` | 实际 build 编译器 | x86_64 动态链接 PIE | 6,924,216 B | `e59d009b256a1067c16d09c03b2c696144efa4e202d930071afcf835daab8706` |

验证结果：

```text
./uya/bin/uya --version       -> Uya 编译器版本 v0.9.9
./uya/bin/cmd/build --version -> v0.9.9
```

`make b` 能生成静态启动器，但其末尾仍调用已移除的隐式编译入口进行自比较，当前会打印跳过比较信息并以 0 退出。实际编译器使用 `make cmd-build-current` 从当前源码重新生成。

## 4. redis-uya 兼容调整

- `src/command/latency.uya`：三个私有延迟状态变量增加 `_value` 后缀，避免与同名导出 getter 冲突。
- `src/main.uya`：入口日志按项目既有 FFI 规范显式声明并调用 libc `printf`，消除 split-C 模块中的隐式 `printf/sprintf` 声明。
- 上述调整不改变 Redis 命令、协议、持久化或运行时语义。

## 5. 验证结果

### 上游 Uya

| 命令 | 结果 |
|------|------|
| `make cmd-build-current` | 通过，重新生成启动器和 `cmd/build` |
| `bash tests/verify_c99_exported_global_split.sh` | 通过 |
| `./tests/run_programs_parallel.sh tests/multifile` | 通过，1/1 多文件任务通过 |
| `make tests-uya e` | 未通过：总计 1025，通过 678，失败 347 |

上游全量失败主要集中在 nostdlib 测试生成代码：测试计数全局量未生成、`printf`/`memcpy` 声明与格式问题导致链接失败。该状态属于 Uya 1.0 上游待修问题，不能记为同步验证通过。

### redis-uya

| 命令 | 结果 |
|------|------|
| `make build` | 通过，无 C 编译警告 |
| `make test` | 通过，完整单元测试全部通过 |
| `make test-integration` | 通过，33 项集成场景全部通过 |
| `make test-redis-cli` | 通过 |
| `make build-release` | 通过 |

release 产物 `build/redis-uya` 为动态链接 x86_64 PIE，大小 1,597,232 B，SHA256 为 `d9c1f59f93089eaf8caa033e36c6c346174efb8730992f0149666748dc0ff763`，运行时依赖 glibc 和 ELF 动态加载器。

## 6. 结论与边界

Uya 1.0 / v0.9.9 工具链已经完成源码构建、成套同步和 redis-uya 全链路兼容验证，可作为当前项目开发工具链。上游 Uya 自身的 nostdlib 全量测试仍未转绿，后续同步前必须继续复核该失败矩阵；redis-uya 当前通过的是 hosted C99/split-C 项目路径，不代表上游所有后端和运行时均已完成。
