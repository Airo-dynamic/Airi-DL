.DEFAULT_GOAL := help

UV ?= uv
PROFILE ?= auto

.PHONY: help sync doctor lint typecheck py-test configure build cpp-test sanitize check

help:
	@echo "Airi-DL day001 targets: sync doctor lint typecheck py-test build cpp-test sanitize check"

sync:
	$(UV) sync --frozen

doctor:
	$(UV) run airidl doctor --profile $(PROFILE)

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

typecheck:
	$(UV) run mypy src tests

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
