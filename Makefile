.NOTPARALLEL:

UYA ?= ./uya/bin/uya
SRC ?= src/main.uya
BUILD_DIR ?= build
BIN ?= $(BUILD_DIR)/redis-uya
C_OUT ?= $(BUILD_DIR)/redis-uya.c
TEST_DIR ?= tests/unit
APP_WORKSPACE ?= $(BUILD_DIR)/app_workspace
TEST_WORKSPACE ?= $(BUILD_DIR)/test_workspace

.PHONY: all build run test test-integration test-redis-cli test-long-run benchmark-v0.1.0 benchmark-persistence-v0.3.0 benchmark-replication-v0.4.0 benchmark-v0.8.0 report-v0.8.0-gaps evaluate-io-uring-v0.8.0 test-all clean version dirs

all: build

dirs:
	@mkdir -p $(BUILD_DIR)

version:
	$(UYA) --version

build: dirs
	@mkdir -p $(APP_WORKSPACE)
	@rm -rf $(APP_WORKSPACE)/src $(APP_WORKSPACE)/main.uya
	@ln -s ../../src $(APP_WORKSPACE)/src
	@cp $(SRC) $(APP_WORKSPACE)/main.uya
	$(UYA) build $(APP_WORKSPACE)/main.uya -o $(BIN) --c99 -e

run: build
	$(BUILD_DIR)/redis-uya

test:
	@echo "=== redis-uya unit tests ==="
	@mkdir -p $(TEST_WORKSPACE)
	@rm -rf $(TEST_WORKSPACE)/src $(TEST_WORKSPACE)/tests $(TEST_WORKSPACE)/main.uya
	@ln -s ../../src $(TEST_WORKSPACE)/src
	@ln -s ../../tests $(TEST_WORKSPACE)/tests
	@cp tests/unit/test_runner.uya $(TEST_WORKSPACE)/main.uya
	$(UYA) build $(TEST_WORKSPACE)/main.uya -o $(BUILD_DIR)/unit-tests --c99 -e
	$(BUILD_DIR)/unit-tests

test-integration: build
	python3 tests/integration/smoke_tcp.py
	python3 tests/integration/idle_client.py
	python3 tests/integration/slow_reader.py
	python3 tests/integration/persistence_aof.py
	python3 tests/integration/persistence_bgsave.py
	python3 tests/integration/persistence_rdb_aof.py
	python3 tests/integration/persistence_crash_matrix.py
	python3 tests/integration/persistence_corruption.py
	python3 tests/integration/redis_py_subset.py
	python3 tests/integration/replication_role_state.py
	python3 tests/integration/replication_psync_backlog.py
	python3 tests/integration/replication_full_sync.py
	python3 tests/integration/replication_incremental_sync.py
	python3 tests/integration/replication_heartbeat.py
	python3 tests/integration/replication_consistency.py
	python3 tests/integration/pubsub_smoke.py
	python3 tests/integration/client_config_smoke.py
	python3 tests/integration/v0_5_compat.py
	python3 tests/integration/cluster_smoke.py
	python3 tests/integration/cluster_consistency.py
	python3 tests/integration/maxmemory_noeviction.py
	python3 tests/integration/maxmemory_allkeys_lru.py
	python3 tests/integration/maxmemory_allkeys_lfu.py
	python3 tests/integration/maxmemory_volatile_policies.py
	python3 tests/integration/memory_info_stats.py
	python3 tests/integration/maxmemory_pressure.py
	python3 tests/integration/error_compat.py

test-redis-cli: build
	bash tests/integration/redis_cli_smoke.sh

test-long-run: build
	python3 tests/integration/long_run_smoke.py

benchmark-v0.1.0: build
	python3 scripts/benchmark_v0_1_0.py

benchmark-persistence-v0.3.0: build
	python3 scripts/benchmark_persistence_v0_3_0.py

benchmark-replication-v0.4.0: build
	python3 scripts/benchmark_replication_v0_4_0.py

benchmark-v0.8.0: build
	python3 scripts/benchmark_v0_8_0.py

report-v0.8.0-gaps:
	python3 scripts/report_v0_8_0_gaps.py

evaluate-io-uring-v0.8.0:
	python3 scripts/evaluate_io_uring_v0_8_0.py

test-all: test test-integration

clean:
	rm -rf $(BUILD_DIR) .uyacache
