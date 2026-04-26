# QuackBox — common dev commands
.PHONY: help up down logs build rebuild test test-cov

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start backend + frontend (foreground)
	docker compose up

up-d: ## Start backend + frontend (detached)
	docker compose up -d

down: ## Stop containers
	docker compose down

logs: ## Tail backend logs
	docker compose logs -f backend

build: ## Build images
	docker compose build

rebuild: ## Rebuild from scratch and start
	docker compose up --build

PROJECT := $(notdir $(CURDIR))
BACKEND_IMAGE := $(PROJECT)-backend

test: ## Run the backend test suite (requires `make build` to have run once)
	docker run --rm \
	  -v "$(CURDIR)/backend:/app" -w /app \
	  $(BACKEND_IMAGE) \
	  sh -c "pip install --quiet -r requirements-dev.txt && pytest tests/ -v"

test-cov: ## Run tests with a coverage report
	docker run --rm \
	  -v "$(CURDIR)/backend:/app" -w /app \
	  $(BACKEND_IMAGE) \
	  sh -c "pip install --quiet -r requirements-dev.txt && pytest tests/ --cov=app --cov-report=term-missing"
