FINAL_PYTHON ?= python3

.PHONY: install install-final dev dev-final check check-final verify verify-final test test-algorithms test-frontend build mysql setup-local backend backend-cangjie algorithms-cangjie frontend verify-cangjie verify-cangjie-browser install-cangjie seed-knowledge seed-knowledge-cangjie setup-question-bank-cangjie install-retrieval download-voice download-retrieval-models retrieval

install: install-final
install-final:
	@test -x .venv/bin/python || $(FINAL_PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e './backend-algorithms[dev]'
	pnpm --dir frontend install --frozen-lockfile

install-cangjie:
	bash scripts/install_cangjie.sh
	bash scripts/install_cangjie_mysql.sh

mysql:
	bash scripts/start_mysql.sh

setup-local:
	.venv/bin/python scripts/setup_cangjie_local.py

dev: dev-final
dev-final:
	bash scripts/final.sh start

check: check-final
check-final:
	bash scripts/final.sh check

backend: backend-cangjie
backend-cangjie:
	bash scripts/cangjie.sh run

algorithms-cangjie:
	bash scripts/algorithms.sh

frontend:
	npm --prefix frontend run dev:h5 -- --port $${ZHIWEI_FRONTEND_PORT:-5174} --strictPort

seed-knowledge: seed-knowledge-cangjie
seed-knowledge-cangjie:
	bash scripts/cangjie.sh seed-knowledge

setup-question-bank-cangjie:
	bash scripts/question_bank_cangjie.sh

install-retrieval:
	bash scripts/install_retrieval_env.sh

download-voice:
	PYTHONPATH=backend-algorithms .venv/bin/python scripts/download_models.py --voice

download-retrieval-models:
	conda run --no-capture-output -n $${RETRIEVAL_CONDA_ENV:-minddimension-retrieval} python scripts/download_models.py --retrieval

retrieval:
	bash scripts/start_retrieval.sh

test: test-algorithms test-frontend
test-algorithms:
	PYTHONPATH=backend-algorithms .venv/bin/python -m pytest -q backend-algorithms/tests

test-frontend:
	npm --prefix frontend test

build:
	npm --prefix frontend run build:h5
	npm --prefix frontend run build:app:local

verify-cangjie:
	bash scripts/verify_cangjie.sh

verify-cangjie-browser:
	CANGJIE_VERIFY_BROWSER=1 bash scripts/verify_cangjie.sh

verify: verify-final
verify-final:
	.venv/bin/python scripts/audit_final_source.py
	.venv/bin/python scripts/compile_knowledge_content.py --check
	.venv/bin/ruff check backend-algorithms scripts
	npm --prefix frontend test
	npm --prefix frontend run typecheck
	$(MAKE) build
	$(MAKE) verify-cangjie-browser
