"""`plot --data-type force --component y`: --component is a list (nargs='+')
of x/y/z names; it used to reach plot_force_data as ['y'] and fail with
"unhashable type: 'list'"."""

import matplotlib
matplotlib.use('Agg')
import numpy as np
import pytest

from src.utils import plot_utils


class Reader:
    def _data(self, p):
        t = np.linspace(0, 1, 5)
        return {'times': t, f'{p}x': t, f'{p}y': 2 * t, f'{p}z': 3 * t, 'magnitude': 4 * t}

    def get_total_traction(self):
        return self._data('t')

    def get_total_moment(self):
        return self._data('m')


@pytest.mark.parametrize('component, scale', [(['y'], 2), ('y', 2), (['ty'], 2), (['Z'], 3),
                                              (['magnitude'], 4)])
def test_force_component(component, scale):
    fig, ax = plot_utils.plot_force_data(Reader(), component=component)
    assert np.allclose(ax.lines[0].get_ydata(), scale * np.linspace(0, 1, 5))


def test_moment_component_and_all():
    fig, ax = plot_utils.plot_moment_data(Reader(), component=['x'])
    assert np.allclose(ax.lines[0].get_ydata(), np.linspace(0, 1, 5))
    fig, axes = plot_utils.plot_force_data(Reader(), component=None)
    assert len(axes) == 4


def test_bad_component():
    with pytest.raises(ValueError, match='Use x, y, z'):
        plot_utils.plot_force_data(Reader(), component=['q'])
