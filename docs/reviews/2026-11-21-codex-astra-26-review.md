Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A26 in the
review log. Its range is `50bb887..369abde`, one commit, run non-interactively (standard input closed) in its own worktree (`bella-r26`) at
`369abde`: the compiler's warnings of a main program's text at each start (RL-572, C-8-19, D-29). Its probes (`r26-probes/codex/`) stayed in
that worktree. Eleven findings; each program was run on both sides by the session before any verdict (review log, A26).

---

# A26 · Bella 50bb887..369abde

All probes used the detached checkout and the pinned CPython with PYTHONHASHSEED=0. Paths abbreviated as P below are the absolute paths of the indicated prog.py. The probe directories contain the input and raw byte streams.

The highest-impact findings are **A26-11** (ordinary digit-limit failure substitutes a different warning), **A26-05** (changing that limit during warning display reverses whether the body runs), and **A26-10** (a late cookie changes a compiled string value). Exact inputs and captured output are under [r26-probes/codex](r26-probes/codex/).

## A26-01 · Medium · A later syntax error erases earlier parser warnings

At pipeline/build.py:800 the build uses the recorded warnings only as a Boolean. At pipeline/build.py:801 module discovery can stop the build before line 830 prints them. The exception handler at line 942 prints only the refusal.

Minimal program (r26-probes/codex/late/prog.py, with an indented pass on the third line):

~~~~python
a='\q'
if :
 pass
~~~~

CPython, status 1, empty stdout, stderr:

~~~~text
P:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  a='\q'
<input>:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  File "P", line 2
    if :
       ^
SyntaxError: invalid syntax
~~~~

Bella build, status 70, empty stdout, stderr:

~~~~text
bella: refused: invalid syntax (prog.py, line 2)
~~~~

## A26-02 · Low · Build diagnostics reorder warnings in a package

At pipeline/build.py:784 the build prints diagnostics in module-discovery order. Discovery queues siblings before scanning their dependencies (pipeline/closed_world.py:323). CPython compiles the package and executes its imports before starting the next top-level import.

| File in the package probe | Complete source, one statement per line |
|---|---|
| prog.py | `import pkg`, `import other`, `import pkg`, `print("ran")` |
| pkg/__init__.py | `from . import leaf`, `a='\k'` |
| pkg/leaf.py | `a='\q'` |
| other.py | `a='\y'` |

CPython's first start prints `ran` and exits 0. Its stderr contains the invalid-escape diagnostics in the order **pkg/__init__.py:2, pkg/leaf.py:1, other.py:1**. Bella's successful build prints the executable path and the same three two-line diagnostics in the order **pkg/__init__.py:2, other.py:1, pkg/leaf.py:1**. The executable and CPython's second start both print `ran` with empty stderr. Full streams are in r26-probes/codex/package.

## A26-03 · Low · Build prints a source line the warning formatter omits

Minimal program in tokshadow/prog.py is `print(42)` followed by `a='\q'`. Adjacent tokenize.py contains `print("local tokenize")`. CPython imports that module while looking up the source line. It has no open function, so the warning formatter emits just the header. Both CPython starts and the executable exit 0, print `local tokenize\n42\n`, and produce the same single warning header on stderr. The successful build prints its binary path and the identical header **plus** `  a='\q'\n`. At pipeline/build.py:788 the build decodes the file itself and at line 792 prints the stripped line, bypassing the program's source lookup.

## A26-04 · Low · The warning and bootstrap modules have a different insertion order

Program in state/prog.py:

~~~~python
import sys
print(list(sys.modules))
a="café \q"
~~~~

Both sides exit 0 with identical warning bytes. In the printed list CPython orders the common modules `_thread, _warnings, _contextvars, _py_warnings, warnings`. Bella orders them `_contextvars, _warnings, _thread, _py_warnings, warnings`. These are projections of the complete stdout saved as state/py.out and state/bin.out. The difference persists with fd 2 closed. Bella initializes the Python implementation of _warnings during bootstrap (runtime/src/imports.cpp:1235), which itself imports _contextvars, then replays the warning through the previously initialized module (runtime/src/call.cpp:3534). The finding concerns the order of modules present on both sides.

## A26-05 · High · Changing the digit limit during a warning lets rejected code run

At runtime/src/call.cpp:3548 Bella chooses the refused literal **before** delivering the first warning. CPython resumes parsing after displaying the warning and consults the digit limit then in effect. This requires no warning filter or startup option.

Minimal files in tighten/ (replace N by 641 consecutive ASCII nines):

~~~~python
# prog.py (the file starts with the assignment)
a='\q'
b=N
print('ran')
~~~~

~~~~python
# warnings.py
import sys
sys.set_int_max_str_digits(640)
~~~~

CPython's two starts both exit 1 with empty stdout. Stderr gives the ordinary two-line invalid-escape warning at P:1, then:

~~~~text
  File "P", line 2
    b=N
SyntaxError: Exceeds the limit (640 digits) for integer string conversion: value has 641 digits; use sys.set_int_max_str_digits() to increase the limit - Consider hexadecimal for huge integer literals to avoid decimal conversion limits.
~~~~

Bella exits 0 and prints `ran\n`. Stderr ends after the identical escape warning. The build and both runs began with PYTHONINTMAXSTRDIGITS unset.

The converse also reproduces in loosen/. Its warnings.py calls `sys.set_int_max_str_digits(0)`. Built with the environment variable unset, then run with PYTHONINTMAXSTRDIGITS=640, CPython prints `ran\n` and exits 0 after the warning. Bella exits 1 after the warning and the same digit-limit SyntaxError shown above, with empty stdout. See the 640-py and 640-bin streams.

## A26-06 · Medium · A valid relative path makes a warning quote another file

In path/, create actual/sub/, make link point to actual/sub, and start `path/link/../prog.py` using the same relative argument on both sides. The selected file, actual/prog.py, contains `print('right')` and `a='\q'`. A different file, path/prog.py, contains two comment lines, the second reading `# unrelated second line`.

Both print `right\n` and exit 0. CPython's warning names **path/link/../prog.py:2** and quotes `  a='\q'`. Bella's warning names **path/prog.py:2** and quotes `  # unrelated second line`. The rest of the warning header is byte-identical. The filesystem resolves the symbolic link before interpreting the parent component. At pipeline/build.py:732 the emitted warning filename uses os.path.abspath, which discards that component lexically. Opening the original program during the build and reopening the recorded filename during warning display consequently reach different files.

## A26-07 · Low · A BOM conflicting with its cookie blames the wrong encoding

Minimal bytes in bom/prog.py are `EF BB BF` followed by `# coding: latin1\npass\n`. CPython exits 1 with empty stdout and stderr:

~~~~text
  File "P", line 1
    # coding: latin1
SyntaxError: encoding problem: latin1 with BOM
~~~~

Bella's build exits 70 with empty stdout and only `bella: refused: encoding problem: utf-8\n` on stderr. pipeline/build.py:800 discards the file compiler's diagnostic. Module discovery goes through importlib.util.decode_source at pipeline/closed_world.py:48. Its encoding detection supplies the different error.

## A26-08 · Low · The harness accepts a real warning-filename mismatch

Run the two-line program from A26-03 as `r26-probes/codex/lineshadow/../lineshadow/prog.py`, without a local tokenize.py. Both sides exit 0 and print `42\n`. The warning and its source echo agree, except CPython retains `lineshadow/../lineshadow/prog.py:2` and Bella emits `lineshadow/prog.py:2`. Calling the actual conformance/harness.py:188 mask on the two stderr captures gives identical strings. Thus the harness's complete comparison passes for this real difference, even though the raw headers differ. Keeping a path relative to a shared checkout root would still permit moving the checkout and would preserve the distinguishing components. Reproducer and raw outputs are in maskprobe.py and mask/ under the probe directory.

## A26-09 · Medium · Rebuilding the warning-enabled variant deletes the last warning-disabled executable

Reproducer in switch.py, using one prog.py throughout:

1. Write `print("plain")`. CPython prints `plain\n`, empty stderr, status 0. Build on, then off. Both builds succeed, print the same executable path and have empty stderr. That path runs and matches CPython.
2. Append `a="\q"` and build **on only**. CPython and the new binary print `plain\n`, give the same two-line warning on line 2 and exit 0. The successful build prints the new path and the same diagnostic.
3. Launch the path returned by the last **off** build. exec fails with ENOENT. There is no child stdout, stderr or exit status. The raw launcher error is in switch/old-after.missing.

pipeline/build.py:845 returns a shared cached executable without recording the second variant as an owner. At pipeline/build.py:880 rebuilding the first variant removes its old directory unconditionally. The separate pointer keys therefore protect the two variants only when their binaries started out distinct.

## A26-10 · High · A comment on line three changes a string's value

Bytes of crcookie/prog.py, constructed as `"# first\rx=0\r# coding: latin-1\ra='é \\q'\rprint(a)\r".encode("utf-8")`. Every physical line ends in CR. The encoding declaration is too late to apply.

CPython prints `é \q` and a newline (initial bytes C3 A9). Bella prints `Ã© \q` and a newline (initial bytes C3 83 C2 A9). Both exit 0. Their two-line escape warnings agree byte for byte, even down to the echo reading `a='Ã© \q'` on both sides. Checking only the diagnostic would miss the value change.

At pipeline/closed_world.py:48, read_source passes the original bytes to importlib.util.decode_source. Its cookie reader reads to LF, sees the entire CR-delimited file as its first comment, and picks up the third line's cookie before newline translation. Feeding the probe's bytes to that exact decoder produced the mojibake used for lowering at pipeline/build.py:802. CPython's file compiler counts physical lines and uses UTF-8. Its linecache independently makes the same display mistake as Bella.

A related malformed-input result for A26-07 is in utf16/. For a UTF-16 BOM followed by UTF-16 `print('ran')\n`, CPython reports a SyntaxError for non-UTF-8 code starting with byte FF and no encoding declaration. Bella instead reports `source code cannot contain null bytes`. For A26-01, backsl/ and badimport/ retain further captures of diagnostics lost on a trailing backslash at EOF and on a syntax error in an imported module.

## A26-11 · High · A digit-limit failure replays the wrong warning

No shadow modules or custom filters are needed. In prefix/prog.py line 1 is `x=` followed by `"1_" * 640 + "1"`, a 641-digit decimal literal. The remaining lines are:

~~~~python
a='\q'
b=1if True else 0
print(b)
~~~~

Build with PYTHONINTMAXSTRDIGITS unset. Run both with PYTHONINTMAXSTRDIGITS=640. Both exit 1 with empty stdout. CPython's stderr begins:

~~~~text
P:3: SyntaxWarning: invalid decimal literal
  b=1if True else 0
~~~~

Bella's stderr begins:

~~~~text
P:2: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  a='\q'
~~~~

From `  File "P", line 1` to the end of the digit-limit SyntaxError, stderr is byte-identical. With the limit set to 641 both succeed, print `1\n`, and give both warnings, line 2 then line 3.

CPython's error handling tokenizes the remaining source to check for tokenizer errors (Parser/pegen_errors.c:134). This can warn for a later numeric token without parsing an earlier string escape. At pipeline/build.py:680 Bella retains only the **length** of the warning sequence from the failed compile. runtime/src/call.cpp:3551 takes that many warnings from the **successful** compile. Both lists have a first warning, but it is a different warning. The existing count assertion cannot distinguish them. The two 640 captures in prefix/ preserve the complete outputs.

## Source changes after the build

The num/ probe also ran from a different working directory with a copy of the executable. With its source present, all three outputs matched CPython. With the source renamed away, CPython exited 2 with an ENOENT diagnostic and empty stdout. The copied executable printed `1\n`, exited 0, and emitted its four stored warning headers without source echoes. Making the source unreadable produced the same compiled result and CPython's permission-denied diagnostic, status 2. With the original replaced by a comment followed by `print('new')`, CPython printed `new\n` without warnings. The executable still printed `1\n`, but the first two stored warnings quoted the two replacement lines. Continuing to run the built code and omitting unavailable source lines is reasonable for a standalone executable. Source echoes from a replacement file describe the current disk contents. A26-06 is distinct because both original files were present and unchanged throughout.

## Checks that matched

- The bulk probe emitted **1,011 warnings** on both CPython starts and the compiled start. The whole stderr, stdout and status matched. It covered a greater-than-65,536-byte warning line, repeated warnings, a multiline docstring, a nested f-string, a conversion and format spec, raw f-string, t-string, postponed annotations, a generic bound, default, type alias and match pattern.
- The matrix probe matched all three outputs, including **201 warnings**. It included a backslash-continued string, octal bytes escapes, a decorator, identity comparisons in loops, with, except*, match, comprehensions, a generator, nonlocal and async functions, guarded tuple assertion, chained comparison, and calls and subscripts across fourteen literal forms. It used Barry's valid `<>` operator, a warning after line 65,536, embedded control characters and no final newline.
- The regs/ program matched in full, including the initial filters, once registry, absence of a main warning registry, the exact linecache key and retrieved line, and an empty catch_warnings recorder.
- The state/ program's **warning stderr** matched under ASCII, Latin-1 and unbuffered I/O. Its observed exit statuses agreed with fd 2 closed (0), a closed reader or /dev/full (120), and a directory as fd 2 (1). Its module-list stdout difference is A26-04.
- Adjacent warnings.py, linecache.py and tokenize.py matched CPython's first and second starts at runtime. A local warnings.py importing __main__ saw the same initial global names on both sides. The package executable matched CPython's cached second start.
- In num/, all three outputs matched at digit limits 0, 640, 641, 650, 651, 700 and 701, and for three invalid settings (639, a non-number and an overflowing value). The same checks matched for 700 zeros. In prefix/, the exact 641-digit boundary and the unlimited run matched.
- With an unchanged warned program, building off left the already distinct on binary runnable. Repeated options selected the last setting. Lean with warnings on matched CPython's warning output, and off with lean gave no warning. The tested mixed-case, Boolean-like and whitespace-padded environment values exited 2. A bare switch with no program also exited 2.
