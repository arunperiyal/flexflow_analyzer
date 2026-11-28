"""The delete stage of `auto apply`: the commands `auto show` lists, run (auto.md 13.27).

`auto show` prints `case organise out|plt|rst|vtu ...` as the Action of each file kind. Those
commands decide, file by file, what has a stand-in (src/core/chain.py); `apply` does not
decide again. It runs each one as its own process, the way a user does, and reads what it did
from `--result FILE`. What stays in `apply`: the hold-back (the queue was read, the case does
not need you, no post job is queued), the one question with totals, the log.
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[3]
MAIN = REPO / 'main.py'

# plan step key -> the kind of file it deletes (the keys of the old plan.ctx['delete'])
KIND_OF = {'delete-ascii': 'ascii', 'delete-binary': 'binary', 'delete-out': 'out',
           'thin-rst': 'rst', 'delete-vtu': 'vtu'}


@dataclass
class Ran:
    command: str
    code: int
    files: Dict[str, int] = field(default_factory=dict)      # rel path -> size
    failed: int = 0
    output: str = ''

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.failed == 0


def delete_steps(plan):
    """The plan's delete steps `apply` may run, in the order `auto show` lists them; none
    when the case is held back (it needs you, or the queue could not be read)."""
    if not plan.ctx.get('delete_allowed'):
        return []
    return [s for s in plan.steps if s.kind == 'delete' and s.key in KIND_OF]


def run_command(command: str, folder, dry_run: bool, timeout=None) -> Ran:
    """One `case organise ...` command, from the folder the case is in. With dry_run it
    lists what would go and changes nothing."""
    with tempfile.TemporaryDirectory(prefix='ff_apply_') as tmp:
        result = Path(tmp) / 'result.json'
        argv = [sys.executable, str(MAIN), *shlex.split(command),
                '--dry-run' if dry_run else '--yes', '--result', str(result)]
        try:
            done = subprocess.run(argv, cwd=str(folder), capture_output=True, text=True,
                                  timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return Ran(command, 1, output=str(e))
        out = (done.stdout or '') + (done.stderr or '')
        try:
            data = json.loads(result.read_text())
        except (OSError, ValueError):
            # the command stopped before it knew what to do: nothing was deleted
            return Ran(command, done.returncode or 1, output=out)
        return Ran(command, done.returncode, {rel: size for rel, size in data.get('files', [])},
                   int(data.get('failed', 0)), out)


def listed(plan, folder) -> Dict[str, Dict[str, int]]:
    """What the plan's delete commands would delete, by kind: {kind: {rel: size}}, from a
    dry run of each. Empty when the case is held back."""
    found: Dict[str, Dict[str, int]] = {}
    for step in delete_steps(plan):
        ran = run_command(step.command, folder, dry_run=True)
        if ran.files:
            found.setdefault(KIND_OF[step.key], {}).update(ran.files)
    return found


def run_all(plan, folder, say) -> List[Ran]:
    """Run the delete commands for real, in order. A command that fails stops the stage:
    the ones after it may rest on what it should have done."""
    ran = []
    for step in delete_steps(plan):
        say(f"$ {step.command}")
        one = run_command(step.command, folder, dry_run=False)
        ran.append(one)
        for rel in sorted(one.files):
            say(f"deleted {rel}")
        if not one.ok:
            say(f"{step.command}: "
                f"{'exit ' + str(one.code) if one.code else str(one.failed) + ' file(s) not deleted'}")
            for line in one.output.strip().splitlines()[-6:]:
                say(f"    {line}")
            break
    return ran
