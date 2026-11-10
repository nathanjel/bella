Round 19 (R19), 2026-11-10: gemini-3.8-flash, run by the author on the request of the same day; it came as `R19-review.md` and twice under the reviewer's name
(`gemini-38-flash-2026-11-10.md` and `.mc`), three identical files. Verbatim. Its range is `28f1105..17f9262` (3 commits: the dry run confined and the import
system's modules, the two hooks, `os.scandir`); it ran in its own worktree (`bella-r19`) at `17f9262`. Two findings, RL-422 and RL-423; its probes (`review-r19/`)
stayed in that worktree.

---

# Bella review, round 19

Reviewed `28f1105..17f9262` in the separate detached `bella-r19` worktree at `17f9262`. Reference: CPython 3.15.2 (`uv run python`). Native builds ran sequentially with `BELLA_JOBS=8`.

## R19-01 — P1: atexit callbacks escape dry-run confinement and perform writes during build

**Location:** `pipeline/staging/dryrun.py:254` (the early return when `_bodies` is empty; effect checking follows at line 256).

A module body can register an ordinary atexit callback that opens a file for writing, spawns a process, or deletes files. When the dry-run interpreter exits, that callback runs after module-body tracking has ended. In `_loader_exec`, the `finally:` block pops `_bodies`. When Python's shutdown sequence executes `atexit` callbacks, `_bodies` is empty. `_audit` returns immediately before testing effect events or write flags, so the side effects execute unconfined against the build host, and no confinement note is recorded. This requires neither ctypes nor a previously opened descriptor. Compilation alone (`build.py` without `--run`) changes host files.

Reproducer, also saved as `review-r19/effect.py`:

```python
import atexit
exec('x = 1')
def finish():
    with open('/tmp/bella-r19-effect.txt', 'a') as f:
        f.write('effect\n')
atexit.register(finish)
print('body')
```

Starting with the target file absent, run:

```sh
BELLA_JOBS=8 uv run python pipeline/build.py review-r19/effect.py
```

**Bella output:** the executable path, status 0, and no confinement note. Crucially, this is **build only**, without `--run`. The build created the file on the host machine with these contents:

```text
effect
effect
```

**CPython output**, `uv run python review-r19/effect.py`:

```text
body
```

Status 0; one execution appends exactly one `effect` line. Running that reference command after the build changed the observed two-line file into a three-line file. `review-r19/effect-after-build.txt` preserves the two-line build-only result; `r19buildout` and `r19builderr` preserve the build streams.

The regression is that any such write occurs while compiling. Confinement must also cover deferred callbacks registered by the program, or prevent them from being executed by the staging interpreter. Keeping the current `_bodies`-only predicate leaves shutdown effects outside the check.

---

## R19-02 — P2: socket.sethostname in module body crashes dry-run audit hook with IndexError, dropping confinement record and build note

**Location:** `pipeline/staging/dryrun.py:237`

`_confine` hardcodes `args[1]` for all `socket.*` audit events:

```python
    elif event.startswith("socket."):
        what = f"{event}({args[1]!r})"
```

While socket operations such as `socket.connect`, `socket.bind`, `socket.sendto`, and `socket.sendmsg` pass `(socket, address)` (where `args[1]` is the target address), `socket.sethostname(name)` passes a 1-tuple `(b'name',)` (`len(args) == 1`). Accessing `args[1]` raises `IndexError: tuple index out of range` inside the audit hook before `_confined.append(...)` or `raise Confined(...)`.

In `dryrun.py`, this `IndexError` aborts module execution and is caught by `_import_entry` as `failed_imports["__bella_entry__"] = "IndexError"`. Because `_confined` is never populated:
1. `pipeline/build.py:361` finds `made["confined"]` empty and emits **no build note** (`bella: note: ...: the dry run of this module body ended here...`).
2. `dryrun.py:485` does not record the confinement site under `unstaged["*"]`.
3. When the compiled program runs and reaches definition-time code after `socket.sethostname`, the runtime aborts with generic error `E-01: exec at ... of a text the dry run did not stage` without the required diagnostic explaining where the dry run stopped.

Reproducer, saved as `review-r19/test_unstaged_sock.py`:

```python
exec("a = 1")
import sys
sys.audit("socket.sethostname", "foo")
exec("b = 2")
```

Captured outputs are in `review-r19/r19sock*`.

**CPython output**, `uv run python review-r19/test_unstaged_sock.py`:
Exits 0 with empty stdout and stderr.

**Bella build output**, `BELLA_JOBS=8 uv run python pipeline/build.py review-r19/test_unstaged_sock.py`:
```text
/home/nathan/workspaces/nth/bella-r19/build/compiled/test_unstaged_sock-3caeffa7388bc2a5/test_unstaged_sock
```
Status 0. No note emitted.

In contrast, any working confined effect (e.g. `sys.audit("os.remove", "foo")` in `review-r19/test_unstaged_rm.py`) produces the required build note:
```text
bella: note: /home/nathan/workspaces/nth/bella-r19/review-r19/test_unstaged_rm.py:3: the dry run of this module body ended here, at os.remove('foo'): a module body's effects on the world are not performed at build time. Definition-time code the body reaches after this line is not staged and stops the program by name (docs/staging.md)
```

**Bella run output**, `BELLA_JOBS=8 uv run python pipeline/build.py --run review-r19/test_unstaged_sock.py`:
Status 70.
Stderr:
```text
bella: not implemented: E-01: exec at __main__:<module> of a text the dry run did not stage (spec section 8)
```
The reason clause (`; the dry run stopped at test_unstaged_sock.py:3 (socket.sethostname('foo')), so what the module body does after that line was not staged`) is completely omitted.

---

## Other validation and limits

Saved differential programs and captured streams are in `review-r19/` (`*ref` is CPython stdout, `*out` is Bella stdout, `*err` is Bella stderr).

- `surface.py`: importer-class member presence (`FrozenImporter`, `PathFinder`, `FileFinder`, `BuiltinImporter`, `SourceFileLoader`), bound-method `__doc__` forwarding to the underlying function, and manual `sys.excepthook` attaching a supplied traceback matched exactly.
- `scan.py`: file/link stat-cache identity (`e.stat() is e.stat()`, `e.stat(follow_symlinks=False) is e.stat()`), `follow_symlinks` behavior, str and bytes entry names, descriptor paths after iterator closure, `ResourceWarning` as an unraisable error, and warning filename/line matched exactly.
- `excepthook.py`: hook arguments and `sys.last_exc`, `sys.last_type`, `sys.last_value`, `sys.last_traceback`, replacing the hook during its call, `SystemExit` from the hook, and atexit execution matched; both exited with status 7.
- `hooks.py`: destructor exception delivered to `sys.unraisablehook` matched after deliberately omitting the nondeterministic function address from the printed message.
- Destructor and generator closure unraisable hooks, `sys.stderr = None`, `sys.excepthook = None`, `sys.unraisablehook = None`, and hook replacement matched CPython semantics.
- `test_walk_glob_rmtree.py`: `os.walk`, recursive `glob.glob`, and `shutil.rmtree` descriptor-based cleanup matched byte-for-byte.
- Existing `test_where_the_dry_run_is_confined` passed: direct and indirect source locations, ordinary exception handling, BaseException interception, finally blocks, main guards, executed text, and imported program modules.
- `tempfile.gettempdir()` candidate-directory probing exemption in `_confine` was verified: candidate file creation/deletion inside `_get_default_tempdir` correctly does not trip confinement.

These are targeted checks, not exhaustive conformance. No full test suite was run; not every importer operation, hook failure combination, filesystem error, or walk/glob/rmtree case was exercised. Known exclusions in the request are not reported.
