.NOTPARALLEL:

UYA ?= ./uya/bin/uya
SRC ?= src/main.uya
BUILD_DIR ?= build
BIN ?= ../$(BUILD_DIR)/redis-uya
C_OUT ?= ../$(BUILD_DIR)/redis-uya.c
TEST_DIR ?= tests/unit
APP_WORKSPACE ?= $(BUILD_DIR)/app_workspace
TEST_WORKSPACE ?= $(BUILD_DIR)/test_workspace

.PHONY: all build run test test-integration test-all clean version dirs

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
	$(UYA) build $(TEST_WORKSPACE)/main.uya -o ../$(BUILD_DIR)/unit-tests --c99 -e
	$(BUILD_DIR)/unit-tests

test-integration: build
	python3 tests/integration/smoke_tcp.py
	python3 tests/integration/idle_client.py
	python3 tests/integration/persistence_aof.py

test-all: test test-integration

clean:
	rm -rf $(BUILD_DIR) .uyacache
