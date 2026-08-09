"""Progress feedback for long field operations (rich bars/spinners, no-op when unwanted).

Both helpers degrade to a no-op when output is redirected, when --no-progress is
given, or when --verbose is on (per-step log lines are the feedback then, and a
live bar would interleave with them).
"""

import sys
from contextlib import contextmanager


def progress_enabled(args, n_items=2):
    """True if a bar/spinner should be drawn for `n_items` units of work."""
    return (n_items > 0
            and not getattr(args, "no_progress", False)
            and not getattr(args, "verbose", False)
            and sys.stdout.isatty())


class _NullBar:
    """Stand-in used when progress is disabled."""

    def step(self, description=None):
        pass

    def advance(self, n=1):
        pass


class _RichBar:
    def __init__(self, progress, task, base):
        self._progress = progress
        self._task = task
        self._base = base

    def step(self, description=None):
        """Announce the unit of work about to start."""
        self._progress.update(self._task, description=description or self._base)

    def advance(self, n=1):
        """Mark n units of work finished."""
        self._progress.update(self._task, advance=n)


@contextmanager
def step_bar(total, description="Working", enabled=True):
    """Yield a bar over `total` steps: call .step(label) then .advance() per step."""
    if not enabled or total <= 0:
        yield _NullBar()
        return
    from rich.progress import (Progress, SpinnerColumn, BarColumn, TextColumn,
                               MofNCompleteColumn, TimeRemainingColumn)
    with Progress(SpinnerColumn(),
                  TextColumn("[cyan]{task.description}"),
                  BarColumn(),
                  MofNCompleteColumn(),
                  TimeRemainingColumn(),
                  transient=True) as progress:
        task = progress.add_task(description, total=total)
        yield _RichBar(progress, task, description)


@contextmanager
def spinner(message, enabled=True):
    """Show a spinner while a single long step (e.g. reading one big PLT) runs."""
    if not enabled:
        yield
        return
    from rich.console import Console
    with Console().status(f"[cyan]{message}", spinner="dots"):
        yield
