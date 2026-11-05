.PHONY: parity parity-test spark-venv spark-smoke

export CANDIDATE

parity: ## Compare legacy with CANDIDATE shell command (or legacy)
	python3 parity/harness.py

parity-test: ## Run parity harness tests, including the red proof
	python3 -m unittest discover -s parity -p 'test_*.py' -v

LEGACY_SPARK_VENV ?= .venv
spark-venv: ## Install the pinned local Spark runtime
	python3 -m venv "$(LEGACY_SPARK_VENV)"
	"$(LEGACY_SPARK_VENV)/bin/python" -m pip install -r requirements-spark.txt

spark-smoke: spark-venv ## Count generated .dat rows using local[*]
	@if [ -z "$$JAVA_HOME" ] && [ -d "$$HOME/.sdkman/candidates/java/current" ]; then export JAVA_HOME="$$HOME/.sdkman/candidates/java/current"; fi; \
	SPARK_LOCAL_IP=127.0.0.1 "$(LEGACY_SPARK_VENV)/bin/python" parity/spark_smoke.py
