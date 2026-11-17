PYTHON ?= python3
.DEFAULT_GOAL := help
.PHONY: help install install-browser mysql setup-local dev check build preview backend algorithms frontend seed-knowledge import-questions download-questions install-retrieval download-retrieval-models download-voice retrieval
help:
	@printf '%s\n' '错题帮（Linux x86_64，Node 24+，Python 3.11+，MySQL 8）' '首次准备：make install install-browser' '本地数据库：make mysql setup-local' '模型配置：复制 config/api_pool.example.json 为 config/api_pool.json 并填写可用服务' '运行：make dev（前端默认5175，Python统一后端8002，内置算法计算）' '状态：make check；构建：make build' '题库：make download-questions import-questions' '检索：make install-retrieval download-retrieval-models retrieval'
install:
	@test -x .venv/bin/python || $(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e ./backend-algorithms -e "./backend-python[dev]"
	pnpm --dir frontend install --frozen-lockfile
install-browser:
	cd frontend && PLAYWRIGHT_BROWSERS_PATH="$(CURDIR)/frontend/.playwright-browsers" pnpm exec playwright install --with-deps chromium
mysql:
	bash scripts/start_mysql.sh
setup-local:
	.venv/bin/python scripts/setup_local.py
dev:
	bash scripts/final.sh start
check:
	bash scripts/final.sh check
build:
	npm --prefix frontend run build:h5
	npm --prefix frontend run build:app:local
preview:
	node scripts/serve_build_preview.mjs
backend:
	bash scripts/backend.sh
algorithms:
	bash scripts/algorithms.sh
frontend:
	npm --prefix frontend run dev:h5 -- --port $${ZHIWEI_FRONTEND_PORT:-5175} --strictPort
seed-knowledge:
	PYTHONPATH=backend-python:backend-algorithms .venv/bin/python -m cuoti_backend.manage_db seed-knowledge
import-questions:
	bash scripts/question_bank.sh
download-questions:
	.venv/bin/python scripts/fetch_public_question_sources.py
install-retrieval:
	bash scripts/install_retrieval_env.sh
download-retrieval-models:
	conda run --no-capture-output -n $${RETRIEVAL_CONDA_ENV:-minddimension-retrieval} python scripts/download_models.py --retrieval
download-voice:
	PYTHONPATH=backend-algorithms .venv/bin/python scripts/download_models.py --voice
retrieval:
	bash scripts/start_retrieval.sh
