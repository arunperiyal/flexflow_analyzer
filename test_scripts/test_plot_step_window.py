"""plot --start-step/--end-step (and the t1/t2 context behind them) become
times n*dt; with t1:3000 taken as a time, a 250 s run plotted nothing."""

from types import SimpleNamespace

import pytest

from src.commands.visualization.plot_impl.command import apply_step_window


class Case:
    def __init__(self, dt):
        self.dt = dt

    def get_time_increment(self):
        return self.dt


class Log:
    def __init__(self):
        self.warned = []

    def info(self, msg):
        pass

    def warning(self, msg):
        self.warned.append(msg)


def args(**kw):
    base = dict(start_step=None, end_step=None, start_time=None, end_time=None)
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize('given, expected', [
    (dict(start_step=1000, end_step=3000), (50.0, 150.0)),
    (dict(start_step=0), (0.0, None)),
    (dict(start_step=1000, start_time=20.0), (20.0, None)),   # a typed time wins
    (dict(end_step=2000, start_time=5.0), (5.0, 100.0)),
    (dict(), (None, None)),
])
def test_steps_to_times(given, expected):
    a = args(**given)
    apply_step_window(a, Case(0.05), Log())
    for got, want in zip((a.start_time, a.end_time), expected):
        assert got == (None if want is None else pytest.approx(want))


def test_no_dt_warns_and_keeps_times():
    a, log = args(start_step=10), Log()
    apply_step_window(a, Case(None), log)
    assert a.start_time is None and log.warned


def test_gnu_with_a_plotext_that_cannot_plot(monkeypatch, tmp_path):
    # A directory named plotext on the path imports as an empty namespace
    # package: say where it came from instead of "has no attribute 'plot'"
    import types
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.commands.visualization.plot_impl import command as c
    empty = types.ModuleType('plotext')
    empty.__path__ = [str(tmp_path / 'plotext')]
    monkeypatch.setattr(c, 'plt_terminal', empty, raising=False)
    monkeypatch.setattr(c, 'HAS_PLOTEXT', True)
    errors = []
    log = types.SimpleNamespace(error=errors.append, info=print, debug=print, warning=print)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    assert c.plot_in_terminal(fig, ax, log) is False
    assert 'plain directory' in errors[0] and 'pip install -U plotext' in errors[0]


def test_gnu_with_plotext_6(monkeypatch):
    # plotext 6.x has no plot(): the matplotlib figure goes to plotext.matplotlib
    import types
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.commands.visualization.plot_impl import command as c
    shown = []
    converted = types.SimpleNamespace(show=lambda: shown.append(True))
    six = types.ModuleType('plotext')
    six.figure = object()
    six.matplotlib = lambda fig: shown.append(fig) or converted
    monkeypatch.setattr(c, 'plt_terminal', six, raising=False)
    monkeypatch.setattr(c, 'HAS_PLOTEXT', True)
    log = types.SimpleNamespace(error=print, info=print, debug=print, warning=print)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    assert c.plot_in_terminal(fig, ax, log) is True
    assert shown == [fig, True]
