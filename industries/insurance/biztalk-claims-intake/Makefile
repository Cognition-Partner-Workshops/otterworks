# Behaviour corpus for the BizTalk claims hub. Runs on any machine with Python 3.11+; no BizTalk, no Windows.
REPO_ROOT := $(abspath ../../..)
RUNNER := python3 $(REPO_ROOT)/tools/xslt-golden/xslt_golden.py --manifest corpus/manifest.yaml

.PHONY: deps corpus golden check clean

deps:
	pip install -r $(REPO_ROOT)/tools/xslt-golden/requirements.txt

corpus:            ## regenerate the 40 input messages, stubs and aggregates
	python3 corpus/generate.py
	$(RUNNER) write --only Fnol_to_CanonicalClaim
	python3 corpus/generate.py aggregates

golden: corpus     ## regenerate every golden: map outputs, positional files, triage results
	$(RUNNER) write
	python3 tools/ff_render.py
	python3 tools/triage_reference.py

check:             ## the gate: every golden must match byte for byte
	$(RUNNER) check
	python3 tools/ff_render.py check
	python3 tools/triage_reference.py check

clean:
	rm -rf corpus/golden corpus/inputs/fnol-enriched
