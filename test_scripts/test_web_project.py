"""Tests for src/web/services/project.py: (probe, frame) -> views and projections.

Covers each probe type -- a straight line, a closed ring (helix/surface with a
declared radius), a cloud -- run both with a beam frame from domain.yml and
with no frame at all (the largest-range-pair fallback).
"""

import math

import numpy as np
import pytest

from src.web.services.project import Frame, project, views_for


def _straight_riser_points(n=11, length=10.0):
    """A line along +z, origin at the base, with a small x wobble."""
    z = np.linspace(0.0, length, n)
    x = 0.05 * np.sin(z)
    y = np.zeros(n)
    return np.column_stack([x, y, z])


def _ring_points(n=12, radius=1.0, z=3.0):
    """A ring of points around +z at a fixed height -- a closed helix/surface probe."""
    theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    z_arr = np.full(n, z)
    return np.column_stack([x, y, z_arr]), theta


@pytest.fixture
def beam_body():
    return {'name': 'cyl', 'type': 'beam',
            'geometry': {'origin': [0.0, 0.0, 0.0], 'axis': '+z', 'length': 10.0, 'radius': None}}


@pytest.fixture
def beam_body_with_radius():
    return {'name': 'cyl', 'type': 'beam',
            'geometry': {'origin': [0.0, 0.0, 0.0], 'axis': '+z', 'length': 10.0, 'radius': 1.0}}


# -- line probe -------------------------------------------------------------

def test_line_with_frame_offers_s_and_profile(beam_body):
    frame = Frame.from_body(beam_body)
    views = views_for('line', frame)
    ids = [v['id'] for v in views]
    assert ids[:2] == ['s_profile', 'profile']
    assert {'xy', 'yz', 'xz'} <= set(ids)


def test_line_s_profile_matches_axial_position(beam_body):
    frame = Frame.from_body(beam_body)
    points = _straight_riser_points()
    result = project('s_profile', points, frame)
    s = np.array([p[0] for p in result['pts']])
    assert np.allclose(s, points[:, 2])   # axis is +z, origin at 0 -> s == z


def test_line_without_frame_falls_back_to_largest_range_pair():
    views = views_for('line', None)
    assert views[0]['id'] == 'largest_pair'
    points = _straight_riser_points()
    result = project('largest_pair', points, None)
    # z has the largest range by far, x barely wobbles -> (x, z) pair, y excluded
    assert 'z' in result['ay'] or 'z' in result['ax']


# -- helix / surface (a ring, closed) ---------------------------------------

def test_helix_unrolled_uses_declared_radius(beam_body_with_radius):
    frame = Frame.from_body(beam_body_with_radius)
    points, theta = _ring_points(radius=1.0)
    result = project('unrolled', points, frame)
    assert 'r=1' in result['ay']
    circumferential = np.array([p[1] for p in result['pts']])
    # radius is 1.0, so circumferential == angle in radians. The transverse
    # basis's own zero-angle and handedness are unspecified, so check the
    # invariant instead of an exact angle: sorting recovers the ring's even
    # angular step regardless of where zero sits or which way it winds.
    wrapped = np.sort(np.mod(circumferential, 2 * math.pi))
    steps = np.diff(np.concatenate([wrapped, [wrapped[0] + 2 * math.pi]]))
    assert np.allclose(steps, 2 * math.pi / len(theta), atol=1e-9)


def test_helix_unrolled_falls_back_to_degrees_without_declared_radius(beam_body):
    frame = Frame.from_body(beam_body)   # radius is None
    points, _ = _ring_points()
    result = project('unrolled', points, frame)
    assert 'radius not declared' in result['ay']
    circumferential = np.array([p[1] for p in result['pts']])
    assert circumferential.max() <= 180.0 and circumferential.min() >= -180.0


def test_helix_cross_section_recovers_the_ring_radius(beam_body):
    frame = Frame.from_body(beam_body)
    points, _ = _ring_points(radius=2.5)
    result = project('cross_section', points, frame)
    u = np.array([p[0] for p in result['pts']])
    v = np.array([p[1] for p in result['pts']])
    r = np.hypot(u, v)
    assert np.allclose(r, 2.5, atol=1e-9)


def test_helix_without_frame_offers_theta_pair(beam_body):
    views = views_for('helix', None)
    ids = [v['id'] for v in views]
    assert ids[0] == 'theta_pair'
    points, _ = _ring_points()
    result = project('theta_pair', points, None)
    assert len(result['pts']) == len(points)


# -- surface ------------------------------------------------------------

def test_surface_with_frame_offers_unrolled_and_cross_section(beam_body):
    frame = Frame.from_body(beam_body)
    ids = [v['id'] for v in views_for('surface', frame)]
    assert ids[:2] == ['unrolled', 'cross_section']


def test_surface_grid_without_frame_uses_largest_range_pair():
    xs, ys = np.meshgrid(np.linspace(0, 1, 4), np.linspace(0, 5, 4))
    points = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(16)])
    views = views_for('surface', None)
    assert views[0]['id'] == 'largest_pair'
    result = project('largest_pair', points, None)
    assert 'y' in result['ay'] or 'y' in result['ax']   # y has the larger range


# -- cloud ----------------------------------------------------------------

def test_cloud_offers_profile_and_cross_section_with_frame(beam_body):
    ids = [v['id'] for v in views_for('cloud', Frame.from_body(beam_body))]
    assert ids[:2] == ['profile', 'cross_section']


def test_cloud_without_frame_uses_largest_range_pair():
    views = views_for('cloud', None)
    assert views[0]['id'] == 'largest_pair'


# -- point ------------------------------------------------------------------

def test_point_probe_offers_no_views():
    assert views_for('point', None) == []
    assert views_for('point', Frame.from_body({'geometry': {'axis': '+z'}})) == []


# -- planes are always present, and error on unknown view id ----------------

def test_planes_always_available_and_computed_directly():
    points = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    result = project('xy', points, None)
    assert result['pts'] == [[1.0, 2.0], [4.0, 5.0]]
    result = project('yz', points, None)
    assert result['pts'] == [[2.0, 3.0], [5.0, 6.0]]


def test_unknown_view_id_raises():
    with pytest.raises(ValueError):
        project('nonsense', np.zeros((2, 3)), None)


def test_frame_view_without_frame_raises():
    with pytest.raises(ValueError):
        project('unrolled', np.zeros((2, 3)), None)
