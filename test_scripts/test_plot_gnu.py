"""plot --gnu: the terminal plot through whichever plotext is installed."""

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
