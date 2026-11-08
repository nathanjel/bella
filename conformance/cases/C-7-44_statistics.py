# clause: C-7-44
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_statisticsmodule.c, Lib/statistics.py
"""The _statistics accelerator behind statistics: _normal_dist_inv_cdf across its three branches (the central rational approximation,
the tails below and above r = 5), its domain errors, its conversions and its parsing; and the statistics module over it with the
values a data program prints: mean, fmean, geometric_mean, harmonic_mean, median and its variants, mode, multimode, quantiles,
variance and stdev of ints, floats, Fractions and Decimals, correlation and linear_regression, NormalDist, and the module's errors."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _statistics  # type: ignore[import-not-found]
import statistics
from decimal import Decimal
from fractions import Fraction


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


class Fl:
    def __float__(self):  # type: ignore[no-untyped-def]
        return 0.25


class Ix:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 1


class FS(float):
    pass


f = _statistics._normal_dist_inv_cdf
print("module:", repr(_statistics.__doc__), [n for n in dir(_statistics) if not n.startswith("__")], f.__name__, f.__module__, repr(f.__doc__), statistics._normal_dist_inv_cdf is f)  # type: ignore[attr-defined]
print("values:", [f(p, 0, 1) for p in (0.5, 0.975, 0.001, 1e-300, 0.9999999, 0.075, 0.925, 0.0751, 0.9249, 2e-9, 1 - 2e-9, 0.25, 0.75, 1e-12, 0.3, 0.6)])
print("scaled:", f(0.3, 10, 2), f(0.9, -5, 0.5), f(0.5, 7, 3), f(0.001, 5, 2), f(0.3, float("inf"), 1), f(0.3, 0, float("nan")), f(float("nan"), 0, 1), f(0.5, 0, 0), f(0.2, 0, -1))
print("errors:", m(lambda: f(0, 0, 1)), m(lambda: f(1, 0, 1)), m(lambda: f(-0.1, 0, 1)), m(lambda: f(1.5, 0, 1)), m(lambda: f("0.5", 0, 1)), m(lambda: f(0.5, "0", 1)), m(lambda: f(Fl(), 0, 1)), m(lambda: f(0.5, Ix(), 1)), m(lambda: f(FS(0.5), 0, 1)), m(lambda: f(1, 0, 1)), m(lambda: f(0.5, 0)), m(lambda: f(0.5, 0, 1, 2)), m(lambda: f(p=0.5, mu=0, sigma=1)), m(lambda: f()), m(lambda: f(0.5, 0, None)), m(lambda: f(True, 0, 1)), m(lambda: f(0.5, 2**1100, 1)), m(lambda: f(0.5, 2**70, 1)), m(lambda: f(Fraction(1, 4), 0, 1)), m(lambda: f(Decimal("0.25"), 0, 1)))  # type: ignore[no-untyped-call]
data = [2, 4, 4, 4, 5, 5, 7, 9]
floats = [1.5, 2.25, 3.125, 4.0625, 10.5]
fracs = [Fraction(1, 3), Fraction(2, 3), Fraction(5, 6), Fraction(7, 4)]
decs = [Decimal("1.10"), Decimal("2.25"), Decimal("3.30"), Decimal("7.5")]
print("mean:", statistics.mean(data), statistics.mean(floats), statistics.mean(fracs), statistics.mean(decs), statistics.fmean(data), statistics.fmean(floats), statistics.fmean(data, weights=[1, 2, 3, 4, 5, 6, 7, 8]), statistics.mean([1e308, 1e308]), m(lambda: statistics.mean([])), m(lambda: statistics.fmean([])), m(lambda: statistics.mean(iter(data))), statistics.mean([True, False, True]))  # type: ignore[no-untyped-call]
print("means:", statistics.geometric_mean(data), statistics.geometric_mean(floats), statistics.harmonic_mean(data), statistics.harmonic_mean(floats), statistics.harmonic_mean([40, 60], weights=[5, 30]), m(lambda: statistics.geometric_mean([])), m(lambda: statistics.harmonic_mean([1, -2])), statistics.harmonic_mean([0, 2]))  # type: ignore[no-untyped-call]
print("median:", statistics.median(data), statistics.median(data[:-1]), statistics.median(floats), statistics.median(fracs), statistics.median(decs), statistics.median_low(data), statistics.median_high(data), statistics.median_low([3, 1]), statistics.median_high([3, 1]), statistics.median_grouped(data), statistics.median_grouped(data, interval=2), m(lambda: statistics.median([])), statistics.median([Decimal("3"), Decimal("1")]))  # type: ignore[no-untyped-call]
print("mode:", statistics.mode(data), statistics.mode("aabbbc"), statistics.mode([1, 1, 2, 2]), statistics.multimode(data), statistics.multimode([1, 1, 2, 2, 3]), statistics.multimode([]), m(lambda: statistics.mode([])))  # type: ignore[no-untyped-call]
print("spread:", statistics.variance(data), statistics.pvariance(data), statistics.stdev(data), statistics.pstdev(data), statistics.variance(floats), statistics.stdev(floats), statistics.variance(fracs), statistics.pvariance(decs), statistics.stdev(decs), statistics.variance(data, 5), m(lambda: statistics.variance([1])), statistics.pvariance([1]), m(lambda: statistics.pvariance([])))  # type: ignore[no-untyped-call]
print("quantiles:", statistics.quantiles(data), statistics.quantiles(data, n=10), statistics.quantiles(data, method="inclusive"), statistics.quantiles(floats, n=3), statistics.quantiles(fracs), m(lambda: statistics.quantiles([1])), m(lambda: statistics.quantiles(data, n=0)), m(lambda: statistics.quantiles(data, method="x")))  # type: ignore[arg-type,no-untyped-call]
xs = [1, 2, 3, 4, 5, 6, 7, 8, 9]
ys = [1, 2, 3, 1, 2, 3, 1, 2, 3]
print("relations:", statistics.correlation(xs, ys), statistics.correlation(xs, xs), statistics.correlation(xs, ys, method="ranked"), statistics.covariance(xs, ys), statistics.linear_regression(xs, ys), statistics.linear_regression(xs, [2 * x + 1 for x in xs]), statistics.linear_regression(xs, [3 * x for x in xs], proportional=True), m(lambda: statistics.correlation([1], [1])), m(lambda: statistics.correlation(xs, ys[:-1])), m(lambda: statistics.correlation(xs, [1] * 9)))  # type: ignore[no-untyped-call]
nd = statistics.NormalDist(10, 2)
print("normal:", nd, nd.mean, nd.stdev, nd.variance, nd.median, nd.mode, nd.cdf(12), nd.pdf(10), nd.inv_cdf(0.9), nd.inv_cdf(0.1), nd.quantiles(), nd.quantiles(n=10), nd.zscore(13), nd.overlap(statistics.NormalDist(12, 2)), (nd + 1).mean, (nd * 2).stdev, (nd - nd).mean, nd == statistics.NormalDist(10, 2), hash(nd) == hash(statistics.NormalDist(10, 2)), statistics.NormalDist.from_samples([1, 2, 3, 4]), m(lambda: nd.inv_cdf(0)), m(lambda: nd.inv_cdf(1)), m(lambda: statistics.NormalDist(0, -1)), m(lambda: statistics.NormalDist(0, 0).inv_cdf(0.5)), m(lambda: statistics.NormalDist(0, 0).zscore(1)))  # type: ignore[no-untyped-call]
print("kde:", [round(v, 6) for v in (statistics.kde([1, 2, 3], h=1.0)(2.0), statistics.kde([1, 2, 3], h=1.0, kernel="triangular")(1.5), statistics.kde([1, 2, 3], h=0.5, cumulative=True)(2.5))], statistics.kde_random([1, 2, 3], h=1.0, seed=42)(), m(lambda: statistics.kde([], h=1.0)), m(lambda: statistics.kde([1], h=0)), m(lambda: statistics.kde([1], h=1, kernel="x")))  # type: ignore[arg-type,no-untyped-call]
print("errors:", m(lambda: statistics.mean(["a"])), m(lambda: statistics.mean([1, "a"])), m(lambda: statistics.median_grouped([])), m(lambda: statistics.fmean([1], weights=[1, 2])), m(lambda: statistics.mean([1.5, Fraction(1, 2)])), m(lambda: statistics.mean([Decimal(1), Fraction(1, 2)])).split(" coerce")[0], m(lambda: statistics.stdev([1, 2], xbar="x")), m(lambda: statistics.variance([float("nan"), 1])), statistics.mean([float("inf"), 1]), m(lambda: statistics.mean([complex(1, 2), 3])), m(lambda: statistics.quantiles(data, n=1)))  # type: ignore[no-untyped-call,type-var]
