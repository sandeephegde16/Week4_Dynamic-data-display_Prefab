PORT ?= 8503
PREFAB_PORT ?= 5175
RUNTIME_DIR := .streamlit_runtime
PID_FILE := $(RUNTIME_DIR)/server.pid
LOG_FILE := $(RUNTIME_DIR)/server.log

.PHONY: help setup run run-bg prefab stop kill-port status logs check clean

help:
	@echo "Available commands:"
	@echo "  make setup      Install dependencies with uv"
	@echo "  make run        Run Streamlit in the foreground"
	@echo "  make run-bg     Run Streamlit in the background on PORT=$(PORT)"
	@echo "  make prefab     Serve only generated/current_prefab_app.py on PREFAB_PORT=$(PREFAB_PORT)"
	@echo "  make stop       Stop the background Streamlit process for this project"
	@echo "  make kill-port  Kill any process listening on PORT=$(PORT)"
	@echo "  make status     Show project app process and listener status"
	@echo "  make logs       Tail the Streamlit log"
	@echo "  make check      Compile Python files"
	@echo "  make clean      Remove local runtime files and Python caches"

setup:
	uv sync

run:
	uv run streamlit run main.py --server.port $(PORT)

run-bg:
	@mkdir -p $(RUNTIME_DIR)
	@if [ -f $(PID_FILE) ] && kill -0 "$$(cat $(PID_FILE))" 2>/dev/null; then \
		echo "App already running with PID $$(cat $(PID_FILE))."; \
	else \
		nohup uv run streamlit run main.py --server.headless true --server.port $(PORT) > $(LOG_FILE) 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "Started Streamlit on http://localhost:$(PORT) with PID $$(cat $(PID_FILE))."; \
		echo "Logs: $(LOG_FILE)"; \
	fi

prefab:
	uv run prefab serve generated/current_prefab_app.py --port $(PREFAB_PORT)

stop:
	@if [ -f $(PID_FILE) ] && kill -0 "$$(cat $(PID_FILE))" 2>/dev/null; then \
		echo "Stopping Streamlit PID $$(cat $(PID_FILE))..."; \
		kill "$$(cat $(PID_FILE))"; \
		rm -f $(PID_FILE); \
	else \
		echo "No running project Streamlit process found."; \
		rm -f $(PID_FILE); \
	fi

kill-port:
	@pids="$$(lsof -tiTCP:$(PORT) -sTCP:LISTEN 2>/dev/null || true)"; \
	if [ -n "$$pids" ]; then \
		echo "Killing listener(s) on port $(PORT): $$pids"; \
		kill $$pids; \
	else \
		echo "No listener found on port $(PORT)."; \
	fi

status:
	@if [ -f $(PID_FILE) ]; then \
		pid="$$(cat $(PID_FILE))"; \
		if kill -0 "$$pid" 2>/dev/null; then \
			echo "PID file: $$pid"; \
			ps -p "$$pid" -o pid=,stat=,command= || true; \
		else \
			echo "Stale PID file found: $$pid"; \
		fi; \
	else \
		echo "No PID file."; \
	fi
	@lsof -n -P -iTCP:$(PORT) -sTCP:LISTEN 2>/dev/null || true

logs:
	@if [ -f $(LOG_FILE) ]; then \
		tail -f $(LOG_FILE); \
	else \
		echo "No log file found at $(LOG_FILE)."; \
	fi

check:
	uv run python -m compileall app main.py

clean:
	@find . -path './.venv' -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
	@find . -path './.venv' -prune -o -type f -name '*.py[co]' -delete
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -rf $(RUNTIME_DIR)
	@rm -rf generated
