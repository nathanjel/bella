# Bella -- developer entry points. Everything here also runs inside the Docker image.
# the project venv when there is one (developer machine), else the image's /opt/venv python3
PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CXX     ?= g++
CXXSTD  ?= c++26
RUNNER  ?= $(PY) {case}

.PHONY: help test selftest closure record verify check-conformance probes slice int-test float-diff object-test targets-record targets-check targets-closure staging-check eval1-corpus eval2-corpus targets-eval1 targets-eval2 lint check clean

help:
	@echo "make test              pytest (refmodel, pipeline, validation, tools) + refmodel self-check"
	@echo "make closure           phase-1 import closure vs manifest.toml  -> closure.lock.json"
	@echo "make record            record conformance expectations under the pinned CPython"
	@echo "make verify            the pinned CPython must reproduce every recorded expectation"
	@echo "make check-conformance run the corpus through RUNNER and compare with expected/"
	@echo "make probes            compile the C++26 feature probes       -> toolchain-probes.md"
	@echo "make slice             the toy end-to-end slice: python == eval1 == emitted C++"
	@echo "make int-test          differential test of runtime/include/bella/int.hpp vs CPython"
	@echo "make float-diff        libstdc++ to_chars/from_chars vs CPython's float digits (FLOAT_CASES=3000000 on a GCC bump)"
	@echo "make object-test       object.hpp against the reference model and CPython in lockstep (also under ASan/UBSan)"
	@echo "make targets-record    record the six target programs under the pinned CPython -> targets/expected/"
	@echo "make targets-check     re-run the targets (two hash seeds) and compare; TARGET_RUNNER= for compiled binaries"
	@echo "make staging-check     the staging prototype: dry-run determinism, the P1 corpus and targets under the replay"
	@echo "make eval1-corpus      the conformance corpus under eval1: no case of conformance/eval1-baseline.txt may regress"
	@echo "make eval2-corpus      the corpus through L2 (to-anf, lifetimes, wf2) under eval2; conformance/eval2-baseline.txt"
	@echo "make targets-eval1     the easy three under eval1, each with its whole closure lowered (the gates' second leg)"
	@echo "make targets-eval2     the easy three through L2 under eval2, each with its whole closure"
	@echo "make targets-closure   each target's closure and the phase-1 increments -> targets/closure*"
	@echo "make lint              ruff and mypy, and the dialect programs under strict mypy (keep them clean)"
	@echo "make check             everything above (what CI runs)"

test:
	@if $(PY) -c "import pytest" 2>/dev/null; then $(PY) -m pytest; else \
	  echo "pytest not installed: running the test modules directly"; \
	  $(PY) tools/tests/test_closure.py && $(PY) tools/tests/test_scope.py && $(PY) tools/tests/test_shims.py && $(PY) -m refmodel.tests.test_cases && \
	  $(PY) -m pipeline.tests.test_frontend_eval1 && $(PY) -m validation.tests.test_certificates; fi
	$(PY) -m refmodel.selftest --iterations 3000

selftest:
	$(PY) -m refmodel.selftest --iterations 20000

closure:
	$(PY) tools/closure.py --manifest manifest.toml --out closure.lock.json

eval1-corpus:
	$(PY) tools/eval1_corpus.py

eval2-corpus:
	$(PY) tools/eval1_corpus.py --level 2

EVAL1_RUNNER = $(shell $(PY) -c "import sys; print(sys.executable)") -P $(CURDIR)/pipeline/l1/run.py --modules closure --lock closure/{name}.lock.json {driver} {argv}
targets-eval1:
	$(PY) targets/run_targets.py check --target cli_easy_slugs --target service_easy_tokens --target data_easy_sales \
	  --runner "$(EVAL1_RUNNER)"

EVAL2_RUNNER = $(subst /l1/run.py,/l2/run.py,$(EVAL1_RUNNER))
targets-eval2:
	$(PY) targets/run_targets.py check --target cli_easy_slugs --target service_easy_tokens --target data_easy_sales \
	  --runner "$(EVAL2_RUNNER)"

staging-check:
	$(PY) pipeline/staging/check.py

record:
	$(PY) conformance/harness.py record

verify:
	$(PY) conformance/harness.py verify

check-conformance:
	$(PY) conformance/harness.py check --runner "$(RUNNER)"

probes:
	$(PY) tools/probe_toolchain.py --cxx $(CXX) --std $(CXXSTD) --out toolchain-probes.md

slice:
	$(PY) -m pipeline.slice --cxx $(CXX) --std $(CXXSTD) pipeline/examples/*.py

int-test:
	$(PY) runtime/tests/int_differential.py --cxx $(CXX) --std $(CXXSTD) --cases 2000

object-test:
	$(PY) runtime/tests/object_differential.py --cxx $(CXX) --std $(CXXSTD) --iterations 3000
	$(PY) runtime/tests/object_differential.py --cxx $(CXX) --std $(CXXSTD) --iterations 1000 --sanitize

FLOAT_CASES ?= 300000
float-diff:
	$(PY) runtime/tests/float_differential.py --cxx $(CXX) --std $(CXXSTD) --cases $(FLOAT_CASES)

targets-record:
	$(PY) targets/run_targets.py record

targets-check:
	$(PY) targets/run_targets.py check $(if $(TARGET_RUNNER),--runner "$(TARGET_RUNNER)",)

targets-closure:
	$(PY) tools/closure.py --all-targets

lint:
	$(PY) -m ruff check . && $(PY) -m mypy
	# dialect programs: the input contract of design section 2 (strict, no explicit Any)
	$(PY) -m mypy --disallow-any-explicit conformance/cases pipeline/examples
	# the target drivers too; the vendored libraries they import are read, not reported
	MYPYPATH=targets/vendor $(PY) -m mypy --disallow-any-explicit --follow-imports=silent targets/drivers

check: closure targets-closure lint test verify probes slice int-test float-diff object-test targets-check staging-check eval1-corpus eval2-corpus targets-eval1 targets-eval2

clean:
	rm -rf build runtime/build pipeline/examples/out/*.bin .pytest_cache .hypothesis
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
