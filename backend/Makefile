# =====================================================================
# Catch-a-Scammer :: build + database + server
#   make help        list targets
#   make setup       python venv + C++ header deps
#   make db-migrate  apply supabase/migrations/*.sql to $DATABASE_URL
#   make db-seed     build the persistent world (providers, actors, people, ...)
#   make server      FastAPI on :8000
#   make client      raylib game  -> build/catch_a_scammer
#   make smoke       terminal client -> build/api_smoke
#   make test        end-to-end: generate cases, check solvability + scoring
# =====================================================================

-include .env
export

PY        ?= python3
VENV      := .venv
VPY       := $(VENV)/bin/python
API_PORT  ?= 8000

CXX       ?= g++
CXXFLAGS  ?= -std=c++17 -O2 -Wall -Wextra
CPPFLAGS  += -Iclient/src -Iclient/vendor
BUILD     := build

HTTPLIB_VER := v0.18.3
JSON_VER    := v3.11.3

# ---- platform link flags (httplib needs sockets; raylib needs GL) -----
ifeq ($(OS),Windows_NT)
  NET_LIBS    := -lws2_32 -lcrypt32
  RAYLIB_LIBS ?= -lraylib -lopengl32 -lgdi32 -lwinmm
  EXE         := .exe
else
  UNAME := $(shell uname -s)
  NET_LIBS := -pthread
  ifeq ($(UNAME),Darwin)
    RAYLIB_LIBS ?= $(shell pkg-config --libs raylib 2>/dev/null || echo -lraylib) \
                   -framework CoreVideo -framework IOKit -framework Cocoa -framework GLUT -framework OpenGL
  else
    RAYLIB_LIBS ?= $(shell pkg-config --libs raylib 2>/dev/null || echo -lraylib -lGL -lm -ldl -lrt -lX11)
  endif
  RAYLIB_CFLAGS ?= $(shell pkg-config --cflags raylib 2>/dev/null)
  EXE :=
endif

# Your existing UI sources live in client/src (main.cpp, windows/apps, ...).
CLIENT_SRC := $(shell find client/src -name '*.cpp')
CLIENT_OBJ := $(patsubst client/src/%.cpp,$(BUILD)/obj/%.o,$(CLIENT_SRC))
NET_OBJ    := $(BUILD)/obj/net/ApiClient.o

.PHONY: help setup deps venv db-migrate db-seed db-reset db-push db-up db-down server client smoke run test psql scenarios clean check-env

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

setup: venv deps
	@test -f .env || (cp .env.example .env && echo "created .env - it points at the Docker Postgres from docker compose")

venv: $(VENV)/.ok
$(VENV)/.ok: server/requirements.txt
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -q -r server/requirements.txt
	@touch $@

deps: client/vendor/httplib.h client/vendor/nlohmann/json.hpp
client/vendor/httplib.h:
	@mkdir -p $(@D)
	curl -fsSL -o $@ https://raw.githubusercontent.com/yhirose/cpp-httplib/$(HTTPLIB_VER)/httplib.h
client/vendor/nlohmann/json.hpp:
	@mkdir -p $(@D)
	curl -fsSL -o $@ https://raw.githubusercontent.com/nlohmann/json/$(JSON_VER)/single_include/nlohmann/json.hpp

check-env:
	@test -n "$(DATABASE_URL)" || (echo "DATABASE_URL not set - run 'make setup' and edit .env"; exit 1)

# ---- database ----------------------------------------------------------
db-migrate: check-env venv
	$(VPY) scripts/migrate.py

db-seed: check-env venv
	$(VPY) -m server.generator.world

db-reset: check-env
	$(VPY) -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True); c.execute(open('supabase/reset.sql').read())"
	$(MAKE) db-migrate db-seed

# Legacy: only if a hosted Supabase project is linked (supabase link --project-ref <ref>)
db-push:
	supabase db push

db-up:                           ## start the local Postgres container (Docker)
	docker compose up -d

db-down:                         ## stop it
	docker compose down

psql: check-env
	psql "$(DATABASE_URL)"

scenarios: check-env venv       ## list the scam scenarios in the catalog
	$(VPY) -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True); c.execute('set search_path=public,extensions'); [print(f'  {k:<16} {t}') for k,t in c.execute('select key,title from scenarios order by category,title')]"

# ---- server -------------------------------------------------------------
server: check-env venv
	$(VPY) -m uvicorn server.app:app --host 127.0.0.1 --port $(API_PORT) --reload

# ---- client -------------------------------------------------------------
client: deps $(BUILD)/catch_a_scammer$(EXE)
$(BUILD)/catch_a_scammer$(EXE): $(CLIENT_OBJ)
	$(CXX) $^ -o $@ $(RAYLIB_LIBS) $(NET_LIBS)

$(BUILD)/obj/%.o: client/src/%.cpp
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(RAYLIB_CFLAGS) -c $< -o $@

smoke: deps $(BUILD)/api_smoke$(EXE)
$(BUILD)/api_smoke$(EXE): client/tools/api_smoke.cpp $(NET_OBJ)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $^ -o $@ $(NET_LIBS)

run: client
	@($(MAKE) -s server &) ; sleep 3 ; ./$(BUILD)/catch_a_scammer$(EXE)

# ---- tests --------------------------------------------------------------
test: check-env venv
	@$(VPY) -m uvicorn server.app:app --port $(API_PORT) --log-level warning > $(BUILD)/test-api.log 2>&1 & \
	 UVPID=$$!; sleep 5; \
	 API_URL=http://127.0.0.1:$(API_PORT) $(VPY) scripts/playtest.py 1; rc=$$?; \
	 kill $$UVPID 2>/dev/null; exit $$rc

clean:
	rm -rf $(BUILD)

$(shell mkdir -p $(BUILD))
