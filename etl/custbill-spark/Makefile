.PHONY: help chain test parity recon

LEGACY := ../legacy-extra
PYTHON := $(shell [ -x $(LEGACY)/.venv/bin/python ] && echo $(LEGACY)/.venv/bin/python || echo python3)
export SPARK_LOCAL_IP ?= 127.0.0.1

help: ## List available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

chain: ## Run the Spark CUSTBILL chain (ROOT=<estate root>, STRICT=1 to quarantine bad files)
	bin/custbill-spark chain $(if $(ROOT),--root $(ROOT),) $(if $(STRICT),--strict,)

test: ## Unit tests + byte-equivalence against the legacy awk/Perl (needs `make -C ../legacy-extra spark-venv`)
	$(PYTHON) -m unittest discover -s tests -v

parity: ## Parity table: legacy chain vs Spark chain, every case must be byte-identical
	CANDIDATE="etl/custbill-spark/bin/custbill-spark chain" $(MAKE) -C $(LEGACY) parity

recon: ## Parity + idempotent rerun + planted anomalies -> docs/tech-partnerships/recon/custbill-spark-chain.recon.json
	python3 recon.py $(if $(OUT),--out $(OUT),)
