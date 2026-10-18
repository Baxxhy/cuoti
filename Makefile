CONDA_ENV ?= minddimension
CONDA_RUN = conda run --no-capture-output -n $(CONDA_ENV)
PYTHON = $(CONDA_RUN) python
export ZHIWEI_BACKEND_PORT ?= $(or $(shell sed -nE 's/^ZHIWEI_BACKEND_PORT=([0-9]+)$$/\1/p' .env 2>/dev/null | tail -n 1),8000)
export ZHIWEI_FRONTEND_PORT ?= $(or $(shell sed -nE 's/^ZHIWEI_FRONTEND_PORT=([0-9]+)$$/\1/p' .env 2>/dev/null | tail -n 1),5173)
export ZHIWEI_BACKEND_URL ?= http://127.0.0.1:$(ZHIWEI_BACKEND_PORT)

.PHONY: install install-retrieval download-voice download-retrieval-models mysql retrieval migrate seed seed-knowledge fresh-student import-question-bank map-question-bank index-question-bank setup-question-bank backend frontend dev audit verify-adaptive-practice test test-backend test-frontend test-e2e build verify verify-services verify-local verify-recognition-concurrency verify-live-ai verify-retrieval verify-agent verify-knowledge verify-visualizations verify-voice verify-papers verify-parent-teacher verify-roles verify-pages validate-data verify-real-exams verify-diagnosis verify-database verify-functional verify-live completion-report verify-all

install:
	@conda env list | awk '{print $$1}' | grep -qx '$(CONDA_ENV)' || conda create -n $(CONDA_ENV) python=3.13 pip -y
	$(PYTHON) -m pip install -e './backend[dev]'
	pnpm --dir frontend install

install-retrieval:
	bash scripts/install_retrieval_env.sh

download-voice:
	$(PYTHON) scripts/download_models.py --voice

download-retrieval-models:
	RETRIEVAL_MODEL_CACHE=$(CURDIR)/.models/bge conda run --no-capture-output -n $${RETRIEVAL_CONDA_ENV:-minddimension-retrieval} python scripts/download_models.py --retrieval

mysql:
	bash scripts/start_mysql.sh

retrieval:
	bash scripts/start_retrieval.sh

migrate:
	$(CONDA_RUN) alembic -c backend/alembic.ini upgrade head

seed: seed-knowledge
	$(PYTHON) scripts/seed_demo.py

seed-knowledge:
	$(PYTHON) scripts/seed_knowledge.py

fresh-student:
	$(PYTHON) scripts/reset_local_student.py

import-question-bank:
	$(PYTHON) scripts/import_question_bank_datasets.py --source all
	$(PYTHON) scripts/audit_question_bank.py

map-question-bank:
	$(PYTHON) scripts/map_question_knowledge.py

index-question-bank:
	$(PYTHON) scripts/index_question_bank_qdrant.py

setup-question-bank: import-question-bank map-question-bank index-question-bank

.PHONY: setup-question-bank-cangjie
setup-question-bank-cangjie:
	bash scripts/question_bank_cangjie.sh

generate-validation-data:
	$(PYTHON) scripts/generate_functional_validation_data.py

validate-data:
	$(PYTHON) scripts/validate_functional_data.py

verify-real-exams:
	conda run --no-capture-output -n base python scripts/verify_real_exam_samples.py

backend:
	PYTHONPATH=backend $(CONDA_RUN) uvicorn app.main:app --host 0.0.0.0 --port $${ZHIWEI_BACKEND_PORT:-8000} --reload

frontend:
	pnpm --dir frontend run dev:h5 -- --port $(ZHIWEI_FRONTEND_PORT) --strictPort

dev:
	bash scripts/start_local.sh

audit:
	$(PYTHON) scripts/audit_project.py

verify-adaptive-practice:
	$(PYTHON) scripts/verify_adaptive_practice.py

test: test-backend test-frontend

test-backend:
	$(CONDA_RUN) pytest backend/tests -q

test-frontend:
	pnpm --dir frontend test

build:
	pnpm --dir frontend run build:h5

test-e2e:
	pnpm --dir frontend run test:e2e

verify-diagnosis:
	$(PYTHON) scripts/verify_diagnosis.py

verify-agent:
	$(PYTHON) scripts/verify_agent_branches.py

verify-knowledge:
	$(PYTHON) scripts/verify_knowledge_base.py

verify-visualizations:
	$(PYTHON) scripts/verify_visualizations.py
	pnpm --dir frontend run test:e2e -- --grep '全部功能页'

verify-voice:
	HF_HOME=$(CURDIR)/.models/huggingface HF_HUB_OFFLINE=1 $(PYTHON) scripts/verify_voice.py

verify-papers:
	$(PYTHON) scripts/verify_papers.py

verify-parent-teacher:
	$(PYTHON) scripts/verify_parent_teacher.py

verify-roles: verify-parent-teacher

verify-pages:
	$(PYTHON) scripts/verify_pages.py

verify-database:
	FLAGS_use_mkldnn=0 $(PYTHON) scripts/verify_database_usage.py

verify-live:
	FLAGS_use_mkldnn=0 $(PYTHON) scripts/verify_live_e2e.py

verify-local:
	$(PYTHON) scripts/smoke_local.py
	$(MAKE) verify-recognition-concurrency

# 独立临时账号/题目，结束后清理；验证真实 MySQL 并发，不调用远程 AI。
verify-recognition-concurrency:
	$(PYTHON) scripts/verify_recognition_concurrency.py

# 显式运行：要求本地模型已加载，新增独立验收学生；不调用远程 AI 或下载模型。
verify-retrieval:
	$(PYTHON) scripts/smoke_retrieval.py

verify-services:
	CI=1 bash scripts/start_background_services.sh

# 显式运行：会调用现有 API 池并新增一名独立验收学生及学习记录。
verify-live-ai:
	$(PYTHON) scripts/smoke_demo.py

verify-functional: validate-data verify-diagnosis verify-agent verify-visualizations verify-knowledge

completion-report:
	$(PYTHON) scripts/build_completion_report.py --round $${ROUND:-3}

verify-all:
	$(CONDA_RUN) ruff check backend/app backend/tests scripts
	$(CONDA_RUN) mypy --ignore-missing-imports backend/app
	$(MAKE) test-backend
	pnpm --dir frontend run typecheck
	$(MAKE) test-frontend
	$(MAKE) build
	$(MAKE) validate-data
	$(MAKE) verify-database
	$(MAKE) verify-diagnosis
	$(MAKE) verify-agent
	$(MAKE) verify-visualizations
	$(MAKE) verify-voice
	$(MAKE) verify-papers
	$(MAKE) verify-roles
	$(MAKE) verify-pages
	$(MAKE) verify-live
	$(MAKE) completion-report ROUND=$${ROUND:-3}

verify: test
	$(CONDA_RUN) ruff check backend/app backend/tests scripts
	$(PYTHON) scripts/migrate_api_pool_model.py --path backend/config/api_pool.example.json --dry-run
	pnpm --dir frontend run typecheck
	pnpm --dir frontend run build:h5
	$(MAKE) verify-services
	$(MAKE) test-e2e
	$(MAKE) verify-local

# 独立仓颉版；保留 Python 版入口，使用临时数据库验证。
.PHONY: install-cangjie backend-cangjie verify-cangjie
.PHONY: algorithms-cangjie
algorithms-cangjie:
	bash scripts/algorithms.sh
install-cangjie:
	bash scripts/install_cangjie.sh
	bash scripts/install_cangjie_mysql.sh

backend-cangjie:
	bash scripts/cangjie.sh run

verify-cangjie:
	bash scripts/verify_cangjie.sh

# 现有浏览器流程连接隔离仓颉后端，保留原 Python 验证入口。
.PHONY: verify-cangjie-browser
verify-cangjie-browser:
	CANGJIE_VERIFY_BROWSER=1 bash scripts/verify_cangjie.sh

.PHONY: seed-knowledge-cangjie
seed-knowledge-cangjie:
	bash scripts/cangjie.sh seed-knowledge

# Recommended final architecture. Legacy targets above remain explicit compatibility entries.
.PHONY: install-final dev-final check-final verify-final
FINAL_PYTHON ?= python3
install-final:
	@test -x .venv/bin/python || $(FINAL_PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e './backend[dev]'
	pnpm --dir frontend install --frozen-lockfile

dev-final:
	bash scripts/final.sh start

check-final:
	bash scripts/final.sh check

verify-final:
	npm --prefix frontend test
	npm --prefix frontend run typecheck
	npm --prefix frontend run build:h5
	npm --prefix frontend run build:app:local
	$(MAKE) verify-cangjie-browser
