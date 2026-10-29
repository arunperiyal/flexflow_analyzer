"""
`case upload|download history`: the OTHD/OISD history of `case organise
history` -- archive/, cleaned/ and the compiled file, of othd_files/ and
oisd_files/ -- or the sets of it named with --archive/--cleaned/--compiled.

The readers take the compiled file only while it is newer than archive/,
cleaned/ and every run (core/history.py), and a copied file is as new as the
copy. So the compiled file goes after the runs of its type, and is then made
older than them on the other side when it does not hold all they do: when it
was not up to date where it came from, or the other side has runs it lacks.
"""

import os
import posixpath
import tempfile
from typing import Dict, List, Optional

from rich.progress import (Progress, BarColumn, TextColumn, DownloadColumn,
                           TransferSpeedColumn, TimeRemainingColumn)

from src.core import history

# The transfer target of `case upload|download history`, with the sets after
# the colon: __history__:archive,cleaned,compiled.
HISTORY_TARGET = '__history__'
HISTORY_SETS = ('archive', 'cleaned', 'compiled')


def history_target(sets) -> str:
    return f"{HISTORY_TARGET}:{','.join(sets)}"


def history_sets(target: str) -> Optional[List[str]]:
    """The sets a history target carries, or None for another target."""
    if not target.startswith(HISTORY_TARGET + ':'):
        return None
    return [s for s in target.split(':', 1)[1].split(',') if s in HISTORY_SETS]


def history_label(target: str) -> Optional[str]:
    sets = history_sets(target)
    return None if sets is None else f"history ({', '.join(sets)})"


class _Local:
    """A case on this machine, by paths relative to it."""

    def __init__(self, root):
        self.root = str(root)

    def path(self, rel):
        return os.path.join(self.root, *rel.split('/'))

    def names(self, rel):
        path = self.path(rel)
        return os.listdir(path) if os.path.isdir(path) else []

    def stat(self, rel):
        try:
            st = os.stat(self.path(rel))
        except FileNotFoundError:
            return None
        return st.st_size, st.st_mtime

    def set_mtime(self, rel, mtime):
        os.utime(self.path(rel), (mtime, mtime))


class _Remote:
    """A case on the remote, the same way."""

    def __init__(self, ssh, root):
        self.ssh, self.root = ssh, root

    def path(self, rel):
        return f"{self.root}/{rel}"

    def names(self, rel):
        path = self.path(rel)
        return self.ssh.list_remote_dir(path) if self.ssh.remote_is_dir(path) else []

    def stat(self, rel):
        return self.ssh.remote_stat(self.path(rel))

    def set_mtime(self, rel, mtime):
        self.ssh.set_remote_mtime(self.path(rel), mtime)


def _runs(side, ext: str, problem: str) -> Dict[str, List[str]]:
    """{'archive'|'cleaned'|'flat': [path relative to the case]} of the runs."""
    pattern = history.run_pattern(ext, problem)
    found = {}
    for group, rel in (('archive', f'{ext}_files/archive'),
                       ('cleaned', f'{ext}_files/cleaned'), ('flat', f'{ext}_files')):
        names = sorted((n for n in side.names(rel) if pattern.match(n)),
                       key=lambda n: int(pattern.match(n).group(1)))
        found[group] = [f'{rel}/{n}' for n in names]
    return found


def _numbers(ext: str, problem: str, runs: Dict[str, List[str]]) -> set:
    pattern = history.run_pattern(ext, problem)
    return {int(pattern.match(posixpath.basename(p)).group(1))
            for paths in runs.values() for p in paths}


def _compiled(ext: str, problem: str) -> str:
    return f'{ext}_files/{problem}.{ext}'


def _fresh(side, ext: str, problem: str, runs) -> bool:
    """history.compiled_is_fresh, on either side."""
    compiled = side.stat(_compiled(ext, problem))
    if not compiled or runs['flat']:
        return False
    watched = [f'{ext}_files/archive', f'{ext}_files/cleaned', *runs['archive'], *runs['cleaned']]
    return compiled[1] >= _newest(side, watched)


def _newest(side, rels) -> float:
    return max((st[1] for st in map(side.stat, rels) if st), default=0.0)


class HistoryTransferMixin:
    """upload_history / download_history for CaseUploadCommand."""

    def upload_history(self, ssh, remote_case_path: str, local_case_path: str,
                       sets: List[str], force: bool = False) -> bool:
        from src.core.simflow_config import SimflowConfig
        problem = SimflowConfig(os.path.join(local_case_path, 'simflow.config')).problem
        if not problem:
            self.console.print(f"[red]Error:[/red] simflow.config in {local_case_path} "
                               f"needs 'problem' to name the history files")
            return False
        if not ssh.remote_path_exists(remote_case_path):
            if not force:
                self.console.print(f"[yellow]Warning:[/yellow] Remote case not found: "
                                   f"{remote_case_path}")
                self.console.print("[dim]Use --force to create remote directories[/dim]")
                return False
        made = set()

        def send(rel):
            parent = posixpath.dirname(rel)
            if parent not in made:
                if not ssh.make_remote_dir(f"{remote_case_path}/{parent}"):
                    raise IOError(f"could not create {remote_case_path}/{parent}")
                made.add(parent)
            ssh.upload_file(src.path(rel), dst.path(rel))

        src, dst = _Local(local_case_path), _Remote(ssh, remote_case_path)
        return self._carry_history(src, dst, send, sets, problem, 'Uploaded')

    def download_history(self, ssh, remote_case_path: str, local_case_path: str,
                         sets: List[str]) -> bool:
        """problem comes from the remote simflow.config -- the run that wrote
        the files -- or the local one when the remote has none."""
        from src.core.simflow_config import SimflowConfig
        cfg_path, tmp = os.path.join(local_case_path, 'simflow.config'), None
        try:
            remote_cfg = f"{remote_case_path}/simflow.config"
            if ssh.remote_path_exists(remote_cfg):
                fd, tmp = tempfile.mkstemp(suffix='.config')
                os.close(fd)
                ssh.download_file(remote_cfg, tmp)
                cfg_path = tmp
            problem = SimflowConfig(cfg_path).problem
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not read the remote simflow.config: {exc}")
            return False
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        if not problem:
            self.console.print("[red]Error:[/red] simflow.config needs 'problem' "
                               "to name the history files")
            return False

        def send(rel):
            ssh.download_file(src.path(rel), dst.path(rel))

        src, dst = _Remote(ssh, remote_case_path), _Local(local_case_path)
        return self._carry_history(src, dst, send, sets, problem, 'Downloaded')

    def _carry_history(self, src, dst, send, sets, problem, done: str) -> bool:
        """Send the sets of both types from src to dst, compiled file last."""
        try:
            plan, keep_fresh, skipped = [], {}, 0
            for ext in history.TYPES:
                runs = _runs(src, ext, problem)
                picked = {'archive': runs['archive'] + runs['flat'],
                          'cleaned': runs['cleaned'],
                          'compiled': [_compiled(ext, problem)]
                          if src.stat(_compiled(ext, problem)) else []}
                counts = []
                for name in sets:
                    files = picked[name]
                    if name == 'archive':
                        # An archived run never changes, so one already there is kept.
                        there = [r for r in files if (dst.stat(r) or (None,))[0]
                                 == src.stat(r)[0]]
                        skipped += len(there)
                        files = [r for r in files if r not in there]
                    plan += [(r, src.stat(r)[0]) for r in files]
                    counts.append(f"{name} {len(picked[name])}")
                if 'compiled' in sets and picked['compiled']:
                    keep_fresh[ext] = (_fresh(src, ext, problem, runs),
                                       _numbers(ext, problem, runs))
                self.console.print(f"[cyan]Selecting:[/cyan] {ext}_files: {', '.join(counts)}")
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not list the history in {src.root}: {exc}")
            return False

        if skipped:
            self.console.print(f"[dim]    {skipped} archived run(s) already in {dst.root}[/dim]")
        if not plan and not skipped:
            self.console.print(f"[yellow]Warning:[/yellow] No {'/'.join(sets)} history in {src.root}")
            return False

        total = sum(size for _, size in plan)
        try:
            with Progress(TextColumn("[progress.description]{task.description}"), BarColumn(),
                          DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn()) as progress:
                task = progress.add_task("Transferring history...", total=total or None)
                moved = 0
                for rel, size in plan:
                    send(rel)
                    moved += size
                    progress.update(task, completed=moved, description=f"Transferred {rel}")
            for ext, (fresh, numbers) in keep_fresh.items():
                self._settle_compiled(dst, ext, problem, fresh, numbers)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Failed to transfer the history: {exc}")
            return False
        self.console.print(f"[green]✓[/green] {done} {len(plan)} history file(s) to {dst.root}")
        return True

    def _settle_compiled(self, dst, ext, problem, fresh, numbers) -> None:
        """Make the compiled file just sent older than dst's runs, so the
        readers take the runs, unless it holds everything they do."""
        runs = _runs(dst, ext, problem)
        extra = sorted(_numbers(ext, problem, runs) - numbers)
        if fresh and not extra:
            return
        watched = [f'{ext}_files/archive', f'{ext}_files/cleaned', *runs['archive'],
                   *runs['cleaned'], *runs['flat']]
        newest = _newest(dst, watched)
        if newest:
            dst.set_mtime(_compiled(ext, problem), newest - 1)
        why = (f"run(s) {', '.join(map(str, extra))} only in {dst.root}" if extra
               else "it was not up to date with its runs")
        self.console.print(f"[yellow]  {problem}.{ext}:[/yellow] {why}; the readers take "
                           f"the runs until `case organise history --compile`")
