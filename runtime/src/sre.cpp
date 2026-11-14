// The regular expression engine under runtime/prelude/_sre.py: a C++ port of CPython 3.15.2's Modules/_sre (spec section 7, review log D-9, licence
// register L-08). The matching engine (sre_lib.inc) and the code validator below are the C's, kept in its shape so that the one can be read against
// the other; what sre.c does with objects is in the prelude, in Python.
//
// Secret Labs' Regular Expression Engine
//
// Copyright (c) 1997-2001 by Secret Labs AB.  All rights reserved.
//
// This version of the SRE library can be redistributed under CNRI's Python 1.6 license. For any other use, please contact Secret Labs AB
// (info@pythonware.com).
//
// Portions of this engine have been developed in cooperation with CNRI. Hewlett-Packard provided funding for 1.6 integration and other
// compatibility work.
#include <ctype.h>

#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <utility>

#include "bella/runtime.hpp"

namespace bella {
namespace {
// PyErr_CheckSignals as MAYBE_CHECK_SIGNALS calls it, every 4096 steps of a match (C-7-85). The engine is C: it answers
// SRE_ERROR_INTERRUPTED and gives back what it holds on its way out, so what a handler raised waits here until the engine has
// returned, and pattern_error lets it fly
thread_local std::exception_ptr sre_interrupted;
int sre_check_signals() {
    if (!detail::signal_tripped || detail::looks_held != 0) return 0;
    try {
        check_signals();
    } catch (...) {
        sre_interrupted = std::current_exception();
        return -1;
    }
    return 0;
}
using Py_ssize_t = std::ptrdiff_t;
using Py_UCS1 = std::uint8_t;
using Py_UCS2 = std::uint16_t;
using Py_UCS4 = std::uint32_t;
constexpr Py_ssize_t PY_SSIZE_T_MAX = INT64_MAX;
#define Py_STRINGIFY(x) #x
#define Py_ARRAY_LENGTH(a) (sizeof(a) / sizeof((a)[0]))
#define Py_UNREACHABLE() __builtin_unreachable()
#define Py_ISDIGIT(c) ((c) >= '0' && (c) <= '9')
#define Py_ISSPACE(c) ((c) == ' ' || ((c) >= '\t' && (c) <= '\r'))
#define Py_ISALPHA(c) (((c) >= 'a' && (c) <= 'z') || ((c) >= 'A' && (c) <= 'Z'))
#define Py_ISALNUM(c) (Py_ISALPHA(c) || Py_ISDIGIT(c))
#define Py_TOLOWER(c) ((c) >= 'A' && (c) <= 'Z' ? (c) + 32 : (c))
#define PyMem_Malloc std::malloc
#define PyMem_Realloc std::realloc
#define PyMem_Free std::free
#define PyErr_CheckSignals() sre_check_signals()

#define Py_UNICODE_ISDECIMAL unicode_is_decimal
#define Py_UNICODE_ISSPACE unicode_is_space
#define Py_UNICODE_ISLINEBREAK unicode_is_linebreak
#define Py_UNICODE_ISALNUM unicode_is_alnum
#define Py_UNICODE_TOLOWER unicode_to_lower
#define Py_UNICODE_TOUPPER unicode_to_upper

#define SRE_MAGIC 20230612
#define SRE_OP_FAILURE 0
#define SRE_OP_SUCCESS 1
#define SRE_OP_ANY 2
#define SRE_OP_ANY_ALL 3
#define SRE_OP_ASSERT 4
#define SRE_OP_ASSERT_NOT 5
#define SRE_OP_AT 6
#define SRE_OP_BRANCH 7
#define SRE_OP_CATEGORY 8
#define SRE_OP_CHARSET 9
#define SRE_OP_BIGCHARSET 10
#define SRE_OP_GROUPREF 11
#define SRE_OP_GROUPREF_EXISTS 12
#define SRE_OP_IN 13
#define SRE_OP_INFO 14
#define SRE_OP_JUMP 15
#define SRE_OP_LITERAL 16
#define SRE_OP_MARK 17
#define SRE_OP_MAX_UNTIL 18
#define SRE_OP_MIN_UNTIL 19
#define SRE_OP_NOT_LITERAL 20
#define SRE_OP_NEGATE 21
#define SRE_OP_RANGE 22
#define SRE_OP_REPEAT 23
#define SRE_OP_REPEAT_ONE 24
#define SRE_OP_SUBPATTERN 25
#define SRE_OP_MIN_REPEAT_ONE 26
#define SRE_OP_ATOMIC_GROUP 27
#define SRE_OP_POSSESSIVE_REPEAT 28
#define SRE_OP_POSSESSIVE_REPEAT_ONE 29
#define SRE_OP_GROUPREF_IGNORE 30
#define SRE_OP_IN_IGNORE 31
#define SRE_OP_LITERAL_IGNORE 32
#define SRE_OP_NOT_LITERAL_IGNORE 33
#define SRE_OP_GROUPREF_LOC_IGNORE 34
#define SRE_OP_IN_LOC_IGNORE 35
#define SRE_OP_LITERAL_LOC_IGNORE 36
#define SRE_OP_NOT_LITERAL_LOC_IGNORE 37
#define SRE_OP_GROUPREF_UNI_IGNORE 38
#define SRE_OP_IN_UNI_IGNORE 39
#define SRE_OP_LITERAL_UNI_IGNORE 40
#define SRE_OP_NOT_LITERAL_UNI_IGNORE 41
#define SRE_OP_RANGE_UNI_IGNORE 42
#define SRE_AT_BEGINNING 0
#define SRE_AT_BEGINNING_LINE 1
#define SRE_AT_BEGINNING_STRING 2
#define SRE_AT_BOUNDARY 3
#define SRE_AT_NON_BOUNDARY 4
#define SRE_AT_END 5
#define SRE_AT_END_LINE 6
#define SRE_AT_END_STRING 7
#define SRE_AT_LOC_BOUNDARY 8
#define SRE_AT_LOC_NON_BOUNDARY 9
#define SRE_AT_UNI_BOUNDARY 10
#define SRE_AT_UNI_NON_BOUNDARY 11
#define SRE_CATEGORY_DIGIT 0
#define SRE_CATEGORY_NOT_DIGIT 1
#define SRE_CATEGORY_SPACE 2
#define SRE_CATEGORY_NOT_SPACE 3
#define SRE_CATEGORY_WORD 4
#define SRE_CATEGORY_NOT_WORD 5
#define SRE_CATEGORY_LINEBREAK 6
#define SRE_CATEGORY_NOT_LINEBREAK 7
#define SRE_CATEGORY_LOC_WORD 8
#define SRE_CATEGORY_LOC_NOT_WORD 9
#define SRE_CATEGORY_UNI_DIGIT 10
#define SRE_CATEGORY_UNI_NOT_DIGIT 11
#define SRE_CATEGORY_UNI_SPACE 12
#define SRE_CATEGORY_UNI_NOT_SPACE 13
#define SRE_CATEGORY_UNI_WORD 14
#define SRE_CATEGORY_UNI_NOT_WORD 15
#define SRE_CATEGORY_UNI_LINEBREAK 16
#define SRE_CATEGORY_UNI_NOT_LINEBREAK 17
#define SRE_FLAG_IGNORECASE 2
#define SRE_FLAG_LOCALE 4
#define SRE_FLAG_MULTILINE 8
#define SRE_FLAG_DOTALL 16
#define SRE_FLAG_UNICODE 32
#define SRE_FLAG_VERBOSE 64
#define SRE_FLAG_DEBUG 128
#define SRE_FLAG_ASCII 256
#define SRE_INFO_PREFIX 1
#define SRE_INFO_LITERAL 2
#define SRE_INFO_CHARSET 4

#define SRE_CODE Py_UCS4
#define SRE_MAXREPEAT (~(SRE_CODE)0)
#define SRE_MAXGROUPS ((SRE_CODE)INT32_MAX / 2)
#define SRE_CODE_BITS (8 * sizeof(SRE_CODE))

typedef struct SRE_REPEAT_T {
    Py_ssize_t count;
    const SRE_CODE* pattern; /* points to REPEAT operator arguments */
    const void* last_ptr; /* helper to check for infinite loops */
    struct SRE_REPEAT_T *prev; /* points to previous repeat context */
    /* for SRE_REPEAT pool */
    struct SRE_REPEAT_T *pool_prev;
    struct SRE_REPEAT_T *pool_next;
} SRE_REPEAT;

typedef struct {
    /* string pointers */
    const void* ptr; /* current position (also end of current slice) */
    const void* beginning; /* start of original string */
    const void* start; /* start of current slice */
    const void* end; /* end of original string */
    Py_ssize_t pos, endpos;
    int isbytes;
    int charsize; /* character size */
    int match_all;
    int must_advance;
    int debug;
    /* marks */
    int lastmark;
    int lastindex;
    const void** mark;
    /* dynamically allocated stuff */
    char* data_stack;
    size_t data_stack_size;
    size_t data_stack_base;
    /* current repeat context */
    SRE_REPEAT *repeat;
    /* SRE_REPEAT pool */
    SRE_REPEAT *repeat_pool_used;
    SRE_REPEAT *repeat_pool_unused;
    unsigned int sigcount;
} SRE_STATE;

#define LOCAL(type) static inline type
#define SRE_ERROR_ILLEGAL -1 /* illegal opcode */
#define SRE_ERROR_STATE -2 /* illegal state */
#define SRE_ERROR_RECURSION_LIMIT -3 /* runaway recursion */
#define SRE_ERROR_MEMORY -9 /* out of memory */
#define SRE_ERROR_INTERRUPTED -10 /* signal handler raised exception */
#define INIT_TRACE(state)
#define DO_TRACE 0
#define TRACE(v)
#define USE_COMPUTED_GOTOS 0

int sre_isalnum(unsigned int ch) { return isalnum((int)ch); }
unsigned int sre_tolower(unsigned int ch) { return (unsigned int)tolower((int)ch); }
unsigned int sre_toupper(unsigned int ch) { return (unsigned int)toupper((int)ch); }
#define SRE_IS_DIGIT(ch) ((ch) <= '9' && Py_ISDIGIT(ch))
#define SRE_IS_SPACE(ch) ((ch) <= ' ' && Py_ISSPACE(ch))
#define SRE_IS_LINEBREAK(ch) ((ch) == '\n')
#define SRE_IS_WORD(ch) ((ch) <= 'z' && (Py_ISALNUM(ch) || (ch) == '_'))
unsigned int sre_lower_ascii(unsigned int ch) { return ((ch) < 128 ? Py_TOLOWER(ch) : ch); }
#define SRE_LOC_IS_ALNUM(ch) (!((ch) & ~255) ? sre_isalnum((ch)) : 0)
#define SRE_LOC_IS_WORD(ch) (SRE_LOC_IS_ALNUM((ch)) || (ch) == '_')
unsigned int sre_lower_locale(unsigned int ch) { return ((ch) < 256 ? (unsigned int)sre_tolower((ch)) : ch); }
unsigned int sre_upper_locale(unsigned int ch) { return ((ch) < 256 ? (unsigned int)sre_toupper((ch)) : ch); }
#define SRE_UNI_IS_DIGIT(ch) Py_UNICODE_ISDECIMAL(ch)
#define SRE_UNI_IS_SPACE(ch) Py_UNICODE_ISSPACE(ch)
#define SRE_UNI_IS_LINEBREAK(ch) Py_UNICODE_ISLINEBREAK(ch)
#define SRE_UNI_IS_ALNUM(ch) Py_UNICODE_ISALNUM(ch)
#define SRE_UNI_IS_WORD(ch) (SRE_UNI_IS_ALNUM(ch) || (ch) == '_')
unsigned int sre_lower_unicode(unsigned int ch) { return (unsigned int)Py_UNICODE_TOLOWER(ch); }
unsigned int sre_upper_unicode(unsigned int ch) { return (unsigned int)Py_UNICODE_TOUPPER(ch); }

LOCAL(int)
sre_category(SRE_CODE category, unsigned int ch)
{
    switch (category) {

    case SRE_CATEGORY_DIGIT:
        return SRE_IS_DIGIT(ch);
    case SRE_CATEGORY_NOT_DIGIT:
        return !SRE_IS_DIGIT(ch);
    case SRE_CATEGORY_SPACE:
        return SRE_IS_SPACE(ch);
    case SRE_CATEGORY_NOT_SPACE:
        return !SRE_IS_SPACE(ch);
    case SRE_CATEGORY_WORD:
        return SRE_IS_WORD(ch);
    case SRE_CATEGORY_NOT_WORD:
        return !SRE_IS_WORD(ch);
    case SRE_CATEGORY_LINEBREAK:
        return SRE_IS_LINEBREAK(ch);
    case SRE_CATEGORY_NOT_LINEBREAK:
        return !SRE_IS_LINEBREAK(ch);

    case SRE_CATEGORY_LOC_WORD:
        return SRE_LOC_IS_WORD(ch);
    case SRE_CATEGORY_LOC_NOT_WORD:
        return !SRE_LOC_IS_WORD(ch);

    case SRE_CATEGORY_UNI_DIGIT:
        return SRE_UNI_IS_DIGIT(ch);
    case SRE_CATEGORY_UNI_NOT_DIGIT:
        return !SRE_UNI_IS_DIGIT(ch);
    case SRE_CATEGORY_UNI_SPACE:
        return SRE_UNI_IS_SPACE(ch);
    case SRE_CATEGORY_UNI_NOT_SPACE:
        return !SRE_UNI_IS_SPACE(ch);
    case SRE_CATEGORY_UNI_WORD:
        return SRE_UNI_IS_WORD(ch);
    case SRE_CATEGORY_UNI_NOT_WORD:
        return !SRE_UNI_IS_WORD(ch);
    case SRE_CATEGORY_UNI_LINEBREAK:
        return SRE_UNI_IS_LINEBREAK(ch);
    case SRE_CATEGORY_UNI_NOT_LINEBREAK:
        return !SRE_UNI_IS_LINEBREAK(ch);
    }
    return 0;
}

LOCAL(int)
char_loc_ignore(SRE_CODE pattern, SRE_CODE ch)
{
    return ch == pattern
        || (SRE_CODE) sre_lower_locale(ch) == pattern
        || (SRE_CODE) sre_upper_locale(ch) == pattern;
}

void data_stack_dealloc(SRE_STATE* state)
{
    if (state->data_stack) {
        PyMem_Free(state->data_stack);
        state->data_stack = NULL;
    }
    state->data_stack_size = state->data_stack_base = 0;
}

int data_stack_grow(SRE_STATE* state, Py_ssize_t size)
{
    Py_ssize_t minsize, cursize;
    minsize = state->data_stack_base+size;
    cursize = state->data_stack_size;
    if (cursize < minsize) {
        void* stack;
        cursize = minsize+minsize/4+1024;
        stack = PyMem_Realloc(state->data_stack, cursize);
        if (!stack) {
            data_stack_dealloc(state);
            return SRE_ERROR_MEMORY;
        }
        state->data_stack = (char *)stack;
        state->data_stack_size = cursize;
    }
    return 0;
}

SRE_REPEAT* repeat_pool_malloc(SRE_STATE *state)
{
    SRE_REPEAT *repeat;
    if (state->repeat_pool_unused) {
        /* remove from unused pool (singly-linked list) */
        repeat = state->repeat_pool_unused;
        state->repeat_pool_unused = repeat->pool_next;
    }
    else {
        repeat = (SRE_REPEAT*)PyMem_Malloc(sizeof(SRE_REPEAT));
        if (!repeat) {
            return NULL;
        }
    }
    /* add to used pool (doubly-linked list) */
    SRE_REPEAT *temp = state->repeat_pool_used;
    if (temp) {
        temp->pool_prev = repeat;
    }
    repeat->pool_prev = NULL;
    repeat->pool_next = temp;
    state->repeat_pool_used = repeat;
    return repeat;
}

void repeat_pool_free(SRE_STATE *state, SRE_REPEAT *repeat)
{
    SRE_REPEAT *prev = repeat->pool_prev;
    SRE_REPEAT *next = repeat->pool_next;
    /* remove from used pool (doubly-linked list) */
    if (prev) {
        prev->pool_next = next;
    }
    else {
        state->repeat_pool_used = next;
    }
    if (next) {
        next->pool_prev = prev;
    }
    /* add to unused pool (singly-linked list) */
    repeat->pool_next = state->repeat_pool_unused;
    state->repeat_pool_unused = repeat;
}

void repeat_pool_clear(SRE_STATE *state)
{
    /* clear used pool */
    SRE_REPEAT *next = state->repeat_pool_used;
    state->repeat_pool_used = NULL;
    while (next) {
        SRE_REPEAT *temp = next;
        next = temp->pool_next;
        PyMem_Free(temp);
    }
    /* clear unused pool */
    next = state->repeat_pool_unused;
    state->repeat_pool_unused = NULL;
    while (next) {
        SRE_REPEAT *temp = next;
        next = temp->pool_next;
        PyMem_Free(temp);
    }
}

/* generate 8-bit version */
#define SRE_CHAR Py_UCS1
#define SIZEOF_SRE_CHAR 1
#define SRE(F) sre_ucs1_##F
#include "sre_lib.inc"

/* generate 16-bit unicode version */
#define SRE_CHAR Py_UCS2
#define SIZEOF_SRE_CHAR 2
#define SRE(F) sre_ucs2_##F
#include "sre_lib.inc"

/* generate 32-bit unicode version */
#define SRE_CHAR Py_UCS4
#define SIZEOF_SRE_CHAR 4
#define SRE(F) sre_ucs4_##F
#include "sre_lib.inc"

LOCAL(Py_ssize_t)
sre_match(SRE_STATE* state, SRE_CODE* pattern)
{
    if (state->charsize == 1)
        return sre_ucs1_match(state, pattern, 1);
    if (state->charsize == 2)
        return sre_ucs2_match(state, pattern, 1);
    assert(state->charsize == 4);
    return sre_ucs4_match(state, pattern, 1);
}

LOCAL(Py_ssize_t)
sre_search(SRE_STATE* state, SRE_CODE* pattern)
{
    if (state->charsize == 1)
        return sre_ucs1_search(state, pattern);
    if (state->charsize == 2)
        return sre_ucs2_search(state, pattern);
    assert(state->charsize == 4);
    return sre_ucs4_search(state, pattern);
}

/* -------------------------------------------------------------------- */
/* Code validation */

/* To learn more about this code, have a look at the _compile() function in
   Lib/sre_compile.py.  The validation functions below checks the code array
   for conformance with the code patterns generated there.

   The nice thing about the generated code is that it is position-independent:
   all jumps are relative jumps forward.  Also, jumps don't cross each other:
   the target of a later jump is always earlier than the target of an earlier
   jump.  IOW, this is okay:

   J---------J-------T--------T
    \         \_____/        /
     \______________________/

   but this is not:

   J---------J-------T--------T
    \_________\_____/        /
               \____________/

   It also helps that SRE_CODE is always an unsigned type.
*/

/* Defining this one enables tracing of the validator */
#undef VVERBOSE

/* Trace macro for the validator */
#if defined(VVERBOSE)
#define VTRACE(v) printf v
#else
#define VTRACE(v) do {} while(0)  /* do nothing */
#endif

/* Report failure */
#define FAIL do { VTRACE(("FAIL: %d\n", __LINE__)); return -1; } while (0)

/* Extract opcode, argument, or skip count from code array */
#define GET_OP                                          \
    do {                                                \
        VTRACE(("%p: ", code));                         \
        if (code >= end) FAIL;                          \
        op = *code++;                                   \
        VTRACE(("%lu (op)\n", (unsigned long)op));      \
    } while (0)
#define GET_ARG                                         \
    do {                                                \
        VTRACE(("%p= ", code));                         \
        if (code >= end) FAIL;                          \
        arg = *code++;                                  \
        VTRACE(("%lu (arg)\n", (unsigned long)arg));    \
    } while (0)
#define GET_SKIP_ADJ(adj)                               \
    do {                                                \
        VTRACE(("%p= ", code));                         \
        if (code >= end) FAIL;                          \
        skip = *code;                                   \
        VTRACE(("%lu (skip to %p)\n",                   \
               (unsigned long)skip, code+skip));        \
        if (skip-adj > (uintptr_t)(end - code))         \
            FAIL;                                       \
        code++;                                         \
    } while (0)
#define GET_SKIP GET_SKIP_ADJ(0)

static int
_validate_charset(SRE_CODE *code, SRE_CODE *end)
{
    /* Some variables are manipulated by the macros above */
    SRE_CODE op;
    SRE_CODE arg;
    SRE_CODE offset;
    int i;

    while (code < end) {
        GET_OP;
        switch (op) {

        case SRE_OP_NEGATE:
            break;

        case SRE_OP_LITERAL:
            GET_ARG;
            break;

        case SRE_OP_RANGE:
        case SRE_OP_RANGE_UNI_IGNORE:
            GET_ARG;
            GET_ARG;
            break;

        case SRE_OP_CHARSET:
            offset = 256/SRE_CODE_BITS; /* 256-bit bitmap */
            if (offset > (uintptr_t)(end - code))
                FAIL;
            code += offset;
            break;

        case SRE_OP_BIGCHARSET:
            GET_ARG; /* Number of blocks */
            offset = 256/sizeof(SRE_CODE); /* 256-byte table */
            if (offset > (uintptr_t)(end - code))
                FAIL;
            /* Make sure that each byte points to a valid block */
            for (i = 0; i < 256; i++) {
                if (((unsigned char *)code)[i] >= arg)
                    FAIL;
            }
            code += offset;
            offset = arg * (256/SRE_CODE_BITS); /* 256-bit bitmap times arg */
            if (offset > (uintptr_t)(end - code))
                FAIL;
            code += offset;
            break;

        case SRE_OP_CATEGORY:
            GET_ARG;
            switch (arg) {
            case SRE_CATEGORY_DIGIT:
            case SRE_CATEGORY_NOT_DIGIT:
            case SRE_CATEGORY_SPACE:
            case SRE_CATEGORY_NOT_SPACE:
            case SRE_CATEGORY_WORD:
            case SRE_CATEGORY_NOT_WORD:
            case SRE_CATEGORY_LINEBREAK:
            case SRE_CATEGORY_NOT_LINEBREAK:
            case SRE_CATEGORY_LOC_WORD:
            case SRE_CATEGORY_LOC_NOT_WORD:
            case SRE_CATEGORY_UNI_DIGIT:
            case SRE_CATEGORY_UNI_NOT_DIGIT:
            case SRE_CATEGORY_UNI_SPACE:
            case SRE_CATEGORY_UNI_NOT_SPACE:
            case SRE_CATEGORY_UNI_WORD:
            case SRE_CATEGORY_UNI_NOT_WORD:
            case SRE_CATEGORY_UNI_LINEBREAK:
            case SRE_CATEGORY_UNI_NOT_LINEBREAK:
                break;
            default:
                FAIL;
            }
            break;

        default:
            FAIL;

        }
    }

    return 0;
}

/* Returns 0 on success, -1 on failure, and 1 if the last op is JUMP. */
static int
_validate_inner(SRE_CODE *code, SRE_CODE *end, Py_ssize_t groups)
{
    /* Some variables are manipulated by the macros above */
    SRE_CODE op;
    SRE_CODE arg;
    SRE_CODE skip;

    VTRACE(("code=%p, end=%p\n", code, end));

    if (code > end)
        FAIL;

    while (code < end) {
        GET_OP;
        switch (op) {

        case SRE_OP_MARK:
            /* We don't check whether marks are properly nested; the
               sre_match() code is robust even if they don't, and the worst
               you can get is nonsensical match results. */
            GET_ARG;
            if (arg >= 2 * (size_t)groups) {
                VTRACE(("arg=%d, groups=%d\n", (int)arg, (int)groups));
                FAIL;
            }
            break;

        case SRE_OP_LITERAL:
        case SRE_OP_NOT_LITERAL:
        case SRE_OP_LITERAL_IGNORE:
        case SRE_OP_NOT_LITERAL_IGNORE:
        case SRE_OP_LITERAL_UNI_IGNORE:
        case SRE_OP_NOT_LITERAL_UNI_IGNORE:
        case SRE_OP_LITERAL_LOC_IGNORE:
        case SRE_OP_NOT_LITERAL_LOC_IGNORE:
            GET_ARG;
            /* The arg is just a character, nothing to check */
            break;

        case SRE_OP_SUCCESS:
        case SRE_OP_FAILURE:
            /* Nothing to check; these normally end the matching process */
            break;

        case SRE_OP_AT:
            GET_ARG;
            switch (arg) {
            case SRE_AT_BEGINNING:
            case SRE_AT_BEGINNING_STRING:
            case SRE_AT_BEGINNING_LINE:
            case SRE_AT_END:
            case SRE_AT_END_LINE:
            case SRE_AT_END_STRING:
            case SRE_AT_BOUNDARY:
            case SRE_AT_NON_BOUNDARY:
            case SRE_AT_LOC_BOUNDARY:
            case SRE_AT_LOC_NON_BOUNDARY:
            case SRE_AT_UNI_BOUNDARY:
            case SRE_AT_UNI_NON_BOUNDARY:
                break;
            default:
                FAIL;
            }
            break;

        case SRE_OP_ANY:
        case SRE_OP_ANY_ALL:
            /* These have no operands */
            break;

        case SRE_OP_IN:
        case SRE_OP_IN_IGNORE:
        case SRE_OP_IN_UNI_IGNORE:
        case SRE_OP_IN_LOC_IGNORE:
            GET_SKIP;
            /* Stop 1 before the end; we check the FAILURE below */
            if (_validate_charset(code, code+skip-2))
                FAIL;
            if (code[skip-2] != SRE_OP_FAILURE)
                FAIL;
            code += skip-1;
            break;

        case SRE_OP_INFO:
            {
                /* A minimal info field is
                   <INFO> <1=skip> <2=flags> <3=min> <4=max>;
                   If SRE_INFO_PREFIX or SRE_INFO_CHARSET is in the flags,
                   more follows. */
                SRE_CODE flags, i;
                SRE_CODE *newcode;
                GET_SKIP;
                newcode = code+skip-1;
                GET_ARG; flags = arg;
                GET_ARG;
                GET_ARG;
                /* Check that only valid flags are present */
                if ((flags & ~(SRE_INFO_PREFIX |
                               SRE_INFO_LITERAL |
                               SRE_INFO_CHARSET)) != 0)
                    FAIL;
                /* PREFIX and CHARSET are mutually exclusive */
                if ((flags & SRE_INFO_PREFIX) &&
                    (flags & SRE_INFO_CHARSET))
                    FAIL;
                /* LITERAL implies PREFIX */
                if ((flags & SRE_INFO_LITERAL) &&
                    !(flags & SRE_INFO_PREFIX))
                    FAIL;
                /* Validate the prefix */
                if (flags & SRE_INFO_PREFIX) {
                    SRE_CODE prefix_len;
                    GET_ARG; prefix_len = arg;
                    GET_ARG;
                    /* Here comes the prefix string */
                    if (prefix_len > (uintptr_t)(newcode - code))
                        FAIL;
                    code += prefix_len;
                    /* And here comes the overlap table */
                    if (prefix_len > (uintptr_t)(newcode - code))
                        FAIL;
                    /* Each overlap value should be < prefix_len */
                    for (i = 0; i < prefix_len; i++) {
                        if (code[i] >= prefix_len)
                            FAIL;
                    }
                    code += prefix_len;
                }
                /* Validate the charset */
                if (flags & SRE_INFO_CHARSET) {
                    if (_validate_charset(code, newcode-1))
                        FAIL;
                    if (newcode[-1] != SRE_OP_FAILURE)
                        FAIL;
                    code = newcode;
                }
                else if (code != newcode) {
                  VTRACE(("code=%p, newcode=%p\n", code, newcode));
                    FAIL;
                }
            }
            break;

        case SRE_OP_BRANCH:
            {
                SRE_CODE *target = NULL;
                for (;;) {
                    GET_SKIP;
                    if (skip == 0)
                        break;
                    /* Stop 2 before the end; we check the JUMP below */
                    if (_validate_inner(code, code+skip-3, groups))
                        FAIL;
                    code += skip-3;
                    /* Check that it ends with a JUMP, and that each JUMP
                       has the same target */
                    GET_OP;
                    if (op != SRE_OP_JUMP)
                        FAIL;
                    GET_SKIP;
                    if (target == NULL)
                        target = code+skip-1;
                    else if (code+skip-1 != target)
                        FAIL;
                }
                if (code != target)
                    FAIL;
            }
            break;

        case SRE_OP_REPEAT_ONE:
        case SRE_OP_MIN_REPEAT_ONE:
        case SRE_OP_POSSESSIVE_REPEAT_ONE:
            {
                SRE_CODE min, max;
                GET_SKIP;
                GET_ARG; min = arg;
                GET_ARG; max = arg;
                if (min > max)
                    FAIL;
                if (max > SRE_MAXREPEAT)
                    FAIL;
                if (_validate_inner(code, code+skip-4, groups))
                    FAIL;
                code += skip-4;
                GET_OP;
                if (op != SRE_OP_SUCCESS)
                    FAIL;
            }
            break;

        case SRE_OP_REPEAT:
        case SRE_OP_POSSESSIVE_REPEAT:
            {
                SRE_CODE op1 = op, min, max;
                GET_SKIP;
                GET_ARG; min = arg;
                GET_ARG; max = arg;
                if (min > max)
                    FAIL;
                if (max > SRE_MAXREPEAT)
                    FAIL;
                if (_validate_inner(code, code+skip-3, groups))
                    FAIL;
                code += skip-3;
                GET_OP;
                if (op1 == SRE_OP_POSSESSIVE_REPEAT) {
                    if (op != SRE_OP_SUCCESS)
                        FAIL;
                }
                else {
                    if (op != SRE_OP_MAX_UNTIL && op != SRE_OP_MIN_UNTIL)
                        FAIL;
                }
            }
            break;

        case SRE_OP_ATOMIC_GROUP:
            {
                GET_SKIP;
                if (_validate_inner(code, code+skip-2, groups))
                    FAIL;
                code += skip-2;
                GET_OP;
                if (op != SRE_OP_SUCCESS)
                    FAIL;
            }
            break;

        case SRE_OP_GROUPREF:
        case SRE_OP_GROUPREF_IGNORE:
        case SRE_OP_GROUPREF_UNI_IGNORE:
        case SRE_OP_GROUPREF_LOC_IGNORE:
            GET_ARG;
            if (arg >= (size_t)groups)
                FAIL;
            break;

        case SRE_OP_GROUPREF_EXISTS:
            /* The regex syntax for this is: '(?(group)then|else)', where
               'group' is either an integer group number or a group name,
               'then' and 'else' are sub-regexes, and 'else' is optional. */
            GET_ARG;
            if (arg >= (size_t)groups)
                FAIL;
            GET_SKIP_ADJ(1);
            code--; /* The skip is relative to the first arg! */
            /* There are two possibilities here: if there is both a 'then'
               part and an 'else' part, the generated code looks like:

               GROUPREF_EXISTS
               <group>
               <skipyes>
               ...then part...
               JUMP
               <skipno>
               (<skipyes> jumps here)
               ...else part...
               (<skipno> jumps here)

               If there is only a 'then' part, it looks like:

               GROUPREF_EXISTS
               <group>
               <skip>
               ...then part...
               (<skip> jumps here)

               There is no direct way to decide which it is, and we don't want
               to allow arbitrary jumps anywhere in the code; so we just look
               for a JUMP opcode preceding our skip target.
            */
            VTRACE(("then part:\n"));
            int rc;
            rc = _validate_inner(code+1, code+skip-1, groups);
            if (rc == 1) {
                VTRACE(("else part:\n"));
                code += skip-2; /* Position after JUMP, at <skipno> */
                GET_SKIP;
                rc = _validate_inner(code, code+skip-1, groups);
            }
            if (rc)
                FAIL;
            code += skip-1;
            break;

        case SRE_OP_ASSERT:
        case SRE_OP_ASSERT_NOT:
            GET_SKIP;
            GET_ARG; /* 0 for lookahead, width for lookbehind */
            code--; /* Back up over arg to simplify math below */
            /* Stop 1 before the end; we check the SUCCESS below */
            if (_validate_inner(code+1, code+skip-2, groups))
                FAIL;
            code += skip-2;
            GET_OP;
            if (op != SRE_OP_SUCCESS)
                FAIL;
            break;

        case SRE_OP_JUMP:
            if (code + 1 != end)
                FAIL;
            VTRACE(("JUMP: %d\n", __LINE__));
            return 1;

        default:
            FAIL;

        }
    }

    VTRACE(("okay\n"));
    return 0;
}

static int
_validate_outer(SRE_CODE *code, SRE_CODE *end, Py_ssize_t groups)
{
    if (groups < 0 || (size_t)groups > SRE_MAXGROUPS ||
        code >= end || end[-1] != SRE_OP_SUCCESS)
        FAIL;
    return _validate_inner(code, end-1, groups);
}

// ---- what the prelude asks of it

struct StringData {
    const void* data = nullptr;
    Py_ssize_t length = 0;
    int isbytes = 0, charsize = 1;
};
bool get_string(Obj string, StringData& out) {   // getstring: a str's data, or a byte string's buffer
    if (const Str* s = as_str(string)) {
        out.data = s->units.data();
        out.length = static_cast<Py_ssize_t>(s->length);
        out.charsize = s->width;
        out.isbytes = 0;
        return true;
    }
    if (is_bytes_like(string)) {
        const std::string& b = bytes_data(string);
        out.data = b.data();
        out.length = static_cast<Py_ssize_t>(b.size());
        out.charsize = 1;
        out.isbytes = 1;
        return true;
    }
    if (!type_lookup(type_of(string), intern("__buffer__")).is_unset())
        throw NotImplemented("a regular expression over an object with the buffer protocol that is not bytes or bytearray (CPython has it; the runtime does not yet)");
    return false;
}
std::int64_t i64_of(Obj v) {
    std::int64_t out = 0;
    int_fits_i64(v, out);
    return out;
}
const SRE_CODE* code_of(Obj code) { return reinterpret_cast<const SRE_CODE*>(bytes_data(code).data()); }

Ref i_getstring(Obj, Args a) {                   // (string) -> (length, isbytes)
    StringData s;
    if (!get_string(a.pos(0), s))
        raise_new("TypeError", "expected string or bytes-like object, got '" + type_of(a.pos(0))->name + "'");
    Ref length = int_from_i64(s.length);
    return tuple_new({length.get(), Ref::steal(boolean(s.isbytes != 0)).get()});
}
Ref i_slice(Obj, Args a) {                       // getslice: (string, start, end)
    Obj string = a.pos(0);
    std::int64_t start = i64_of(a.pos(1)), end = i64_of(a.pos(2));
    if (const Str* s = as_str(string)) {
        if (start == 0 && end >= static_cast<std::int64_t>(s->length))   // PyUnicode_Substring: unicode_result_unchanged
            return is_exact_str(string) ? Ref::share(string) : str_new(s->text);
        std::u32string out;
        for (std::int64_t i = start; i < end; ++i) out += s->at(static_cast<std::size_t>(i));
        return str_from_codepoints(out);
    }
    const std::string& b = bytes_data(string);
    if (is_kind(string, Kind::Bytes) && !is_subclass_instance(string) && start == 0 && end == static_cast<std::int64_t>(b.size())) return Ref::share(string);
    return bytes_new(std::string_view(b).substr(static_cast<std::size_t>(start), static_cast<std::size_t>(end - start)));
}
Ref i_has_backslash(Obj, Args a) {               // pattern_subx: is it a literal?  None when it is no string at all
    StringData s;
    if (!get_string(a.pos(0), s)) return none_ref();
    if (const Str* t = as_str(a.pos(0))) return Ref::steal(boolean(t->text.find('\\') != std::string::npos));
    return Ref::steal(boolean(bytes_data(a.pos(0)).find('\\') != std::string::npos));
}
// (code bytes, groups, string, pos, endpos, start, must_advance, mode): the marks, or None. pos and endpos are state_init's; start is where a scan has got to
Ref i_run(Obj, Args a) {
    Obj code = a.pos(0);
    Py_ssize_t groups = i64_of(a.pos(1));
    StringData data;
    get_string(a.pos(2), data);
    Py_ssize_t pos = i64_of(a.pos(3)), end = i64_of(a.pos(4)), start = i64_of(a.pos(5));
    int must_advance = truth(a.pos(6)) ? 1 : 0;
    std::int64_t mode = i64_of(a.pos(7));        // 0 match, 1 fullmatch, 2 search
    SRE_STATE state;
    std::memset(&state, 0, sizeof(SRE_STATE));
    state.mark = static_cast<const void**>(PyMem_Malloc(sizeof(void*) * static_cast<std::size_t>(groups * 2 + 1)));
    if (state.mark == nullptr) raise_new("MemoryError", "");
    std::memset(state.mark, 0, sizeof(void*) * static_cast<std::size_t>(groups * 2 + 1));
    state.lastmark = -1;
    state.lastindex = -1;
    const char* ptr = static_cast<const char*>(data.data);
    state.isbytes = data.isbytes;
    state.charsize = data.charsize;
    state.match_all = mode == 1 ? 1 : 0;
    state.must_advance = must_advance;
    state.beginning = ptr;
    state.start = ptr + start * data.charsize;
    state.end = ptr + end * data.charsize;
    state.pos = pos;
    state.endpos = end;
    state.ptr = state.start;
    SRE_CODE* program = const_cast<SRE_CODE*>(code_of(code));
    Py_ssize_t status = mode == 2 ? sre_search(&state, program) : sre_match(&state, program);
    auto finish = [&] {
        data_stack_dealloc(&state);
        repeat_pool_clear(&state);
        PyMem_Free(state.mark);
    };
    if (status == 0) {
        finish();
        return none_ref();
    }
    if (status < 0) {                            // pattern_error
        finish();
        if (status == SRE_ERROR_INTERRUPTED) std::rethrow_exception(std::exchange(sre_interrupted, nullptr));   // "An exception has already been raised, so let it fly"
        if (status == SRE_ERROR_RECURSION_LIMIT) raise_new("RecursionError", "maximum recursion limit exceeded");
        if (status == SRE_ERROR_MEMORY) raise_new("MemoryError", "");
        raise_new("RuntimeError", "internal error in regular expression engine");
    }
    std::vector<Obj> out;
    auto offset = [&](const void* p) { return (static_cast<const char*>(p) - ptr) / data.charsize; };
    auto push = [&](std::int64_t v) { out.push_back(int_from_i64(v).release()); };
    push(offset(state.start));
    push(offset(state.ptr));
    push(state.lastindex);
    bool wrong = false;
    for (Py_ssize_t i = 0, j = 0; i < groups; ++i, j += 2) {
        if (j + 1 <= state.lastmark && state.mark[j] && state.mark[j + 1]) {
            auto b = offset(state.mark[j]), e = offset(state.mark[j + 1]);
            wrong = wrong || b > e;
            push(b);
            push(e);
        } else {
            push(-1);
            push(-1);
        }
    }
    finish();
    Ref result = tuple_steal(std::move(out));
    if (wrong) raise_new("SystemError", "The span of capturing group is wrong, please report a bug for the re module.");
    return result;
}
Ref i_code(Obj, Args a) {                        // (list of ints) -> what the engine reads, or OverflowError as _sre_compile_impl says
    std::string out;
    for (Obj v : static_cast<List*>(a.pos(0).object())->items) {
        if (!is_int(v)) raise_new("TypeError", "an integer is required");   // PyLong_AsUnsignedLong
        if (int_is_negative(v)) raise_new("OverflowError", "can't convert negative value to unsigned int");
        std::int64_t value = 0;
        if (!int_fits_i64(v, value)) raise_new("OverflowError", "Python int too large to convert to C unsigned long");
        if (value > 0xFFFFFFFFLL) raise_new("OverflowError", "regular expression code size limit exceeded");
        auto word = static_cast<SRE_CODE>(value);
        out.append(reinterpret_cast<const char*>(&word), sizeof word);
    }
    return bytes_new(out);
}
Ref i_validate(Obj, Args a) {                    // _validate: (code bytes, groups)
    const std::string& b = bytes_data(a.pos(0));
    Py_ssize_t size = static_cast<Py_ssize_t>(b.size() / sizeof(SRE_CODE));
    SRE_CODE* program = const_cast<SRE_CODE*>(code_of(a.pos(0)));
    if (_validate_outer(program, program + size, i64_of(a.pos(1))) != 0) raise_new("RuntimeError", "invalid SRE code");
    return none_ref();
}
Ref i_export(Obj, Args a) {                      // (string, +1 or -1): PyObject_GetBuffer and PyBuffer_Release, which only a bytearray notices
    if (is_kind(a.pos(0), Kind::ByteArray)) static_cast<BytesObject*>(a.pos(0).object())->exports += i64_of(a.pos(1));
    return none_ref();
}
Ref i_unicode_lower(Obj, Args a) { return int_from_i64(sre_lower_unicode(static_cast<unsigned int>(i64_of(a.pos(0))))); }
Ref i_unicode_upper(Obj, Args a) { return int_from_i64(sre_upper_unicode(static_cast<unsigned int>(i64_of(a.pos(0))))); }
}  // namespace

Ref i_sre_call(Obj, Args a) {                    // _sre_call(name, ...)
    const std::string& name = as_str(a.pos(0))->text;
    Args rest{a.data + 1, a.npos - 1, nullptr, 0};
    if (name == "run") return i_run(Obj{}, rest);
    if (name == "slice") return i_slice(Obj{}, rest);
    if (name == "getstring") return i_getstring(Obj{}, rest);
    if (name == "has_backslash") return i_has_backslash(Obj{}, rest);
    if (name == "code") return i_code(Obj{}, rest);
    if (name == "validate") return i_validate(Obj{}, rest);
    if (name == "export") return i_export(Obj{}, rest);
    if (name == "lower") return i_unicode_lower(Obj{}, rest);
    if (name == "upper") return i_unicode_upper(Obj{}, rest);
    throw NotImplemented("_sre primitive " + name);
}
}  // namespace bella
