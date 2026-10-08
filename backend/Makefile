# =====================================================================
# Catch-a-Scammer :: database + server + React client  (macOS / Linux / WSL)
# On Windows without make, use the VS Code tasks or the README's PowerShell steps.
#   make help        list targets
#   make setup       python venv + .env + client packages (npm install)
#   make db-up       start the local Postgres container (Docker)
#   make db-migrate  apply database/migrations/*.sql to $DATABASE_URL
#   make db-seed     build the persistent world (providers, actors, people, ...)
#   make db-reset    drop everything, then migrate and seed again
#   make server      FastAPI on :8000
#   make web         React client dev server on :5173 (proxies the API)
#   make web-build   build the client into ../frontend/dist (then `make server` serves it at :8000)
#   make test        end-to-end: generate cases, check solvability, the Messenger, the study
# =====================================================================

-include .env
export

PY        ?= python3
VENV      := .venv
VPY       := $(VENV)/bin/python
API_PORT  ?= 8000
BUILD     := build

.PHONY: help setup venv db-migrate db-seed db-reset db-up db-down server web web-build test psql scenarios clean check-env

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

setup: venv
	@test -f .env || (cp .env.example .env && echo "created .env - it points at the Docker Postgres from docker compose")
	cd ../frontend && npm install

venv: $(VENV)/.ok
$(VENV)/.ok: server/requirements.txt
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -q -r server/requirements.txt
	@touch $@

check-env:
	@test -n "$(DATABASE_URL)" || (echo "DATABASE_URL not set - run 'make setup' and edit .env"; exit 1)

# ---- database ----------------------------------------------------------
db-up:                           ## start the local Postgres container (Docker)
	docker compose up -d --wait

db-down:                         ## stop it
	docker compose down

db-migrate: check-env venv
	$(VPY) scripts/migrate.py

db-seed: check-env venv
	$(VPY) -m server.generator.world

db-reset: check-env venv
	$(VPY) -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True); c.execute(open('database/reset.sql').read())"
	$(MAKE) db-migrate db-seed

psql: check-env
	psql "$(DATABASE_URL)"

scenarios: check-env venv       ## list the scam scenarios in the catalog
	$(VPY) -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True); c.execute('set search_path=public,extensions'); [print(f'  {k:<16} {t}') for k,t in c.execute('select key,title from scenarios order by category,title')]"

# ---- server and client ---------------------------------------------------
server: check-env venv
	$(VPY) -m uvicorn server.app:app --host 127.0.0.1 --port $(API_PORT) --reload

web:
	cd ../frontend && npm run dev

web-build:
	cd ../frontend && npm run build

# ---- tests --------------------------------------------------------------
test: check-env venv
	@mkdir -p $(BUILD)
	@$(VPY) -m uvicorn server.app:app --port $(API_PORT) --log-level warning > $(BUILD)/test-api.log 2>&1 & \
	 UVPID=$$!; sleep 5; \
	 API_URL=http://127.0.0.1:$(API_PORT) $(VPY) scripts/playtest.py 1; rc=$$?; \
	 kill $$UVPID 2>/dev/null; exit $$rc

clean:
	rm -rf $(BUILD)
