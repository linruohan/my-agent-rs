# 跨平台快捷命令（Linux/macOS 优先；Windows 可用 npm scripts）
.PHONY: setup dev dev-web dev-desktop dev-sidecar test build build-web build-all sidecar clean check-ws-types gen-ws-types

PYTHON ?= python
NPM ?= npm

setup:
	$(NPM) run setup:sh

dev: dev-web

dev-web:
	bash scripts/run-web.sh

dev-desktop:
	bash scripts/run-desktop.sh

dev-sidecar:
	bash scripts/run-sidecar.sh

test:
	AGENT_CONFIG_DIR=$(CURDIR)/agent/config AGENT_DATA_DIR=$(CURDIR)/data \
		$(PYTHON) -m pytest tests/agent -q
	$(PYTHON) scripts/check_ws_types_sync.py

gen-ws-types:
	$(PYTHON) scripts/generate_ws_types.py

check-ws-types:
	$(PYTHON) scripts/check_ws_types_sync.py

build-web:
	$(NPM) run build

build-all:
	bash scripts/build.sh

sidecar:
	$(PYTHON) scripts/build_sidecar.py

clean:
	rm -rf dist data/sidecar.log src-tauri/target/release/bundle
