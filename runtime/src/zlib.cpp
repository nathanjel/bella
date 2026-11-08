// zlib 1.3.2 (runtime/vendor/zlib-1.3.2, licence entry L-02) behind the zlib prelude (runtime/prelude/zlib.py): one primitive, `_zlib`,
// that runs the library's calls on z_stream handles and answers (err, output, ...) tuples; Modules/zlibmodule.c's rules (the
// messages, when a stream ends, what is saved) stay in the prelude, in Python. A handle is an integer the prelude holds in a slot
// and frees in __del__; the output loops grow their buffer as the C's _BlocksOutputBuffer does, which deflate's and inflate's
// bytes do not depend on.
#include "bella/runtime.hpp"

#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>

#include "../vendor/zlib-1.3.2/zlib.h"

namespace bella {
namespace {
struct ZHandle {
    z_stream zst{};
    bool inflating = false;
    bool ended = false;                          // deflateEnd / inflateEnd ran: the stream is no longer valid
    ~ZHandle() {
        if (!ended) {
            if (inflating) inflateEnd(&zst);
            else deflateEnd(&zst);
        }
    }
};
std::unordered_map<std::int64_t, std::unique_ptr<ZHandle>>& handles() {
    static std::unordered_map<std::int64_t, std::unique_ptr<ZHandle>> table;
    return table;
}
std::int64_t next_handle = 1;

ZHandle& handle_of(Obj v) {
    auto it = handles().find(index_value(v));
    if (it == handles().end()) raise_new("SystemError", "zlib: a stream handle that is not open");
    return *it->second;
}
const std::string& data_of(Obj v) {
    if (is_kind(v, Kind::Bytes)) return bytes_data(v);
    raise_new("TypeError", "a zlib primitive needs bytes");
}
Ref msg_of(const z_stream& zst) { return zst.msg == nullptr ? none_ref() : str_new(zst.msg); }
Ref u32(unsigned long v) { return int_from_i64(static_cast<std::int64_t>(v & 0xffffffffUL)); }

// The C module's output buffer (Include/internal/pycore_blocks_output_buffer.h): a first block of 32 KB (or the limit, when smaller;
// or the size the caller gives), then blocks from this table, the last cut to the limit. deflate's stored blocks and its flushes
// take their boundaries from avail_out, so the compressed bytes depend on this schedule; the prelude passes the first block's size.
constexpr std::int64_t KB = 1024, MB = 1024 * KB;
constexpr std::int64_t BLOCK_SIZES[] = {32 * KB, 64 * KB, 256 * KB, MB, 4 * MB, 8 * MB, 16 * MB, 16 * MB, 32 * MB, 32 * MB, 32 * MB, 32 * MB,
                                        64 * MB, 64 * MB, 128 * MB, 128 * MB, 256 * MB};
struct Blocks {
    std::int64_t max_length;                     // -1: none
    std::int64_t allocated = 0;
    std::size_t num_blocks = 0;
    std::int64_t first(std::int64_t init_size) {   // _BlocksOutputBuffer_InitAndGrow (init_size < 0) or _InitWithSize
        std::int64_t size = init_size >= 0 ? init_size : (max_length >= 0 && max_length < BLOCK_SIZES[0] ? max_length : BLOCK_SIZES[0]);
        allocated = size;
        num_blocks = 1;
        return size;
    }
    std::int64_t grow() {                        // _BlocksOutputBuffer_Grow: called with avail_out == 0 and room left under the limit
        std::int64_t size = BLOCK_SIZES[std::min<std::size_t>(num_blocks, std::size(BLOCK_SIZES) - 1)];
        if (max_length >= 0) size = std::min(size, max_length - allocated);
        allocated += size;
        num_blocks += 1;
        return size;
    }
};

// deflate(zst, flush) over the whole input, growing the output while the library fills it (the C's inner do-while)
Ref run_deflate(ZHandle& h, const std::string& data, int flush) {
    h.zst.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(data.data()));
    h.zst.avail_in = static_cast<uInt>(data.size());   // phase 1: inputs below UINT_MAX
    std::string out;
    Blocks blocks{-1};
    std::int64_t room = blocks.first(-1);
    int err;
    do {
        std::size_t old = out.size();
        out.resize(old + static_cast<std::size_t>(room));
        h.zst.next_out = reinterpret_cast<Bytef*>(&out[old]);
        h.zst.avail_out = static_cast<uInt>(room);
        err = deflate(&h.zst, flush);
        out.resize(old + static_cast<std::size_t>(room) - h.zst.avail_out);
        if (err == Z_STREAM_ERROR) break;
        room = blocks.grow();
    } while (h.zst.avail_out == 0);
    Ref bytes = bytes_new(out);
    return tuple_new({Obj::small(err), bytes.get(), msg_of(h.zst).get()});
}

// inflate(zst, flush) over the input, up to max_length bytes of output (-1: no limit), the first output block of init_size (-1: the
// schedule's), a dictionary set when the stream asks for one; answers (err, output, consumed, msg, context) where context is
// "setdict" when setting the dictionary failed. inflate's bytes and what it consumes do not depend on the blocks, only its calls do.
Ref run_inflate(ZHandle& h, const std::string& data, std::int64_t max_length, std::int64_t init_size, int flush, Obj zdict) {
    h.zst.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(data.data()));
    h.zst.avail_in = static_cast<uInt>(data.size());
    std::string out;
    int err = Z_OK;
    const char* context = "";
    Blocks blocks{max_length};
    std::int64_t room = blocks.first(init_size);   // the space left in the current block
    for (;;) {
        if (room == 0) {                         // the C's loop top, with avail_out == 0
            if (max_length >= 0 && blocks.allocated >= max_length) break;   // OutputBuffer_GetDataSize == max_length: save
            room = blocks.grow();
        }
        std::size_t old = out.size();
        out.resize(old + static_cast<std::size_t>(room));
        h.zst.next_out = reinterpret_cast<Bytef*>(&out[old]);
        h.zst.avail_out = static_cast<uInt>(room);
        err = inflate(&h.zst, flush);
        out.resize(old + static_cast<std::size_t>(room) - h.zst.avail_out);
        room = h.zst.avail_out;                  // the rest of this block, written to next
        if (err == Z_NEED_DICT && zdict != None()) {
            const std::string& dict = data_of(zdict);
            int set = inflateSetDictionary(&h.zst, reinterpret_cast<const Bytef*>(dict.data()), static_cast<uInt>(dict.size()));
            if (set != Z_OK) {
                err = set;
                context = "setdict";
                break;
            }
            continue;                            // the C's loop runs inflate again
        }
        if (err != Z_OK && err != Z_BUF_ERROR && err != Z_STREAM_END) break;
        if (room != 0) break;
    }
    std::int64_t consumed = static_cast<std::int64_t>(data.size()) - h.zst.avail_in;
    Ref bytes = bytes_new(out);
    Ref ctx = str_new(context);
    return tuple_new({Obj::small(err), bytes.get(), Obj::small(consumed), msg_of(h.zst).get(), ctx.get()});
}

std::int64_t put(std::unique_ptr<ZHandle> h) {
    std::int64_t id = next_handle++;
    handles()[id] = std::move(h);
    return id;
}
}  // namespace

Ref i_zlib(Obj, Args a) {                         // _zlib(name, ...)
    const std::string& name = as_str(a.pos(0))->text;
    if (name == "version") {
        Ref compiled = str_new(ZLIB_VERSION), runtime = str_new(zlibVersion());
        return tuple_new({compiled.get(), runtime.get()});
    }
    if (name == "adler32" || name == "crc32") {
        const std::string& data = data_of(a.pos(1));
        unsigned long value = static_cast<unsigned long>(index_value(a.pos(2)));
        const auto* p = reinterpret_cast<const Bytef*>(data.data());
        value = name == "adler32" ? adler32(value, p, static_cast<uInt>(data.size())) : crc32(value, p, static_cast<uInt>(data.size()));
        return u32(value);
    }
    if (name == "adler32_combine" || name == "crc32_combine") {
        auto c1 = static_cast<unsigned long>(index_value(a.pos(1))), c2 = static_cast<unsigned long>(index_value(a.pos(2)));
        auto len = static_cast<z_off64_t>(index_value(a.pos(3)));
        return u32(name == "adler32_combine" ? adler32_combine64(c1, c2, len) : crc32_combine64(c1, c2, len));
    }
    if (name == "deflate_init") {                // (level, method, wbits, memLevel, strategy) -> (err, handle, msg)
        auto h = std::make_unique<ZHandle>();
        int err = deflateInit2(&h->zst, static_cast<int>(index_value(a.pos(1))), static_cast<int>(index_value(a.pos(2))),
                               static_cast<int>(index_value(a.pos(3))), static_cast<int>(index_value(a.pos(4))), static_cast<int>(index_value(a.pos(5))));
        Ref msg = msg_of(h->zst);
        if (err != Z_OK) {
            h->ended = true;                     // deflateInit2 failed: nothing to end
            return tuple_new({Obj::small(err), Obj::small(0), msg.get()});
        }
        return tuple_new({Obj::small(err), Obj::small(put(std::move(h))), msg.get()});
    }
    if (name == "inflate_init") {                // (wbits) -> (err, handle, msg)
        auto h = std::make_unique<ZHandle>();
        h->inflating = true;
        int err = inflateInit2(&h->zst, static_cast<int>(index_value(a.pos(1))));
        Ref msg = msg_of(h->zst);
        if (err != Z_OK) {
            h->ended = true;
            return tuple_new({Obj::small(err), Obj::small(0), msg.get()});
        }
        return tuple_new({Obj::small(err), Obj::small(put(std::move(h))), msg.get()});
    }
    if (name == "deflate_setdict" || name == "inflate_setdict") {   // (handle, zdict) -> err
        ZHandle& h = handle_of(a.pos(1));
        const std::string& dict = data_of(a.pos(2));
        const auto* p = reinterpret_cast<const Bytef*>(dict.data());
        int err = h.inflating ? inflateSetDictionary(&h.zst, p, static_cast<uInt>(dict.size())) : deflateSetDictionary(&h.zst, p, static_cast<uInt>(dict.size()));
        return Ref::steal(Obj::small(err));
    }
    if (name == "deflate") return run_deflate(handle_of(a.pos(1)), data_of(a.pos(2)), static_cast<int>(index_value(a.pos(3))));
    if (name == "inflate")                       // (handle, data, max_length, init_size, flush, zdict)
        return run_inflate(handle_of(a.pos(1)), data_of(a.pos(2)), index_value(a.pos(3)), index_value(a.pos(4)), static_cast<int>(index_value(a.pos(5))), a.pos(6));
    if (name == "copy") {                        // (handle) -> (err, handle)
        ZHandle& h = handle_of(a.pos(1));
        auto copy = std::make_unique<ZHandle>();
        copy->inflating = h.inflating;
        int err = h.inflating ? inflateCopy(&copy->zst, &h.zst) : deflateCopy(&copy->zst, &h.zst);
        if (err != Z_OK) {
            copy->ended = true;
            return tuple_new({Obj::small(err), Obj::small(0)});
        }
        return tuple_new({Obj::small(err), Obj::small(put(std::move(copy)))});
    }
    if (name == "end") {                         // (handle) -> err: deflateEnd or inflateEnd, once
        ZHandle& h = handle_of(a.pos(1));
        if (h.ended) return Ref::steal(Obj::small(Z_STREAM_ERROR));
        int err = h.inflating ? inflateEnd(&h.zst) : deflateEnd(&h.zst);
        h.ended = true;
        return Ref::steal(Obj::small(err));
    }
    if (name == "free") {                        // (handle): the object died
        handles().erase(index_value(a.pos(1)));
        return none_ref();
    }
    raise_new("SystemError", "zlib: unknown primitive " + name);
}
}  // namespace bella
