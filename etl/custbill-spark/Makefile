.PHONY: setup test chain parity lint
setup:
	uv venv --python 3.11 .venv
	uv pip install --python .venv/bin/python -r ../legacy-extra/requirements-spark.txt pytest ruff
test:
	SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=$(CURDIR)/.venv/bin/python .venv/bin/python -m pytest -q
chain:
	./launch chain
parity:
	$(MAKE) -C ../legacy-extra parity CANDIDATE="$(CURDIR)/launch chain"
lint:
	.venv/bin/ruff check custbill.py test_custbill.py
