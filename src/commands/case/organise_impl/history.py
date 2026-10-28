"""
`case organise history`: the OTHD/OISD history of a case, in three stages
(layout in src/core/history.py):

    --update   run dir           → {ext}_files/archive/{problem}N.{ext}
    --clean    archive/          → {ext}_files/cleaned/{problem}N.{ext}
    --compile  cleaned/          → {ext}_files/{problem}.{ext}
    --verify   check archive/, cleaned/ and the compiled file
    --prune    delete archive/ once cleaned/ is checked and up to date

The steps run in that order, whichever are given. Only --prune deletes, and
only files whose every step is in cleaned/.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich import box
from rich.table import Table

from ....core import history
from ....core.readers.othd_reader import OTHDReader
from ....core.readers.oisd_reader import OISDReader

STEPS = ('update', 'clean', 'compile', 'verify', 'prune')
READERS = {'othd': OTHDReader, 'oisd': OISDReader}


def _fmt_tsid(tsid: int) -> str:
    return f"{tsid:,}"


def _interval(ts_ids) -> int:
    """The usual step between output tsIds (1 when every step is written)."""
    diffs = [b - a for a, b in zip(ts_ids, ts_ids[1:]) if b > a]
    return max(set(diffs), key=diffs.count) if diffs else 1


def _runs(ts_ids, interval: int) -> List[Tuple[int, int]]:
    """Sorted tsIds as (first, last) runs, each one interval apart."""
    runs = []
    for t in ts_ids:
        if runs and t - runs[-1][1] == interval:
            runs[-1][1] = t
        else:
            runs.append([t, t])
    return [tuple(r) for r in runs]


def _fmt_runs(runs, limit: int = 5) -> str:
    shown = [_fmt_tsid(a) if a == b else f"{_fmt_tsid(a)} – {_fmt_tsid(b)}"
             for a, b in runs[:limit]]
    return ", ".join(shown) + (", …" if len(runs) > limit else "")


def _missing(gaps, interval: int) -> int:
    return sum((b - a) // interval + 1 for a, b in gaps)


def _range(ts_ids) -> str:
    return f"{_fmt_tsid(min(ts_ids))} – {_fmt_tsid(max(ts_ids))}" if ts_ids else "—"


def scan_blocks(path: Path) -> Tuple[bytes, List[Tuple[int, int, int]]]:
    """
    Split an OTHD/OISD file into its header (everything before the first
    `tsId` line) and its timestep blocks, each (tsId, start offset, end
    offset) — a block runs from its `tsId` line to the next one.
    """
    header = b''
    blocks = []
    offset = 0
    current = None  # (tsId, start)
    with open(path, 'rb') as f:
        for line in f:
            if line.startswith(b'tsId '):
                if current is not None:
                    blocks.append((current[0], current[1], offset))
                try:
                    ts_id = int(line.split()[1])
                except (IndexError, ValueError):
                    ts_id = None
                current = (ts_id, offset)
            elif current is None:
                header += line
            offset += len(line)
    if current is not None:
        blocks.append((current[0], current[1], offset))
    return header, blocks


def check_file(path: Path) -> dict:
    """
    Read one OTHD/OISD file through to the end. Every timestep block has the
    same shape — the same keyword lines with the same value counts — so a
    block that differs, a value that is not a number or a missing final
    newline is a problem. A problem confined to the last block is a job
    killed mid-write (`cut`, as is a file with no step at all); --clean
    leaves that block out. Restarts inside
    the file (tsId going back) are counted, but are fine.

    Returns blocks, ts_ids (in file order), restarts, cut (texts about the
    last block) and problems (the rest).
    """
    shapes = []      # (tsId, shape) per block
    shape = None
    bad_values = []  # block indices with a non-numeric value
    ts_id = None
    last_line = b''
    with open(path, 'rb') as f:
        for line in f:
            last_line = line
            tokens = line.split()
            if tokens and tokens[0] == b'tsId':
                if shape is not None:
                    shapes.append((ts_id, tuple(shape)))
                try:
                    ts_id = int(tokens[1])
                except (IndexError, ValueError):
                    ts_id = None
                shape = []
                continue
            if shape is None:
                continue  # header
            if tokens and tokens[0][:1].isalpha():
                shape.append((tokens[0], len(tokens)))
                numbers = tokens[1:]
            else:
                shape.append(len(tokens))
                numbers = tokens
            try:
                for value in numbers:
                    float(value)
            except ValueError:
                if not bad_values or bad_values[-1] != len(shapes):
                    bad_values.append(len(shapes))
    if shape is not None:
        shapes.append((ts_id, tuple(shape)))

    result = {'blocks': len(shapes), 'ts_ids': [t for t, _ in shapes if t is not None],
              'restarts': 0, 'cut': [], 'problems': []}
    if not shapes:
        result['cut'].append("no timesteps")
        return result
    last = len(shapes) - 1
    cut, problems = result['cut'], result['problems']
    if not last_line.endswith(b'\n'):
        cut.append("no newline at end (cut off mid-line)")
    if any(t is None for t, _ in shapes):
        problems.append("unreadable tsId line")

    usual = max(set(s for _, s in shapes), key=[s for _, s in shapes].count)
    odd = [i for i, (_, s) in enumerate(shapes) if s != usual]
    if odd == [last] and last > 0:
        cut.append(f"incomplete last step (tsId {shapes[last][0]})")
    elif odd:
        listed = ", ".join(str(shapes[i][0]) for i in odd[:5]) + (", …" if len(odd) > 5 else "")
        problems.append(f"{len(odd)} step(s) with an unusual layout (tsId {listed})")
    if bad_values == [last]:
        cut.append(f"non-numeric values in the last step (tsId {shapes[last][0]})")
    elif bad_values:
        listed = ", ".join(str(shapes[i][0]) for i in bad_values[:5]) + (", …" if len(bad_values) > 5 else "")
        problems.append(f"non-numeric values (tsId {listed})")

    ts_ids = result['ts_ids']
    result['restarts'] = sum(1 for a, b in zip(ts_ids, ts_ids[1:]) if b <= a)
    return result


class HistoryMixin:
    """The `history` subcommand of CaseOrganizer."""

    # --- the steps, in order ---------------------------------------------------

    def _organize_history(self, t1: Optional[float], t2: Optional[float]):
        steps = [step for step in STEPS if getattr(self.args, step, False)]
        if not steps:
            self.console.print(
                "[yellow]Nothing to do — pass --update, --clean, --compile, "
                "--verify and/or --prune[/yellow]"
            )
            return
        if not self.case.problem_name:
            self.console.print("[red]'problem' is not set in simflow.config — "
                               "cannot name the history files[/red]")
            return

        self._migrate_flat()

        if 'update' in steps:
            self.console.print("[bold]Step: Update archive/ from the run directory[/bold]")
            self._update_history(t1, t2)
            self.console.print()

        # Everything after --update works on the whole history, ignoring
        # --t1/--t2: which steps a run keeps depends on every later run, and a
        # t1/t2 context left over from something else would silently cut the
        # cleaned and compiled files short.
        if 'clean' in steps:
            self.console.print("[bold]Step: Clean archive/ → cleaned/[/bold]")
            if not self._clean_history():
                self._show_final_summary('history', steps)
                return
            self.console.print()

        if 'compile' in steps:
            self.console.print("[bold]Step: Compile cleaned/[/bold]")
            self._compile_history()
            self.console.print()

        if 'verify' in steps:
            self.console.print("[bold]Step: Verify[/bold]")
            if not self._verify_history() and 'prune' in steps:
                self.console.print("[red]Stopping: fix the files above before --prune[/red]")
                self._show_final_summary('history', steps)
                return
            self.console.print()

        if 'prune' in steps:
            self.console.print("[bold]Step: Prune archive/[/bold]")
            self._prune_history()
            self.console.print()

        self._show_final_summary('history', steps)

    def _types(self):
        """(ext, label) for OTHD and OISD."""
        return [(ext, ext.upper()) for ext in history.TYPES]

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(self.case_dir))

    # --- the old flat layout ---------------------------------------------------

    def _migrate_flat(self):
        """
        Move parts still in the old layout ({ext}_files/{problem}N.{ext}) into
        archive/. A number already taken there or in cleaned/ — a job script
        from before this layout keeps writing flat parts — moves to the next
        free one. OTHD and OISD parts of one run move together, to one number.
        """
        problem = self.case.problem_name
        flat = {ext: history.flat(self.case_dir, ext, problem) for ext, _ in self._types()}
        numbers = sorted(set().union(*flat.values()))
        if not numbers:
            return
        taken = set()
        for ext, _ in self._types():
            taken |= set(history.archived(self.case_dir, ext, problem))
            taken |= set(history.cleaned(self.case_dir, ext, problem))
        dry_run = getattr(self.args, 'dry_run', False)

        self.console.print("[bold]Moving parts from the old layout into archive/[/bold]")
        for n in numbers:
            new = n if n not in taken else max(taken | set(numbers)) + 1
            taken.add(new)
            for ext, _ in self._types():
                old = flat[ext].get(n)
                if old is None:
                    continue
                dest = history.archive_dir(self.case_dir, ext) / f'{problem}{new}.{ext}'
                self.console.print(f"  [green]↳[/green] {self._rel(old)} → {self._rel(dest)}"
                                   + (" [dim](dry run)[/dim]" if dry_run else ""))
                if not dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(old, dest)
                    self.stats['migrated'] += 1
        for ext, _ in self._types():
            old = history.type_dir(self.case_dir, ext) / 'compiled' / f'{problem}.{ext}'
            if old.exists():
                self.console.print(f"  [dim]{self._rel(old)} is no longer read — "
                                   f"delete it when you like[/dim]")
        self.console.print()

    # --- --update ----------------------------------------------------------------

    def _update_history(self, t1: Optional[float], t2: Optional[float]):
        """
        Move the run directory's .othd/.oisd into archive/ as {problem}N, N
        one past every run kept, and its .rcv into rcv_files/ under the same
        N. With --t1/--t2, only files whose steps overlap that window move.
        """
        run_dir = self._get_run_dir_path()
        if not run_dir:
            self.console.print("[yellow]  No run directory found in simflow.config[/yellow]")
            return
        problem = self.case.problem_name
        found = {ext: sorted(run_dir.glob(f'*.{ext}')) for ext in ('othd', 'oisd', 'rcv')}
        if t1 is not None or t2 is not None:
            for ext, reader in READERS.items():
                found[ext] = self._filter_by_range(found[ext], reader, t1, t2)
        if not any(found.values()):
            self.console.print("[dim]  No .othd/.oisd/.rcv files in the run directory[/dim]")
            return

        dry_run = getattr(self.args, 'dry_run', False)
        n = max(history.next_number(self.case_dir, ext, problem) for ext in history.TYPES)
        rcv_dir = self.case_dir / 'rcv_files'
        while (rcv_dir / f'{problem}{n}.rcv').exists():
            n += 1
        # one job writes one of each; more than one moves in name order, each to its own N
        for i in range(max(len(files) for files in found.values())):
            for ext, files in found.items():
                if i >= len(files):
                    continue
                dest_dir = rcv_dir if ext == 'rcv' else history.archive_dir(self.case_dir, ext)
                dest = dest_dir / f'{problem}{n + i}.{ext}'
                if dry_run:
                    self.console.print(f"  [cyan]↳[/cyan] {files[i].name} → {self._rel(dest)} [dim](dry run)[/dim]")
                    continue
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(files[i]), str(dest))
                self.console.print(f"  [green]↳[/green] {files[i].name} → {self._rel(dest)}")
                self.stats[f'archived_{ext}'] += 1

    # --- the plan: which steps of which run survive ------------------------------

    def _plan(self, ext: str, label: str, quiet: bool = False) -> Optional[dict]:
        """
        Read every run (archive/, or cleaned/ once pruned) in run order. A
        tsId at or below one already taken is a restart: everything from that
        tsId on is dropped for the later run's data — the "later run wins"
        rule the readers apply, which also covers a restart inside one file.
        A last step cut off by a killed job is left out. All runs must share
        one header (`mask`/`nOths` or `nOsfs`).

        Returns None (and says why, unless quiet) when that cannot be done.
        """
        def say(text):
            if not quiet:
                self.console.print(text)

        problem = self.case.problem_name
        scanned = []
        for n, path in history.runs(self.case_dir, ext, problem).items():
            check = check_file(path)
            if check['problems']:
                say(f"  [red]✗[/red]  {label}: {self._rel(path)}: {'; '.join(check['problems'])} — "
                    f"fix or remove it first")
                return None
            header, blocks = scan_blocks(path)
            dropped = None
            if check['cut'] and blocks:
                dropped = blocks.pop()
            scanned.append((n, path, header, blocks, dropped))
        if not scanned:
            return {'header': b'', 'merged': [], 'runs': {}, 'superseded': 0, 'restarts': [],
                    'dropped': []}
        if len({header for _, _, header, blocks, _ in scanned if blocks}) > 1:
            say(f"  [red]✗[/red]  {label} runs have different headers "
                f"(different probe/surface sets) — cannot join them")
            return None

        merged: List[Tuple[int, int, Path, int, int]] = []   # (tsId, run, file, start, end)
        superseded = 0
        # Where a run took over from the one before: the first block of every
        # run but the first, and any block at or below the last one taken.
        restarts = []
        for k, (n, path, _, blocks, _) in enumerate(scanned):
            for i, (ts_id, start, end) in enumerate(blocks):
                before = merged[-1] if merged else None
                replaced = 0
                while merged and merged[-1][0] >= ts_id:
                    merged.pop()
                    replaced += 1
                superseded += replaced
                if before and (replaced or (i == 0 and k > 0)):
                    restarts.append({'after': ts_id - 1, 'first': ts_id, 'reached': before[0],
                                     'replaced': replaced, 'part': path, 'previous': before[2],
                                     'start': start})
                merged.append((ts_id, n, path, start, end))

        header = next((header for _, _, header, blocks, _ in scanned if blocks), b'')
        return {
            'header': header,
            'merged': merged,
            'runs': {n: path for n, path, *_ in scanned},
            'superseded': superseded,
            'restarts': restarts,
            'dropped': [(path, d[0]) for _, path, _, _, d in scanned if d],
        }

    @staticmethod
    def _chunks(header: bytes, blocks):
        """A file's bytes, header first: `blocks` are (file, start, end)."""
        yield header
        handles = {}
        try:
            for path, start, end in blocks:
                src = handles.get(path)
                if src is None:
                    src = handles[path] = open(path, 'rb')
                src.seek(start)
                yield src.read(end - start)
        finally:
            for src in handles.values():
                src.close()

    @staticmethod
    def _same(path: Path, chunks) -> bool:
        """Whether `path` holds exactly the bytes of `chunks`."""
        if not path.is_file():
            return False
        with open(path, 'rb') as f:
            for chunk in chunks:
                if f.read(len(chunk)) != chunk:
                    return False
            return f.read(1) == b''

    @staticmethod
    def _write(path: Path, chunks):
        """Through a temporary file, so an interrupted write leaves the old file whole."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.__tmp__')
        with open(tmp, 'wb') as out:
            for chunk in chunks:
                out.write(chunk)
        os.replace(tmp, path)

    def _cleaned_blocks(self, plan: dict) -> Dict[int, list]:
        """{run: [(file, start, end)]}: the blocks each cleaned file should hold."""
        kept = {n: [] for n in plan['runs']}
        for _, n, path, start, end in plan['merged']:
            kept[n].append((path, start, end))
        return kept

    def _stale_cleaned(self, ext: str, plan: dict) -> List[int]:
        """Runs whose cleaned file is not what --clean would write now."""
        problem = self.case.problem_name
        present = history.cleaned(self.case_dir, ext, problem)
        stale = []
        for n, blocks in self._cleaned_blocks(plan).items():
            path = history.cleaned_dir(self.case_dir, ext) / f'{problem}{n}.{ext}'
            if blocks:
                if not self._same(path, self._chunks(plan['header'], blocks)):
                    stale.append(n)
            elif n in present:
                stale.append(n)
        stale += [n for n in present if n not in plan['runs']]
        return sorted(set(stale))

    # --- --clean -----------------------------------------------------------------

    def _clean_history(self) -> bool:
        """
        Write cleaned/{problem}N for every run: its steps that no later run
        redid, without a cut-off last step. A run with nothing left has no
        cleaned file. Once archive/ is pruned the cleaned file is the run's
        only copy: cutting it shorter (a new run restarted inside it) asks
        first, unless --no-confirm. Returns False if nothing could be done.
        """
        problem = self.case.problem_name
        dry_run = getattr(self.args, 'dry_run', False)
        written = False
        for ext, label in self._types():
            plan = self._plan(ext, label)
            if plan is None:
                return False
            if not plan['runs']:
                self.console.print(f"  [dim]{label}: no runs in archive/ or cleaned/[/dim]")
                continue
            for path, ts in plan['dropped']:
                self.console.print(f"  [yellow]⚠[/yellow]  {label}: {self._rel(path)}: last step "
                                   f"(tsId {ts}) cut off — left out")
            if not dry_run and not written:
                self._record_restarts(plan)   # the same in OTHD and OISD: one record
                written = True

            archived = history.archived(self.case_dir, ext, problem)
            out_dir = history.cleaned_dir(self.case_dir, ext)
            changes = []   # (run, path, blocks or None to delete, only copy)
            for n, blocks in self._cleaned_blocks(plan).items():
                path = out_dir / f'{problem}{n}.{ext}'
                if blocks and self._same(path, self._chunks(plan['header'], blocks)):
                    continue
                if not blocks and not path.exists():
                    continue
                changes.append((n, path, blocks, n not in archived and path.exists()))

            merged = plan['merged']
            notes = [f"{len(plan['runs'])} run(s)", f"tsId {_range([m[0] for m in merged])}",
                     f"{len(merged):,} steps"]
            if plan['superseded']:
                notes.append(f"{plan['superseded']:,} redone by later runs")
            self.console.print(f"  {label}: {', '.join(notes)}")
            if not changes:
                self.console.print(f"    [dim]cleaned/ is up to date[/dim]")
                continue
            for n, path, blocks, only in changes:
                kept = [m[0] for m in merged if m[1] == n]
                text = (f"{len(kept):,} steps, tsId {_range(kept)}" if blocks
                        else "nothing left — every step redone later: removed")
                warn = " [yellow](only copy: archive/ pruned)[/yellow]" if only else ""
                self.console.print(f"    {self._rel(path)}: {text}{warn}"
                                   + (" [dim](dry run)[/dim]" if dry_run else ""))
            if dry_run:
                continue
            only = [c for c in changes if c[3]]
            if only and not self.args.no_confirm:
                self.console.print(
                    f"[bold yellow]{len(only)} cleaned file(s) above are the only copy of their run "
                    f"and lose steps a later run redid. Go on?[/bold yellow] \\[y/N]: ", end="")
                if self._read_answer() not in ('y', 'yes'):
                    self.console.print("[dim]  Clean stopped[/dim]")
                    return False
            for n, path, blocks, _ in changes:
                if blocks:
                    self._write(path, self._chunks(plan['header'], blocks))
                else:
                    path.unlink()
                self.stats['cleaned'] += 1
        return True

    def _record_restarts(self, plan: dict):
        """Keep where the runs took over (.restarts): the cleaned and compiled
        files are one history, and once --prune deletes archive/ there is no
        telling how much each restart redid."""
        from ....core import restarts
        if not plan.get('restarts') and not restarts.path_for(self.case_dir).exists():
            return
        try:
            rows = restarts.record(self.case_dir, plan.get('restarts', []))
        except OSError as e:
            self.console.print(f"  [yellow]⚠[/yellow]  could not write {restarts.FILENAME}: {e}")
            return
        if rows:
            shown = ', '.join(f"{r['after']}" + (f" ({r['replaced']} replaced)"
                                                 if r['replaced'] not in ('0', '-') else '')
                              for r in rows)
            self.console.print(f"  Restarts after {shown} [dim]→ {restarts.FILENAME}[/dim]")

    # --- --compile -----------------------------------------------------------------

    def _compiled_plan(self, ext: str) -> Tuple[Optional[bytes], list, List[str]]:
        """(header, blocks, problems) of the compiled file: cleaned/ joined in run
        order. The cleaned files must follow on from each other."""
        problem = self.case.problem_name
        header, blocks, problems = None, [], []
        last = None
        for n, path in history.cleaned(self.case_dir, ext, problem).items():
            head, file_blocks = scan_blocks(path)
            if not file_blocks:
                continue
            if header is None:
                header = head
            elif head != header:
                problems.append(f"{path.name} has a different header")
            ts = [b[0] for b in file_blocks]
            if any(b <= a for a, b in zip(ts, ts[1:])) or (last is not None and ts[0] <= last):
                problems.append(f"{path.name} overlaps the runs before it")
            last = ts[-1]
            blocks += [(path, start, end) for _, start, end in file_blocks]
        return header, blocks, problems

    def _compile_history(self):
        """
        Join cleaned/ into {ext}_files/{problem}.{ext}. Only from a cleaned/
        that is up to date with archive/ (--clean first). A compiled file
        already holding exactly that is left, its time brought up to now so
        the readers keep taking it.
        """
        problem = self.case.problem_name
        dry_run = getattr(self.args, 'dry_run', False)
        for ext, label in self._types():
            out = history.compiled_path(self.case_dir, ext, problem)
            plan = self._plan(ext, label, quiet=True)
            if plan is None or self._stale_cleaned(ext, plan):
                self.console.print(f"  [yellow]⚠[/yellow]  {label}: cleaned/ is out of date with "
                                   f"archive/ — run --clean first; not compiled")
                continue
            header, blocks, problems = self._compiled_plan(ext)
            if problems:
                self.console.print(f"  [red]✗[/red]  {label}: {'; '.join(problems)} — run --clean")
                continue
            if not blocks:
                self.console.print(f"  [dim]{label}: nothing in cleaned/ — skipped[/dim]")
                continue
            steps = len(blocks)
            if self._same(out, self._chunks(header, blocks)):
                self.console.print(f"  {label}: {self._rel(out)} is up to date "
                                   f"[dim]({steps:,} steps)[/dim]")
                if not dry_run:
                    os.utime(out)
                continue
            self.console.print(f"  {label}: {len(history.cleaned(self.case_dir, ext, problem))} "
                               f"cleaned file(s) → {self._rel(out)}  [dim]{steps:,} steps[/dim]"
                               + (" [dim](dry run)[/dim]" if dry_run else ""))
            if dry_run:
                continue
            self._write(out, self._chunks(header, blocks))
            self.stats['compiled'].append(f"{self._rel(out)} ({steps:,} steps, "
                                          f"{self._format_size(out.stat().st_size)})")

    # --- --verify ------------------------------------------------------------------

    def _verify_history(self) -> bool:
        """
        Check every file of the history:
          archive/   reads through (a cut-off last step is only noted:
                     --clean leaves it out)
          cleaned/   reads through, follows on from the runs before it, and is
                     what --clean would write now
          compiled   reads through and is cleaned/ joined (--compile)
        tsIds in no run at all — a run restarted from later than the one
        before got to — are lost data, not a bad file: reported, not failed.
        Returns False if anything else is wrong.
        """
        table = Table(title="History check", box=box.ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("Steps", justify="right")
        table.add_column("tsId range", justify="right")
        table.add_column("Status")

        problem = self.case.problem_name
        all_ok = True
        any_file = False
        lost = []

        def row(path, check, problems, notes=()):
            nonlocal all_ok, any_file
            any_file = True
            if problems:
                all_ok = False
                status = "[red]" + "; ".join(problems) + "[/red]"
            else:
                status = "[green]ok[/green]"
            if notes:
                status += " [yellow]" + "; ".join(notes) + "[/yellow]"
            if check['restarts']:
                status += f" [dim]({check['restarts']} restart(s) inside)[/dim]"
            table.add_row(self._rel(path), f"{check['blocks']:,}", _range(check['ts_ids']), status)

        for ext, label in self._types():
            for path in history.archived(self.case_dir, ext, problem).values():
                check = check_file(path)
                row(path, check, check['problems'],
                    [c + " — --clean leaves it out" for c in check['cut']])

            plan = self._plan(ext, label, quiet=True)
            stale = set(self._stale_cleaned(ext, plan)) if plan else set()
            _, _, joined = self._compiled_plan(ext)
            for n, path in history.cleaned(self.case_dir, ext, problem).items():
                check = check_file(path)
                problems = check['problems'] + check['cut']
                problems += [p for p in joined if p.startswith(path.name)]
                if n in stale:
                    problems.append("out of date with archive/ — run --clean")
                row(path, check, problems)
            if plan is not None:
                missing = [n for n in stale if n not in history.cleaned(self.case_dir, ext, problem)]
                for n in missing:
                    any_file = True
                    all_ok = False
                    table.add_row(f"{ext}_files/cleaned/{problem}{n}.{ext}", "—", "—",
                                  "[red]missing — run --clean[/red]")
                ts = [m[0] for m in plan['merged']]
                interval = _interval(ts)
                gaps = [(a + interval, b - interval) for a, b in zip(ts, ts[1:]) if b - a > interval]
                if gaps:
                    lost.append((label, gaps, interval))

            out = history.compiled_path(self.case_dir, ext, problem)
            if out.exists():
                check = check_file(out)
                problems = check['problems'] + check['cut']
                header, blocks, joined = self._compiled_plan(ext)
                if not joined and not self._same(out, self._chunks(header or b'', blocks)):
                    problems.append("not cleaned/ joined — run --compile")
                row(out, check, problems)

        if not any_file:
            self.console.print("  [dim]No OTHD/OISD history[/dim]")
            return True

        self.console.print(table)
        for label, gaps, interval in lost:
            n = _missing(gaps, interval)
            self.stats['verify_lost'] += n
            self.console.print(
                f"  [yellow]⚠[/yellow]  {label}: {n:,} tsId(s) in no run "
                f"({_fmt_runs(gaps)}) — lost: a run restarted later than the one before reached"
            )
        self.stats['verify_ok'] = all_ok
        return all_ok

    # --- --prune -------------------------------------------------------------------

    def _prune_history(self):
        """
        Delete archive/ for each type whose cleaned/ reads through and is
        what --clean would write now: every step the archive holds that
        counts is then in cleaned/. Asks first unless --no-confirm; --dry-run
        only lists. rcv_files/ is not touched.
        """
        problem = self.case.problem_name
        dry_run = getattr(self.args, 'dry_run', False)
        to_delete = []
        for ext, label in self._types():
            parts = list(history.archived(self.case_dir, ext, problem).values())
            if not parts:
                self.console.print(f"  [dim]{label}: archive/ is empty — nothing to prune[/dim]")
                continue
            plan = self._plan(ext, label, quiet=True)
            if plan is None or self._stale_cleaned(ext, plan):
                self.console.print(f"  [yellow]⚠[/yellow]  {label}: cleaned/ is out of date with "
                                   f"archive/ — run --clean first; nothing pruned")
                continue
            bad = [p.name for p in history.cleaned(self.case_dir, ext, problem).values()
                   if check_file(p)['problems'] or check_file(p)['cut']]
            _, _, joined = self._compiled_plan(ext)
            if bad or joined:
                self.console.print(f"  [red]✗[/red]  {label}: cleaned/ does not check out "
                                   f"({', '.join(bad + joined)}) — nothing pruned")
                continue
            size = sum(p.stat().st_size for p in parts)
            self.console.print(f"  {label}: cleaned/ is up to date — {len(parts)} archived "
                               f"file(s), {self._format_size(size)} can go")
            for part in parts:
                self.console.print(f"    {self._rel(part)}")
            to_delete += parts

        if not to_delete:
            return
        if dry_run:
            self.console.print(f"  [bold cyan]Dry run:[/bold cyan] {len(to_delete)} file(s) would be deleted")
            return
        if not self.args.no_confirm:
            self.console.print(f"[bold yellow]Delete {len(to_delete)} archived file(s)? "
                               f"cleaned/ keeps their steps.[/bold yellow] \\[y/N]: ", end="")
            if self._read_answer() not in ('y', 'yes'):
                self.console.print("[dim]  Prune skipped[/dim]")
                return
        for part in to_delete:
            self.stats['pruned'] += 1
            self.stats['pruned_space_freed'] += part.stat().st_size
        self.files_to_delete = to_delete
        self.files_to_rename = []
        self._perform_deletions()
        # emptying archive/ changes its time, not the history: a compiled file
        # that is cleaned/ joined stays the one the readers take
        for ext, _ in self._types():
            out = history.compiled_path(self.case_dir, ext, problem)
            header, blocks, joined = self._compiled_plan(ext)
            if out.exists() and not joined and self._same(out, self._chunks(header or b'', blocks)):
                os.utime(out)

    @staticmethod
    def _read_answer() -> Optional[str]:
        """A line from the user, lower-cased; None at end of input."""
        try:
            return input().strip().lower()
        except EOFError:
            return None

    def _history_summary(self, steps) -> List[str]:
        lines = []
        if self.stats['migrated']:
            lines.append(f"Moved from the old layout: {self.stats['migrated']} file(s) → archive/")
        if 'update' in steps:
            lines.append(f"Archived: {self.stats['archived_othd']} OTHD, "
                         f"{self.stats['archived_oisd']} OISD, {self.stats['archived_rcv']} RCV")
        if 'clean' in steps:
            lines.append(f"Cleaned: {self.stats['cleaned']} file(s) written or removed")
        if 'compile' in steps:
            lines.append("Compiled: " + ("; ".join(self.stats['compiled']) or "nothing written"))
        if 'verify' in steps:
            lines.append(("Verified: all files ok" if self.stats['verify_ok']
                          else "Verified: [red]problems found[/red]")
                         + (f"  [yellow]({self.stats['verify_lost']:,} tsId(s) lost)[/yellow]"
                            if self.stats['verify_lost'] else ""))
        if 'prune' in steps:
            lines.append(f"Pruned: {self.stats['pruned']} archived file(s) removed  "
                         f"({self._format_size(self.stats['pruned_space_freed'])} freed)")
        return lines
