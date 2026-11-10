.PHONY: install lint typecheck test check run up down deploy destroy

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

lint:
	ruff check app tests scripts && ruff format --check app tests scripts && cfn-lint infra/*.yaml

typecheck:
	mypy

test:
	pytest --cov=app --cov-report=term --cov-fail-under=85

check: lint typecheck test

run:
	uvicorn app.main:app --reload --port 8000

up:
	docker compose up --build

down:
	docker compose down -v

deploy:
	./scripts/deploy_infra.sh

destroy:
	./scripts/destroy_infra.sh
