"""
Has a finished case's history settled? -- the `data check steady` analysis, run
for `auto` over the last N steps, quietly (auto.md 13.24).

    got = judge(case_dir, 'dy', last=2000)
    got.verdict       # 'steady', 'not steady', 'too short', or '' when it could not be judged
    got.reasons       # why not steady; or why it could not be judged
    got.first, got.last_step    # the steps judged
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from ...utils.logger import Logger


@dataclass
class Judged:
    verdict: str = ''
    reasons: List[str] = field(default_factory=list)
    first: Optional[int] = None
    last_step: Optional[int] = None
    cycles: int = 0


class _Quiet(Logger):
    """Collects what the check would print, so `auto show` stays its own."""

    def __init__(self):
        super().__init__(verbose=False)
        self.lines: List[str] = []

    def info(self, message):
        pass

    def success(self, message):
        pass

    def warning(self, message):
        pass

    def debug(self, message):
        pass

    def error(self, message):
        self.lines.append(' '.join(str(message).split()))


def judge(case_dir, var: str, last: int, **limits) -> Judged:
    """The steady verdict of `var` over the last `last` steps of the case's
    history; a variable or file that cannot be read gives verdict '' and the reason."""
    import numpy as np
    from ...commands.data import shared
    from ...commands.data.check_impl import steady

    case_dir = Path(case_dir)
    log = _Quiet()
    args = SimpleNamespace(othd=False, oisd=False, group=None, othid=None, osgid=None)
    limits = dict(blocks=steady.BLOCKS, tol=steady.TOL, mean_tol=steady.MEAN_TOL,
                  min_cycles=steady.MIN_CYCLES, **limits) if not limits.keys() >= {
                      'blocks', 'tol', 'mean_tol', 'min_cycles'} else limits
    try:
        metas = shared.scan_kinds(case_dir, shared.which_kinds(args), log)
        requested = shared.split_vars([var])
        matched = {k: [r for r in requested if shared.known_name(m, r)] for k, m in metas.items()}
        matched = {k: v for k, v in matched.items() if v}
        if not matched:
            return Judged(reasons=[f"{var} is not in this case's data"])
        if len(matched) > 1:
            return Judged(reasons=[f"{var} lives in both the othd and the oisd files"])
        kind = next(iter(matched))
        meta = metas[kind]
        group = shared.resolve_group(meta, args, log)
        columns = shared.resolve_columns(meta, requested, log, group)
        node = shared.resolve_node(meta, None, log, group)
        mask = shared.step_mask(meta, None, None, log, last)
        times, tsids, values = shared.gather(meta, columns, node, mask, group)
        order = tsids.argsort(kind='stable')
        times, tsids = times[order], tsids[order]
        worst = None
        for label, series_values in values.items():
            got = steady.analyse(times, series_values[order], **limits)
            rank = {steady.STEADY: 0, steady.TOO_SHORT: 1, steady.NOT_STEADY: 2}[got.verdict]
            if worst is None or rank > worst[0]:
                worst = (rank, label, got)
        _, label, got = worst
        reasons = [f"{label}: {r}" for r in got.failures] if got.verdict != steady.STEADY else []
        return Judged(got.verdict, reasons, int(tsids.min()), int(tsids.max()), got.cycles)
    except SystemExit:
        return Judged(reasons=log.lines[:1] or ["the history could not be read"])
    except Exception as e:                      # a damaged file must not stop `auto`
        return Judged(reasons=[f"the history could not be read: {e}"])
