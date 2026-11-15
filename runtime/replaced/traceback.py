"""The functions of traceback (CPython 3.15.2, Lib/traceback.py) that its adaptation replaces (manifest.toml
[adaptations] and [replaced]): each def stands for the one of the same qualified name, whose signature it repeats; the
frontend puts its body there (pipeline/l1/frontend.py, replace_functions).

_find_incompatible_extension_module looks for an extension module built for another Python version on sys.path, to
suggest it when an import fails; a closed world has none, so it finds none.

A traceback is formatted from the source maps, file and line (D-06). Where CPython walks a traceback's frames and reads
each one's code positions (co_positions, E-02), _walk_tb_with_full_positions gives for each entry the frame it stands for
as the runtime has one (`__bella_traceback_frame__`: an object of the type `frame` with nothing a program can read) with
the entry's line and no positions, and StackSummary._extract_from_extended_frame_gen reads such a frame's file and function
from its code (`__bella_frame_code__`, the code object its function's __code__ gives) and gives its summary no source line,
so that nothing is looked up: no line follows the file and line, and a summary's `line` is empty. What is no such frame
(an object of the program's own making that stands for a traceback or a frame, a traceback where a frame is wanted) is
walked and read as CPython walks and reads it; capturing a frame's locals stops by name.

extract_stack, format_stack and print_stack, asked for the running stack (no frame given), take it from the runtime
(`__bella_stack__`: a frame and the line it is at for each frame, this one's first, as walk_stack gives them) where
CPython asks sys._getframe. Given the frame a signal handler was passed, they take from the runtime the stack the signal
found (`__bella_stack__(f)`), while the handlers of that arrival run; any other frame given is walked as CPython walks it.

_compute_suggestion_error is CPython's but for its three reads of the frame that raised (tb_frame.f_locals, f_globals,
f_builtins: whether an AttributeError's object is the `self` of the method, and the names a NameError's frame could see):
the runtime gives them for an entry of its own (`__bella_traceback_names__`: the locals an entry took over when an
exception left the frame, or the running frame's own).

clear_frames clears each frame of a traceback (frame.clear()): an entry gives up the locals of the frame it stands for
(`__bella_traceback_clear__`), which it holds once the exception has left that frame; a frame still running keeps its
own, where CPython's refuses to be cleared and clear_frames goes on."""


def _find_incompatible_extension_module(module_name):  # type: ignore[no-untyped-def]
    return None


def print_stack(f=None, limit=None, file=None):  # type: ignore[no-untyped-def]
    if f is None:
        stack = StackSummary.extract(__bella_stack__()[1:], limit=limit)  # type: ignore[name-defined]  # noqa: F821  # the caller's frame first
        stack.reverse()
        print_list(stack, file=file)  # type: ignore[name-defined]  # noqa: F821
        return
    print_list(extract_stack(f, limit=limit), file=file)  # type: ignore[name-defined]  # noqa: F821


def format_stack(f=None, limit=None):  # type: ignore[no-untyped-def]
    if f is None:
        stack = StackSummary.extract(__bella_stack__()[1:], limit=limit)  # type: ignore[name-defined]  # noqa: F821  # the caller's frame first
        stack.reverse()
        return format_list(stack)  # type: ignore[name-defined]  # noqa: F821
    return format_list(extract_stack(f, limit=limit))  # type: ignore[name-defined]  # noqa: F821


def extract_stack(f=None, limit=None):  # type: ignore[no-untyped-def]
    if f is None:
        stack = StackSummary.extract(__bella_stack__()[1:], limit=limit)  # type: ignore[name-defined]  # noqa: F821  # the caller's frame first
        stack.reverse()
        return stack
    walked = __bella_stack__(f)  # type: ignore[name-defined]  # noqa: F821  # the stack a signal found, of the frame its handler was given; else None
    stack = StackSummary.extract(walk_stack(f) if walked is None else walked, limit=limit)  # type: ignore[name-defined]  # noqa: F821
    stack.reverse()
    return stack


def clear_frames(tb):  # type: ignore[no-untyped-def]
    while tb is not None:
        if not __bella_traceback_clear__(tb):  # type: ignore[name-defined]  # noqa: F821  # an entry gives up its frame's locals
            try:
                tb.tb_frame.clear()
            except RuntimeError:
                # Ignore the exception raised if the frame is still executing.
                pass
        tb = tb.tb_next


def _walk_tb_with_full_positions(tb):  # type: ignore[no-untyped-def]
    while tb is not None:
        frame = __bella_traceback_frame__(tb)  # type: ignore[name-defined]  # noqa: F821  # an entry's frame, as the runtime has one
        if frame is not None:
            yield frame, (tb.tb_lineno, None, None, None)
        else:
            positions = _get_code_position(tb.tb_frame.f_code, tb.tb_lasti)  # type: ignore[name-defined]  # noqa: F821
            # Yield tb_lineno when co_positions does not have a line number to
            # maintain behavior with walk_tb.
            if positions[0] is None:
                yield tb.tb_frame, (tb.tb_lineno, ) + positions[1:]
            else:
                yield tb.tb_frame, positions
        tb = tb.tb_next


def _compute_suggestion_error(exc_value, tb, wrong_name):  # type: ignore[no-untyped-def]  # noqa: C901, PLR0912, PLR0915
    if wrong_name is None or not isinstance(wrong_name, str):
        return None
    not_normalized = False
    if not wrong_name.isascii():
        from unicodedata import normalize
        normalized_name = normalize('NFKC', wrong_name)
        if normalized_name != wrong_name:
            not_normalized = True
            wrong_name = normalized_name
    if isinstance(exc_value, AttributeError):
        obj = exc_value.obj
        try:
            d = _get_safe___dir__(obj)  # type: ignore[name-defined]  # noqa: F821
            hide_underscored = (wrong_name[:1] != '_')
            if hide_underscored and tb is not None:
                while tb.tb_next is not None:
                    tb = tb.tb_next
                names = __bella_traceback_names__(tb)  # type: ignore[name-defined]  # noqa: F821  # the frame's f_locals, f_globals and f_builtins, as the runtime has them
                f_locals = tb.tb_frame.f_locals if names is None else names[0]
                if 'self' in f_locals and f_locals['self'] is obj:
                    hide_underscored = False
            if hide_underscored:
                d = [x for x in d if x[:1] != '_']
        except Exception:
            return None
    elif isinstance(exc_value, ModuleNotFoundError):
        try:
            if parent_name := wrong_name.rpartition('.')[0]:
                parent = importlib.util.find_spec(parent_name)  # type: ignore[name-defined]  # noqa: F821
            else:
                parent = None
            d = []
            for finder in sys.meta_path:  # type: ignore[name-defined]  # noqa: F821
                if discover := getattr(finder, 'discover', None):
                    d += [spec.name for spec in discover(parent)]
        except Exception:
            return None
    elif isinstance(exc_value, ImportError):
        try:
            mod = __import__(exc_value.name)
            d = _get_safe___dir__(mod)  # type: ignore[name-defined]  # noqa: F821
            if wrong_name[:1] != '_':
                d = [x for x in d if x[:1] != '_']
        except Exception:
            return None
    else:
        assert isinstance(exc_value, NameError)
        try:
            # find most recent frame
            if tb is None:
                return None
            while tb.tb_next is not None:
                tb = tb.tb_next
            names = __bella_traceback_names__(tb)  # type: ignore[name-defined]  # noqa: F821  # the frame's f_locals, f_globals and f_builtins, as the runtime has them
            if names is None:
                frame = tb.tb_frame
                names = (frame.f_locals, frame.f_globals, frame.f_builtins)
            f_locals = names[0]
            d = (
                list(f_locals)
                + list(names[1])
                + list(names[2])
            )
            d = [x for x in d if isinstance(x, str)]
            if not_normalized and wrong_name in d:
                return wrong_name

            # Check first if we are in a method and the instance
            # has the wrong name as attribute
            if 'self' in f_locals:
                self = f_locals['self']
                try:
                    has_wrong_name = hasattr(self, wrong_name)
                except Exception:
                    has_wrong_name = False
                if has_wrong_name:
                    return f"self.{wrong_name}"
        except Exception:
            return None

    if not_normalized and wrong_name in d:
        return wrong_name
    try:
        import _suggestions
    except ImportError:
        pass
    else:
        suggestion = _suggestions._generate_suggestions(d, wrong_name)
        if suggestion:
            return suggestion

    # Compute closest match

    if len(d) > _MAX_CANDIDATE_ITEMS:  # type: ignore[name-defined]  # noqa: F821
        return None
    wrong_name_len = len(wrong_name)
    if wrong_name_len > _MAX_STRING_SIZE:  # type: ignore[name-defined]  # noqa: F821
        return None
    best_distance = wrong_name_len
    suggestion = None
    for possible_name in d:
        if possible_name == wrong_name:
            # A missing attribute is "found". Don't suggest it (see GH-88821).
            continue
        # No more than 1/3 of the involved characters should need changed.
        max_distance = (len(possible_name) + wrong_name_len + 3) * _MOVE_COST // 6  # type: ignore[name-defined]  # noqa: F821
        # Don't take matches we've already beaten.
        max_distance = min(max_distance, best_distance - 1)
        current_distance = _levenshtein_distance(wrong_name, possible_name, max_distance)  # type: ignore[name-defined]  # noqa: F821
        if current_distance > max_distance:
            continue
        if not suggestion or current_distance < best_distance:
            suggestion = possible_name
            best_distance = current_distance

    # If no direct attribute match found, check for nested attributes
    if not suggestion and isinstance(exc_value, AttributeError):
        with suppress(Exception):  # type: ignore[name-defined]  # noqa: F821
            nested_suggestion = _check_for_nested_attribute(exc_value.obj, wrong_name, d)  # type: ignore[name-defined]  # noqa: F821
            if nested_suggestion:
                return nested_suggestion

    return suggestion


class StackSummary:
    def _extract_from_extended_frame_gen(klass, frame_gen, *, limit=None,  # type: ignore[no-untyped-def]  # noqa: N805
            lookup_lines=True, capture_locals=False):
        builtin_limit = limit is BUILTIN_EXCEPTION_LIMIT  # type: ignore[name-defined]  # noqa: F821
        if limit is None or builtin_limit:
            limit = getattr(sys, 'tracebacklimit', None)  # type: ignore[name-defined]  # noqa: F821
            if limit is not None and limit < 0:
                limit = 0
        if limit is not None:
            if builtin_limit:
                frame_gen = tuple(frame_gen)
                frame_gen = frame_gen[len(frame_gen) - limit:]
            elif limit >= 0:
                frame_gen = itertools.islice(frame_gen, limit)  # type: ignore[name-defined]  # noqa: F821
            else:
                frame_gen = collections.deque(frame_gen, maxlen=-limit)  # type: ignore[name-defined]  # noqa: F821

        result = klass()
        fnames = set()
        for f, (lineno, end_lineno, colno, end_colno) in frame_gen:
            co = __bella_frame_code__(f, capture_locals)  # type: ignore[name-defined]  # noqa: F821  # the code of a frame of the runtime's, else None
            if co is not None:
                filename = co.co_filename
                fnames.add(filename)
                result.append(
                    FrameSummary(filename, lineno, co.co_name,  # type: ignore[name-defined]  # noqa: F821
                        lookup_line=False, line="",
                        end_lineno=end_lineno, colno=colno, end_colno=end_colno,
                        _code=co,
                    )
                )
                continue
            co = f.f_code
            filename = co.co_filename
            name = co.co_name
            fnames.add(filename)
            linecache.lazycache(filename, f.f_globals)  # type: ignore[name-defined]  # noqa: F821
            # Must defer line lookups until we have called checkcache.
            if capture_locals:
                f_locals = f.f_locals
            else:
                f_locals = None
            result.append(
                FrameSummary(filename, lineno, name,  # type: ignore[name-defined]  # noqa: F821
                    lookup_line=False, locals=f_locals,
                    end_lineno=end_lineno, colno=colno, end_colno=end_colno,
                    _code=f.f_code,
                )
            )
        for filename in fnames:
            linecache.checkcache(filename)  # type: ignore[name-defined]  # noqa: F821

        # If immediate lookup was desired, trigger lookups now.
        if lookup_lines:
            for f in result:
                f.line  # noqa: B018  # CPython's: the lookup
        return result
