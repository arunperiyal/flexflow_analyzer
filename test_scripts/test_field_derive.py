"""Tests for derived variables -- lambda2 in particular.

A vortex criterion is a function of the velocity gradient, so a solver that
writes QCriterion and not lambda2 has not withheld anything: the second is
computable from U/V/W. What is worth testing is that it is computed correctly,
that it is not recomputed once present, and that asking for a variable that is
neither present nor derivable says so rather than failing later inside VTK.
"""

import numpy as np
import pytest

from src.plt import derive

pv = pytest.importorskip("pyvista")


def _flow(gradient):
    """A box of points carrying a velocity field with a known constant gradient."""
    grid = pv.ImageData(dimensions=(8, 8, 8), spacing=(0.25, 0.25, 0.25))
    mesh = grid.cast_to_unstructured_grid()
    p = mesh.points
    vel = p @ np.asarray(gradient, dtype=float).T
    mesh.point_data["U"], mesh.point_data["V"], mesh.point_data["W"] = vel.T
    return mesh


class TestLambda2:
    """lambda2 is the middle eigenvalue of S^2 + Omega^2."""

    def test_solid_body_rotation_is_a_vortex(self):
        """Pure rotation: lambda2 must be negative -- it is all vortex."""
        mesh = _flow([[0, -1, 0], [1, 0, 0], [0, 0, 0]])
        derive.ensure(mesh, "lambda2", log=lambda *_: None)
        assert (mesh["lambda2"] < 0).all()

    def test_pure_shear_is_not_a_vortex(self):
        """Simple shear has equal strain and rotation; lambda2 is not negative."""
        mesh = _flow([[0, 1, 0], [0, 0, 0], [0, 0, 0]])
        derive.ensure(mesh, "lambda2", log=lambda *_: None)
        assert (mesh["lambda2"] >= -1e-9).all()

    def test_uniform_flow_has_no_structure(self):
        """A constant velocity has zero gradient, so lambda2 is zero."""
        grid = pv.ImageData(dimensions=(6, 6, 6)).cast_to_unstructured_grid()
        n = grid.n_points
        grid.point_data["U"] = np.ones(n)
        grid.point_data["V"] = np.zeros(n)
        grid.point_data["W"] = np.zeros(n)
        derive.ensure(grid, "lambda2", log=lambda *_: None)
        assert np.allclose(grid["lambda2"], 0.0, atol=1e-6)

    def test_it_is_float32(self):
        """Half the memory of float64, and plenty for a contour level."""
        mesh = _flow([[0, -1, 0], [1, 0, 0], [0, 0, 0]])
        derive.ensure(mesh, "lambda2", log=lambda *_: None)
        assert mesh["lambda2"].dtype == np.float32


class TestEnsure:
    def test_present_is_not_recomputed(self):
        mesh = _flow([[0, -1, 0], [1, 0, 0], [0, 0, 0]])
        mesh.point_data["lambda2"] = np.zeros(mesh.n_points, dtype=np.float32)
        assert derive.ensure(mesh, "lambda2", log=lambda *_: None) is False
        assert np.array_equal(mesh["lambda2"], np.zeros(mesh.n_points))

    def test_an_unknown_name_says_what_is_possible(self):
        mesh = _flow([[0, -1, 0], [1, 0, 0], [0, 0, 0]])
        with pytest.raises(ValueError) as exc:
            derive.ensure(mesh, "nonsense", log=lambda *_: None)
        assert "nonsense" in str(exc.value)
        assert "lambda2" in str(exc.value)          # names what it could do

    def test_missing_velocity_is_named(self):
        grid = pv.ImageData(dimensions=(4, 4, 4)).cast_to_unstructured_grid()
        grid.point_data["Pressure"] = np.zeros(grid.n_points)
        with pytest.raises(ValueError) as exc:
            derive.ensure(grid, "lambda2", log=lambda *_: None)
        assert "velocity" in str(exc.value)

    def test_registry(self):
        assert derive.is_derived("lambda2")
        assert not derive.is_derived("QCriterion")   # solver-written, not ours
        assert "lambda2" in derive.names()
        assert all(len(row) == 3 for row in derive.describe())
