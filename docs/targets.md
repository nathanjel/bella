# Target programs for the first compilation attempt

*Status: recommendation, 2026-11-01. Inputs: the sources of 23 candidate libraries (cloned at
head, scored with `tools/score_candidate.py`), the dynamic import closure of each finished
program against `manifest.toml`, and two runs of every program under different hash seeds.
Everything measured here is reproducible with `python3 targets/run_targets.py` and the two
scripts named in section 6.*

*Imported into the repository and re-checked on 2026-11-01, against the CPython 3.15.2 pin and
the manifest as closed on it (175 modules):*

* *Recorded on 3.15.2, authoritative: every program prints the same bytes as on 3.13.18, under
  both hash seeds, and again under the phase-1 configuration (the manifest's omissions and the
  codecs outside the phase-1 set blocked at start-up, as deviation D-20 is simulated).*
* *Loaded on 3.15.2, the five library programs stay inside the manifest except for `optparse` and
  `configparser` (pycodestyle), as below; `cli_easy_slugs` needs nothing outside it.*
* *Closures on the pin (`make targets-closure`, 2026-11-01): the five targets other than
  `cli_tricky_check` are closed, two of them with a declaration of their own in `targets.toml`
  (humanize's `_get_default_locale_path`, mistune's plugin loader). The increments: 1a (the easy
  three) is 149 manifest modules with 71,219 compiled source lines; the tricky three add 6
  modules (`html`, `html.entities`, `signal` and three core ones) plus pycodestyle's `optparse`
  and `configparser`; 25 manifest modules, `unittest` and `logging` among them, are reached by
  no target (1c).*
* *Section 5: item 6 is done (the manifest's `[dynamic]` table reviews each computed-import site
  and lists the modules it must reach, review log RL-56); item 2's deviation would be D-21, since
  D-20 is now the phase-1 omissions; item 5's HACL\* code is what spec section 7 would map the
  digests onto instead of BearSSL or libsodium, which is the author's choice.*
* *Decided by the author the same day: `cli_easy_slugs` no longer uses `unicodedata` (it drops
  non-ASCII characters instead of decomposing them), so `unicodedata` stays \[P2+\]; each
  phase-1 increment is the closure of its target programs (design section 11); items 4 and 5 of
  section 5 (zlib's licence, the source of the hash primitives) join the licence register,
  `docs/licences.md`, to be settled when worth it.*

## 1. Recommendation

Six programs, two per shape, all under `targets/`. The **first attempt is the easy three**, in
this order; the tricky three are the next review's material (Gate 1).

| Order | Target | Shape | Library | Why this one |
| --- | --- | --- | --- | --- |
| 1 | `cli_easy_slugs` | CLI, easy | none (stdlib) | The slice plus `str`, `re`, `Counter` and argparse (`unicodedata` dropped on 2026-11-01). No third-party code; everything it needs is already in the manifest. Argparse is the shared cost of every CLI and brings the first tier-2 object (`Namespace`, written with `setattr(namespace, dest, value)`). |
| 2 | `service_easy_tokens` | service, easy | itsdangerous 2.3.0.dev (868 lines, BSD-3) | Smallest library of the six. Exceptions as control flow with payloads, the `bytes`/`str` boundary, `json`, `struct`, `base64`; the first *mapped* modules with real implementations behind them (`_sha1`/`_sha2`, `zlib`). A subclass overriding a method the library calls back (`ClockedSigner.get_timestamp`). |
| 3 | `data_easy_sales` | data, easy | humanize 4.14.0 (1,316 lines, MIT) | `csv`, `Decimal` on the pure-Python `_pydecimal` (exact-int heavy), `Fraction`, `statistics`, `defaultdict`, format specs; humanize's `threading.local` with `getattr(..., default)`. |
| 4 | `service_tricky_markdown` | service, tricky | mistune 3.4.0 (3,145 lines loaded, BSD-3) | Tier 2 by construction: method tables built with `getattr(self, "parse_" + name)`, renderer dispatch through `object.__getattribute__(self, token["type"])`, plugins loaded by name with `importlib.import_module`, regex-driven parsing with `lastgroup`. |
| 5 | `data_tricky_toml` | data, tricky | tomlkit 0.15.2 (4,715 lines, MIT) | The deepest object-model stress: subclasses of `str`, `int`, `float`, `list`, `dict`, `datetime` with extra state and `__new__`, ABC mixins mixed with builtins, `copy.copy` through `__reduce_ex__`, 58 classes. |
| 6 | `cli_tricky_check` | CLI, tricky | pycodestyle 2.15.0 (2,176 lines, MIT) | Introspection: `inspect.signature(check).parameters` and `check.__doc__` at import, `getattr(self, name)` per check argument, `options.__dict__.update(kwargs)` on an `optparse.Values`, 66 generators, the `_tokenize` core module. The only target that **grows the manifest** (`optparse`, `configparser`). |

If only one program can be taken through end to end for Gate 0, it is `cli_easy_slugs`: the
"done when" of `TODO.md` task 4 is written for it.

What was changed to make the programs deterministic and dependency-closed is in section 3; the
decisions this work surfaced are in section 5. Every program prints the same bytes under
`PYTHONHASHSEED=0` and `1`; their recordings are under `targets/expected/` (first recorded on
CPython 3.13.18, non-authoritative; recorded again on the pinned 3.15.2 on 2026-11-01, with
identical output).

## 2. The six programs

| Target | Driver | Library (commit, date) | Vendored lines | stdlib modules (pure-Python lines) | Outside the manifest | Dialect profile (`score_candidate`) |
| --- | --- | --- | --- | --- | --- | --- |
| `cli_easy_slugs` | 62 lines | — | 0 | 53 (20.7k) | — | tier 0; 2 comprehensions, f-strings, keyword-only args |
| `cli_tricky_check` | 30 | pycodestyle `3cee4cc`, 2026-10-13 | 2,176 | 66 (27.9k) | `configparser`, `optparse` | computed `getattr`/`setattr`, `__dict__` write, `inspect.signature`, 66 generators, 30 decorators, one dead `compile()` |
| `data_easy_sales` | 47 | humanize `38d9d91`, 2026-11-01 | 1,316 | 63 (20.9k) | — | tier 1: `threading.local` + `getattr(obj, "locale", None)`; 11 `try`, 23 f-strings |
| `data_tricky_toml` | 41 | tomlkit `d7def7d`, 2026-10-29 | 4,715 | 71 (27.2k) | — | 17 multiple-inheritance classes (builtins + ABCs), `__new__` ×6, `__reduce_ex__`, 58 classes, 79 decorators |
| `service_easy_tokens` | 87 | itsdangerous `672971d`, 2025-06-14 | 868 | 65 (20.5k) | — | tier 0/1: `Generic[...]` bases, one mixin, 18 classes, 14 `try` |
| `service_tricky_markdown` | 42 | mistune `f7ec702`, 2026-10-24 | 3,145 (19 of 39 modules load) | 81 (33.4k) | — | computed `getattr` ×3, `object.__getattribute__` ×1, `import_module` ×1, `ABCMeta` (directives, not loaded), 31 classes |

"stdlib modules" is the dynamic closure of the finished program on this host (union of
`-X importtime` and the `sys.modules` difference, since `importtime` does not log
`importlib.import_module`), minus the imports the manifest omits. The line counts are of
CPython 3.13's pure-Python sources and are indicative only: on the manifest, `datetime` and
`decimal` run on `_pydatetime` and `_pydecimal` (about 9k lines together), which this host never
loads because it has the C modules. The authoritative closure is `tools/closure.py` on the pin
(3.15.2 since 2026-11-01).

Licences: pycodestyle Expat (MIT), humanize MIT, tomlkit MIT, itsdangerous BSD-3, mistune
BSD-3 — all shippable. Each is vendored as a snapshot of the commit above with its licence file
beside it (`targets/vendor/LICENSE.<name>`), not installed, so the programs are closed over
exactly the code that was read.

### 2.1 `cli_easy_slugs` — slugify lines of text

Stdlib-only replacement for python-slugify (which depends on `text-unidecode`, so it could not
be vendored closed, and loads its transliteration backend with `import_module`,
`slugify/_legacy.py:56-62`). NFKD-decompose, drop combining marks, lower-case, collapse to
`[a-z0-9]+` joined by `-`, cut to `--max-length` at a word boundary, count duplicates. It does
not transliterate scripts without a Latin decomposition (`'東京タワー' -> ''` is the recorded
behaviour), which is the honest stdlib answer and a nice fixed point for the Unicode tables.

Exercises: `argparse` (2.7k lines; `BooleanOptionalAction`; `HelpFormatter` calls
`shutil.get_terminal_size()` from `add_argument`, so `shutil` and `COLUMNS` are live in every
argparse program), `re` (the `_sre` engine, mapped), `str` methods (`unicodedata.normalize` and
`combining` until 2026-11-01, when the author lowered the requirements: `unicodedata` stays
\[P2+\]), `collections.Counter`, `pathlib.Path.read_text`.
Argparse's `Namespace` is written with `setattr(namespace, self.dest, values)`
(`argparse.py:975`) — the first `MAY_RECEIVE_COMPUTED_WRITES` object every CLI target meets.

### 2.2 `cli_tricky_check` — run pycodestyle over a file and summarise by code

`pycodestyle.StyleGuide(paths=[...], max_line_length=88, ignore=["W6"]).check_files()`, then
`report.counters` sorted. Exit status 1 when anything was reported (recorded).

What makes it tricky, with the lines:

* **Registration by introspection.** Every check is decorated with `@register_check`, which
  reads the parameter names with `inspect.signature(function).parameters`
  (`pycodestyle.py:168`) and the error codes out of `check.__doc__` with a regex (`:183`). The
  compiled function objects must carry their signature and their docstring. `inspect` itself
  is in the manifest; whether compiled functions answer `inspect.signature` is a clause the spec
  does not have yet (section 5).
* **Computed attribute reads.** `run_check` does `arguments = [getattr(self, name) for name in
  argument_names]` (`:1960`): tier 2 reads on `Checker` with a bounded name set — exactly the
  computed-name path of the object model.
* **Computed attribute writes.** `StyleGuide.__init__` does `options.__dict__.update(options_dict)`
  on an `optparse.Values` (`:2361`): a dictionary write through `__dict__` on an object of a
  class that never names those attributes. Live in this program (`max_line_length`, `ignore`).
* **Generators everywhere** (66 `yield`s): the tokenizer pipeline, `tokenize.generate_tokens`
  over the C tokenizer (`_tokenize`, a *core* module the runtime must provide — Python's
  tokenizer ported, not the parser).
* **Two stdlib modules outside the manifest.** `process_options` always builds an
  `optparse.OptionParser` and parses the path list with it, then `read_config` constructs a
  `configparser.RawConfigParser` and walks the parents of the checked path looking for
  `setup.cfg`/`tox.ini` (`:2558` ff.). Taking pycodestyle means adding `optparse` and
  `configparser` (both pure Python) to the phase-1 manifest and re-running the closure. The
  directory walk also makes the output depend on the environment; the recording was made in
  a tree without those files.
* **A dead excluded call.** `check_ast` compiles the file with `PyCF_ONLY_AST` (`:2056`) but is
  reached only when `_ast_checks` is non-empty, which needs a plugin. The linter will flag
  `compile()` under E-01; the program is still in the dialect because the call is unreachable
  for this configuration. How the pipeline treats *reachable-in-principle but dead* excluded
  calls is a decision (section 5).

### 2.3 `data_easy_sales` — totals, shares and buckets from a CSV

`csv.DictReader` → `defaultdict(Decimal)` per region and per month, `ROUND_HALF_EVEN`
quantisation, `Fraction(...).limit_denominator(100)` shares, `statistics.mean/median`,
`humanize.intword/intcomma/naturalsize`. Exercises exact arithmetic end to end: `_pydecimal` is
6.2k lines of pure Python built on `int`, so this program is the real test of `bella::Int`
beyond the slice. In humanize, `i18n.py` keeps the active locale in a `threading.local` and
reads it with `getattr(_CURRENT, "locale", None)` (`:56`, `:203`, `:212`) — an attribute that
may be absent, on a thread-local object; `gettext.NullTranslations` is the default translation
and `importlib.resources` is only reached by `activate()`, which the program never calls.
humanize's generated `_version.py` is not in the repository; `vendor/humanize/_version.py`
pins `__version__ = "4.14.0"`.

### 2.4 `data_tricky_toml` — round-trip edit of a `pyproject.toml`

Parse with tomlkit, bump the patch version, append a dependency and sort the array, add a
`[tool.bella]` table, dump, re-parse, compare. Comments and formatting survive, which is the
point of tomlkit and what makes it a style-preserving *document* model rather than a data
model.

What makes it tricky (all live in this program):

* `class String(str, Item)` (`items.py:2254`), `Integer(Item, _CustomInt)` (`:632`),
  `Array(Item, _CustomList)` (`:1421`), `AbstractTable(Item, _CustomDict)` (`:1788`),
  `DateTime(Item, datetime)` (`:1060`): builtin subclasses carrying trivia, comments and
  indentation, created through `__new__` (`:637`, `:860`, `:1065`, `:2259`). The object model
  needs a layout for "a `str` with promoted fields and a dict".
* `_CustomList(MutableSequence, list)`, `_CustomDict(MutableMapping, dict)`,
  `_CustomInt(Integral, int)` (`_types.py:44-71`): ABCs mixed into builtins, so `ABCMeta`,
  `__abstractmethods__` checks and the mixin methods of `collections.abc` run at class-creation
  time — the staging path of the design.
* `copy.copy()` through `__reduce_ex__`/`_getstate` (`items.py:567-571`,
  `container.py:1072-1099`): the copy protocol over those subclasses.
* `inspect.signature(encoder)` (`items.py:225`) is reached only for registered custom encoders:
  dead here.

### 2.5 `service_easy_tokens` — sign and verify session tokens

A `handle(request, serializer)` function over a JSONL stream of `sign`/`verify` requests:
200 on success, 400 on a tampered token, 401 on an expired one, 404 on an unknown op. All four
statuses are exercised by the recorded run.

itsdangerous reads the clock in the *signer* (`timed.py:33`, `int(time.time())`), not in the
serializer, so the driver injects it there: `ClockedSigner(TimestampSigner)` overrides
`get_timestamp()`, and `ClockedSerializer(URLSafeTimedSerializer)` passes `signer=ClockedSigner`
and attaches the clock in `make_signer()`. Requests advance the clock (`"advance": 7200`), which
is how a `max_age=3600` token expires deterministically. This is a small but real pattern: a
library calling back into a user subclass through a method it defined.

Mapped modules with substance behind them: `hashlib` falls back to the builtin `_sha1`/`_sha2`
modules because the manifest omits `_hashlib` (OpenSSL is Apache-2.0: out), `hmac` then runs
its pure-Python path over those objects; `zlib.compress` is tried on every payload
(`url_safe.py`, `URLSafeSerializerMixin.dump_payload`); `base64`, `struct`, `binascii`, `json`
(the pure-Python `json.decoder/encoder/scanner` are compiled; `_json` is mapped).
`URLSafeTimedSerializer(URLSafeSerializerMixin, TimedSerializer[str])` subscripts a generic
base at class-definition time — `typing` machinery that staging executes once.

### 2.6 `service_tricky_markdown` — render Markdown requests to HTML

`handle(request)` builds a `mistune.create_markdown(escape=..., plugins=[names])` renderer per
request and returns the HTML, its length and a status; a missing plugin is a 400 with the
exception class name (`ValueError`, from `name.rsplit(".", 1)` unpacking in
`plugins/__init__.py:45`).

What makes it tricky, all live:

* `BlockParser.__init__`/`InlineParser.__init__` build `self._methods = {name: getattr(self,
  "parse_" + name) for name in ...}` (`block_parser.py:108`, `inline_parser.py:118`): computed
  attribute reads whose names are string arithmetic over a class-level list.
* `BaseRenderer._get_method` resolves token types with `object.__getattribute__(self, name)`
  and falls back to a name-mangled private dict `self.__methods` (`core.py:274-281`); plugins
  register renderers as `lambda *arg, **kwargs: method(self, *arg, **kwargs)` (`:272`).
* `import_plugin(name)` maps a plugin name through a dict of `"module.func"` strings and calls
  `importlib.import_module(module_path)` (`plugins/__init__.py:42-48`): a dynamic import with
  a closed, enumerable set of targets. The closure tool must be told about
  `mistune.plugins.{table,formatting,task_lists,footnotes}` (a `[lazy_unsupported]`-style
  per-API entry or explicit roots); in this program they are the only four reached.
* Regex-driven scanning: `re.finditer`, `m.lastgroup` dispatch (`core.py:251-253`),
  alternation patterns composed at runtime from the rule table.
* `html.escape` and the private `html._replace_charref` (`util.py:7`) — a closed-world program
  may reach into stdlib privates; the manifest compiles `html` whole.
* `mistune.directives` (the one `ABCMeta` metaclass) is never imported by this program.

## 3. What had to change, and what was rejected

Changes to make the six closed and deterministic:

* python-slugify → stdlib slugify (section 2.1). The removed `vendor/slugify/` is not missed.
* humanize: added the generated `_version.py`.
* itsdangerous: clock injected into the signer; requests carry `advance`.
* All drivers: inputs are files in `targets/data/`, outputs are stdout + exit status, no
  wall-clock, no randomness, no network, no environment reads beyond what argparse does
  (`COLUMNS` is pinned by the harness).

Rejected candidates, with the construct that decided it (all read in the sources):

| Candidate | Shape | Why not |
| --- | --- | --- |
| click 8.x (BSD-3) | CLI | `sys._getframe`/`inspect.currentframe`/`inspect.stack` (E-02) in the context and decorator machinery; 9 `__getattr__`, 11 MI classes; `termios`, `tty`, `shlex`, `getpass` outside the manifest. |
| pyflakes (MIT) | CLI | `ast.parse(codeString)` at run time (`api.py:39`): the whole Python parser as a runtime dependency. Not E-01 (nothing executes), but the biggest core module imaginable for a first attempt. |
| Python-Markdown (BSD-3) | service | `sys._getframe(size)` + `frame.f_back` (`util.py:169-172`, E-02); `xml.etree`, `optparse` outside; optional `pygments`/`yaml`. |
| werkzeug (BSD-3) | service | 18.4k lines; `exec()` ×2, `compile()`, frames ×10, `__getattribute__` ×2, `__class__` assignment; `markupsafe` dependency; 17 stdlib modules outside. |
| starlette (BSD-3) | service | 244 `await`/138 `async def` — P2+; `anyio`. |
| attrs (MIT) | data | Generates `__init__` with `compile()` + `eval()` (`_make.py:217-228`, E-01). |
| boltons (BSD-3) | data | frames ×16 (E-02), `exec()` ×3, 15 stdlib modules outside. |
| packaging (Apache/BSD dual) | data | `ctypes`, `platform`, `sysconfig`, `email.*` outside the manifest; one `compile()`. |
| pyparsing (MIT) | data | `f_locals` ×2 (E-02), `vars()`/`globals()`/`locals()` ×10, 21 class-attribute writes after definition, 11 star imports. |
| python-dotenv (BSD-3) | data | `sys._getframe` + `f_back` in `find_dotenv` (E-02); `shlex` outside. |
| PyYAML (MIT) | data | A plausible tricky-data alternative (16 MI classes, one metaclass) but 36 star imports fail the lint-clean input rule and the C `_yaml` path must be cut; tomlkit stresses the same mechanisms with a smaller, cleaner surface. |
| toolz (BSD-3) | data | Clean (`__slots__`, no exclusions) but curried call-signature introspection (`inspect.signature` on every curried function) is the pycodestyle stressor again, in a less interesting program. |
| pathspec | CLI | Clean, no dynamism, `__slots__` ×13 — the best *alternative* easy CLI library (gitignore matching), but licensed MPL-2.0 today (`pyproject.toml:31`; a relicensing to MIT is in progress, `LICENSING.md`). Out until that completes. |
| idna (BSD-3) | data | 20k lines of tables, `array` outside the manifest; nothing to learn from it. |
| schedule (MIT) | service | Clean and small (732 lines) but built on `datetime.now()`/`time.time()`; a deterministic program needs most of it mocked. |
| tenacity | — | Apache-2.0: not shippable. |
| advent-of-code-wim | — | WTFPL; numpy/scipy/z3 — out of scope. |

## 4. Shared costs the manifest already carries

Everything below is in the phase-1 manifest and is paid once, whichever target goes first;
the per-target numbers in section 2 include it.

* `re` and its `_sre` engine (mapped): all six programs. The parser/compiler halves of `re`
  are pure Python and compile; the matcher is a C++ port of `_sre` with identical semantics,
  not a regex library swap.
* `argparse` + `gettext` + `shutil.get_terminal_size` (compiled/mapped): both CLIs.
* `typing` (compiled, 3.5k lines) and `_typing` (mapped): itsdangerous, tomlkit, mistune —
  executed at import, mostly dead afterwards; a staging candidate.
* `dataclasses` → `inspect` → `ast`, `dis`, `opcode`, `tokenize`, `token`, `linecache`
  (compiled, ~8.7k lines) and `_ast`, `_tokenize` (core): tomlkit and mistune import
  `dataclasses`; pycodestyle imports `inspect` directly. The easy three reach the same chain
  without calling it (review log RL-86): `enum.EnumType.__signature__` imports `inspect`, and
  argparse's lazy `_colorize` imports `dataclasses`. The `[adaptations]` entry for
  `inspect` in the manifest is where this chain gets cut if it must be.
* `json` (compiled pure-Python paths; `_json` mapped), `datetime` on `_pydatetime`, `decimal`
  on `_pydecimal`: the two services and the data scripts.
* `unicodedata` (mapped): UCD tables generated from the Unicode data files (Unicode licence,
  permissive), not copied from CPython. No target uses it since 2026-11-01; `urllib.parse`
  reaches it lazily. The licence is entry L-03 of `docs/licences.md`.
* `hashlib` → `_sha1`/`_sha2`/`_md5`/`_blake2` (mapped), `zlib` (mapped): the token service.

## 5. Decisions and clauses this surfaced

1. **Function metadata at run time.** pycodestyle needs `inspect.signature(f).parameters`
   (names and kinds) and `f.__doc__`; tomlkit and toolz would too. Proposal: compiled function
   objects carry a static signature record and their docstring; `inspect.signature` is answered
   from it; `__code__` stays excluded (E-05). Needs a spec clause (C-3-09?) and a conformance
   case before the function-object layout is fixed.
2. **Dead excluded calls.** `pycodestyle.check_ast` contains `compile()` on a path this
   program never takes. Options: (a) the linter rejects any program whose closure contains an
   excluded call — pycodestyle is then out; (b) the call compiles to a `bella::Excluded` throw
   and the linter reports it as a warning with the call site — the program is in, the
   behaviour is exact up to the point where CPython would have compiled source. (b) matches
   "never approximate" and is the recommendation; it needs a deviation entry (D-21; D-20 is now
   the phase-1 omissions) because a
   CPython run with a tree plugin would succeed where Bella throws.
3. **Manifest growth.** `optparse` and `configparser` for pycodestyle: ~2.9k pure-Python lines,
   no C dependencies. Accept, or swap pycodestyle for pathspec (clean, no growth, less
   interesting).
4. **zlib's licence.** `zlib` is reached by itsdangerous (and by `shutil`). The zlib licence is
   permissive but is not MIT/BSD/ISC by name; either admit it to the allowed list or map `zlib`
   onto miniz (MIT). A one-line decision for `DECISIONS.md`.
5. **Hash primitives.** No OpenSSL (Apache-2.0). The natural source for `_sha1`/`_sha2`/`_md5`/
   `_blake2` is the HACL* C code CPython itself vendors under `Modules/_hacl`: formally verified,
   generated C, **MIT-licensed** (INRIA, CMU, Microsoft; checked in the file headers). Taking it
   keeps the digests bit-identical to the reference interpreter's fallback path. Public-domain
   alternatives exist (Steve Reid's SHA-1, Brad Conte's crypto-algorithms) if a smaller
   dependency is preferred.
6. **Dynamic import with enumerable targets.** `mistune.import_plugin` and argparse-free
   plugin registries in general: the closure tool should accept a per-call-site list of
   admissible module names (today: `[lazy_unsupported]` per API or explicit roots). Tooling,
   not spec.

## 6. Reproducing the numbers

```
python3 targets/run_targets.py list
python3 targets/run_targets.py record --allow-unpinned     # or `make targets-record` in the image
python3 targets/run_targets.py check                       # two hash seeds, exit status, stderr
python3 -I tools/score_candidate.py --manifest manifest.toml targets/drivers/*.py targets/vendor/*
```

`targets/closure-summary.json` was the dynamic closure of each program as measured for this
document (host CPython 3.13.18). Since 2026-11-01 it is regenerated by `make targets-closure`
(`tools/closure.py --all-targets` on the pin): each target's static and runtime closure, its
lock under `targets/closure/`, and the phase-1 increments derived from them. Candidate clones were read at the commits in section 2 and in the table of section 3;
they are not part of the repository.
