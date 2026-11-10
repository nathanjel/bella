// The tokenizer under runtime/prelude/_tokenize.py (spec section 7, C-7-53; licence register L-01): CPython 3.15.2's own lexer, which
// Lib/tokenize.py reaches through _tokenize.TokenizerIter. The lexer is the C's text (tokenizer_lexer.inc: Parser/lexer and the
// operator tables of Parser/token.c), compiled as C++ over the few names of CPython's API it uses, which are defined first. What
// touches objects is written here against the runtime, each function after the C one it is named for, so that the one can be read
// against the other: the errors and warnings of Parser/tokenizer/helpers.c, the reader of Parser/tokenizer/readline_tokenizer.c
// (the only source a TokenizerIter has), and the iterator of Python/Python-tokenize.c behind one primitive, `_tokenizer(name, ...)`.
//
// The C reports an error by setting the interpreter's error indicator and returning a code, and a tokenizer is left in the state
// that return left it in: a second next() after an error answers from that state (another token, another error, a MemoryError
// out of a freed buffer). So the indicator is kept as the C has it, a slot the functions below set and test, and what it holds is
// thrown once the primitive is done.
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <memory>
#include <string>
#include <unordered_map>

#include "bella/runtime.hpp"

namespace bella {
namespace {
// ---- the error indicator (PyErr_Occurred and the rest): an exception this tokenizer made, or one it caught on its way out of
// a call into the program (readline, a codec, the warnings machinery), kept whole so that it goes on as the same exception
struct Pending {
    Ref exc;
    std::exception_ptr thrown;                   // the caught C++ exception, when it was one
    const PyError* owner = nullptr;
};
Pending& indicator() {
    static Pending slot;
    return slot;
}
void set_pending(const PyError& e) { indicator() = Pending{e.exc, std::current_exception(), &e}; }   // inside its catch block
void set_error(Ref exc) { indicator() = Pending{std::move(exc), nullptr, nullptr}; }
void set_error(const char* type, std::initializer_list<Obj> args) {   // PyErr_SetObject(type, args): the instance its normalisation makes
    try {
        set_error(invoke(Obj::of(exception_class(type)), args));
    } catch (const PyError& e) {
        set_pending(e);
    }
}
[[noreturn]] void throw_this(Pending p) {
    if (p.thrown) {
        detail::raising() = p.exc.get();
        detail::raising_owner() = p.owner;
        std::rethrow_exception(p.thrown);
    }
    raise(p.exc.get());
}

// ---- the names of CPython's API the C text uses
using Py_ssize_t = std::ptrdiff_t;
using Py_UCS4 = std::uint32_t;
typedef Object PyObject;

#undef assert
#define assert(e) ((void)0)                      // a release build of CPython, which the pin is, checks none of them

#define Py_CHARMASK(c) ((unsigned char)((c) & 0xff))
inline int Py_ISDIGIT(int c) { c &= 0xff; return c >= '0' && c <= '9'; }
inline int Py_ISXDIGIT(int c) { c &= 0xff; return Py_ISDIGIT(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'); }
inline int Py_ISALNUM(int c) { c &= 0xff; return Py_ISDIGIT(c) || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
inline int Py_TOLOWER(int c) { c &= 0xff; return c >= 'A' && c <= 'Z' ? c + 32 : c; }
#define Py_UNREACHABLE() __builtin_unreachable()
#define Py_MAX(x, y) (((x) > (y)) ? (x) : (y))
#define PyMem_Malloc std::malloc
#define PyMem_Calloc std::calloc
#define PyMem_Realloc std::realloc
#define PyMem_Free std::free
#define Py_UNICODE_ISPRINTABLE unicode_is_printable
[[noreturn]] void Py_FatalError(const char* message) {
    std::fprintf(stderr, "Fatal Python error: %s\n", message);
    std::abort();
}
inline void Py_INCREF(PyObject* o) { incref(o); }
inline void Py_DECREF(PyObject* o) { decref(o); }
inline void Py_XDECREF(PyObject* o) { if (o != nullptr) decref(o); }
#define Py_SETREF(dst, src) do { PyObject* py_tmp_ = (dst); (dst) = (src); Py_DECREF(py_tmp_); } while (0)
inline PyObject* PyErr_Occurred() {
    Obj e = indicator().exc.get();
    return e.is_unset() ? nullptr : e.object();
}
inline void PyErr_Clear() { indicator() = Pending{}; }
inline int PyErr_ExceptionMatches(PyObject* type) {
    Obj e = indicator().exc.get();
    return !e.is_unset() && isinstance(e, static_cast<ClassObject*>(type));
}
#define PyExc_UnicodeDecodeError (static_cast<PyObject*>(exception_class("UnicodeDecodeError")))
#define PyExc_SyntaxWarning (static_cast<PyObject*>(exception_class("SyntaxWarning")))
inline void PyErr_NoMemory() { set_error("MemoryError", {}); }

// PyUnicode_DecodeUTF8(s, size, errors): a new str, or NULL with the indicator set. A negative size is a MemoryError, as the
// pin's unicode_decode_utf8 answers it (the size compared as unsigned): what next() raises after a failed readline freed the buffer
PyObject* PyUnicode_DecodeUTF8(const char* s, Py_ssize_t size, const char* errors) {
    if (size < 0) {
        PyErr_NoMemory();
        return nullptr;
    }
    try {
        std::string handler = errors == nullptr ? "strict" : errors;
        Ref text = unicode_decode(std::string_view(s, static_cast<std::size_t>(size)), nullptr, &handler);
        return text.release().object();
    } catch (const PyError& e) {
        set_pending(e);
        return nullptr;
    }
}
inline const Str* text_of(PyObject* o) { return static_cast<const Str*>(o); }
inline Py_ssize_t PyUnicode_GET_LENGTH(PyObject* o) { return static_cast<Py_ssize_t>(text_of(o)->length); }
inline Py_UCS4 PyUnicode_READ_CHAR(PyObject* o, Py_ssize_t i) { return text_of(o)->at(static_cast<std::size_t>(i)); }
Py_ssize_t _PyUnicode_ScanIdentifier(PyObject* self) {   // Objects/unicodeobject.c
    Py_ssize_t i;
    Py_ssize_t len = PyUnicode_GET_LENGTH(self);
    if (len == 0) {
        /* an empty string is not a valid identifier */
        return 0;
    }
    Py_UCS4 ch = PyUnicode_READ_CHAR(self, 0);
    if (!unicode_is_xid_start(ch) && ch != 0x5F /* LOW LINE */) {
        return 0;
    }
    for (i = 1; i < len; i++) {
        ch = PyUnicode_READ_CHAR(self, i);
        if (!unicode_is_xid_continue(ch)) {
            return i;
        }
    }
    return i;
}
PyObject* PyUnicode_Substring(PyObject* self, Py_ssize_t start, Py_ssize_t end) {
    std::u32string cps;
    for (Py_ssize_t i = start; i < end && i < PyUnicode_GET_LENGTH(self); ++i) cps += static_cast<char32_t>(PyUnicode_READ_CHAR(self, i));
    return str_from_codepoints(cps).release().object();
}
PyObject* PyUnicode_AsUTF8String(PyObject* self) {
    try {
        return bytes_new(utf8_with_errors(Obj::of(self), "strict")).release().object();
    } catch (const PyError& e) {
        set_pending(e);
        return nullptr;
    }
}
inline Py_ssize_t PyBytes_GET_SIZE(PyObject* o) { return static_cast<Py_ssize_t>(bytes_data(Obj::of(o)).size()); }

// the C text declares what this file does not need (the file and string sources' helpers) and keeps parameters only its
// asserts read
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wunused-parameter"
#include "tokenizer_lexer.inc"
#pragma GCC diagnostic pop

// ---- Parser/tokenizer/helpers.c: the errors and the warnings

// PyUnicode_FromFormatV for what the tokenizer's messages hold: %c (a code point), %d and %i, %s, %04X and %.2x
std::string format_v(const char* format, va_list vargs) {
    std::string out;
    for (const char* f = format; *f != '\0'; ++f) {
        if (*f != '%') {
            out += *f;
            continue;
        }
        std::string spec = "%";
        ++f;
        while (*f == '0' || *f == '.' || (*f >= '1' && *f <= '9')) spec += *f++;
        spec += *f;
        char piece[64];
        switch (*f) {
            case 'c': {
                std::u32string one(1, static_cast<char32_t>(va_arg(vargs, int)));
                out += as_str(str_from_codepoints(one).get())->text;
                break;
            }
            case 'd':
            case 'i':
                std::snprintf(piece, sizeof piece, spec.c_str(), va_arg(vargs, int));
                out += piece;
                break;
            case 'X':
            case 'x':
                std::snprintf(piece, sizeof piece, spec.c_str(), va_arg(vargs, unsigned int));
                out += piece;
                break;
            case 's':
                out += va_arg(vargs, const char*);
                break;
            default:
                throw NotImplemented(std::string("the tokenizer's message format ") + spec);
        }
    }
    return out;
}

/* Convert a 1-based column in bytes into a 1-based column in characters.
   The line is UTF-8 encoded, so it is enough to skip continuation bytes. */
int byte_col_to_char_col(const char* line, int byte_col) {
    int char_col = 1;
    for (int i = 0; i < byte_col - 1; i++) {
        if ((line[i] & 0xC0) != 0x80) {
            char_col++;
        }
    }
    return char_col;
}

int _syntaxerror_range(struct tok_state* tok, const char* format, int col_offset, int end_col_offset, va_list vargs) {
    // In release builds, we don't want to overwrite a previous error
    if (tok->done == E_ERROR) {
        return ERRORTOKEN;
    }
    Ref errmsg = str_new(format_v(format, vargs));
    PyObject* errtext = PyUnicode_DecodeUTF8(tok->line_start, tok->cur - tok->line_start, "replace");
    if (!errtext) {
        goto error;
    }
    if (col_offset == -1) {
        col_offset = (int)PyUnicode_GET_LENGTH(errtext);
    }
    else if (col_offset > 0) {
        col_offset = byte_col_to_char_col(tok->line_start, col_offset);
    }
    if (end_col_offset == -1) {
        end_col_offset = col_offset;
    }
    else if (end_col_offset > 0) {
        end_col_offset = byte_col_to_char_col(tok->line_start, end_col_offset);
    }
    {
        Py_ssize_t line_len = static_cast<Py_ssize_t>(strcspn(tok->line_start, "\n"));
        if (line_len != tok->cur - tok->line_start) {
            Py_DECREF(errtext);
            errtext = PyUnicode_DecodeUTF8(tok->line_start, line_len, "replace");
        }
    }
    if (!errtext) {
        goto error;
    }
    {
        Ref text = Ref::steal(Obj::of(errtext));
        Ref lineno = int_from_i64(tok->lineno), col = int_from_i64(col_offset), end_col = int_from_i64(end_col_offset);
        Ref where = tuple_new({tok->filename ? Obj::of(tok->filename) : None(), lineno.get(), col.get(), text.get(), lineno.get(), end_col.get()});
        set_error("SyntaxError", {errmsg.get(), where.get()});
    }
error:
    tok->done = E_ERROR;
    return ERRORTOKEN;
}

int _PyTokenizer_syntaxerror(struct tok_state* tok, const char* format, ...) {
    va_list vargs;
    va_start(vargs, format);
    int ret = _syntaxerror_range(tok, format, -1, -1, vargs);
    va_end(vargs);
    return ret;
}

int _PyTokenizer_syntaxerror_known_range(struct tok_state* tok, int col_offset, int end_col_offset, const char* format, ...) {
    va_list vargs;
    va_start(vargs, format);
    int ret = _syntaxerror_range(tok, format, col_offset, end_col_offset, vargs);
    va_end(vargs);
    return ret;
}

int _PyTokenizer_indenterror(struct tok_state* tok) {
    tok->done = E_TABSPACE;
    tok->cur = tok->inp;
    return ERRORTOKEN;
}

char* _PyTokenizer_error_ret(struct tok_state* tok) /* XXX */ {
    tok->decoding_erred = 1;
    if ((tok->fp != NULL || tok->readline != NULL) && tok->buf != NULL) { /* see _PyTokenizer_Free */
        PyMem_Free(tok->buf);
    }
    tok->buf = tok->cur = tok->inp = NULL;
    tok->start = NULL;
    tok->end = NULL;
    tok->done = E_DECODE;
    return NULL; /* as if it were EOF */
}

// PyErr_WarnExplicitObject(category, message, tok->filename, tok->lineno, tok->module, NULL): through the _warnings prelude's
// warn_explicit, imported here if the program has not, as the C machinery is always there; -1 with the indicator set when the
// filters make it an error
int warn_explicit_object(PyObject* category, const std::string& message, struct tok_state* tok) {
    try {
        Ref warnings = Ref::share(dict_get(sys_modules(), Obj::of(intern("_warnings"))));
        if (warnings.get().is_unset()) warnings = import_module_level(Obj::of(intern("_warnings")), None(), None(), None(), 0);
        Ref warn = getattr(warnings.get(), intern("warn_explicit"));
        Ref msg = str_new(message), lineno = int_from_i64(tok->lineno);
        invoke(warn.get(), {msg.get(), Obj::of(category), tok->filename ? Obj::of(tok->filename) : None(), lineno.get()});
        return 0;
    } catch (const PyError& e) {
        set_pending(e);
        return -1;
    }
}

int _PyTokenizer_warn_invalid_escape_sequence(struct tok_state* tok, int first_invalid_escape_char) {
    if (!tok->report_warnings) {
        return 0;
    }
    char c = (char)first_invalid_escape_char;
    std::string msg = std::string("\"\\") + c + "\" is an invalid escape sequence. Such sequences will not work in the future. "
                      "Did you mean \"\\\\" + c + "\"? A raw string is also an option.";
    if (warn_explicit_object(PyExc_SyntaxWarning, msg, tok) < 0) {
        if (PyErr_ExceptionMatches(PyExc_SyntaxWarning)) {
            /* Replace the SyntaxWarning exception with a SyntaxError
               to get a more accurate error report */
            PyErr_Clear();
            return _PyTokenizer_syntaxerror(tok,
                "\"\\%c\" is an invalid escape sequence. "
                "Did you mean \"\\\\%c\"? A raw string is also an option.",
                (char) first_invalid_escape_char,
                (char) first_invalid_escape_char);
        }
        return -1;
    }
    return 0;
}

int _PyTokenizer_parser_warn(struct tok_state* tok, PyObject* category, const char* format, ...) {
    if (!tok->report_warnings) {
        return 0;
    }
    va_list vargs;
    va_start(vargs, format);
    std::string errmsg = format_v(format, vargs);
    va_end(vargs);
    if (warn_explicit_object(category, errmsg, tok) < 0) {
        if (PyErr_ExceptionMatches(category)) {
            /* Replace the DeprecationWarning exception with a SyntaxError
               to get a more accurate error report */
            PyErr_Clear();
            _PyTokenizer_syntaxerror(tok, "%s", errmsg.c_str());
        }
        goto error;
    }
    return 0;
error:
    tok->done = E_ERROR;
    return -1;
}

char* _PyTokenizer_new_string(const char* s, Py_ssize_t len, struct tok_state* tok) {
    char* result = (char*)PyMem_Malloc(len + 1);
    if (!result) {
        tok->done = E_NOMEM;
        PyErr_NoMemory();
        return NULL;
    }
    memcpy(result, s, len);
    result[len] = '\0';
    return result;
}

/* Check whether the characters at s start a valid
   UTF-8 sequence. Return the number of characters forming
   the sequence if yes, 0 if not.  The special cases match
   those in stringlib/codecs.h:utf8_decode.
*/
int valid_utf8(const unsigned char* s) {
    int expected = 0;
    int length;
    if (*s < 0x80) {
        /* single-byte code */
        return 1;
    }
    else if (*s < 0xE0) {
        /* \xC2\x80-\xDF\xBF -- 0080-07FF */
        if (*s < 0xC2) {
            /* invalid sequence
               \x80-\xBF -- continuation byte
               \xC0-\xC1 -- fake 0000-007F */
            return 0;
        }
        expected = 1;
    }
    else if (*s < 0xF0) {
        /* \xE0\xA0\x80-\xEF\xBF\xBF -- 0800-FFFF */
        if (*s == 0xE0 && *(s + 1) < 0xA0) {
            /* invalid sequence
               \xE0\x80\x80-\xE0\x9F\xBF -- fake 0000-0800 */
            return 0;
        }
        else if (*s == 0xED && *(s + 1) >= 0xA0) {
            /* Decoding UTF-8 sequences in range \xED\xA0\x80-\xED\xBF\xBF
               will result in surrogates in range D800-DFFF. Surrogates are
               not valid UTF-8 so they are rejected. */
            return 0;
        }
        expected = 2;
    }
    else if (*s < 0xF5) {
        /* \xF0\x90\x80\x80-\xF4\x8F\xBF\xBF -- 10000-10FFFF */
        if (*(s + 1) < 0x90 ? *s == 0xF0 : *s == 0xF4) {
            /* invalid sequence -- one of:
               \xF0\x80\x80\x80-\xF0\x8F\xBF\xBF -- fake 0000-FFFF
               \xF4\x90\x80\x80- -- 110000- overflow */
            return 0;
        }
        expected = 3;
    }
    else {
        /* invalid start byte */
        return 0;
    }
    length = expected + 1;
    for (int i = 1; i <= expected; i++) {
        if (s[i] < 0x80 || s[i] >= 0xC0) {
            return 0;
        }
    }
    return length;
}

int _PyTokenizer_ensure_utf8(const char* line, struct tok_state* tok, int lineno) {
    const char* badchar = NULL;
    const char* c;
    int length;
    const char* line_start = line;
    for (c = line; *c; c += length) {
        if (!(length = valid_utf8((const unsigned char*)c))) {
            badchar = c;
            break;
        }
        if (*c == '\n') {
            lineno++;
            line_start = c + 1;
        }
    }
    if (badchar) {
        tok->lineno = lineno;
        tok->line_start = line_start;
        tok->cur = (char*)badchar;
        char start[8];
        std::snprintf(start, sizeof start, "%.2x", (unsigned char)*badchar);
        std::string msg = std::string("Non-UTF-8 code starting with '\\x") + start + "'" +
                          (tok->filename ? " in file " + text_of(tok->filename)->text : std::string()) + " on line " + std::to_string(lineno) +
                          ", but no encoding declared; see https://peps.python.org/pep-0263/ for details";
        _PyTokenizer_syntaxerror_known_range(tok, (int)(badchar - line_start) + 1, (int)(badchar - line_start) + 1, "%s", msg.c_str());
        return 0;
    }
    return 1;
}

// ---- Parser/tokenizer/readline_tokenizer.c

int tok_readline_string(struct tok_state* tok) {
    Ref line, raw_line;
    try {
        raw_line = invoke(Obj::of(tok->readline), Args{});   // PyObject_CallNoArgs(tok->readline)
    } catch (const PyError& e) {
        if (isinstance(e.exc.get(), exception_class("StopIteration"))) {
            return 1;                                // PyErr_Clear(): the end of the input
        }
        set_pending(e);
        _PyTokenizer_error_ret(tok);
        return 0;
    }
    if (tok->encoding != NULL) {
        if (!is_kind(raw_line.get(), Kind::Bytes)) {
            set_error("TypeError", {Ref(str_new("readline() returned a non-bytes object")).get()});
            _PyTokenizer_error_ret(tok);
            return 0;
        }
        try {                                        // PyUnicode_Decode(bytes, size, tok->encoding, "replace")
            std::string encoding = tok->encoding, errors = "replace";
            line = unicode_decode(bytes_data(raw_line.get()), &encoding, &errors);
        } catch (const PyError& e) {
            set_pending(e);
            _PyTokenizer_error_ret(tok);
            return 0;
        }
    } else {
        if (as_str(raw_line.get()) == nullptr) {
            set_error("TypeError", {Ref(str_new("readline() returned a non-string object")).get()});
            _PyTokenizer_error_ret(tok);
            return 0;
        }
        line = raw_line;
    }
    std::string buf;
    try {                                            // PyUnicode_AsUTF8AndSize(line, &buflen): a lone surrogate has no UTF-8
        buf = utf8_with_errors(line.get(), "strict");
    } catch (const PyError& e) {
        set_pending(e);
        _PyTokenizer_error_ret(tok);
        return 0;
    }
    Py_ssize_t buflen = static_cast<Py_ssize_t>(buf.size());

    // Make room for the null terminator *and* potentially
    // an extra newline character that we may need to artificially
    // add.
    size_t buffer_size = buflen + 2;
    if (!_PyLexer_tok_reserve_buf(tok, buffer_size)) {
        return 0;
    }
    memcpy(tok->inp, buf.data(), buflen);
    tok->inp += buflen;
    *tok->inp = '\0';

    tok->line_start = tok->cur;
    return 1;
}

int tok_underflow_readline(struct tok_state* tok) {
    assert(tok->decoding_state == STATE_NORMAL);
    assert(tok->fp == NULL && tok->input == NULL && tok->decoding_readline == NULL);
    if (tok->start == NULL && !INSIDE_FSTRING(tok)) {
        tok->cur = tok->inp = tok->buf;
    }
    if (!tok_readline_string(tok)) {
        return 0;
    }
    if (tok->inp == tok->cur) {
        tok->done = E_EOF;
        return 0;
    }
    tok->implicit_newline = 0;
    if (tok->inp[-1] != '\n') {
        assert(tok->inp + 1 < tok->end);
        /* Last line does not end in \n, fake one */
        *tok->inp++ = '\n';
        *tok->inp = '\0';
        tok->implicit_newline = 1;
    }

    ADVANCE_LINENO();
    /* The default encoding is UTF-8, so make sure we don't have any
       non-UTF-8 sequences in it. */
    if (!tok->encoding && !_PyTokenizer_ensure_utf8(tok->cur, tok, tok->lineno)) {
        _PyTokenizer_error_ret(tok);
        return 0;
    }
    assert(tok->done == E_OK);
    return tok->done == E_OK;
}

struct tok_state* _PyTokenizer_FromReadline(PyObject* readline, const char* enc, int /*exec_input*/, int /*preserve_crlf*/) {
    struct tok_state* tok = _PyTokenizer_tok_new();
    if (tok == NULL)
        return NULL;
    if ((tok->buf = (char*)PyMem_Malloc(BUFSIZ)) == NULL) {
        _PyTokenizer_Free(tok);
        PyErr_NoMemory();
        return NULL;
    }
    tok->cur = tok->inp = tok->buf;
    tok->end = tok->buf + BUFSIZ;
    tok->fp = NULL;
    if (enc != NULL) {
        tok->encoding = _PyTokenizer_new_string(enc, strlen(enc), tok);
        if (!tok->encoding) {
            _PyTokenizer_Free(tok);
            return NULL;
        }
    }
    tok->decoding_state = STATE_NORMAL;
    tok->underflow = &tok_underflow_readline;
    Py_INCREF(readline);
    tok->readline = readline;
    return tok;
}

// ---- Python/Python-tokenize.c: the iterator

struct tokenizeriterobject {
    struct tok_state* tok = nullptr;
    int done = 0;
    /* Needed to cache line for performance */
    PyObject* last_line = nullptr;
    Py_ssize_t last_lineno = 0;
    Py_ssize_t last_end_lineno = 0;
    Py_ssize_t byte_col_offset_diff = 0;
    ~tokenizeriterobject() {                         // tokenizeriter_dealloc
        Py_XDECREF(last_line);
        if (tok != nullptr) _PyTokenizer_Free(tok);
    }
};

// Parser/pegen.c
Py_ssize_t _PyPegen_byte_offset_to_character_offset_line(PyObject* line, Py_ssize_t col_offset, Py_ssize_t end_col_offset) {
    const unsigned char* data = (const unsigned char*)text_of(line)->text.c_str();   // PyUnicode_AsUTF8(line)
    Py_ssize_t size = static_cast<Py_ssize_t>(text_of(line)->text.size());

    Py_ssize_t len = 0;
    while (col_offset < end_col_offset) {
        // the C reads on past the line's terminator when the offsets say so; no token is known to ask it, and one that did stops
        if (col_offset < 0 || col_offset > size) throw NotImplemented("a token's column past the end of its line (the C tokenizer reads beyond the line there)");
        Py_UCS4 ch = data[col_offset];
        if (ch < 0x80) {
            col_offset += 1;
        } else if ((ch & 0xe0) == 0xc0) {
            col_offset += 2;
        } else if ((ch & 0xf0) == 0xe0) {
            col_offset += 3;
        } else if ((ch & 0xf8) == 0xf0) {
            col_offset += 4;
        } else {
            set_error("ValueError", {Ref(str_new("Invalid UTF-8 sequence")).get()});
            return -1;
        }
        len++;
    }
    return len;
}

Py_ssize_t _PyPegen_byte_offset_to_character_offset_raw(const char* str, Py_ssize_t col_offset) {
    Py_ssize_t len = (Py_ssize_t)strlen(str);
    if (col_offset > len + 1) {
        col_offset = len + 1;
    }
    assert(col_offset >= 0);
    PyObject* text = PyUnicode_DecodeUTF8(str, col_offset, "replace");
    if (!text) {
        return -1;
    }
    Py_ssize_t size = PyUnicode_GET_LENGTH(text);
    Py_DECREF(text);
    return size;
}

Py_ssize_t _PyPegen_byte_offset_to_character_offset(PyObject* line, Py_ssize_t col_offset) {
    const char* str = text_of(line)->text.c_str();   // PyUnicode_AsUTF8(line)
    return _PyPegen_byte_offset_to_character_offset_raw(str, col_offset);
}

// PyErr_SyntaxLocationObject(filename, lineno, col_offset) on the exception the indicator holds (Python/errors.c). It would quote
// the line of a file named as the tokenizer's filename, "<string>": a program with such a file in its directory stops by name
void syntax_location(PyObject* filename, int lineno, int col_offset) {
    Obj exc = indicator().exc.get();
    try {
        Ref line = int_from_i64(lineno);
        setattr(exc, intern("lineno"), line.get());
        Ref offset = col_offset >= 0 ? int_from_i64(col_offset) : none_ref();
        setattr(exc, intern("offset"), offset.get());
        setattr(exc, intern("end_lineno"), line.get());      // end_lineno is lineno, end_col_offset -1: None
        setattr(exc, intern("end_offset"), None());
        if (filename != NULL) {
            setattr(exc, intern("filename"), Obj::of(filename));
            if (std::FILE* f = std::fopen(text_of(filename)->text.c_str(), "r")) {   // PyErr_ProgramTextObject
                std::fclose(f);
                throw NotImplemented("a tokenizer error's source line read from a file named " + text_of(filename)->text + " (PyErr_ProgramTextObject)");
            }
        }
    } catch (const PyError&) {                       // _PyErr_Clear: each attribute's failure is dropped
    }
}

int _tokenizer_error(tokenizeriterobject* it) {
    if (PyErr_Occurred()) {
        return -1;
    }

    const char* msg = NULL;
    const char* errtype = "SyntaxError";
    struct tok_state* tok = it->tok;
    switch (tok->done) {
        case E_TOKEN:
            msg = "invalid token";
            break;
        case E_EOF:
            set_error("SyntaxError", {Ref(str_new("unexpected EOF in multi-line statement")).get()});
            syntax_location(tok->filename, tok->lineno, tok->inp - tok->buf < 0 ? 0 : (int)(tok->inp - tok->buf));
            return -1;
        case E_DEDENT:
            msg = "unindent does not match any outer indentation level";
            errtype = "IndentationError";
            break;
        case E_INTR:
            if (!PyErr_Occurred()) {
                set_error("KeyboardInterrupt", {});
            }
            return -1;
        case E_NOMEM:
            PyErr_NoMemory();
            return -1;
        case E_TABSPACE:
            errtype = "TabError";
            msg = "inconsistent use of tabs and spaces in indentation";
            break;
        case E_TOODEEP:
            errtype = "IndentationError";
            msg = "too many levels of indentation";
            break;
        case E_LINECONT: {
            msg = "unexpected character after line continuation character";
            break;
        }
        default:
            msg = "unknown tokenization error";
    }

    Py_ssize_t size = tok->inp - tok->buf;
    assert(tok->buf[size-1] == '\n');
    size -= 1; // Remove the newline character from the end of the line
    PyObject* error_line = PyUnicode_DecodeUTF8(tok->buf, size, "replace");
    if (!error_line) {
        return -1;
    }
    Ref line = Ref::steal(Obj::of(error_line));
    Py_ssize_t offset = _PyPegen_byte_offset_to_character_offset(error_line, tok->inp - tok->buf);
    if (offset == -1) {
        return -1;
    }
    Ref lineno = int_from_i64(tok->lineno), off = int_from_i64(offset);
    Ref tmp = tuple_new({Obj::of(tok->filename), lineno.get(), off.get(), line.get(), None(), None()});
    Ref errstr = str_new(msg);
    set_error(errtype, {errstr.get(), tmp.get()});
    return 0;
}

PyObject* _get_current_line(tokenizeriterobject* it, const char* line_start, Py_ssize_t size, int* line_changed) {
    PyObject* line;
    if (it->tok->lineno != it->last_lineno) {
        // Line has changed since last token, so we fetch the new line and cache it
        // in the iter object.
        Py_XDECREF(it->last_line);
        line = PyUnicode_DecodeUTF8(line_start, size, "replace");
        it->last_line = line;
        it->byte_col_offset_diff = 0;
    }
    else {
        line = it->last_line;
        *line_changed = 0;
    }
    return line;
}

void _get_col_offsets(tokenizeriterobject* it, struct token token, const char* line_start, PyObject* line, int line_changed,
                      Py_ssize_t lineno, Py_ssize_t end_lineno, Py_ssize_t* col_offset, Py_ssize_t* end_col_offset) {
    Py_ssize_t byte_offset = -1;
    if (token.start != NULL && token.start >= line_start) {
        byte_offset = token.start - line_start;
        if (line_changed) {
            *col_offset = _PyPegen_byte_offset_to_character_offset_line(line, 0, byte_offset);
            it->byte_col_offset_diff = byte_offset - *col_offset;
        }
        else {
            *col_offset = byte_offset - it->byte_col_offset_diff;
        }
    }

    if (token.end != NULL && token.end >= it->tok->line_start) {
        Py_ssize_t end_byte_offset = token.end - it->tok->line_start;
        if (lineno == end_lineno) {
            // If the whole token is at the same line, we can just use the token.start
            // buffer for figuring out the new column offset, since using line is not
            // performant for very long lines.
            Py_ssize_t token_col_offset = _PyPegen_byte_offset_to_character_offset_line(line, byte_offset, end_byte_offset);
            *end_col_offset = *col_offset + token_col_offset;
            it->byte_col_offset_diff += token.end - token.start - token_col_offset;
        }
        else {
            *end_col_offset = _PyPegen_byte_offset_to_character_offset_raw(it->tok->line_start, end_byte_offset);
            it->byte_col_offset_diff += end_byte_offset - *end_col_offset;
        }
    }
    it->last_lineno = lineno;
    it->last_end_lineno = end_lineno;
}

// tokenizeriter_next, between the token's set-up and the `exit` label: the tuple, Unset with *stop for StopIteration("EOF"), or
// Unset with the indicator set
Ref next_token(tokenizeriterobject* it, struct token& token, int& type, bool* stop) {
    type = _PyTokenizer_Get(it->tok, &token);
    if (type == ERRORTOKEN) {
        if (!PyErr_Occurred()) {
            _tokenizer_error(it);
            assert(PyErr_Occurred());
        }
        return Ref{};
    }
    if (it->done || type == ERRORTOKEN) {
        *stop = true;
        it->done = 1;
        return Ref{};
    }
    Ref str;
    if (token.start == NULL || token.end == NULL) {
        str = str_new("");
    }
    else {
        PyObject* made = PyUnicode_DecodeUTF8(token.start, token.end - token.start, NULL);   // PyUnicode_FromStringAndSize
        if (made == NULL) {
            return Ref{};
        }
        str = Ref::steal(Obj::of(made));
    }

    int is_trailing_token = 0;
    if (type == ENDMARKER || (type == DEDENT && it->tok->done == E_EOF)) {
        is_trailing_token = 1;
    }

    const char* line_start = ISSTRINGLIT(type) ? it->tok->multi_line_start : it->tok->line_start;
    Ref line;
    int line_changed = 1;
    if (it->tok->tok_extra_tokens && is_trailing_token) {
        line = str_new("");
    } else {
        Py_ssize_t size = it->tok->inp - line_start;
        if (size >= 1 && it->tok->implicit_newline) {
            size -= 1;
        }
        PyObject* current = _get_current_line(it, line_start, size, &line_changed);
        if (current == NULL) {
            return Ref{};
        }
        line = Ref::share(Obj::of(current));
    }

    Py_ssize_t lineno = ISSTRINGLIT(type) ? it->tok->first_lineno : it->tok->lineno;
    Py_ssize_t end_lineno = it->tok->lineno;
    Py_ssize_t col_offset = -1;
    Py_ssize_t end_col_offset = -1;
    _get_col_offsets(it, token, line_start, line.get().object(), line_changed, lineno, end_lineno, &col_offset, &end_col_offset);

    if (it->tok->tok_extra_tokens) {
        if (is_trailing_token) {
            lineno = end_lineno = lineno + 1;
            col_offset = end_col_offset = 0;
        }
        // Necessary adjustments to match the original Python tokenize
        // implementation
        if (type > DEDENT && type < OP) {
            type = OP;
        }
        else if (type == NEWLINE) {
            // The C releases str here and, for the newline it made up at the end of a last line without one, still hands it to
            // Py_BuildValue: the token's own text, '' or '\r', which CPython keeps as immortal single objects, so it is still that
            if (!it->tok->implicit_newline) {
                if (it->tok->start[0] == '\r') {
                    str = str_new("\r\n");
                } else {
                    str = str_new("\n");
                }
            }
            end_col_offset++;
        }
        else if (type == NL) {
            if (it->tok->implicit_newline) {
                str = str_new("");
            }
        }
    }
    Ref type_obj = int_from_i64(type);
    Ref l0 = int_from_i64(lineno), c0 = int_from_i64(col_offset), l1 = int_from_i64(end_lineno), c1 = int_from_i64(end_col_offset);
    Ref start = tuple_new({l0.get(), c0.get()}), end = tuple_new({l1.get(), c1.get()});
    return tuple_new({type_obj.get(), str.get(), start.get(), end.get(), line.get()});
}

std::unordered_map<std::int64_t, std::unique_ptr<tokenizeriterobject>>& iterators() {
    static std::unordered_map<std::int64_t, std::unique_ptr<tokenizeriterobject>> table;
    return table;
}
std::int64_t next_id = 1;
}  // namespace

// _tokenizer(name, ...), for runtime/prelude/_tokenize.py:
//   "new", readline, extra_tokens, encoding or None -> an iterator's handle (tokenizeriter_new_impl)
//   "next", handle -> the token's tuple, or None at the end (tokenizeriter_next); an error is raised
//   "free", handle -> None (tokenizeriter_dealloc)
Ref i_tokenizer(Obj, Args a) {
    const std::string& name = as_str(a.pos(0))->text;
    if (name == "new") {
        Pending saved = std::move(indicator());      // a readline may run another tokenizer: each call has the indicator to itself
        indicator() = Pending{};
        const Str* encoding = a.pos(3) == None() ? nullptr : as_str(a.pos(3));
        auto it = std::make_unique<tokenizeriterobject>();
        it->tok = _PyTokenizer_FromReadline(a.pos(1).object(), encoding != nullptr ? encoding->text.c_str() : NULL, 1, 1);
        Pending raised = std::move(indicator());
        indicator() = std::move(saved);
        if (it->tok == NULL) throw_this(std::move(raised));
        it->tok->filename = str_new("<string>").release().object();
        if (truth(a.pos(2))) {
            it->tok->tok_extra_tokens = 1;
        }
        std::int64_t id = next_id++;
        iterators()[id] = std::move(it);
        return int_from_i64(id);
    }
    if (name == "next") {
        auto found = iterators().find(index_value(a.pos(1)));
        if (found == iterators().end()) raise_new("SystemError", "_tokenize: an iterator that was freed");
        tokenizeriterobject* it = found->second.get();
        Pending saved = std::move(indicator());
        indicator() = Pending{};
        struct token token;
        _PyToken_Init(&token);
        int type = ERRORTOKEN;
        bool stop = false;
        Ref result;
        try {
            result = next_token(it, token, type, &stop);
        } catch (...) {                              // a stop by name, on its way out
            indicator() = std::move(saved);
            throw;
        }
        // exit:
        _PyToken_Free(&token);
        if (type == ENDMARKER) {
            it->done = 1;
        }
        Pending raised = std::move(indicator());
        indicator() = std::move(saved);
        if (!raised.exc.get().is_unset()) {
            if (!result.get().is_unset())
                throw NotImplemented("a token returned with an exception set (a SystemError in CPython's tokenizer)");
            throw_this(std::move(raised));
        }
        if (!result.get().is_unset()) return result;
        // NULL with no exception set: StopIteration("EOF") at the end, or, where the C returns NULL and sets nothing (the cached
        // line it could not make), the bare StopIteration a tp_iternext's NULL reads as
        return stop ? none_ref() : Ref::steal(boolean(false));
    }
    if (name == "free") {
        iterators().erase(index_value(a.pos(1)));
        return none_ref();
    }
    throw NotImplemented("_tokenizer: " + name);
}
}  // namespace bella
