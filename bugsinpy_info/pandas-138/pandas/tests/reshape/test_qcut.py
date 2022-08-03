import os

import numpy as np
import pytest

from pandas import (
    Categorical,
    DatetimeIndex,
    Interval,
    IntervalIndex,
    NaT,
    Series,
    TimedeltaIndex,
    Timestamp,
    cut,
    date_range,
    isna,
    qcut,
    timedelta_range,
)
from pandas.api.types import CategoricalDtype as CDT
from pandas.core.algorithms import quantile
import pandas.util.testing as tm

from pandas.tseries.offsets import Day, Nano


def test_qcut():
    arr = np.random.randn(1000)

    # We store the bins as Index that have been
    # rounded to comparisons are a bit tricky.
    labels, bins = qcut(arr, 4, retbins=True)
    ex_bins = quantile(arr, [0, 0.25, 0.5, 0.75, 1.0])

    result = labels.categories.left.values
    assert np.allclose(result, ex_bins[:-1], atol=1e-2)

    result = labels.categories.right.values
    assert np.allclose(result, ex_bins[1:], atol=1e-2)

    ex_levels = cut(arr, ex_bins, include_lowest=True)
    tm.assert_categorical_equal(labels, ex_levels)


def test_qcut_bounds():
    arr = np.random.randn(1000)

    factor = qcut(arr, 10, labels=False)
    assert len(np.unique(factor)) == 10


def test_qcut_specify_quantiles():
    arr = np.random.randn(100)
    factor = qcut(arr, [0, 0.25, 0.5, 0.75, 1.0])

    expected = qcut(arr, 4)
    tm.assert_categorical_equal(factor, expected)


def test_qcut_all_bins_same():
    with pytest.raises(ValueError, match="edges.*unique"):
        qcut([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 3)


def test_qcut_include_lowest():
    values = np.arange(10)
    ii = qcut(values, 4)

    ex_levels = IntervalIndex(
        [
            Interval(-0.001, 2.25),
            Interval(2.25, 4.5),
            Interval(4.5, 6.75),
            Interval(6.75, 9),
        ]
    )
    tm.assert_index_equal(ii.categories, ex_levels)


def test_qcut_nas():
    arr = np.random.randn(100)
    arr[:20] = np.nan

    result = qcut(arr, 4)
    assert isna(result[:20]).all()


def test_qcut_index():
    result = qcut([0, 2], 2)
    intervals = [Interval(-0.001, 1), Interval(1, 2)]

    expected = Categorical(intervals, ordered=True)
    tm.assert_categorical_equal(result, expected)


def test_qcut_binning_issues(datapath):
    # see gh-1978, gh-1979
    cut_file = datapath(os.path.join("reshape", "data", "cut_data.csv"))
    arr = np.loadtxt(cut_file)
    result = qcut(arr, 20)

    starts = []
    ends = []

    for lev in np.unique(result):
        s = lev.left
        e = lev.right
        assert s != e

        starts.append(float(s))
        ends.append(float(e))

    for (sp, sn), (ep, en) in zip(
        zip(starts[:-1], starts[1:]), zip(ends[:-1], ends[1:])
    ):
        assert sp < sn
        assert ep < en
        assert ep <= sn


def test_qcut_return_intervals():
    ser = Series([0, 1, 2, 3, 4, 5, 6, 7, 8])
    res = qcut(ser, [0, 0.333, 0.666, 1])

    exp_levels = np.array(
        [Interval(-0.001, 2.664), Interval(2.664, 5.328), Interval(5.328, 8)]
    )
    exp = Series(exp_levels.take([0, 0, 0, 1, 1, 1, 2, 2, 2])).astype(CDT(ordered=True))
    tm.assert_series_equal(res, exp)


@pytest.mark.parametrize(
    "kwargs,msg",
    [
        (dict(duplicates="drop"), None),
        (dict(), "Bin edges must be unique"),
        (dict(duplicates="raise"), "Bin edges must be unique"),
        (dict(duplicates="foo"), "invalid value for 'duplicates' parameter"),
    ],
)
def test_qcut_duplicates_bin(kwargs, msg):
    # see gh-7751
    values = [0, 0, 0, 0, 1, 2, 3]

    if msg is not None:
        with pytest.raises(ValueError, match=msg):
            qcut(values, 3, **kwargs)
    else:
        result = qcut(values, 3, **kwargs)
        expected = IntervalIndex([Interval(-0.001, 1), Interval(1, 3)])
        tm.assert_index_equal(result.categories, expected)


@pytest.mark.parametrize(
    "data,start,end", [(9.0, 8.999, 9.0), (0.0, -0.001, 0.0), (-9.0, -9.001, -9.0)]
)
@pytest.mark.parametrize("length", [1, 2])
@pytest.mark.parametrize("labels", [None, False])
def test_single_quantile(data, start, end, length, labels):
    # see gh-15431
    ser = Series([data] * length)
    result = qcut(ser, 1, labels=labels)

    if labels is None:
        intervals = IntervalIndex([Interval(start, end)] * length, closed="right")
        expected = Series(intervals).astype(CDT(ordered=True))
    else:
        expected = Series([0] * length)

    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "ser",
    [
        Series(DatetimeIndex(["20180101", NaT, "20180103"])),
        Series(TimedeltaIndex(["0 days", NaT, "2 days"])),
    ],
    ids=lambda x: str(x.dtype),
)
def test_qcut_nat(ser):
    # see gh-19768
    intervals = IntervalIndex.from_tuples(
        [(ser[0] - Nano(), ser[2] - Day()), np.nan, (ser[2] - Day(), ser[2])]
    )
    expected = Series(Categorical(intervals, ordered=True))

    result = qcut(ser, 2)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("bins", [3, np.linspace(0, 1, 4)])
def test_datetime_tz_qcut(bins):
    # see gh-19872
    tz = "US/Eastern"
    ser = Series(date_range("20130101", periods=3, tz=tz))

    result = qcut(ser, bins)
    expected = Series(
        IntervalIndex(
            [
                Interval(
                    Timestamp("2012-12-31 23:59:59.999999999", tz=tz),
                    Timestamp("2013-01-01 16:00:00", tz=tz),
                ),
                Interval(
                    Timestamp("2013-01-01 16:00:00", tz=tz),
                    Timestamp("2013-01-02 08:00:00", tz=tz),
                ),
                Interval(
                    Timestamp("2013-01-02 08:00:00", tz=tz),
                    Timestamp("2013-01-03 00:00:00", tz=tz),
                ),
            ]
        )
    ).astype(CDT(ordered=True))
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "arg,expected_bins",
    [
        [
            timedelta_range("1day", periods=3),
            TimedeltaIndex(["1 days", "2 days", "3 days"]),
        ],
        [
            date_range("20180101", periods=3),
            DatetimeIndex(["2018-01-01", "2018-01-02", "2018-01-03"]),
        ],
    ],
)
def test_date_like_qcut_bins(arg, expected_bins):
    # see gh-19891
    ser = Series(arg)
    result, result_bins = qcut(ser, 2, retbins=True)
    tm.assert_index_equal(result_bins, expected_bins)


@pytest.mark.parametrize("bins", [6, 7])
@pytest.mark.parametrize(
    "box, compare",
    [
        (Series, tm.assert_series_equal),
        (np.array, tm.assert_categorical_equal),
        (list, tm.assert_equal),
    ],
)
def test_qcut_bool_coercion_to_int(bins, box, compare):
    # issue 20303
    data_expected = box([0, 1, 1, 0, 1] * 10)
    data_result = box([False, True, True, False, True] * 10)
    expected = qcut(data_expected, bins, duplicates="drop")
    result = qcut(data_result, bins, duplicates="drop")
    compare(result, expected)

@pytest.mark.parametrize("bins", [6, 7])
@pytest.mark.parametrize(
    "box, compare",
    [
        (Series, tm.assert_series_equal),
        (np.array, tm.assert_categorical_equal),
        (list, tm.assert_equal),
    ],
)
def test_qcut_bool_coercion_to_int_noassert(bins, box, compare):
    # issue 20303
    data_expected = box([0, 1, 1, 0, 1] * 10)
    data_result = box([False, True, True, False, True] * 10)
    expected = qcut(data_expected, bins, duplicates="drop")
    result = qcut(data_result, bins, duplicates="drop")
    #compare(result, expected)
