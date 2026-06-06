# Makefile for E2E testing orchestration
# Usage:
#   make e2e-build                    Build addon ZIP via build_addon.py
#   make e2e-start                    Start Kodi 20 container (default)
#   make e2e-start KODI_VERSION=kodi21  Start Kodi 21 container
#   make e2e-test                     Run e2e tests against running container
#   make e2e-stop                     Stop container, remove volumes
#   make e2e                          Full cycle: build -> start -> test -> stop

KODI_VERSION ?= kodi20
COMPOSE_FILE := tests/e2e/docker-compose.yml
CONTAINER_NAME := kodi-e2e-$(KODI_VERSION)
ARTIFACTS_DIR := tests/e2e/artifacts
HEALTHCHECK_TIMEOUT := 60
HEALTHCHECK_INTERVAL := 2

.PHONY: e2e-build e2e-start e2e-test e2e-stop e2e

# Build addon ZIP for e2e testing
e2e-build:
	@echo "Building addon ZIP..."
	@python3 build_addon.py
	@echo "Addon ZIP built successfully."

# Start Kodi container and wait for healthcheck
e2e-start:
	@echo "Starting $(KODI_VERSION) container..."
	@docker compose -f $(COMPOSE_FILE) --profile $(KODI_VERSION) up -d
	@echo "Waiting for healthcheck (timeout $(HEALTHCHECK_TIMEOUT)s, polling every $(HEALTHCHECK_INTERVAL)s)..."
	@elapsed=0; \
	while [ $$elapsed -lt $(HEALTHCHECK_TIMEOUT) ]; do \
		if curl -sf -X POST -H "Content-Type: application/json" \
			-d '{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}' \
			http://localhost:8080/jsonrpc > /dev/null 2>&1; then \
			echo "$(KODI_VERSION) container is ready (took $${elapsed}s)"; \
			exit 0; \
		fi; \
		sleep $(HEALTHCHECK_INTERVAL); \
		elapsed=$$((elapsed + $(HEALTHCHECK_INTERVAL))); \
	done; \
	echo "ERROR: Healthcheck timeout after $(HEALTHCHECK_TIMEOUT)s for $(KODI_VERSION)"; \
	mkdir -p $(ARTIFACTS_DIR); \
	docker logs $(CONTAINER_NAME) > $(ARTIFACTS_DIR)/container_logs_$(KODI_VERSION)_timeout.txt 2>&1 || true; \
	echo "Container logs saved to $(ARTIFACTS_DIR)/container_logs_$(KODI_VERSION)_timeout.txt"; \
	exit 1

# Run e2e tests against running container
e2e-test:
	@KODI_VERSION=$(KODI_VERSION) python3 -m pytest -m e2e

# Stop container and remove anonymous volumes, preserve artifacts
e2e-stop:
	@echo "Stopping $(KODI_VERSION) container..."
	@docker compose -f $(COMPOSE_FILE) --profile $(KODI_VERSION) down -v
	@echo "Container stopped and anonymous volumes removed."

# Full cycle: build -> start -> test -> stop (always stop, exit with test code)
e2e:
	@$(MAKE) e2e-build
	@$(MAKE) e2e-start KODI_VERSION=$(KODI_VERSION)
	@test_exit=0; \
	$(MAKE) e2e-test KODI_VERSION=$(KODI_VERSION) || test_exit=$$?; \
	$(MAKE) e2e-stop KODI_VERSION=$(KODI_VERSION); \
	exit $$test_exit
