.PHONY: web-dev web-build web-test web-typecheck web-lint api-dev api-test api-lint db-migrate local-db local-api local-worker seed-demo worker-dev gateway-dev runtime-dev training-image-local python-check infra-up infra-down check

LOCAL_DATABASE_URL := sqlite+pysqlite:///$(CURDIR)/.local-data/sensemu.db
LOCAL_OBJECT_STORAGE_PATH := $(CURDIR)/.local-data/objects

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build

web-test:
	cd apps/web && npm test

web-typecheck:
	cd apps/web && npm run typecheck

web-lint:
	cd apps/web && npm run lint

api-dev:
	.venv/bin/uvicorn sensemu_api.main:app --reload --port 8000

api-test:
	PYTHONPATH='apps/inference-runtime/src' .venv/bin/python -m pytest apps/api/tests apps/worker/tests apps/inference-gateway/tests apps/inference-runtime/tests -q

api-lint:
	.venv/bin/ruff check apps/api/src apps/api/tests apps/api/migrations apps/worker/src apps/worker/tests apps/inference-gateway/src apps/inference-gateway/tests apps/inference-runtime/src apps/inference-runtime/tests

db-migrate:
	cd apps/api && ../../.venv/bin/alembic upgrade head

local-db:
	mkdir -p .local-data
	cd apps/api && SENSEMU_DATABASE_URL='$(LOCAL_DATABASE_URL)' ../../.venv/bin/alembic upgrade head

local-api: local-db
	SENSEMU_DATABASE_URL='$(LOCAL_DATABASE_URL)' \
	SENSEMU_OBJECT_STORAGE_ENDPOINT='local://' \
	SENSEMU_OBJECT_STORAGE_LOCAL_PATH='$(LOCAL_OBJECT_STORAGE_PATH)' \
	.venv/bin/uvicorn sensemu_api.main:app --reload --port 8000

seed-demo: local-db
	SENSEMU_DATABASE_URL='$(LOCAL_DATABASE_URL)' \
	SENSEMU_OBJECT_STORAGE_ENDPOINT='local://' \
	SENSEMU_OBJECT_STORAGE_LOCAL_PATH='$(LOCAL_OBJECT_STORAGE_PATH)' \
	PYTHONPATH='apps/api/src' .venv/bin/python apps/api/scripts/seed_demo.py

local-worker:
	SENSEMU_API_URL='http://localhost:8000' \
	SENSEMU_OBJECT_STORAGE_ENDPOINT='local://' \
	SENSEMU_OBJECT_STORAGE_LOCAL_PATH='$(LOCAL_OBJECT_STORAGE_PATH)' \
	SENSEMU_WORKER_TOKEN='sensemu-worker-local-only' \
	.venv/bin/celery --app sensemu_worker.main:app worker --beat --loglevel=INFO --queues=training,extraction,maintenance

worker-dev:
	.venv/bin/python -m sensemu_worker.main

gateway-dev:
	SENSEMU_GATEWAY_RUNTIME_URL='http://localhost:8090' \
	SENSEMU_GATEWAY_RUNTIME_TOKEN='sensemu-runtime-local-only' \
	.venv/bin/uvicorn sensemu_gateway.main:app --reload --port 8080

runtime-dev:
	PYTHONPATH='apps/inference-runtime/src' \
	SENSEMU_RUNTIME_OBJECT_STORAGE_ENDPOINT='local://' \
	SENSEMU_RUNTIME_OBJECT_STORAGE_LOCAL_PATH='$(LOCAL_OBJECT_STORAGE_PATH)' \
	SENSEMU_RUNTIME_CACHE_PATH='$(CURDIR)/.local-data/inference-cache' \
	.venv/bin/uvicorn sensemu_runtime.main:app --reload --port 8090

training-image-local:
	docker build --pull=false -t sensemu-ultralytics:local-cpu \
		-f infra/training-runtime/Dockerfile.cpu infra/training-runtime

python-check:
	.venv/bin/python -m compileall -q apps/api/src apps/worker/src apps/inference-gateway/src apps/inference-runtime/src

infra-up:
	docker compose -f infra/compose/compose.yml up -d

infra-down:
	docker compose -f infra/compose/compose.yml down

check: web-test web-typecheck web-lint api-test api-lint python-check
