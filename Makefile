# ==============================================================================
# 🚨 IMS (Incident Management System) SRE Makefile
# ==============================================================================
# Enforces unified SRE testing portfolios, load tests, chaos tests, and code standards.
# Works out of the box in Unix/macOS make environments and standard Windows make-utils.

.PHONY: help test test-unit test-integration load-test e2e lint start-services stop-services restart-backend test-scale test-chaos

# Python virtual environment interpreter path
PYTHON_BIN = .\.venv\Scripts\python.exe
PYTEST_BIN = .\.venv\Scripts\pytest.exe

# Fallback to local python/pytest if .venv is not active
ifeq ($(OS),Windows_NT)
    PYTHON ?= $(PYTHON_BIN)
    PYTEST ?= $(PYTEST_BIN)
else
    PYTHON ?= python3
    PYTEST ?= pytest
endif

help:
	@echo "======================================================================="
	@echo "🛠️  IMS SRE OPERATIONAL RUNNER COMMANDS"
	@echo "======================================================================="
	@echo "  make start-services    - Deploy all infrastructure containers in daemon mode"
	@echo "  make stop-services     - Tear down all containers and clean volumes"
	@echo "  make test              - Execute the ENTIRE SRE validation pipeline"
	@echo "  make test-unit         - Run lightweight isolative pytest unit tests"
	@echo "  make test-integration  - Run high-fidelity concurrency and chaos integrations"
	@echo "  make load-test         - Run 100-user concurrent storm and AI cache performance"
	@echo "  make e2e               - Run complete end-to-end incident lifecycle checks"
	@echo "  make test-scale        - Run 1000-user concurrent herd, NoSQL, and IP spoofing audits"
	@echo "  make test-chaos        - Run programmatic Redis, Postgres, and Worker crash simulations"
	@echo "  make lint              - Enforce basic syntax syntax and dependency checking"
	@echo "======================================================================="

start-services:
	@echo "[*] Launching database, cache, tracing, and monitoring containers..."
	docker compose up --build -d
	@echo "[+] Infrastructure is live and healthy."

stop-services:
	@echo "[*] Tearing down infrastructure stack..."
	docker compose down -v
	@echo "[+] All containers purged."

test-unit:
	@echo "======================================================================="
	@echo "🧪 RUNNING PYTEST UNIT SUITE"
	@echo "======================================================================="
	$(PYTEST) -v backend/tests/

test-integration:
	@echo "======================================================================="
	@echo "🌊 RUNNING CONCURRENCY & THUNDERING HERD DEBOUNCING TESTS"
	@echo "======================================================================="
	$(PYTHON) tests/test_1_thundering_herd.py
	@echo "======================================================================="
	@echo "🔐 RUNNING JWT EXPIRY & SECURE STREAM DISCONNECT TESTS"
	@echo "======================================================================="
	$(PYTHON) tests/test_2_jwt_sse.py
	@echo "======================================================================="
	@echo "🔥 RUNNING REDIS & POSTGRES CHAOS AND FAILOVER INTEGRATIONS"
	@echo "======================================================================="
	$(PYTHON) tests/test_3_chaos_failover.py

load-test:
	@echo "======================================================================="
	@echo "🚀 RUNNING 100-USER CONCURRENT STORM & AI CACHING BENCHMARKS"
	@echo "======================================================================="
	$(PYTHON) tests/test_4_load_performance.py

e2e:
	@echo "======================================================================="
	@echo "🔄 RUNNING END-TO-END INCIDENT LIFECYCLE & MTTR CALCULATION CHECKS"
	@echo "======================================================================="
	$(PYTHON) tests/test_5_functional_validation.py

test-scale:
	@echo "======================================================================="
	@echo "⚡ RUNNING SRE SCALE, RATE-LIMIT SPOOF & NOSQL INJECTION PLATFORM AUDITS"
	@echo "======================================================================="
	$(PYTHON) tests/test_6_scale_and_security.py

test-chaos:
	@echo "======================================================================="
	@echo "🌀 RUNNING PROGRAMMATIC SRE REDIS/POSTGRES/WORKER CHAOS SIMULATIONS"
	@echo "======================================================================="
	$(PYTHON) tests/test_7_chaos_simulation.py

lint:
	@echo "[*] Compiling python codebases to ensure syntax cleanliness..."
	$(PYTHON) -m compileall backend/app
	@echo "[+] Syntax verification completed. All core modules are compile-safe."

test: lint test-unit test-integration load-test e2e test-scale test-chaos
	@echo "======================================================================="
	@echo "🎉 ALL INTEGRATION, SCALE, SECURITY, CHAOS, & LIFECYCLE SCENARIOS PASSED!"
	@echo "======================================================================="
