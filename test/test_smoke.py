"""Minimal headless smoke test for OpenHRV (issue #28).

Exercises the most basic construction and logic of the app without opening a
real window or needing a Bluetooth sensor. Qt runs via the "offscreen"
platform plugin (see conftest.py), so this is safe in headless CI.
"""

import math

from openhrv import config
from openhrv.utils import sign, valid_address, get_sensor_address
from openhrv.pacer import Pacer
from openhrv.model import Model

# Reuse the existing mock sensor so we never touch real Bluetooth. Imported as a
# top-level module (test/ is on sys.path via conftest.py) rather than `test.app`,
# which would collide with the Python standard library's `test` package.
from app import MockSensor


def test_sign():
    assert sign(5) == 1
    assert sign(-5) == -1
    assert sign(0) == 0


def test_breathing_rate_tick_roundtrip():
    # tick -> rate -> tick must be stable across the supported range.
    for tick in range(0, 7):
        rate = config.tick_to_breathing_rate(tick)
        assert config.MIN_BREATHING_RATE <= rate <= config.MAX_BREATHING_RATE
        assert config.breathing_rate_to_tick(rate) == tick


def test_mock_sensor_address_is_valid():
    sensor = MockSensor()
    address = get_sensor_address(sensor)
    # On Linux/Windows CI runners this resolves to the mock MAC.
    assert valid_address(address)


def test_pacer_radius_within_unit_range(qapp):
    pacer = Pacer()
    # breathing_pattern is scaled to [0, 1].
    for t in (0.0, 1.0, 12.3):
        radius = pacer.breathing_pattern(config.MAX_BREATHING_RATE, t)
        assert 0.0 <= radius <= 1.0

    x, y = pacer.update(config.MAX_BREATHING_RATE)
    assert len(x) == len(y) == len(pacer.cos_theta)
    # All points lie within the unit disk (radius <= 1).
    assert all(math.hypot(xi, yi) <= 1.0 + 1e-9 for xi, yi in zip(x, y))


def test_model_constructs_with_full_buffers(qapp):
    model = Model()
    assert len(model.ibis_buffer) == config.IBI_BUFFER_SIZE
    assert len(model.hrv_buffer) == config.HRV_BUFFER_SIZE
    assert config.MIN_HRV_TARGET <= model.hrv_target <= config.MAX_HRV_TARGET


def test_model_validates_outlier_ibi(qapp):
    model = Model()
    # An absurd IBI (outside [MIN_IBI, MAX_IBI]) is corrected, not stored raw.
    model.update_ibis_buffer(99_999)
    assert config.MIN_IBI <= model.ibis_buffer[-1] <= config.MAX_IBI
    # A physiologically plausible IBI passes through unchanged.
    model.update_ibis_buffer(900)
    assert model.ibis_buffer[-1] == 900


def test_model_reset_buffers_restores_baseline(qapp):
    baseline = Model()
    model = Model()
    # Push real data so the buffers and derived state diverge from baseline.
    for ibi in (850, 950, 1050, 900, 1000):
        model.update_ibis_buffer(ibi)
    assert list(model.ibis_buffer) != list(baseline.ibis_buffer)

    model.reset_buffers()

    assert list(model.ibis_buffer) == list(baseline.ibis_buffer)
    assert list(model.hrv_buffer) == list(baseline.hrv_buffer)
    assert list(model.ibis_seconds) == list(baseline.ibis_seconds)
    assert list(model.hrv_seconds) == list(baseline.hrv_seconds)
    assert model.ewma_hrv == baseline.ewma_hrv
    assert model._duration_current_phase == 0
