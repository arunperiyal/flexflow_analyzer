"""Unit tests for services/fft.py's compute_fft, isolated from Flask/loader."""

import numpy as np
import pytest

from src.web.services.fft import compute_fft


def _synthetic_signal(fs=100.0, duration=4.0, dc=10.0, tones=((5.0, 3.0), (12.0, 1.5))):
    """A DC offset plus known-amplitude sine tones, on a uniform time grid."""
    n = int(fs * duration)
    times = np.arange(n) / fs
    values = np.full(n, dc)
    for freq, amp in tones:
        values = values + amp * np.sin(2 * np.pi * freq * times)
    return times, values


def test_recovers_the_exact_amplitude_of_each_known_tone():
    times, values = _synthetic_signal()
    freqs, amplitude = compute_fft(times, values)

    for freq, amp in ((5.0, 3.0), (12.0, 1.5)):
        idx = np.argmin(np.abs(freqs - freq))
        assert freqs[idx] == pytest.approx(freq, abs=1e-9)
        assert amplitude[idx] == pytest.approx(amp, abs=1e-9)


def test_dc_bin_is_near_zero_after_mean_removal():
    times, values = _synthetic_signal()
    _, amplitude = compute_fft(times, values)
    assert amplitude[0] == pytest.approx(0.0, abs=1e-9)


def test_frequency_axis_spans_zero_to_nyquist():
    times, values = _synthetic_signal(fs=100.0, duration=4.0)
    freqs, _ = compute_fft(times, values)
    assert freqs[0] == 0.0
    assert freqs[-1] == pytest.approx(50.0, abs=1e-9)   # Nyquist = fs / 2


def test_odd_length_signal_still_recovers_amplitudes_approximately():
    times, values = _synthetic_signal(duration=4.0)
    times, values = times[:-1], values[:-1]   # drop one sample -> odd N
    freqs, amplitude = compute_fft(times, values)

    idx = np.argmin(np.abs(freqs - 5.0))
    # Non-integer number of periods in the window leaks some energy into
    # neighboring bins, so this is close but not exact -- unlike the even-N case.
    assert amplitude[idx] == pytest.approx(3.0, abs=0.05)


def test_rejects_non_uniformly_spaced_times():
    times = np.array([0.0, 0.1, 0.2, 0.35, 0.4])
    values = np.zeros_like(times)
    with pytest.raises(ValueError, match='evenly spaced'):
        compute_fft(times, values)


def test_rejects_fewer_than_two_samples():
    with pytest.raises(ValueError, match='at least 2 samples'):
        compute_fft(np.array([0.0]), np.array([1.0]))


def test_rejects_non_positive_time_step():
    times = np.array([0.0, 0.0, 0.1])
    values = np.zeros_like(times)
    with pytest.raises(ValueError, match='evenly spaced'):
        compute_fft(times, values)
