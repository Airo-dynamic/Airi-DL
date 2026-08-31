.DEFAULT_GOAL := help

UV ?= uv
PROFILE ?= auto
ifneq ($(strip $(AIRIDL_CACHE_DIR)),)
export UV_CACHE_DIR := $(abspath $(AIRIDL_CACHE_DIR))/uv
endif

.PHONY: help sync doctor lint typecheck py-test configure build cpp-test sanitize check history-verify

help:
	@echo "Airi-DL targets: sync doctor lint typecheck py-test build cpp-test sanitize check history-verify"

sync:
	$(UV) sync --frozen

doctor:
	$(UV) run airidl doctor --profile $(PROFILE)

lint:
	$(UV) run ruff check src tests tools
	$(UV) run ruff format --check src tests tools

typecheck:
	$(UV) run mypy src tests tools

py-test:
	$(UV) run pytest

configure:
	$(UV) run cmake --preset dev

build: configure
	$(UV) run cmake --build --preset dev

cpp-test: build
	$(UV) run ctest --preset dev

sanitize:
	$(UV) run cmake --preset asan
	$(UV) run cmake --build --preset asan
	$(UV) run ctest --preset asan

check: lint typecheck py-test cpp-test sanitize

history-verify:
	$(UV) run python tools/history.py verify-root
