"""services/project.py — (probe, frame) -> the picker's views and projections.

The map says what shape the points make (§6 of docs/WEBAPP_PLAN.md); a beam's
domain.yml frame says what axis they sit on (§7). This module turns that pair
into the View selector's options and, given a chosen view, the 2-D points to
plot -- largest-range pair when there is no frame, arc length / unrolled
angle / cross-section when there is.
"""

from typing import Optional

import numpy as np

_AXIS_VECTORS = {
    '+x': (1.0, 0.0, 0.0), '-x': (-1.0, 0.0, 0.0),
    '+y': (0.0, 1.0, 0.0), '-y': (0.0, -1.0, 0.0),
    '+z': (0.0, 0.0, 1.0), '-z': (0.0, 0.0, -1.0),
}
_COORD_LABELS = ('x', 'y', 'z')
_PLANES = [{'id': 'xy', 'label': 'x–y'}, {'id': 'yz', 'label': 'y–z'},
          {'id': 'xz', 'label': 'x–z'}]
_PLANE_INDEX = {'xy': (0, 1), 'yz': (1, 2), 'xz': (0, 2)}


def axis_vector(axis) -> np.ndarray:
    if isinstance(axis, str):
        vec = _AXIS_VECTORS.get(axis)
        if vec is None:
            raise ValueError(f"unknown axis '{axis}'")
        return np.array(vec, dtype=float)
    vec = np.array(axis, dtype=float)
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def _basis(axis: np.ndarray):
    """An orthonormal (axis, u, v) frame; u/v span the plane transverse to axis."""
    ref = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    return u, v


def _largest_range_pair(points: np.ndarray):
    ranges = points.max(axis=0) - points.min(axis=0)
    order = np.argsort(ranges)[::-1]
    return int(order[0]), int(order[1])


class Frame:
    """A beam-like body's axial frame: origin, axis, length, radius (often None)."""

    def __init__(self, origin, axis, length=None, radius=None, label=None):
        self.origin = np.array(origin, dtype=float)
        self.axis = axis_vector(axis)
        self.length = length
        self.radius = radius
        self.label = label

    @classmethod
    def from_body(cls, body: Optional[dict]) -> Optional['Frame']:
        geometry = (body or {}).get('geometry') or {}
        axis = geometry.get('axis')
        if not body or axis is None:
            return None
        origin = geometry.get('origin') or [0.0, 0.0, 0.0]
        label = f"{body.get('name', '?')} ({body.get('type', '?')})"
        return cls(origin, axis, geometry.get('length'), geometry.get('radius'), label)


def views_for(probe: str, frame: Optional[Frame]) -> list:
    """The View selector's options for (probe, frame), default first (§7 table)."""
    if probe == 'point':
        return []
    if frame is not None:
        by_probe = {
            'line': [{'id': 's_profile', 'label': 's (arc length)'},
                     {'id': 'profile', 'label': 'profile (axis vs transverse)'}],
            'helix': [{'id': 'unrolled', 'label': 'unrolled (θ–s)'},
                      {'id': 'cross_section', 'label': 'cross-section'},
                      {'id': 'profile', 'label': 'profile'}],
            'surface': [{'id': 'unrolled', 'label': 'unrolled (θ–s)'},
                        {'id': 'cross_section', 'label': 'cross-section'}],
            'cloud': [{'id': 'profile', 'label': 'profile'},
                      {'id': 'cross_section', 'label': 'cross-section'}],
        }
        primary = by_probe.get(probe, [])
    else:
        if probe == 'helix':
            primary = [{'id': 'theta_pair', 'label': 'θ about the largest-range axis'},
                       {'id': 'largest_pair', 'label': 'largest-range pair'}]
        else:
            primary = [{'id': 'largest_pair', 'label': 'largest-range pair'}]
    return primary + _PLANES


def project(view_id: str, points: np.ndarray, frame: Optional[Frame] = None) -> dict:
    """{'ax', 'ay', 'pts'} for one view over `points` (n, 3)."""
    if view_id in _PLANE_INDEX:
        i, j = _PLANE_INDEX[view_id]
        return {'ax': f"{_COORD_LABELS[i]} [m]", 'ay': f"{_COORD_LABELS[j]} [m]",
                'pts': points[:, [i, j]].tolist()}

    if view_id == 'largest_pair':
        i, j = _largest_range_pair(points)
        return {'ax': f"{_COORD_LABELS[i]} [m]", 'ay': f"{_COORD_LABELS[j]} [m]",
                'pts': points[:, [i, j]].tolist()}

    if view_id == 'theta_pair':
        i, _ = _largest_range_pair(points)
        others = [k for k in range(3) if k != i]
        a = points[:, others[0]] - points[:, others[0]].mean()
        b = points[:, others[1]] - points[:, others[1]].mean()
        theta = np.degrees(np.arctan2(b, a))
        return {'ax': 'index', 'ay': f"θ about {_COORD_LABELS[i]} [deg]",
                'pts': list(zip(range(len(theta)), theta.tolist()))}

    if frame is None:
        raise ValueError(f"view '{view_id}' needs a body frame")

    u, v = _basis(frame.axis)
    rel = points - frame.origin
    s = rel @ frame.axis
    ru = rel @ u
    rv = rel @ v

    if view_id == 's_profile':
        _, j = _largest_range_pair(points)
        return {'ax': 's [m]', 'ay': f"{_COORD_LABELS[j]} [m]",
                'pts': list(zip(s.tolist(), points[:, j].tolist()))}

    if view_id == 'profile':
        span_u = ru.max() - ru.min() if len(ru) else 0.0
        span_v = rv.max() - rv.min() if len(rv) else 0.0
        transverse, label = (ru, 'u [m] (transverse)') if span_u >= span_v else (rv, 'v [m] (transverse)')
        return {'ax': 's [m]', 'ay': label, 'pts': list(zip(s.tolist(), transverse.tolist()))}

    if view_id == 'unrolled':
        theta = np.arctan2(rv, ru)
        if frame.radius:
            circumferential = theta * frame.radius
            ay = f"rθ [m] (r={frame.radius:g})"
        else:
            circumferential = np.degrees(theta)
            ay = 'θ [deg] (radius not declared)'
        return {'ax': 's [m]', 'ay': ay, 'pts': list(zip(s.tolist(), circumferential.tolist()))}

    if view_id == 'cross_section':
        return {'ax': 'u [m] (transverse)', 'ay': 'v [m] (transverse)',
                'pts': list(zip(ru.tolist(), rv.tolist()))}

    raise ValueError(f"unknown view '{view_id}'")
