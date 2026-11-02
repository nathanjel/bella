# Bella -- developer entry points. Everything here also runs inside the Docker image.
# the project venv when there is one (developer machine), else the image's /opt/venv python3
PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CXX     ?= g++
CXXSTD  ?= c++26
RUNNER  ?= $(PY) {case}

.PHONY: help test selftest closure record verify check-conformance probes slice int-test targets-record targets-check targets-closure staging-check lint check clean

help:
	@echo "make test              pytest (refmodel, pipeline, validation, tools) + refmodel self-check"
	@echo "make closure           phase-1 import closure vs manifest.toml  -> closure.lock.json"
	@echo "make record            record conformance expectations under the pinned CPython"
	@echo "make verify            the pinned CPython must reproduce every recorded expectation"
	@echo "make check-conformance run the corpus through RUNNER and compare with expected/"
	@echo "make probes            compile the C++26 feature probes       -> toolchain-probes.md"
	@echo "make slice             the toy end-to-end slice: python == eval1 == emitted C++"
	@echo "make int-test          differential test of runtime/include/bella/int.hpp vs CPython"
	@echo "make targets-record    record the six target programs under the pinned CPython -> targets/expected/"
	@echo "make targets-check     re-run the targets (two hash seeds) and compare; TARGET_RUNNER= for compiled binaries"
	@echo "make staging-check     the staging prototype: dry-run determinism, the P1 corpus and targets under the replay"
	@echo "make targets-closure   each target's closure and the phase-1 increments -> targets/closure*"
	@echo "make lint              ruff and mypy, and the dialect programs under strict mypy (keep them clean)"
	@echo "make check             everything above (what CI runs)"

test:
	@if $(PY) -c "import pytest" 2>/dev/null; then $(PY) -m pytest; else \
	  echo "pytest not installed: running the test modules directly"; \
	  $(PY) tools/tests/test_closure.py && $(PY) tools/tests/test_scope.py && $(PY) -m refmodel.tests.test_cases && \
	  $(PY) -m pipeline.tests.test_frontend_eval1 && $(PY) -m validation.tests.test_certificates; fi
	$(PY) -m refmodel.selftest --iterations 3000

selftest:
	$(PY) -m refmodel.selftest --iterations 20000

closure:
	$(PY) tools/closure.py --manifest manifest.toml --out closure.lock.json

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

check: closure targets-closure lint test verify probes slice int-test targets-check staging-check

clean:
	rm -rf build runtime/build pipeline/examples/out/*.bin .pytest_cache .hypothesis
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
