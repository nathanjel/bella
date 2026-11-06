// list.sort and sorted (Objects/listobject.c, 3.15's powersort), line for line: which pairs are
// compared and in what order is what a program with its own __lt__ sees. A comparison that raises
// is held in the state and rethrown once the list is whole again, where CPython's C returns -1 and
// goes to `fail`, so a merge's clean-up runs as it does there.
//
// CPython's special-case compares (latin strings, compact ints, floats) give what the general one
// gives, so here they are the general one. unsafe_object_compare is not: on NotImplemented it asks
// again, which a __lt__ that counts its calls can see. So is unsafe_tuple_compare, whose first
// elements go through it.
#include <algorithm>
#include <exception>
#include <vector>

#include "bella/runtime.hpp"

namespace bella {
namespace {

constexpr int MAX_MERGE_PENDING = 64;
constexpr std::int64_t MIN_GALLOP = 7;
constexpr std::int64_t MAX_MINRUN = 64;

struct SortSlice {
    Obj* keys;
    Obj* values;                                 // nullptr without a key function
};
void slice_copy(SortSlice* s1, std::int64_t i, const SortSlice* s2, std::int64_t j) {
    s1->keys[i] = s2->keys[j];
    if (s1->values != nullptr) s1->values[i] = s2->values[j];
}
void slice_copy_incr(SortSlice* dst, SortSlice* src) {
    *dst->keys++ = *src->keys++;
    if (dst->values != nullptr) *dst->values++ = *src->values++;
}
void slice_copy_decr(SortSlice* dst, SortSlice* src) {
    *dst->keys-- = *src->keys--;
    if (dst->values != nullptr) *dst->values-- = *src->values--;
}
void slice_memcpy(SortSlice* s1, std::int64_t i, const SortSlice* s2, std::int64_t j, std::int64_t n) {
    std::copy_n(s2->keys + j, n, s1->keys + i);
    if (s1->values != nullptr) std::copy_n(s2->values + j, n, s1->values + i);
}
void slice_memmove(SortSlice* s1, std::int64_t i, const SortSlice* s2, std::int64_t j, std::int64_t n) {
    std::vector<Obj> keys(s2->keys + j, s2->keys + j + n);
    std::copy(keys.begin(), keys.end(), s1->keys + i);
    if (s1->values != nullptr) {
        std::vector<Obj> values(s2->values + j, s2->values + j + n);
        std::copy(values.begin(), values.end(), s1->values + i);
    }
}
void slice_advance(SortSlice* s, std::int64_t n) {
    s->keys += n;
    if (s->values != nullptr) s->values += n;
}
void slice_reverse(SortSlice* s, std::int64_t n) {
    std::reverse(s->keys, s->keys + n);
    if (s->values != nullptr) std::reverse(s->values, s->values + n);
}

struct Run {
    SortSlice base;
    std::int64_t len;
    int power;
};
enum class Compare { Safe, UnsafeObject, Tuple };

struct MergeState {
    std::int64_t min_gallop = MIN_GALLOP;
    std::int64_t listlen = 0;
    Obj* basekeys = nullptr;
    SortSlice a{nullptr, nullptr};
    std::vector<Obj> temp;
    std::int64_t alloced = 0;
    bool has_values = false;
    int n = 0;
    Run pending[MAX_MERGE_PENDING];
    Compare key_compare = Compare::Safe;
    Compare tuple_elem_compare = Compare::Safe;
    std::int64_t mr_current = 0, mr_e = 0, mr_mask = 0;
    std::exception_ptr error;
};

bool safe_compare(Obj v, Obj w) {                // PyObject_RichCompareBool(v, w, Py_LT)
    Ref r = compare(CmpOp::Lt, v, w);
    return truth(r.get());
}
bool equal_compare(Obj v, Obj w) {               // PyObject_RichCompareBool(v, w, Py_EQ): identity first
    if (v == w) return true;
    Ref r = compare(CmpOp::Eq, v, w);
    return truth(r.get());
}
bool unsafe_object_compare(Obj v, Obj w) {       // the type's own slot; on NotImplemented, all of it
    Ref r = compare_one_side(v, w, CmpOp::Lt);
    if (r.get() == Obj::of(NOTIMPLEMENTED)) return safe_compare(v, w);
    return truth(r.get());
}
bool by_kind(Compare how, Obj v, Obj w, Compare elements);
bool unsafe_tuple_compare(Obj v, Obj w, Compare elements) {
    const auto& vt = static_cast<Tuple*>(v.object())->items;
    const auto& wt = static_cast<Tuple*>(w.object())->items;
    std::size_t i = 0;
    for (; i < vt.size() && i < wt.size(); ++i)
        if (!equal_compare(vt[i], wt[i])) break;
    if (i >= vt.size() || i >= wt.size()) return vt.size() < wt.size();
    if (i == 0) return by_kind(elements, vt[i], wt[i], Compare::Safe);
    return safe_compare(vt[i], wt[i]);
}
bool by_kind(Compare how, Obj v, Obj w, Compare elements) {
    switch (how) {
        case Compare::UnsafeObject: return unsafe_object_compare(v, w);
        case Compare::Tuple: return unsafe_tuple_compare(v, w, elements);
        default: return safe_compare(v, w);
    }
}
// ISLT: 1, 0, or -1 with the exception kept for the end
int islt(MergeState* ms, Obj x, Obj y) {
    try {
        return by_kind(ms->key_compare, x, y, ms->tuple_elem_compare) ? 1 : 0;
    } catch (...) {
        ms->error = std::current_exception();
        return -1;
    }
}
#define IFLT(X, Y)                       \
    if ((k = islt(ms, X, Y)) < 0) goto fail; \
    if (k)

int binarysort(MergeState* ms, const SortSlice* ss, std::int64_t n, std::int64_t ok) {
    std::int64_t k;
    Obj* const a = ss->keys;
    Obj* const v = ss->values;
    const bool has_values = v != nullptr;
    Obj pivot;
    std::int64_t M;
    if (!ok) ++ok;
    std::int64_t L, R;
    for (; ok < n; ++ok) {
        L = 0;
        R = ok;
        pivot = a[ok];
        do {
            M = (L + R) >> 1;
            IFLT(pivot, a[M])
                R = M;
            else
                L = M + 1;
        } while (L < R);
        for (M = ok; M > L; --M) a[M] = a[M - 1];
        a[L] = pivot;
        if (has_values) {
            pivot = v[ok];
            for (M = ok; M > L; --M) v[M] = v[M - 1];
            v[L] = pivot;
        }
    }
    return 0;
fail:
    return -1;
}

std::int64_t count_run(MergeState* ms, SortSlice* slo, std::int64_t nremaining) {
    std::int64_t k;
    std::int64_t n;
    Obj* const lo = slo->keys;
    std::int64_t neq = 0;
    auto reverse_last_neq = [&]() {
        if (neq) {
            SortSlice slice = *slo;
            ++neq;
            slice_advance(&slice, n - neq);
            slice_reverse(&slice, neq);
            neq = 0;
        }
    };
    for (n = 1; n < nremaining; ++n) {
        IFLT(lo[n], lo[n - 1])
            break;
    }
    if (n == nremaining) return n;
    if (n > 1) {
        IFLT(lo[0], lo[n - 1])
            return n;
        slice_reverse(slo, n);
    }
    ++n;
    for (; n < nremaining; ++n) {
        IFLT(lo[n], lo[n - 1]) {
            reverse_last_neq();
        } else {
            IFLT(lo[n - 1], lo[n])
                break;
            else
                ++neq;
        }
    }
    reverse_last_neq();
    slice_reverse(slo, n);
    for (; n < nremaining; ++n) {
        IFLT(lo[n], lo[n - 1])
            break;
    }
    return n;
fail:
    return -1;
}

std::int64_t gallop_left(MergeState* ms, Obj key, Obj* a, std::int64_t n, std::int64_t hint) {
    std::int64_t ofs, lastofs, k;
    a += hint;
    lastofs = 0;
    ofs = 1;
    IFLT(*a, key) {
        const std::int64_t maxofs = n - hint;
        while (ofs < maxofs) {
            IFLT(a[ofs], key) {
                lastofs = ofs;
                ofs = (ofs << 1) + 1;
            } else
                break;
        }
        if (ofs > maxofs) ofs = maxofs;
        lastofs += hint;
        ofs += hint;
    } else {
        const std::int64_t maxofs = hint + 1;
        while (ofs < maxofs) {
            IFLT(*(a - ofs), key)
                break;
            lastofs = ofs;
            ofs = (ofs << 1) + 1;
        }
        if (ofs > maxofs) ofs = maxofs;
        k = lastofs;
        lastofs = hint - ofs;
        ofs = hint - k;
    }
    a -= hint;
    ++lastofs;
    while (lastofs < ofs) {
        std::int64_t m = lastofs + ((ofs - lastofs) >> 1);
        IFLT(a[m], key)
            lastofs = m + 1;
        else
            ofs = m;
    }
    return ofs;
fail:
    return -1;
}

std::int64_t gallop_right(MergeState* ms, Obj key, Obj* a, std::int64_t n, std::int64_t hint) {
    std::int64_t ofs, lastofs, k;
    a += hint;
    lastofs = 0;
    ofs = 1;
    IFLT(key, *a) {
        const std::int64_t maxofs = hint + 1;
        while (ofs < maxofs) {
            IFLT(key, *(a - ofs)) {
                lastofs = ofs;
                ofs = (ofs << 1) + 1;
            } else
                break;
        }
        if (ofs > maxofs) ofs = maxofs;
        k = lastofs;
        lastofs = hint - ofs;
        ofs = hint - k;
    } else {
        const std::int64_t maxofs = n - hint;
        while (ofs < maxofs) {
            IFLT(key, a[ofs])
                break;
            lastofs = ofs;
            ofs = (ofs << 1) + 1;
        }
        if (ofs > maxofs) ofs = maxofs;
        lastofs += hint;
        ofs += hint;
    }
    a -= hint;
    ++lastofs;
    while (lastofs < ofs) {
        std::int64_t m = lastofs + ((ofs - lastofs) >> 1);
        IFLT(key, a[m])
            ofs = m;
        else
            lastofs = m + 1;
    }
    return ofs;
fail:
    return -1;
}

void merge_init(MergeState* ms, std::int64_t list_size, bool has_keyfunc, SortSlice* lo) {
    ms->has_values = has_keyfunc;
    ms->n = 0;
    ms->min_gallop = MIN_GALLOP;
    ms->listlen = list_size;
    ms->basekeys = lo->keys;
    ms->mr_e = 0;
    while ((list_size >> ms->mr_e) >= MAX_MINRUN) ++ms->mr_e;
    ms->mr_mask = (std::int64_t{1} << ms->mr_e) - 1;
    ms->mr_current = 0;
}
void merge_getmem(MergeState* ms, std::int64_t need) {
    if (need <= ms->alloced) return;
    ms->temp.assign(static_cast<std::size_t>(need) * (ms->has_values ? 2 : 1), Obj{});
    ms->alloced = need;
    ms->a.keys = ms->temp.data();
    ms->a.values = ms->has_values ? ms->temp.data() + need : nullptr;
}

std::int64_t merge_lo(MergeState* ms, SortSlice ssa, std::int64_t na, SortSlice ssb, std::int64_t nb) {
    std::int64_t k;
    SortSlice dest;
    int result = -1;
    std::int64_t min_gallop;
    merge_getmem(ms, na);
    slice_memcpy(&ms->a, 0, &ssa, 0, na);
    dest = ssa;
    ssa = ms->a;
    slice_copy_incr(&dest, &ssb);
    --nb;
    if (nb == 0) goto Succeed;
    if (na == 1) goto CopyB;
    min_gallop = ms->min_gallop;
    for (;;) {
        std::int64_t acount = 0;
        std::int64_t bcount = 0;
        for (;;) {
            k = islt(ms, ssb.keys[0], ssa.keys[0]);
            if (k) {
                if (k < 0) goto Fail;
                slice_copy_incr(&dest, &ssb);
                ++bcount;
                acount = 0;
                --nb;
                if (nb == 0) goto Succeed;
                if (bcount >= min_gallop) break;
            } else {
                slice_copy_incr(&dest, &ssa);
                ++acount;
                bcount = 0;
                --na;
                if (na == 1) goto CopyB;
                if (acount >= min_gallop) break;
            }
        }
        ++min_gallop;
        do {
            min_gallop -= min_gallop > 1;
            ms->min_gallop = min_gallop;
            k = gallop_right(ms, ssb.keys[0], ssa.keys, na, 0);
            acount = k;
            if (k) {
                if (k < 0) goto Fail;
                slice_memcpy(&dest, 0, &ssa, 0, k);
                slice_advance(&dest, k);
                slice_advance(&ssa, k);
                na -= k;
                if (na == 1) goto CopyB;
                if (na == 0) goto Succeed;
            }
            slice_copy_incr(&dest, &ssb);
            --nb;
            if (nb == 0) goto Succeed;
            k = gallop_left(ms, ssa.keys[0], ssb.keys, nb, 0);
            bcount = k;
            if (k) {
                if (k < 0) goto Fail;
                slice_memmove(&dest, 0, &ssb, 0, k);
                slice_advance(&dest, k);
                slice_advance(&ssb, k);
                nb -= k;
                if (nb == 0) goto Succeed;
            }
            slice_copy_incr(&dest, &ssa);
            --na;
            if (na == 1) goto CopyB;
        } while (acount >= MIN_GALLOP || bcount >= MIN_GALLOP);
        ++min_gallop;
        ms->min_gallop = min_gallop;
    }
Succeed:
    result = 0;
Fail:
    if (na) slice_memcpy(&dest, 0, &ssa, 0, na);
    return result;
CopyB:
    slice_memmove(&dest, 0, &ssb, 0, nb);
    slice_copy(&dest, nb, &ssa, 0);
    return 0;
}

std::int64_t merge_hi(MergeState* ms, SortSlice ssa, std::int64_t na, SortSlice ssb, std::int64_t nb) {
    std::int64_t k;
    SortSlice dest, basea, baseb;
    int result = -1;
    std::int64_t min_gallop;
    merge_getmem(ms, nb);
    dest = ssb;
    slice_advance(&dest, nb - 1);
    slice_memcpy(&ms->a, 0, &ssb, 0, nb);
    basea = ssa;
    baseb = ms->a;
    ssb.keys = ms->a.keys + nb - 1;
    if (ssb.values != nullptr) ssb.values = ms->a.values + nb - 1;
    slice_advance(&ssa, na - 1);
    slice_copy_decr(&dest, &ssa);
    --na;
    if (na == 0) goto Succeed;
    if (nb == 1) goto CopyA;
    min_gallop = ms->min_gallop;
    for (;;) {
        std::int64_t acount = 0;
        std::int64_t bcount = 0;
        for (;;) {
            k = islt(ms, ssb.keys[0], ssa.keys[0]);
            if (k) {
                if (k < 0) goto Fail;
                slice_copy_decr(&dest, &ssa);
                ++acount;
                bcount = 0;
                --na;
                if (na == 0) goto Succeed;
                if (acount >= min_gallop) break;
            } else {
                slice_copy_decr(&dest, &ssb);
                ++bcount;
                acount = 0;
                --nb;
                if (nb == 1) goto CopyA;
                if (bcount >= min_gallop) break;
            }
        }
        ++min_gallop;
        do {
            min_gallop -= min_gallop > 1;
            ms->min_gallop = min_gallop;
            k = gallop_right(ms, ssb.keys[0], basea.keys, na, na - 1);
            if (k < 0) goto Fail;
            k = na - k;
            acount = k;
            if (k) {
                slice_advance(&dest, -k);
                slice_advance(&ssa, -k);
                slice_memmove(&dest, 1, &ssa, 1, k);
                na -= k;
                if (na == 0) goto Succeed;
            }
            slice_copy_decr(&dest, &ssb);
            --nb;
            if (nb == 1) goto CopyA;
            k = gallop_left(ms, ssa.keys[0], baseb.keys, nb, nb - 1);
            if (k < 0) goto Fail;
            k = nb - k;
            bcount = k;
            if (k) {
                slice_advance(&dest, -k);
                slice_advance(&ssb, -k);
                slice_memcpy(&dest, 1, &ssb, 1, k);
                nb -= k;
                if (nb == 1) goto CopyA;
                if (nb == 0) goto Succeed;
            }
            slice_copy_decr(&dest, &ssa);
            --na;
            if (na == 0) goto Succeed;
        } while (acount >= MIN_GALLOP || bcount >= MIN_GALLOP);
        ++min_gallop;
        ms->min_gallop = min_gallop;
    }
Succeed:
    result = 0;
Fail:
    if (nb) slice_memcpy(&dest, -(nb - 1), &baseb, 0, nb);
    return result;
CopyA:
    slice_memmove(&dest, 1 - na, &ssa, 1 - na, na);
    slice_advance(&dest, -na);
    slice_advance(&ssa, -na);
    slice_copy(&dest, 0, &ssb, 0);
    return 0;
}

std::int64_t merge_at(MergeState* ms, std::int64_t i) {
    SortSlice ssa = ms->pending[i].base;
    std::int64_t na = ms->pending[i].len;
    SortSlice ssb = ms->pending[i + 1].base;
    std::int64_t nb = ms->pending[i + 1].len;
    ms->pending[i].len = na + nb;
    if (i == ms->n - 3) ms->pending[i + 1] = ms->pending[i + 2];
    --ms->n;
    std::int64_t k = gallop_right(ms, *ssb.keys, ssa.keys, na, 0);
    if (k < 0) return -1;
    slice_advance(&ssa, k);
    na -= k;
    if (na == 0) return 0;
    nb = gallop_left(ms, ssa.keys[na - 1], ssb.keys, nb, nb - 1);
    if (nb <= 0) return nb;
    if (na <= nb) return merge_lo(ms, ssa, na, ssb, nb);
    return merge_hi(ms, ssa, na, ssb, nb);
}

int powerloop(std::int64_t s1, std::int64_t n1, std::int64_t n2, std::int64_t n) {
    int result = 0;
    std::int64_t a = 2 * s1 + n1;
    std::int64_t b = a + n1 + n2;
    for (;;) {
        ++result;
        if (a >= n) {
            a -= n;
            b -= n;
        } else if (b >= n) {
            break;
        }
        a <<= 1;
        b <<= 1;
    }
    return result;
}

int found_new_run(MergeState* ms, std::int64_t n2) {
    if (ms->n) {
        Run* p = ms->pending;
        std::int64_t s1 = p[ms->n - 1].base.keys - ms->basekeys;
        std::int64_t n1 = p[ms->n - 1].len;
        int power = powerloop(s1, n1, n2, ms->listlen);
        while (ms->n > 1 && p[ms->n - 2].power > power) {
            if (merge_at(ms, ms->n - 2) < 0) return -1;
        }
        p[ms->n - 1].power = power;
    }
    return 0;
}

int merge_force_collapse(MergeState* ms) {
    Run* p = ms->pending;
    while (ms->n > 1) {
        std::int64_t n = ms->n - 2;
        if (n > 0 && p[n - 1].len < p[n + 1].len) --n;
        if (merge_at(ms, n) < 0) return -1;
    }
    return 0;
}

std::int64_t minrun_next(MergeState* ms) {
    ms->mr_current += ms->listlen;
    std::int64_t result = ms->mr_current >> ms->mr_e;
    ms->mr_current &= ms->mr_mask;
    return result;
}

// The pre-sort check: only what decides between the compares that differ
void choose_compare(MergeState& ms, const Obj* keys, std::int64_t size) {
    auto non_empty_tuple = [](Obj k) { return is_exact_tuple(k) && !static_cast<Tuple*>(k.object())->items.empty(); };
    bool in_tuples = non_empty_tuple(keys[0]);
    ClassObject* key_type = type_of(in_tuples ? static_cast<Tuple*>(keys[0].object())->items[0] : keys[0]);
    bool same_type = true;
    for (std::int64_t i = 0; i < size; ++i) {
        if (in_tuples && !non_empty_tuple(keys[i])) {
            in_tuples = false;
            same_type = false;
            break;
        }
        Obj key = in_tuples ? static_cast<Tuple*>(keys[i].object())->items[0] : keys[i];
        if (type_of(key) != key_type) {
            same_type = false;
            if (!in_tuples) break;
        }
    }
    Types& t = types();
    ms.key_compare = !same_type || key_type == t.str || key_type == t.int_ || key_type == t.float_ ? Compare::Safe : Compare::UnsafeObject;
    if (in_tuples) {
        ms.tuple_elem_compare = key_type == t.tuple ? Compare::Safe : ms.key_compare;
        ms.key_compare = Compare::Tuple;
    }
}
#undef IFLT
}  // namespace

// list_sort_impl
Ref list_sort_m(Obj self, Args a) {
    if (a.npos != 0) raise_new("TypeError", "sort() takes no positional arguments");
    Obj keyfunc;
    bool reverse = false;
    for (std::size_t i = 0; i < a.nkw; ++i) {
        if (a.kwnames[i] == intern("key")) keyfunc = a.kw(i);
        else if (a.kwnames[i] != intern("reverse")) unexpected_keyword("sort()", a.kwnames[i], {"key", "reverse"});
    }
    for (std::size_t i = 0; i < a.nkw; ++i)
        if (a.kwnames[i] == intern("reverse")) reverse = truth(a.kw(i));
    if (keyfunc == None()) keyfunc = Obj{};

    auto* list = static_cast<List*>(self.object());
    // The list is made empty, so that a comparison changing it cannot touch what is being sorted.
    // An operation on it gives it capacity, which is how the end tells it was changed.
    std::vector<Obj> saved;
    saved.swap(list->items);
    auto size = static_cast<std::int64_t>(saved.size());
    std::vector<Obj> keys;
    std::exception_ptr error;
    MergeState ms;
    SortSlice lo{saved.data(), nullptr};
    bool keys_made = false;
    if (!keyfunc.is_unset()) {
        keys.reserve(saved.size());
        try {
            for (Obj item : saved) keys.push_back(invoke(keyfunc, {item}).release());
            keys_made = true;
            lo.keys = keys.data();
            lo.values = saved.data();
        } catch (...) {
            error = std::current_exception();
            for (auto it = keys.rbegin(); it != keys.rend(); ++it) decref(*it);
        }
    }
    if (!error) {
        if (size > 1) choose_compare(ms, lo.keys, size);
        merge_init(&ms, size, keys_made, &lo);
        bool failed = false;
        if (size >= 2) {
            if (reverse) {
                if (keys_made) std::reverse(keys.begin(), keys.end());
                std::reverse(saved.begin(), saved.end());
            }
            std::int64_t nremaining = size;
            do {
                std::int64_t n = count_run(&ms, &lo, nremaining);
                if (n < 0) { failed = true; break; }
                std::int64_t minrun = minrun_next(&ms);
                if (n < minrun) {
                    const std::int64_t force = nremaining <= minrun ? nremaining : minrun;
                    if (binarysort(&ms, &lo, force, n) < 0) { failed = true; break; }
                    n = force;
                }
                if (found_new_run(&ms, n) < 0) { failed = true; break; }
                ms.pending[ms.n].base = lo;
                ms.pending[ms.n].len = n;
                ++ms.n;
                slice_advance(&lo, n);
                nremaining -= n;
            } while (nremaining);
            if (!failed && merge_force_collapse(&ms) < 0) failed = true;
        }
        error = ms.error;
        (void)failed;
        for (Obj k : keys) decref(k);
        // "allocated != -1": it was changed, and there is no other error to report
        bool modified = !list->items.empty() || list->items.capacity() != 0;
        if (reverse && size > 1) std::reverse(saved.begin(), saved.end());
        if (modified && !error) {
            try {
                raise_new("ValueError", "list modified during sort");
            } catch (...) {
                error = std::current_exception();
            }
        }
    }
    // keyfunc_fail: the sorted items back, and whatever a comparison left in the list released
    std::vector<Obj> left;
    left.swap(list->items);
    list->items.swap(saved);
    for (auto it = left.rbegin(); it != left.rend(); ++it) decref(*it);
    if (error) std::rethrow_exception(error);
    return none_ref();
}

// builtin_sorted: a new list, then its sort with the keywords as given
Ref b_sorted(Obj, Args a) {
    if (a.npos != 1) raise_new("TypeError", "sorted expected 1 argument, got " + std::to_string(a.npos));
    Ref out = list_new({});
    list_extend(out.get(), a.pos(0));
    Args rest{a.data + 1, 0, a.kwnames, a.nkw};
    list_sort_m(out.get(), rest);
    return out;
}

}  // namespace bella
