# ─────────────────────────────────────────────────────────────────────────────
# LG TV Tools — Project Makefile
# ─────────────────────────────────────────────────────────────────────────────
SHELL := /bin/bash
.DEFAULT_GOAL := help

# Project metadata
APP_NAME    := lg-tv-tools
VERSION     := 0.3.0
PYTHON      := python3
UV          := uv
VENV_DIR    := .venv
SRC_DIR     := src
TEST_DIR    := tests
SCRIPTS_DIR := scripts

# ═════════════════════════════════════════════════════════════════════════════
# Environment — set up the project for local development
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: venv
venv: ##@Environment Create a new virtual environment using uv
	$(UV) venv $(VENV_DIR)

.PHONY: install
install: ##@Environment Install the project in editable mode (runtime deps only)
	$(UV) pip install -e .

.PHONY: install-dev
install-dev: ##@Environment Install with dev tools (pytest, ruff, mypy)
	$(UV) pip install -e .
	$(UV) pip install pytest ruff mypy

.PHONY: sync
sync: ##@Environment Sync installed packages to match uv.lock exactly
	$(UV) sync

.PHONY: sync-desktop
sync-desktop: ##@Environment Sync with desktop extras (netifaces, zeroconf)
	$(UV) sync --extra desktop

.PHONY: sync-qt
sync-qt: ##@Environment Sync with Qt extras for legacy PyQt6 app
	$(UV) sync --extra qt

.PHONY: sync-all
sync-all: ##@Environment Sync with all optional extras
	$(UV) sync --extra desktop --extra qt

.PHONY: lock
lock: ##@Environment Regenerate uv.lock from pyproject.toml constraints
	$(UV) lock

.PHONY: update
update: ##@Environment Upgrade all deps to latest compatible versions and sync
	$(UV) lock --upgrade
	$(UV) sync

# ═════════════════════════════════════════════════════════════════════════════
# Run — launch the application
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: run
run: ##@Run Start the LG TV Tools Flet desktop application
	$(UV) run lg-tv-tools

.PHONY: run-mobile
run-mobile: ##@Run Start the LG TV Tools mobile/remote application
	$(UV) run lg-tv-remote

.PHONY: run-ios
run-ios: ##@Run Debug the app on a connected iOS device via Flet
	FLET_PYTHON_BUILD_MANIFEST=/tmp/manifest.json $(UV) run flet debug --device-id ios

.PHONY: run-qt
run-qt: ##@Run Start the legacy PyQt6 desktop application (requires qt extras)
	$(UV) run lg-tv-tools-qt

# ═════════════════════════════════════════════════════════════════════════════
# Quality — linting, formatting, and static analysis
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: lint
lint: ##@Quality Check code for style and correctness issues (ruff)
	$(UV) run ruff check $(SRC_DIR) $(TEST_DIR)

.PHONY: lint-fix
lint-fix: ##@Quality Auto-fix linting issues where possible
	$(UV) run ruff check --fix $(SRC_DIR) $(TEST_DIR)

.PHONY: format
format: ##@Quality Format all source files in-place (ruff format)
	$(UV) run ruff format $(SRC_DIR) $(TEST_DIR)

.PHONY: format-check
format-check: ##@Quality Verify formatting without modifying files
	$(UV) run ruff format --check $(SRC_DIR) $(TEST_DIR)

.PHONY: typecheck
typecheck: ##@Quality Run static type analysis with mypy
	$(UV) run mypy $(SRC_DIR)

.PHONY: check
check: lint format-check typecheck ##@Quality Run all quality gates (lint + format + types)

# ═════════════════════════════════════════════════════════════════════════════
# Testing — unit tests, smoke tests, and coverage
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: test
test: ##@Testing Run the test suite (quiet output)
	$(UV) run pytest -q $(TEST_DIR)

.PHONY: test-verbose
test-verbose: ##@Testing Run the test suite with verbose per-test output
	$(UV) run pytest -v $(TEST_DIR)

.PHONY: test-cov
test-cov: ##@Testing Run tests and report line-level coverage
	$(UV) run pytest --cov=$(SRC_DIR)/lgtvtools --cov-report=term-missing -q $(TEST_DIR)

.PHONY: smoke
smoke: ##@Testing Execute the quick smoke-test script (import checks)
	bash $(SCRIPTS_DIR)/smoke_test.sh

# ═════════════════════════════════════════════════════════════════════════════
# Build — package the project for distribution
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: build
build: ##@Build Create Python sdist and wheel archives
	$(UV) build

.PHONY: build-deb
build-deb: ##@Build Assemble a .deb package for Debian/Ubuntu/Kali
	bash $(SCRIPTS_DIR)/build_deb.sh

.PHONY: build-rpm
build-rpm: ##@Build Assemble a .rpm package for RHEL/Alma Linux/Fedora
	bash $(SCRIPTS_DIR)/build_rpm.sh

.PHONY: build-macos
build-macos: ##@Build Create a macOS .app bundle via PyInstaller
	bash $(SCRIPTS_DIR)/build_macos.sh

.PHONY: build-windows
build-windows: ##@Build Create a Windows .exe installer via PyInstaller
	bash $(SCRIPTS_DIR)/build_windows.sh

.PHONY: build-ios
build-ios: ##@Build Build iOS IPA (requires Apple Developer account and team ID)
	FLET_PYTHON_BUILD_MANIFEST=/tmp/manifest.json $(UV) run flet build ipa

.PHONY: build-all
build-all: build build-deb build-rpm build-macos build-windows ##@Build Build all platform packages from current host

.PHONY: sign
sign: ##@Build Sign release artifacts (.deb, checksums) with GPG
	bash $(SCRIPTS_DIR)/sign_release.sh

# ═════════════════════════════════════════════════════════════════════════════
# Desktop — KDE/freedesktop integration for the current user
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: desktop-install
desktop-install: ##@Desktop Install launcher, icon, and .desktop file locally
	bash $(SCRIPTS_DIR)/install.sh

.PHONY: desktop-uninstall
desktop-uninstall: ##@Desktop Remove all user-level desktop integration files
	bash $(SCRIPTS_DIR)/uninstall.sh

# ═════════════════════════════════════════════════════════════════════════════
# Clean — remove generated and temporary files
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: clean
clean: ##@Clean Delete build outputs, caches, and coverage data
	rm -rf build/ dist/ .build/
	rm -rf $(SRC_DIR)/*.egg-info $(SRC_DIR)/lg_tv_tools.egg-info
	find $(SRC_DIR) $(TEST_DIR) -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -f .coverage coverage.xml
	rm -f *.deb *.asc *.sha256

.PHONY: clean-venv
clean-venv: ##@Clean Remove the virtual environment entirely
	rm -rf $(VENV_DIR)

.PHONY: clean-all
clean-all: clean clean-venv ##@Clean Full reset — remove all generated files and venv

# ═════════════════════════════════════════════════════════════════════════════
# Release — pre-release validation pipeline
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: release-check
release-check: check test smoke ##@Release Run full quality + test + smoke validation
	@echo "✓ All release checks passed for v$(VERSION)"

# ═════════════════════════════════════════════════════════════════════════════
# Help
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: help
help: ## Show available targets grouped by category
	@printf "\n\033[1mLG TV Tools v$(VERSION)\033[0m\n"
	@printf "Usage: make \033[36m<target>\033[0m\n"
	@grep -E '^[a-zA-Z_-]+:.*?##@' $(MAKEFILE_LIST) | \
		sed 's/\:.*##@/|/' | sed 's/ /|/' | \
		awk -F'|' '{ \
			if ($$2 != last) { printf "\n\033[1m%s\033[0m\n", $$2; last = $$2 } \
			printf "  \033[36m%-18s\033[0m %s\n", $$1, $$3 \
		}'
	@printf "\n"
