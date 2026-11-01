# slice example: Mandelbrot escape times in fixed-point integer arithmetic (12 fractional bits;
# the toy emitter has no float yet). Negative products make floor division matter: Python
# rounds toward minus infinity, C++ toward zero. Prints how many points of each row stay in the
# set, then a checksum of every escape time.


def escape_time(cr: int, ci: int, limit: int) -> int:
    zr = 0
    zi = 0
    n = 0
    while n < limit:
        zr2 = zr * zr // 4096
        zi2 = zi * zi // 4096
        if zr2 + zi2 > 16384:
            return n
        zi = 2 * zr * zi // 4096 + ci
        zr = zr2 - zi2 + cr
        n += 1
    return limit


width = 64
height = 24
limit = 100
total = 0
inside = 0
for y in range(height):
    ci = y * 8192 // (height - 1) - 4096
    row = 0
    for x in range(width):
        cr = x * 12288 // (width - 1) - 8192
        n = escape_time(cr, ci, limit)
        total += n
        if n == limit:
            row += 1
    inside += row
    print(y, row)
print("points inside:", inside, "total escape time:", total)
