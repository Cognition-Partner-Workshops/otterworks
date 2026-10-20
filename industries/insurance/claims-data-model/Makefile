# Claims and policy data model next to the Commission Pay facts: PostgreSQL 16 + dbt-postgres.
# Every target needs NS=<namespace>; ports derive from it the way the repo Makefile derives them.
REPO        := $(abspath ../../..)
NS          ?=
OFFSET       = $(shell python3 -c "import zlib; print(zlib.crc32('$(NS)'.encode()) % 1000)")
ORACLE_PORT  = $(shell python3 -c "print(51521 + $(OFFSET))")
PG_PORT      = $(shell python3 -c "print(57432 + $(OFFSET))")
CORPUS_REF  ?= origin/devin/1792473658-insurance-biztalk-fixture
CORPUS_PATH := industries/insurance/biztalk-claims-intake/corpus
CORPUS_DIR  := $(CURDIR)/.corpus/corpus

PG_COMPOSE   = CDM_PG_PORT=$(PG_PORT) docker compose -f docker-compose.yml -p otterworks-cdm-$(NS)
PG_PSQL      = docker exec -i otterworks-cdm-$(NS)-cdm-postgres-1 psql -v ON_ERROR_STOP=1 -q -U carrier -d carrier
ORA_SQLPLUS  = docker exec -i otterworks-insurance-$(NS)-insurance-oracle-1 sqlplus -s
PY           = RUST_LOG=warn uv run --no-project -q -p 3.12 --with-requirements requirements.txt
RUN_ENV      = ORACLE_DSN=localhost:$(ORACLE_PORT)/FREEPDB1 \
               PG_DSN=postgresql://carrier:carrier@localhost:$(PG_PORT)/carrier \
               CDM_PG_PORT=$(PG_PORT) CORPUS_DIR=$(CORPUS_DIR) CORPUS_REF=$(CORPUS_REF)
DBT          = $(RUN_ENV) $(PY) dbt

.PHONY: validate up down oracle-up oracle-down oracle-ledger pg-up pg-down corpus schema load dbt parity check

validate:
	@test -n "$(NS)" || (echo "NS is required, e.g. make check NS=dev" >&2; exit 2)

up: validate oracle-up pg-up ## Start Oracle (Commission Pay) and PostgreSQL 16

down: validate pg-down oracle-down ## Stop both containers and drop their volumes

oracle-up: validate
	$(MAKE) -C $(REPO) insurance-up NS=$(NS)

oracle-down: validate
	$(MAKE) -C $(REPO) insurance-down NS=$(NS)

oracle-ledger: validate ## Write the ledger with COMMISSION_PKG, load the star schema, refresh the MV
	$(ORA_SQLPLUS) commission_pay/commission_pay@localhost:1521/FREEPDB1 < oracle/01_calculate_ledger.sql
	$(ORA_SQLPLUS) commission_dw/commission_dw@localhost:1521/FREEPDB1 < oracle/02_load_star.sql

pg-up: validate
	$(PG_COMPOSE) up -d --wait

pg-down: validate
	$(PG_COMPOSE) down -v

corpus: ## Read the claims hub corpus out of git (the fixture branch is read-only here)
	rm -rf .corpus && mkdir -p .corpus
	git -C $(REPO) archive --format=tar $(CORPUS_REF) $(CORPUS_PATH) | tar -x -C .corpus --strip-components=3
	git -C $(REPO) rev-parse $(CORPUS_REF) > .corpus/REF

schema: validate
	$(PG_PSQL) < sql/01_schema.sql

load: validate schema
	$(RUN_ENV) $(PY) python loader/load_oracle.py
	$(RUN_ENV) $(PY) python loader/load_corpus.py

dbt: validate
	$(DBT) build --project-dir dbt --profiles-dir dbt

parity: validate
	$(RUN_ENV) $(PY) python parity/parity.py --out parity/REPORT.md

check: validate corpus oracle-ledger load dbt parity ## The gate: ledger, load, dbt build, parity
