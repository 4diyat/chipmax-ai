"""Tes One-Euro filter: konvergensi, noise, lag, dan validasi parameter."""

from __future__ import annotations

import math

import pytest

from jarvis_hands.vision.filters import OneEuroFilter, OneEuroFilter2D, OneEuroParams


def test_params_reject_invalid_values() -> None:
    with pytest.raises(ValueError):
        OneEuroParams(min_cutoff=0)
    with pytest.raises(ValueError):
        OneEuroParams(beta=-0.1)
    with pytest.raises(ValueError):
        OneEuroParams(d_cutoff=0)


def test_first_sample_returned_unchanged() -> None:
    filt = OneEuroFilter(OneEuroParams(min_cutoff=1.0, beta=0.0))
    assert filt.filter(3.5, t=0.0) == pytest.approx(3.5)


def test_constant_input_converges() -> None:
    filt = OneEuroFilter(OneEuroParams(min_cutoff=1.2, beta=0.0), x0=0.0)
    value = 0.0
    for i in range(120):
        value = filt.filter(1.0, t=i / 30.0)
    assert value == pytest.approx(1.0, abs=0.01)


def test_reduces_noise_more_than_raw() -> None:
    filt = OneEuroFilter(OneEuroParams(min_cutoff=1.2, beta=0.0), x0=0.5)
    samples = [0.0, 1.0] * 60
    out = [filt.filter(x, t=i / 30.0) for i, x in enumerate(samples)]
    assert max(out) - min(out) < 1.0
    assert abs(sum(out) / len(out) - 0.5) < 0.05


def test_higher_beta_reduces_lag_on_step() -> None:
    def settle(beta: float) -> list[float]:
        filt = OneEuroFilter(OneEuroParams(min_cutoff=1.0, beta=beta), x0=0.0)
        return [filt.filter(1.0, t=i / 30.0) for i in range(10)]

    slow = settle(0.0)
    fast = settle(1.0)
    assert fast[-1] > slow[-1]


def test_reset_clears_state() -> None:
    filt = OneEuroFilter(x0=5.0)
    assert filt.filter(5.0, t=0.0) == 5.0
    filt.reset()
    assert filt.filter(2.0, t=1.0) == pytest.approx(2.0)


def test_two_dimensional_filter_matches_axes() -> None:
    filt = OneEuroFilter2D(OneEuroParams(min_cutoff=1.0, beta=0.0), x0=0.0, y0=10.0)
    x, y = filt.filter(1.0, 11.0, t=0.1)
    assert 0.0 < x < 1.0
    assert 10.0 < y < 11.0
    filt.reset(0.0, 0.0)
    assert filt.filter(0.0, 0.0, t=0.2) == (0.0, 0.0)


def test_non_monotonic_time_does_not_crash() -> None:
    filt = OneEuroFilter(x0=0.0)
    filt.filter(1.0, t=5.0)
    filt.filter(1.0, t=1.0)
    assert math.isfinite(filt.filter(1.0, t=6.0))
