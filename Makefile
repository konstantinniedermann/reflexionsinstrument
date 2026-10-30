.DEFAULT_GOAL := help
.PHONY: help install dev test lint format deploy logs ssh

help: ## Zeigt diese Hilfe
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

install: ## Installiert die Abhängigkeiten (uv sync)
	uv sync

dev: ## Startet die App lokal auf http://localhost:8000 (Daten in .daten/)
	DATEN_VERZEICHNIS=.daten uv run uvicorn --factory app.main:erstelle_app --reload --port 8000

test: ## Führt die Python-Tests aus
	uv run pytest

lint: ## Prüft Code und Formatierung (Ruff)
	uv run ruff check
	uv run ruff format --check

format: ## Formatiert den Code und behebt Lint-Funde (Ruff)
	uv run ruff check --fix
	uv run ruff format

deploy: ## Veröffentlicht die Pilot-Version auf fly.io (Build remote)
	fly deploy

logs: ## Zeigt die Logs der laufenden App auf fly.io
	fly logs

ssh: ## Öffnet eine Shell auf der App-Maschine bei fly.io
	fly ssh console
