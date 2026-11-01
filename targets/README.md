# Target programs (phase 0, Gate 0 task 4)

Six programs for the first complete compilation path: for each of the three shapes the design
document names (CLI tool, data script, service handler) one *easy* and one *tricky* program.
Each is a real, deterministic program with observable output over fixed inputs, so it is a
conformance case from day one: CPython records, the compiled binary must reproduce.
`docs/targets.md` holds the comparison, the sources that were read and the recommendation
(first attempt: the three easy ones, `cli_easy_slugs` first).

```
targets.toml        the registry: kind, level, driver, argv, vendored packages, stressors
drivers/            one driver per target; the driver *is* the program
data/               the fixed inputs
vendor/             third-party code at a pinned commit, licence file beside each package
expected/           recorded stdout/stderr/exit status (+ .json: interpreter, authoritative?)
run_targets.py      record | check [--runner TEMPLATE] | list
closure/              each target's closure lock (`make targets-closure`, tools/closure.py --target)
closure-summary.json  every target's closure in brief, and the phase-1 increments derived from them
```

| Target | Shape | Library (pinned commit) | Licence |
| --- | --- | --- | --- |
| `cli_easy_slugs` | CLI, easy | stdlib only | — |
| `cli_tricky_check` | CLI, tricky | pycodestyle 2.15.0, `3cee4cc` (2026-10-13) | MIT (Expat) |
| `data_easy_sales` | data, easy | humanize 4.14.0, `38d9d91` (2026-11-01) | MIT |
| `data_tricky_toml` | data, tricky | tomlkit 0.15.2, `d7def7d` (2026-10-29) | MIT |
| `service_easy_tokens` | service, easy | itsdangerous 2.3.0.dev, `672971d` (2025-06-14) | BSD-3 |
| `service_tricky_markdown` | service, tricky | mistune 3.4.0, `f7ec702` (2026-10-24) | BSD-3 |

Run everything from the repository root:

```
python3 targets/run_targets.py list
python3 targets/run_targets.py record              # pinned CPython only; --allow-unpinned elsewhere
python3 targets/run_targets.py check               # CPython under two hash seeds
python3 targets/run_targets.py check --runner "build/targets/{name} {argv}"   # the compiled binaries
```

Rules for a target program (the same as for conformance cases): fixed inputs under `data/`,
no wall clock, no randomness, no network, output to stdout, exit status meaningful, stderr
empty on the recorded path. Vendored code is a verbatim snapshot: fix a library by pinning a
different commit, never by editing the snapshot (the one exception is a generated file the
repository does not contain, such as `humanize/_version.py`, noted in `docs/targets.md`).
