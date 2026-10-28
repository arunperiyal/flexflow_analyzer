"""
Case organization logic

Handles cleaning and organizing case directories.
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set

from ....core.readers.othd_reader import OTHDReader
from ....core.readers.oisd_reader import OISDReader
from rich.table import Table
from rich.panel import Panel
from rich import box


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


class FileInfo:
    """Information about a data file."""

    def __init__(self, path: Path, start_step: Optional[int], end_step: Optional[int],
                 size: int, mtime: float):
        # start/end are None for a part with no time steps (a run that stopped
        # before writing its first step): it holds no data, so --clean offers it
        self.path = path
        self.start_step = start_step
        self.end_step = end_step
        self.size = size
        self.mtime = mtime
        self.is_redundant = False
        self.redundant_reason = None

    @property
    def is_empty(self) -> bool:
        return self.start_step is None

    @property
    def range_text(self) -> str:
        return ("no time steps" if self.is_empty
                else f"{_fmt_tsid(self.start_step)} – {_fmt_tsid(self.end_step)}")

    def covers_range(self, start: int, end: int) -> bool:
        """Check if this file completely covers the given range."""
        return self.start_step <= start and self.end_step >= end

    def overlaps(self, other: 'FileInfo') -> bool:
        """Check if this file overlaps with another."""
        return not (self.end_step < other.start_step or self.start_step > other.end_step)

    def is_duplicate_of(self, other: 'FileInfo') -> bool:
        """Check if this file is a duplicate of another."""
        return self.start_step == other.start_step and self.end_step == other.end_step

    def is_subset_of(self, other: 'FileInfo') -> bool:
        """Check if this file is a subset of another."""
        return (other.start_step <= self.start_step and
                other.end_step >= self.end_step and
                not self.is_duplicate_of(other))


class CaseOrganizer:
    """Organizes and cleans up case directories."""

    def __init__(self, case, args, logger, console):
        """
        Initialize case organizer.

        Parameters:
        -----------
        case : FlexFlowCase
            Case to organize
        args : Namespace
            Command arguments
        logger : Logger
            Logger instance
        console : Console
            Rich console instance
        """
        self.case = case
        self.args = args
        self.logger = logger
        self.console = console
        self.case_dir = Path(case.case_directory)

        # Statistics
        self.stats = {
            'archived_othd': 0,
            'archived_oisd': 0,
            'archived_rcv': 0,
            'othd_total': 0,
            'othd_redundant': 0,
            'othd_space_freed': 0,
            'oisd_total': 0,
            'oisd_redundant': 0,
            'oisd_space_freed': 0,
            'out_deleted': 0,
            'rst_deleted': 0,
            'plt_deleted': 0,
            'output_space_freed': 0,
            'plt_clean_deleted': 0,
            'plt_clean_space_freed': 0,
            'plt_binary_deleted': 0,
            'plt_binary_space_freed': 0,
            'vtu_deleted': 0,
            'vtu_space_freed': 0,
            'compiled': [],  # one line per compiled file, for the final summary
            'verify_ok': True,
            'verify_lost': 0,
            'pruned': 0,
            'pruned_space_freed': 0,
            'pruned_moved': [],  # compiled files that became {problem}1.{ext}
        }

        # Files to delete/rename
        self.files_to_delete: List[Path] = []
        self.files_to_rename: List[Tuple[Path, Path]] = []  # (old, new)

        # Log file
        self.log_file = None
        if args.log:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = self.case_dir / f'organise_log_{timestamp}.txt'

    def _get_run_dir_path(self) -> Optional[Path]:
        """Resolve the run directory path from simflow.config."""
        if 'dir' not in self.case.config:
            return None
        output_dir_str = self.case.config['dir']
        if not os.path.isabs(output_dir_str):
            output_dir_path = self.case_dir / output_dir_str
        else:
            output_dir_path = Path(output_dir_str)
        return output_dir_path if output_dir_path.exists() else None

    def _t1_t2(self) -> Tuple[Optional[float], Optional[float]]:
        """Read --t1/--t2 from args."""
        return getattr(self.args, 't1', None), getattr(self.args, 't2', None)

    @staticmethod
    def _step_in_bounds(step: float, t1: Optional[float], t2: Optional[float]) -> bool:
        """Whether a single timestep falls inside the [t1, t2] window (either bound optional)."""
        if t1 is not None and step < t1:
            return False
        if t2 is not None and step > t2:
            return False
        return True

    @staticmethod
    def _range_overlaps_bounds(start: float, end: float, t1: Optional[float],
                               t2: Optional[float]) -> bool:
        """Whether a file's [start, end] timestep range overlaps the [t1, t2] window."""
        if t1 is not None and end < t1:
            return False
        if t2 is not None and start > t2:
            return False
        return True

    def _filter_by_range(self, files: List[Path], reader_class,
                         t1: Optional[float], t2: Optional[float]) -> List[Path]:
        """Keep only files whose timestep range (from their reader) overlaps [t1, t2].
        A file that fails to read is kept, so filtering never silently drops it."""
        kept = []
        for f in files:
            try:
                reader = reader_class(str(f), range_only=True)
                if len(reader.tsIds) == 0:
                    kept.append(f)
                    continue
                start, end = min(reader.tsIds), max(reader.tsIds)
            except Exception:
                kept.append(f)
                continue
            if self._range_overlaps_bounds(start, end, t1, t2):
                kept.append(f)
        return kept

    def _archive_run_data_files(self, t1: Optional[float] = None, t2: Optional[float] = None):
        """
        archive: Move .othd, .oisd (and .rcv if present) from the run
        directory into othd_files/, oisd_files/, rcv_files/.

        With --t1/--t2, only files whose timestep range overlaps that window
        are moved. RCV files have no reader to determine their range, so they
        are always moved in full. With --dry-run, only lists the moves.
        """
        run_dir = self._get_run_dir_path()
        if not run_dir:
            self.console.print("[yellow]  No run directory found in simflow.config[/yellow]")
            return

        self.logger.info(f"Archiving data files from: {run_dir}")

        othd_files_found = list(run_dir.glob('*.othd'))
        oisd_files_found = list(run_dir.glob('*.oisd'))
        rcv_files_found = list(run_dir.glob('*.rcv'))

        if t1 is not None or t2 is not None:
            othd_files_found = self._filter_by_range(othd_files_found, OTHDReader, t1, t2)
            oisd_files_found = self._filter_by_range(oisd_files_found, OISDReader, t1, t2)

        if not othd_files_found and not oisd_files_found and not rcv_files_found:
            self.console.print("[dim]  No .othd/.oisd/.rcv files found in run directory[/dim]")
            return

        dry_run = getattr(self.args, 'dry_run', False)
        moved_count = 0

        for files, dest_name, stat_key in [(othd_files_found, 'othd_files', 'archived_othd'),
                                           (oisd_files_found, 'oisd_files', 'archived_oisd'),
                                           (rcv_files_found, 'rcv_files', 'archived_rcv')]:
            if not files:
                continue
            dest_dir = self.case_dir / dest_name
            if not dry_run:
                dest_dir.mkdir(exist_ok=True)
            for file in sorted(files):
                dest_path = self._get_unique_filename(dest_dir, file.name)
                if dry_run:
                    self.console.print(f"  [cyan]↳[/cyan] {file.name} → {dest_name}/{dest_path.name} [dim](dry run)[/dim]")
                    continue
                shutil.move(str(file), str(dest_path))
                self.console.print(f"  [green]↳[/green] {file.name} → {dest_name}/{dest_path.name}")
                self.stats[stat_key] += 1
                moved_count += 1

        if dry_run:
            self.console.print("\n[bold cyan]Dry run:[/bold cyan] nothing moved")
        else:
            self.console.print(
                f"\n[green]✓[/green] Archived {moved_count} file(s) from run directory"
            )

    def _get_unique_filename(self, dest_dir: Path, filename: str) -> Path:
        """Get unique filename with number suffix if file exists."""
        # Parse filename: problem.othd or problem.oisd
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) != 2:
            return dest_dir / filename

        base_name, extension = name_parts

        # Remove any existing number suffix
        import re
        match = re.match(r'(.+?)(\d+)$', base_name)
        if match:
            base_name = match.group(1)

        # Find existing files with same base name
        existing_files = list(dest_dir.glob(f'{base_name}*.{extension}'))

        if not existing_files:
            # No conflicts, use name with 1
            return dest_dir / f'{base_name}1.{extension}'

        # Find highest number suffix
        max_num = 0
        for existing in existing_files:
            existing_base = existing.stem
            match = re.match(rf'{re.escape(base_name)}(\d+)$', existing_base)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

        # Use next available number
        next_num = max_num + 1
        return dest_dir / f'{base_name}{next_num}.{extension}'

    def organize(self, subcommand: str):
        """
        Main organization workflow for one subcommand.

        Parameters:
        -----------
        subcommand : str
            'archive', 'output' or 'plt'
        """
        t1, t2 = self._t1_t2()

        self.console.print()
        self.console.print(Panel(
            f"[bold cyan]Organizing Case:[/bold cyan] {self.case_dir.name}\n"
            f"[dim]Path: {self.case_dir}[/dim]",
            border_style="cyan",
            box=box.ROUNDED
        ))
        self.console.print()

        # --- ARCHIVE --- (its own flow: --clean confirms file by file)
        if subcommand == 'archive':
            self._organize_archive(t1, t2)
            return

        # --- OUTPUT ---
        if subcommand == 'output':
            self.console.print("[bold]Step: Clean output directory[/bold]")
            self._analyze_output_directory(t1, t2)
            self.console.print()

        # --- PLT ---
        elif subcommand == 'plt':
            delete_ascii = getattr(self.args, 'delete_ascii', False)
            delete_binary = getattr(self.args, 'delete_binary', False)
            if not delete_ascii and not delete_binary:
                self.console.print(
                    "[yellow]Nothing to do — pass --delete-ascii and/or "
                    "--delete-binary[/yellow]"
                )
                return
            if delete_ascii:
                self.console.print("[bold]Step: Delete ASCII PLT files from run directory[/bold]")
                self._analyze_clean_plt(t1, t2)
                self.console.print()
            if delete_binary:
                self.console.print("[bold]Step: Delete PLT files from binary/[/bold]")
                self._analyze_delete_binary_plt(t1, t2)
                self.console.print()

        # --- VTU ---
        elif subcommand == 'vtu':
            self.console.print("[bold]Step: .vtu caches in binary/[/bold]")
            self._analyze_vtu(t1, t2)
            self.console.print()
            if not getattr(self.args, 'clean', False):
                if self.files_to_delete:
                    self.console.print("[dim]Listed only: --clean deletes them[/dim]")
                self.files_to_delete = []
                return

        has_deletions = len(self.files_to_delete) > 0
        dry_run = getattr(self.args, 'dry_run', False)

        # Show summary before asking confirmation
        self._show_summary()

        if dry_run:
            self.console.print(
                f"[bold cyan]Dry run:[/bold cyan] {len(self.files_to_delete)} files "
                f"would be deleted. No changes made."
            )
            return

        if has_deletions and not self.args.no_confirm:
            if not self._confirm_deletion():
                self.console.print("[yellow]Operation cancelled[/yellow]")
                return

        if has_deletions:
            self._perform_deletions()

        # Final summary
        self._show_final_summary(subcommand)

    def _organize_archive(self, t1: Optional[float], t2: Optional[float]):
        """
        archive: run the requested steps in a fixed order —
        --update → --verify → --clean → --compile → --prune. Each flag is
        optional; with none of them there is nothing to do.
        """
        steps = [step for step in ('update', 'verify', 'clean', 'compile', 'prune')
                 if getattr(self.args, step, False)]

        if not steps:
            self.console.print(
                "[yellow]Nothing to do — pass --update, --verify, --clean, "
                "--compile and/or --prune[/yellow]"
            )
            return

        if 'update' in steps:
            self.console.print("[bold]Step: Update archive from run directory[/bold]")
            self._archive_run_data_files(t1, t2)
            self.console.print()

        # Everything after --update works on the complete archived set,
        # ignoring --t1/--t2: dedup compares every file against every other,
        # so excluding files by timestep would hide the very files (e.g. a
        # superset) that make another file redundant, and a t1/t2 context left
        # over from something else would silently truncate a compiled file.
        if 'verify' in steps:
            self.console.print("[bold]Step: Verify archive[/bold]")
            if not self._verify_archive():
                if any(step in steps for step in ('clean', 'compile', 'prune')):
                    self.console.print(
                        "[red]Stopping: fix or remove the files above before "
                        "--clean / --compile / --prune[/red]"
                    )
                self._show_final_summary('archive', steps)
                return
            self.console.print()

        if 'clean' in steps:
            self.console.print("[bold]Step: Clean archive (supervised)[/bold]")
            if not self._clean_archive():
                return
            self.console.print()

        if 'compile' in steps:
            self.console.print("[bold]Step: Compile archive[/bold]")
            self._compile_archive()
            self.console.print()

        if 'prune' in steps:
            self.console.print("[bold]Step: Prune compiled parts[/bold]")
            self._prune_archive()
            self.console.print()

        self._show_final_summary('archive', steps)

    def _analyze_data_files(self, file_type: str) -> List[FileInfo]:
        """
        Analyze OTHD or OISD files. Always reads the complete set — dedup
        compares every file against every other, so --t1/--t2 never filters
        this (see the note above the `archive --clean` call site).

        Parameters:
        -----------
        file_type : str
            'othd' or 'oisd'

        Returns:
        --------
        List[FileInfo]
            List of file information objects
        """
        # Find files
        files_dir = self.case_dir / f'{file_type}_files'
        if not files_dir.exists():
            self.logger.warning(f"No {file_type}_files directory found")
            return []

        file_pattern = f'*.{file_type}'
        data_files = list(files_dir.glob(file_pattern))

        if not data_files:
            self.logger.warning(f"No {file_type.upper()} files found")
            return []

        self.logger.info(f"Found {len(data_files)} {file_type.upper()} files")

        # Analyze each file
        file_infos = []
        reader_class = OTHDReader if file_type == 'othd' else OISDReader

        for file_path in data_files:
            try:
                # Read file to get time step range
                reader = reader_class(str(file_path), range_only=True)
                size = file_path.stat().st_size
                mtime = file_path.stat().st_mtime

                if len(reader.tsIds) == 0:
                    # No tsId line at all: the run stopped before its first
                    # step. Anything else read as nothing is not understood.
                    if self._mentions_tsid(file_path):
                        raise ValueError(f"No time steps could be read from {file_path.name}")
                    file_info = FileInfo(file_path, None, None, size, mtime)
                    file_info.is_redundant = True
                    file_info.redundant_reason = "holds no time steps"
                    file_infos.append(file_info)
                    continue

                start_step = min(reader.tsIds)
                end_step = max(reader.tsIds)

                file_info = FileInfo(file_path, start_step, end_step, size, mtime)
                file_infos.append(file_info)

                if self.args.verbose:
                    self.logger.info(f"  {file_path.name}: steps {start_step}-{end_step}, "
                                   f"size {self._format_size(size)}")

            except Exception as e:
                self.logger.error(f"Failed to read {file_path.name}: {e}")
                self.logger.error("Aborting operation to prevent data loss")
                import sys
                sys.exit(1)

        # Update stats
        if file_type == 'othd':
            self.stats['othd_total'] = len(file_infos)
        else:
            self.stats['oisd_total'] = len(file_infos)

        return file_infos

    @staticmethod
    def _mentions_tsid(path: Path) -> bool:
        """Whether the file has the text 'tsId' anywhere (read in chunks)."""
        tail = b''
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                if b'tsId' in tail + chunk:
                    return True
                tail = chunk[-3:]
        return False

    def _find_redundant_files(self, files: List[FileInfo], file_type: str):
        """
        Find redundant files (duplicates and subsets).

        Parameters:
        -----------
        files : List[FileInfo]
            List of file information objects
        file_type : str
            'OTHD' or 'OISD'
        """
        # Sort in place (the order --clean asks in): empty parts first, then by
        # start step, then by size (larger first), then by mtime (recent first)
        files.sort(key=lambda f: (not f.is_empty, f.start_step or 0, -f.size, -f.mtime))
        all_files = files
        files = [f for f in files if not f.is_empty]    # empty parts are already marked
        if not files:
            return

        for i, file in enumerate(files):
            if file.is_redundant:
                continue

            # Check against other files
            for j, other in enumerate(files):
                if i == j or other.is_redundant:
                    continue

                # Check if 'other' is redundant compared to 'file'
                if file.is_duplicate_of(other):
                    # Duplicate: keep larger file, or more recent if same size
                    if other.size > file.size:
                        file.is_redundant = True
                        file.redundant_reason = f"duplicate of {other.path.name} (smaller)"
                        break
                    elif other.size == file.size and other.mtime > file.mtime:
                        file.is_redundant = True
                        file.redundant_reason = f"duplicate of {other.path.name} (older)"
                        break
                    else:
                        other.is_redundant = True
                        other.redundant_reason = f"duplicate of {file.path.name}"

                elif other.is_subset_of(file):
                    # Other is subset of this file
                    other.is_redundant = True
                    other.redundant_reason = f"subset of {file.path.name}"

        # Report tsId gaps in the surviving (non-redundant) files
        survivors = sorted([f for f in files if not f.is_redundant], key=lambda f: f.start_step)
        for i in range(len(survivors) - 1):
            gap_start = survivors[i].end_step + 1
            gap_end   = survivors[i + 1].start_step - 1
            if gap_start <= gap_end:
                self.console.print(
                    f"  [yellow]⚠[/yellow]  {file_type} gap: "
                    f"tsId {_fmt_tsid(gap_start)} – {_fmt_tsid(gap_end)} not covered"
                )

        if self.args.verbose:
            for file in all_files:
                if file.is_redundant:
                    self.logger.info(f"  Redundant: {file.path.name} ({file.redundant_reason})")

    def _collect_redundant(self, files: List[FileInfo], file_type: str):
        """Queue the files still marked redundant (after supervision) for deletion."""
        prefix = file_type.lower()
        for file in files:
            if file.is_redundant:
                self.files_to_delete.append(file.path)
                self.stats[f'{prefix}_redundant'] += 1
                self.stats[f'{prefix}_space_freed'] += file.size

    def _clean_archive(self) -> bool:
        """
        archive --clean: deduplicate othd_files/ and oisd_files/ under manual
        supervision. Shows the full plan, then asks about every file marked
        redundant, one at a time; renumbering gets its own confirmation.
        --no-confirm accepts the whole plan unattended, --dry-run only shows it.

        Returns False if the user aborted (nothing deleted or renamed).
        """
        self.logger.info("Analyzing OTHD files...")
        othd_files = self._analyze_data_files('othd')
        self._find_redundant_files(othd_files, 'OTHD')

        self.logger.info("Analyzing OISD files...")
        oisd_files = self._analyze_data_files('oisd')
        self._find_redundant_files(oisd_files, 'OISD')

        # Warn if OTHD and OISD coverage diverges after deduplication
        self._check_cross_type_consistency(othd_files, oisd_files)

        self._show_clean_plan(othd_files, 'OTHD')
        self._show_clean_plan(oisd_files, 'OISD')

        candidates = [f for f in othd_files + oisd_files if f.is_redundant]
        dry_run = getattr(self.args, 'dry_run', False)

        if dry_run:
            self.console.print(
                f"[bold cyan]Dry run:[/bold cyan] {len(candidates)} file(s) would be "
                f"offered for deletion. No changes made."
            )
            return True

        if candidates and not self.args.no_confirm:
            if not self._supervise_deletions(candidates):
                self.console.print("[yellow]Clean aborted — nothing deleted or renamed[/yellow]")
                return False

        self._collect_redundant(othd_files, 'OTHD')
        self._collect_redundant(oisd_files, 'OISD')

        self._rename_files(othd_files, oisd_files)
        if self.files_to_rename and not self.args.no_confirm:
            self.console.print()
            self.console.print("[bold]Renumber the remaining files by starting tsId:[/bold]")
            for old_path, new_path in self.files_to_rename:
                self.console.print(f"  {old_path.parent.name}/{old_path.name} → {new_path.name}")
            self.console.print("[bold yellow]Apply renames?[/bold yellow] \\[y/N]: ", end="")
            if self._read_answer() not in ('y', 'yes'):
                self.console.print("[dim]  Renames skipped[/dim]")
                self.files_to_rename = []

        self._perform_deletions()
        return True

    def _show_clean_plan(self, files: List[FileInfo], file_type: str):
        """Table of every archived file: tsId range, size, and keep/delete with the reason."""
        if not files:
            return
        table = Table(title=f"{file_type} archive", box=box.ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("tsId range", justify="right")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Action")
        for f in sorted(files, key=lambda f: (not f.is_empty, f.start_step or 0, f.path.name)):
            action = (f"[red]delete[/red] [dim]({f.redundant_reason})[/dim]"
                      if f.is_redundant else "[green]keep[/green]")
            table.add_row(f.path.name, f.range_text,
                          self._format_size(f.size), action)
        self.console.print()
        self.console.print(table)

    def _supervise_deletions(self, candidates: List[FileInfo]) -> bool:
        """
        Ask about each redundant file in turn:
          y = delete, n = keep (it is renumbered with the survivors),
          a = delete this and every remaining one, q = abort the whole clean.
        A file the user keeps is unmarked, so it is neither deleted nor counted.

        Returns False on q (or end of input).
        """
        self.console.print()
        delete_rest = False
        for f in candidates:
            if delete_rest:
                continue
            self.console.print(
                f"[bold]{f.path.parent.name}/{f.path.name}[/bold] "
                f"[dim]tsId {f.range_text}, "
                f"{self._format_size(f.size)}, {f.redundant_reason}[/dim]"
            )
            while True:
                self.console.print("  Delete? \\[y/n/a/q]: ", end="")
                answer = self._read_answer()
                if answer in ('y', 'yes'):
                    break
                if answer in ('n', 'no'):
                    f.is_redundant = False
                    f.redundant_reason = None
                    break
                if answer == 'a':
                    delete_rest = True
                    break
                if answer in ('q', None):
                    return False
                self.console.print("  [dim]y = delete, n = keep, a = delete all remaining, "
                                   "q = abort[/dim]")
        return True

    @staticmethod
    def _read_answer() -> Optional[str]:
        """One line of user input, lowercased; None at end of input."""
        try:
            return input().strip().lower()
        except EOFError:
            return None

    def _archive_types(self):
        """(ext, archive dir, compiled file, parts) for OTHD and OISD."""
        problem = self.case.problem_name
        for ext in ('othd', 'oisd'):
            src_dir = self.case_dir / f'{ext}_files'
            parts = sorted(src_dir.glob(f'*.{ext}')) if src_dir.exists() else []
            yield ext, src_dir, src_dir / 'compiled' / f'{problem}.{ext}', parts

    def _compile_archive(self):
        """
        archive --compile: combine othd_files/*.othd into
        othd_files/compiled/{problem}.othd, and the same for OISD. The parts
        are kept. See _plan_compile for how restarts are resolved.
        """
        if not self.case.problem_name:
            self.console.print("  [yellow]⚠[/yellow]  'problem' not set — cannot name the compiled files")
            return

        recorded = False
        for ext, src_dir, out_path, parts in self._archive_types():
            if not parts:
                self.console.print(f"  [dim]No {ext.upper()} files in {ext}_files/ — skipped[/dim]")
                continue
            plan = self._plan_compile(parts, ext.upper())
            if plan is None:
                continue
            self._report_plan(plan, out_path, ext.upper())

            if getattr(self.args, 'dry_run', False):
                self.console.print("  [dim](dry run — not written)[/dim]")
                continue

            # The restarts are the same in OTHD and OISD: one record, from the first
            if not recorded:
                self._record_restarts(plan)
                recorded = True
            self._write_compiled(plan, out_path)
            self.stats['compiled'].append(
                f"{out_path.relative_to(self.case_dir)} ({len(plan['merged']):,} steps, "
                f"{self._format_size(out_path.stat().st_size)})"
            )

    @staticmethod
    def _scan_blocks(path: Path) -> Tuple[bytes, List[Tuple[int, int, int]]]:
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
                    current = (int(line.split()[1]), offset)
                elif current is None:
                    header += line
                offset += len(line)
        if current is not None:
            blocks.append((current[0], current[1], offset))
        return header, blocks

    def _plan_compile(self, parts: List[Path], file_type: str) -> Optional[dict]:
        """
        Work out which block of which part goes where in the compiled file.

        Only the parts are read: after a --prune the compiled file has become
        {problem}1.{ext}, an ordinary part, so the parts always hold the whole
        history. Parts are taken in order of their first tsId. A tsId at or
        below one already taken is a restart: everything from that tsId
        onwards is dropped and the restarted run's data is used instead — the
        same "later run wins" rule the readers apply. This also covers a
        restart appended inside a single file. All parts must share the same
        header (`mask`/`nOths` or `nOsfs`); otherwise there is no plan.
        """
        scanned = []
        for part in parts:
            header, blocks = self._scan_blocks(part)
            if not blocks:
                self.console.print(f"  [yellow]⚠[/yellow]  {part.name}: no timesteps — skipped")
                continue
            scanned.append((part, header, blocks))
        if not scanned:
            return None
        scanned.sort(key=lambda s: (s[2][0][0], s[0].stat().st_mtime))

        if len({header for _, header, _ in scanned}) > 1:
            self.console.print(
                f"  [red]✗[/red]  {file_type} files have different headers "
                f"(different probe/surface sets) — not compiled"
            )
            return None

        merged: List[Tuple[int, Path, int, int]] = []  # (tsId, file, start, end), tsId increasing
        superseded = 0
        # Where a run took over from the one before: the first block of every
        # part but the first (a part is one run), and any block at or below
        # the last one taken (a restart appended inside a file).
        restarts = []
        for n, (path, _, blocks) in enumerate(scanned):
            for i, (ts_id, start, end) in enumerate(blocks):
                before = merged[-1] if merged else None
                replaced = 0
                while merged and merged[-1][0] >= ts_id:
                    merged.pop()
                    replaced += 1
                superseded += replaced
                if before and (replaced or (i == 0 and n > 0)):
                    restarts.append({'after': ts_id - 1, 'first': ts_id, 'reached': before[0],
                                     'replaced': replaced, 'part': path, 'previous': before[1],
                                     'start': start})
                merged.append((ts_id, path, start, end))

        return {
            'header': scanned[0][1],
            'merged': merged,
            'parts': [path for path, _, _ in scanned],
            'superseded': superseded,
            'restarts': restarts,
        }

    def _record_restarts(self, plan: dict):
        """Keep where the runs took over (.restarts): the compiled file is one
        history, and once --prune deletes the parts there is no telling."""
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

    def _report_plan(self, plan: dict, out_path: Path, file_type: str):
        merged = plan['merged']
        notes = [f"tsId {_fmt_tsid(merged[0][0])} – {_fmt_tsid(merged[-1][0])}",
                 f"{len(merged):,} steps"]
        if plan['superseded']:
            notes.append(f"{plan['superseded']:,} replaced by restarts")
        self.console.print(
            f"  {file_type}: {len(plan['parts'])} part(s) → "
            f"{out_path.relative_to(self.case_dir)}  [dim]{', '.join(notes)}[/dim]"
        )
        self._warn_compile_gaps([ts for ts, _, _, _ in merged], file_type)

    @staticmethod
    def _plan_chunks(plan: dict):
        """The compiled file's bytes, header first, one block at a time."""
        yield plan['header']
        handles = {}
        try:
            for _, path, start, end in plan['merged']:
                src = handles.get(path)
                if src is None:
                    src = handles[path] = open(path, 'rb')
                src.seek(start)
                yield src.read(end - start)
        finally:
            for src in handles.values():
                src.close()

    def _write_compiled(self, plan: dict, out_path: Path):
        """Write through a temporary file, so an interrupted run leaves the old file intact."""
        out_path.parent.mkdir(exist_ok=True)
        tmp_path = out_path.with_name(out_path.name + '.__tmp__')
        with open(tmp_path, 'wb') as out:
            for chunk in self._plan_chunks(plan):
                out.write(chunk)
        os.replace(tmp_path, out_path)

    def _compiled_is_current(self, plan: dict, out_path: Path) -> bool:
        """Whether compiling again would write exactly the bytes already in out_path."""
        with open(out_path, 'rb') as f:
            for chunk in self._plan_chunks(plan):
                if f.read(len(chunk)) != chunk:
                    return False
            return f.read(1) == b''

    def _warn_compile_gaps(self, ts_ids: List[int], file_type: str):
        """Warn where the compiled tsIds jump by more than the usual output interval."""
        if len(ts_ids) < 2:
            return
        diffs = [b - a for a, b in zip(ts_ids, ts_ids[1:])]
        interval = max(set(diffs), key=diffs.count)
        for a, b in zip(ts_ids, ts_ids[1:]):
            if b - a > interval:
                self.console.print(
                    f"  [yellow]⚠[/yellow]  {file_type} gap: "
                    f"tsId {_fmt_tsid(a + interval)} – {_fmt_tsid(b - interval)} not covered"
                )

    def _prune_archive(self):
        """
        archive --prune: replace the parts with the compiled file. The parts
        are deleted and compiled/{problem}.{ext} becomes {problem}1.{ext}, so
        the archive is an ordinary one-part archive that every reader of
        {ext}_files/*.{ext} understands, and the next --update numbers from 2.

        Only when compiling again would reproduce the compiled file byte for
        byte — so every timestep the parts hold is already in it. The compiled
        file is first moved into {ext}_files/ under a temporary name, then the
        parts are deleted, then it takes the name {problem}1.{ext}: the full
        data is on disk at every step. A compiled file with no parts left
        (a prune from before this worked this way) is just moved into place.
        Asks before deleting unless --no-confirm; --dry-run only lists. RCV
        files are not touched.
        """
        problem = self.case.problem_name
        if not problem:
            self.console.print("  [yellow]⚠[/yellow]  'problem' not set — cannot find the compiled files")
            return

        dry_run = getattr(self.args, 'dry_run', False)
        to_prune = []  # (ext, src_dir, compiled, parts)
        for ext, src_dir, out_path, parts in self._archive_types():
            label = ext.upper()
            final = src_dir / f'{problem}1.{ext}'
            if not parts:
                if out_path.exists():
                    self.console.print(
                        f"  {label}: no parts left — {out_path.relative_to(self.case_dir)} "
                        f"→ {ext}_files/{final.name}"
                        + (" [dim](dry run)[/dim]" if dry_run else "")
                    )
                    if not dry_run:
                        os.replace(out_path, final)
                        self._remove_empty(out_path.parent)
                        self.stats['pruned_moved'].append(f"{ext}_files/{final.name}")
                else:
                    self.console.print(f"  [dim]{label}: no parts in {ext}_files/ — nothing to prune[/dim]")
                continue
            if not out_path.exists():
                self.console.print(
                    f"  [yellow]⚠[/yellow]  {label}: no {out_path.relative_to(self.case_dir)} — "
                    f"run with --compile first"
                )
                continue
            plan = self._plan_compile(parts, label)
            if plan is not None and not dry_run and ext == 'othd':
                # the parts are about to go, and with them the restarts
                self._record_restarts(plan)
            if plan is None or not self._compiled_is_current(plan, out_path):
                self.console.print(
                    f"  [yellow]⚠[/yellow]  {label}: {out_path.relative_to(self.case_dir)} is "
                    f"out of date with the parts — run with --compile first; nothing pruned"
                )
                continue
            size = sum(p.stat().st_size for p in parts)
            self.console.print(
                f"  {label}: compiled file is current — {len(parts)} part(s), "
                f"{self._format_size(size)} can go; "
                f"{out_path.relative_to(self.case_dir)} becomes {ext}_files/{final.name}"
            )
            for part in parts:
                self.console.print(f"    {ext}_files/{part.name}")
            to_prune.append((ext, src_dir, out_path, parts))

        if not to_prune:
            return
        n_parts = sum(len(parts) for *_, parts in to_prune)
        if dry_run:
            self.console.print(f"  [bold cyan]Dry run:[/bold cyan] {n_parts} part(s) would be deleted")
            return
        if not self.args.no_confirm:
            self.console.print(
                f"[bold yellow]Delete {n_parts} part(s) and keep the compiled file(s) "
                f"in their place?[/bold yellow] \\[y/N]: ", end=""
            )
            if self._read_answer() not in ('y', 'yes'):
                self.console.print("[dim]  Prune skipped[/dim]")
                return

        # 1. compiled file into {ext}_files/ under a name no glob matches
        staged = []
        for ext, src_dir, out_path, parts in to_prune:
            tmp = src_dir / f'{problem}.{ext}.__prune__'
            os.replace(out_path, tmp)
            self._remove_empty(out_path.parent)
            staged.append((ext, src_dir, tmp, src_dir / f'{problem}1.{ext}'))

        # 2. the parts
        self.files_to_delete = [p for *_, parts in to_prune for p in parts]
        self.files_to_rename = []
        for part in self.files_to_delete:
            self.stats['pruned'] += 1
            self.stats['pruned_space_freed'] += part.stat().st_size
        self._perform_deletions()

        # 3. the compiled file takes the first part's name
        for ext, src_dir, tmp, final in staged:
            if final.exists():
                self.console.print(
                    f"  [red]✗[/red]  {ext}_files/{final.name} still exists (could not be "
                    f"deleted) — the compiled data is kept as {ext}_files/{tmp.name}"
                )
                continue
            os.replace(tmp, final)
            self.stats['pruned_moved'].append(f"{ext}_files/{final.name}")

    @staticmethod
    def _remove_empty(directory: Path):
        """Remove `directory` if nothing is left in it."""
        try:
            directory.rmdir()
        except OSError:
            pass

    def _verify_archive(self) -> bool:
        """
        archive --verify: read every archived part and compiled file through
        to the end. In an OTHD/OISD file every timestep block has the same
        shape — the same keyword lines with the same value counts — so a block
        that differs (typically the last one, from a job killed mid-write), a
        value that is not a number, or a missing final newline is a problem.
        Restarts inside a file (tsId going back) are reported but are fine.

        The tsIds are checked too. A compiled file without a tsId some part
        has is a problem (out of date, or written badly: --compile again).
        A tsId in no file at all — a run restarted from later than the one
        before got to — is lost data rather than a bad file: it is reported,
        but does not fail the check, as no compile could bring it back (and
        after a --prune the gap sits inside {problem}1 for good).

        Returns False if any file has a problem.
        """
        table = Table(title="Archive check", box=box.ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("Steps", justify="right")
        table.add_column("tsId range", justify="right")
        table.add_column("Status")

        all_ok = True
        any_file = False
        lost = []        # (ext, gaps, interval): tsIds in no part
        for ext, src_dir, out_path, parts in self._archive_types():
            rows = [(path, self._check_file(path), []) for path in parts]
            covered = set().union(*(check[4] for _, check, _ in rows))
            interval = _interval(sorted(covered))
            runs = _runs(sorted(covered), interval)
            gaps = [(a[1] + interval, b[0] - interval) for a, b in zip(runs, runs[1:])]
            if gaps:
                lost.append((ext, gaps, interval))

            if out_path.exists():
                check = self._check_file(out_path)
                absent = sorted(covered - check[4])
                notes = [f"{len(absent):,} tsId(s) of the parts missing "
                         f"({_fmt_runs(_runs(absent, interval))}) — run --compile"] if absent else []
                rows.append((out_path, check, notes))

            for path, (n_blocks, ts_range, problems, restarts, _), notes in rows:
                any_file = True
                problems = problems + notes
                if problems:
                    all_ok = False
                    status = "[red]" + "; ".join(problems) + "[/red]"
                else:
                    status = "[green]ok[/green]"
                if restarts:
                    status += f" [dim]({restarts} restart(s) inside)[/dim]"
                table.add_row(str(path.relative_to(self.case_dir)), f"{n_blocks:,}",
                              f"{_fmt_tsid(ts_range[0])} – {_fmt_tsid(ts_range[1])}" if ts_range else "—",
                              status)

        if not any_file:
            self.console.print("  [dim]No OTHD/OISD files in the archive[/dim]")
            return True

        self.console.print(table)
        for ext, gaps, interval in lost:
            n = _missing(gaps, interval)
            self.stats['verify_lost'] += n
            self.console.print(
                f"  [yellow]⚠[/yellow]  {ext.upper()}: {n:,} tsId(s) in no file "
                f"({_fmt_runs(gaps)}) — lost: a run restarted later than the one before reached"
            )
        self.stats['verify_ok'] = all_ok
        return all_ok

    @staticmethod
    def _check_file(path: Path):
        """(blocks, (first, last) tsId, problems, restarts, tsIds) for one OTHD/OISD file."""
        shapes = []      # (tsId, shape) per block
        shape = None
        bad_values = []  # tsIds with a non-numeric value
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
                    if not bad_values or bad_values[-1] != ts_id:
                        bad_values.append(ts_id)
        if shape is not None:
            shapes.append((ts_id, tuple(shape)))

        problems = []
        if not shapes:
            return 0, None, ["no timesteps"], 0, set()
        if not last_line.endswith(b'\n'):
            problems.append("no newline at end (cut off mid-line)")
        if any(t is None for t, _ in shapes):
            problems.append("unreadable tsId line")

        usual = max(set(s for _, s in shapes), key=[s for _, s in shapes].count)
        odd = [t for t, s in shapes if s != usual]
        if odd == [shapes[-1][0]] and len(shapes) > 1:
            problems.append(f"incomplete last step (tsId {odd[0]})")
        elif odd:
            listed = ", ".join(str(t) for t in odd[:5]) + (", …" if len(odd) > 5 else "")
            problems.append(f"{len(odd)} step(s) with an unusual layout (tsId {listed})")
        if bad_values:
            listed = ", ".join(str(t) for t in bad_values[:5]) + (", …" if len(bad_values) > 5 else "")
            problems.append(f"non-numeric values (tsId {listed})")

        ts_ids = [t for t, _ in shapes if t is not None]
        restarts = sum(1 for a, b in zip(ts_ids, ts_ids[1:]) if b <= a)
        return (len(shapes), (min(ts_ids), max(ts_ids)) if ts_ids else None, problems, restarts,
                set(ts_ids))

    def _check_cross_type_consistency(self, othd_files: List[FileInfo], oisd_files: List[FileInfo]):
        """Warn if OTHD and OISD coverage diverges after deduplication."""
        def coverage(files):
            survivors = [f for f in files if not f.is_redundant and not f.is_empty]
            if not survivors:
                return None
            return (min(f.start_step for f in survivors), max(f.end_step for f in survivors))

        othd_cov = coverage(othd_files)
        oisd_cov = coverage(oisd_files)

        if othd_cov and oisd_cov and othd_cov != oisd_cov:
            self.console.print(
                f"  [yellow]⚠[/yellow]  OTHD coverage "
                f"{_fmt_tsid(othd_cov[0])}–{_fmt_tsid(othd_cov[1])} "
                f"differs from OISD "
                f"{_fmt_tsid(oisd_cov[0])}–{_fmt_tsid(oisd_cov[1])}"
            )

    def _analyze_delete_binary_plt(self, t1: Optional[float] = None, t2: Optional[float] = None):
        """
        plt --delete-binary: Unconditionally delete PLT files from binary/
        within the --t1/--t2 window. There is no check against the run
        directory — if the ASCII copy is already gone, this removes the last
        surviving copy of that timestep's PLT data. Omitting both --t1 and
        --t2 deletes every PLT file in binary/.
        """
        binary_dir = self.case_dir / 'binary'
        if not binary_dir.exists():
            self.console.print("  [dim]—[/dim]  binary/ directory not found — nothing to delete")
            return

        problem = self.case.problem_name
        if not problem:
            self.console.print("  [yellow]⚠[/yellow]  'problem' not set — cannot determine PLT file names")
            return

        pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)\.plt$')

        freq = getattr(self.args, 'freq', None)
        keep_freq = getattr(self.args, 'keep_freq', None)

        to_delete = []
        kept = 0
        for binary_plt in sorted(binary_dir.glob(f'{problem}.*.plt'),
                                 key=lambda p: self._extract_plt_step(p.name, problem) or 0):
            match = pattern.match(binary_plt.name)
            if not match:
                continue
            step = int(match.group(1))
            if not self._step_in_bounds(step, t1, t2):
                continue
            if freq and step % freq:
                continue
            if keep_freq and step % keep_freq == 0:
                kept += 1
                continue
            to_delete.append(binary_plt)

        if keep_freq:
            self.console.print(f"  [green]✓[/green]  Keeping {kept} file(s) at steps divisible by {keep_freq}")

        if not to_delete:
            self.console.print(f"  [dim]No {problem}.*.plt files to delete in binary/ for the given range[/dim]")
            return

        if t1 is None and t2 is None and not freq and not keep_freq:
            self.console.print(
                "  [yellow]⚠[/yellow]  No --t1/--t2 given — this deletes ALL PLT files in binary/"
            )

        from rich.table import Table as _Table
        tbl = _Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column("", width=2)
        tbl.add_column("File", style="cyan")
        tbl.add_column("Action")
        for f in to_delete:
            tbl.add_row("[red]✗[/red]", f.name, "[red]will delete (binary/, unconditional)[/red]")
        self.console.print(tbl)

        for f in to_delete:
            self.files_to_delete.append(f)
            self.stats['plt_binary_deleted'] += 1
            self.stats['plt_binary_space_freed'] += f.stat().st_size

    def _analyze_vtu(self, t1: Optional[float] = None, t2: Optional[float] = None):
        """
        vtu: the .vtu files `field render` (and `field convert`) leave beside
        each PLT in binary/ -- {problem}.{step}.vtu, .z{N}.vtu for a zone, and
        the .partial/.deriving leftovers of a run killed mid-write. They are
        a cache: the next render converts the PLT again, so deleting them
        loses nothing but that time. Only these names are touched; another
        .vtu in binary/ is someone's own file.
        """
        binary_dir = self.case_dir / 'binary'
        if not binary_dir.exists():
            self.console.print("  [dim]—[/dim]  binary/ directory not found — nothing to do")
            return
        problem = self.case.problem_name
        if not problem:
            self.console.print("  [yellow]⚠[/yellow]  'problem' not set — cannot tell the .vtu caches by name")
            return

        pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)(\.z\d+)?(\.partial|\.deriving)?\.vtu$')
        found = []
        for path in binary_dir.glob(f'{problem}.*.vtu'):
            match = pattern.match(path.name)
            if match and self._step_in_bounds(int(match.group(1)), t1, t2):
                found.append((int(match.group(1)), path, match))
        if not found:
            self.console.print(f"  [dim]No .vtu caches in binary/"
                               f"{' for the given range' if t1 is not None or t2 is not None else ''}[/dim]")
            return

        found.sort(key=lambda f: (f[0], f[1].name))
        clean = getattr(self.args, 'clean', False)
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column("", width=2)
        tbl.add_column("File", style="cyan")
        tbl.add_column("Size", justify="right")
        tbl.add_column("Note", style="dim")
        total = 0
        for step, path, match in found:
            size = path.stat().st_size
            total += size
            plt = binary_dir / f'{problem}.{step}.plt'
            note = ("left by an interrupted run" if match.group(3)
                    else f"zone {match.group(2)[2:]}" if match.group(2) else "")
            if not plt.exists():
                note = (note + "; " if note else "") + "no .plt: not rebuildable"
            tbl.add_row("[red]✗[/red]" if clean else "", path.name, self._format_size(size), note)
            self.files_to_delete.append(path)
            self.stats['vtu_deleted'] += 1
            self.stats['vtu_space_freed'] += size
        self.console.print(tbl)
        self.console.print(f"  {len(found)} file(s), {self._format_size(total)}")

    def _analyze_clean_plt(self, t1: Optional[float] = None, t2: Optional[float] = None):
        """
        plt --delete-ascii: Mark PLT files in the run directory for deletion where
        binary/ has a corresponding file (same name) with a newer mtime.
        Skips files with no binary copy or where the binary copy is older.
        With --t1/--t2, only PLT files whose timestep falls in that window
        are considered; the rest are left untouched.
        """
        run_dir = self._get_run_dir_path()
        if not run_dir:
            self.console.print("  [yellow]⚠[/yellow]  No run directory found in simflow.config")
            return

        binary_dir = self.case_dir / 'binary'
        if not binary_dir.exists():
            self.console.print("  [dim]—[/dim]  binary/ directory not found — no archived PLT files to compare against")
            return

        problem = self.case.problem_name
        if not problem:
            self.console.print("  [yellow]⚠[/yellow]  'problem' not set — cannot determine PLT file names")
            return

        pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)\.plt$')

        safe_to_delete = []    # run PLT files with a newer binary copy
        skip_no_binary  = []   # run PLT files with no corresponding binary copy
        skip_older      = []   # run PLT files where binary copy is same age or older

        for run_plt in sorted(run_dir.glob(f'{problem}.*.plt')):
            match = pattern.match(run_plt.name)
            if not match:
                continue
            step = int(match.group(1))
            if not self._step_in_bounds(step, t1, t2):
                continue
            binary_plt = binary_dir / run_plt.name
            if not binary_plt.exists():
                skip_no_binary.append(run_plt)
            elif binary_plt.stat().st_mtime <= run_plt.stat().st_mtime:
                skip_older.append(run_plt)
            else:
                safe_to_delete.append(run_plt)

        if not safe_to_delete and not skip_no_binary and not skip_older:
            self.console.print(f"  [dim]No {problem}.*.plt files found in {run_dir.name}/[/dim]")
            return

        # Show what will happen
        from rich.table import Table as _Table
        tbl = _Table(box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column("", width=2)
        tbl.add_column("File", style="cyan")
        tbl.add_column("Action")

        for f in safe_to_delete:
            tbl.add_row("[green]✓[/green]", f.name, "will delete  (binary copy is newer)")
        for f in skip_no_binary:
            tbl.add_row("[dim]—[/dim]", f.name, "[dim]skip — no binary copy[/dim]")
        for f in skip_older:
            tbl.add_row("[yellow]⚠[/yellow]", f.name,
                        "[yellow]skip — binary copy is same age or older[/yellow]")

        self.console.print(tbl)

        # Add safe files to deletion list
        for f in safe_to_delete:
            self.files_to_delete.append(f)
            self.stats['plt_clean_deleted'] += 1
            self.stats['plt_clean_space_freed'] += f.stat().st_size

    def _analyze_output_directory(self, t1: Optional[float] = None, t2: Optional[float] = None):
        """Analyze output directory and find files to delete."""
        # Keep the steps divisible by --keep-freq, by default 10 * freq
        freq = None
        keep_interval = getattr(self.args, 'keep_freq', None)
        if keep_interval is None:
            freq = self._get_frequency()
            if freq is None:
                self.logger.warning("Could not determine frequency, skipping output directory "
                                    "cleanup (give --keep-freq N)")
                return
            keep_interval = freq * 10
            self.logger.info(f"Using freq={freq}, keep_interval={keep_interval}")
        if getattr(self.args, 'all_out', False):
            self.console.print(f"  Keeping .rst at steps divisible by {keep_interval}; "
                               f"[bold]every .out goes[/bold] (--all-out)")
        else:
            self.console.print(f"  Keeping .rst at steps divisible by {keep_interval}; "
                               f".out go once converted to .plt")

        if t1 is not None or t2 is not None:
            self.logger.info(f"Limiting cleanup to timesteps in [{t1}, {t2}]")

        # Find output directories
        output_dirs = self._find_output_directories()
        if not output_dirs:
            self.logger.warning("No output directories found")
            return

        # Get problem name
        problem = self.case.problem_name

        # Analyze each directory
        for output_dir in output_dirs:
            self._analyze_single_output_dir(output_dir, problem, freq, keep_interval, t1, t2)

    def _find_output_directories(self) -> List[Path]:
        """Find output directories from simflow.config."""
        run_dir = self._get_run_dir_path()
        if run_dir is None:
            return []
        return [run_dir]

    def _analyze_single_output_dir(self, output_dir: Path, problem: str, freq: int,
                                   keep_interval: int, t1: Optional[float] = None,
                                   t2: Optional[float] = None):
        """Analyze a single output directory.

        .rst files are restart points, so the steps divisible by keep_interval
        stay. .out files are not read by a restart -- only by the conversion
        that writes {problem}.T.plt -- so any step's .out can go, but only
        once that .plt exists (in binary/ or the run directory): without it
        the step's field data would be gone for good.
        """
        # Find out and rst files (plt files are handled by `plt --delete-ascii`/`--delete-binary`, not `output`)
        out_pattern = f'{problem}.*_*.out'
        rst_pattern = f'{problem}.*_*.rst'

        out_files = list(output_dir.glob(out_pattern))
        rst_files = list(output_dir.glob(rst_pattern))

        self.logger.info(f"Found {len(out_files)} .out files, {len(rst_files)} .rst files "
                        f"in {output_dir.name}")

        binary_dir = self.case_dir / 'binary'
        no_plt = set()          # steps whose .out stay: nothing has converted them
        all_out = getattr(self.args, 'all_out', False)

        for file in out_files + rst_files:
            step = self._extract_step_from_filename(file.name, problem)
            if step is None:
                continue

            # Skip files outside --t1/--t2 (leave them untouched)
            if not self._step_in_bounds(step, t1, t2):
                continue

            if file.suffix == '.out':
                plt = f'{problem}.{step}.plt'
                converted = (binary_dir / plt).exists() or (output_dir / plt).exists()
                delete = converted or all_out
                if not delete:
                    no_plt.add(step)
                reason = f"step {step} has {plt}" if converted else "--all-out"
            else:
                delete = step % keep_interval != 0
                reason = f"step {step} not multiple of {keep_interval}"

            if delete:
                self.files_to_delete.append(file)
                size = file.stat().st_size

                if file.suffix == '.out':
                    self.stats['out_deleted'] += 1
                else:
                    self.stats['rst_deleted'] += 1

                self.stats['output_space_freed'] += size

                if self.args.verbose:
                    self.logger.info(f"  Delete: {file.name} ({reason})")

        if no_plt:
            steps = sorted(no_plt)
            shown = ', '.join(map(str, steps[:10])) + (', ...' if len(steps) > 10 else '')
            self.console.print(f"  [yellow]Keeping .out of {len(steps)} step(s) with no "
                               f"{problem}.<step>.plt yet:[/yellow] {shown}")
            self.console.print("  [dim]Convert them first (run post), or add --all-out to "
                               "delete them anyway.[/dim]")

        # PLT files are handled exclusively by `plt --delete-ascii`/`--delete-binary`, not `output`

    def _analyze_plt_files(self, plt_files: List[Path], problem: str):
        """
        Analyze PLT files and mark for deletion if binary version exists.

        Parameters:
        -----------
        plt_files : List[Path]
            List of PLT file paths in output directory
        problem : str
            Problem name for constructing binary paths
        """
        binary_dir = self.case_dir / 'binary'

        if not binary_dir.exists():
            self.logger.info("No binary directory found, skipping PLT cleanup")
            return

        for plt_file in plt_files:
            # Extract timestep from filename: {problem}.{timestep}.plt
            step = self._extract_plt_step(plt_file.name, problem)
            if step is None:
                continue

            # Check if binary version exists
            binary_plt = binary_dir / f'{problem}.{step}.plt'

            if binary_plt.exists():
                # Binary version exists, mark ASCII version for deletion
                self.files_to_delete.append(plt_file)
                size = plt_file.stat().st_size

                self.stats['plt_deleted'] += 1
                self.stats['output_space_freed'] += size

                if self.args.verbose:
                    self.logger.info(f"  Delete: {plt_file.name} (binary version exists)")

    def _extract_plt_step(self, filename: str, problem: str) -> Optional[int]:
        """Extract time step from PLT filename."""
        # Pattern: {problem}.{step}.plt
        pattern = rf'{re.escape(problem)}\.(\d+)\.plt'
        match = re.match(pattern, filename)
        if match:
            return int(match.group(1))
        return None

    def _get_frequency(self) -> Optional[int]:
        """Get output frequency from config or auto-detect."""
        # Try simflow.config
        if 'outFreq' in self.case.config:
            try:
                return int(self.case.config['outFreq'])
            except ValueError:
                pass

        # Auto-detect from output directory
        return self._auto_detect_frequency()

    def _auto_detect_frequency(self) -> Optional[int]:
        """Auto-detect frequency from output file time steps."""
        output_dirs = list(self.case_dir.glob('RUN_*'))
        if not output_dirs:
            return None

        problem = self.case.problem_name
        out_pattern = f'{problem}.*_*.out'

        steps = []
        for output_dir in output_dirs:
            for file in output_dir.glob(out_pattern):
                step = self._extract_step_from_filename(file.name, problem)
                if step is not None:
                    steps.append(step)

        if len(steps) < 2:
            return None

        steps.sort()

        # Find smallest gap
        min_gap = min(steps[i+1] - steps[i] for i in range(len(steps) - 1))

        self.logger.info(f"Auto-detected frequency: {min_gap}")
        return min_gap

    def _extract_step_from_filename(self, filename: str, problem: str) -> Optional[int]:
        """Extract time step from filename."""
        # Pattern: {problem}.{step}_*.out or {problem}.{step}_*.rst
        pattern = rf'{re.escape(problem)}\.(\d+)_.*\.(?:out|rst)'
        match = re.match(pattern, filename)
        if match:
            return int(match.group(1))
        return None

    def _rename_files(self, othd_files: List[FileInfo], oisd_files: List[FileInfo]):
        """Rename files after cleanup."""
        self.logger.info("Renaming files...")

        problem = self.case.problem_name

        # OTHD and OISD: sort by tsId start step
        for file_type, files in [('OTHD', othd_files), ('OISD', oisd_files)]:
            if not files:
                continue

            kept_files = [f for f in files if not f.is_redundant]
            # an empty part the user kept goes last, so it is renamed rather than overwritten
            kept_files.sort(key=lambda f: (f.is_empty, f.start_step or 0, f.path.name))

            ext = 'othd' if file_type == 'OTHD' else 'oisd'

            for i, file_info in enumerate(kept_files, 1):
                old_path = file_info.path
                new_name = f'{problem}{i}.{ext}'
                new_path = old_path.parent / new_name

                if old_path.name != new_name:
                    self.files_to_rename.append((old_path, new_path))

                    if self.args.verbose:
                        self.logger.info(f"  Rename: {old_path.name} → {new_name}")

        # RCV: no reader available, sort by mtime (oldest first = earliest in run)
        rcv_dir = self.case_dir / 'rcv_files'
        if rcv_dir.exists():
            rcv_files = sorted(rcv_dir.glob('*.rcv'), key=lambda f: f.stat().st_mtime)
            for i, rcv_path in enumerate(rcv_files, 1):
                new_name = f'{problem}{i}.rcv'
                new_path = rcv_dir / new_name
                if rcv_path.name != new_name:
                    self.files_to_rename.append((rcv_path, new_path))
                    if self.args.verbose:
                        self.logger.info(f"  Rename: {rcv_path.name} → {new_name}")

    def _show_summary(self):
        """Show summary before deletion."""
        table = Table(title="Cleanup Summary", box=box.ROUNDED, show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="yellow")
        table.add_column("Space", justify="right", style="green")

        if self.stats['othd_total'] > 0:
            table.add_row(
                "OTHD files to delete",
                str(self.stats['othd_redundant']),
                self._format_size(self.stats['othd_space_freed'])
            )

        if self.stats['oisd_total'] > 0:
            table.add_row(
                "OISD files to delete",
                str(self.stats['oisd_redundant']),
                self._format_size(self.stats['oisd_space_freed'])
            )

        if self.stats['out_deleted'] > 0:
            table.add_row(
                "OUT files to delete",
                str(self.stats['out_deleted']),
                ""
            )

        if self.stats['rst_deleted'] > 0:
            table.add_row(
                "RST files to delete",
                str(self.stats['rst_deleted']),
                ""
            )

        if self.stats['plt_deleted'] > 0:
            table.add_row(
                "PLT files to delete",
                str(self.stats['plt_deleted']),
                ""
            )

        if self.stats['plt_clean_deleted'] > 0:
            table.add_row(
                "PLT files to clean (run dir)",
                str(self.stats['plt_clean_deleted']),
                self._format_size(self.stats['plt_clean_space_freed'])
            )

        if self.stats['plt_binary_deleted'] > 0:
            table.add_row(
                "PLT files to delete (binary/)",
                str(self.stats['plt_binary_deleted']),
                self._format_size(self.stats['plt_binary_space_freed'])
            )

        if self.stats['vtu_deleted'] > 0:
            table.add_row(
                ".vtu caches to delete (binary/)",
                str(self.stats['vtu_deleted']),
                self._format_size(self.stats['vtu_space_freed'])
            )

        if self.stats['output_space_freed'] > 0:
            table.add_row(
                "Output space to free",
                "",
                self._format_size(self.stats['output_space_freed'])
            )

        total_space = self._total_space_freed()

        table.add_row(
            "[bold]Total space to free[/bold]",
            "",
            f"[bold]{self._format_size(total_space)}[/bold]"
        )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _total_space_freed(self) -> int:
        return (self.stats['othd_space_freed'] +
                self.stats['oisd_space_freed'] +
                self.stats['output_space_freed'] +
                self.stats['plt_clean_space_freed'] +
                self.stats['plt_binary_space_freed'] +
                self.stats['vtu_space_freed'])

    def _confirm_deletion(self) -> bool:
        """Ask user to confirm deletion."""
        total_files = len(self.files_to_delete)
        total_space = self._total_space_freed()

        self.console.print(
            f"[bold yellow]Delete {total_files} files "
            f"({self._format_size(total_space)})?[/bold yellow] \\[y/N]: ",
            end=""
        )

        response = input().strip().lower()
        return response in ['y', 'yes']

    def _perform_deletions(self):
        """Perform actual file deletions and renames."""
        if not self.files_to_delete and not self.files_to_rename:
            self.console.print("[green]No files to delete[/green]")
            return

        if not self.files_to_delete:
            # Nothing to delete, fall through to renames below
            pass

        self.logger.info(f"Deleting {len(self.files_to_delete)} files...")

        # Open log file if requested
        log_handle = None
        if self.log_file:
            log_handle = open(self.log_file, 'a')
            log_handle.write(f"FlexFlow Case Organise Log\n")
            log_handle.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_handle.write(f"Case: {self.case_dir}\n\n")

        for file_path in self.files_to_delete:
            try:
                size = file_path.stat().st_size
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                # Log before deletion
                if log_handle:
                    log_handle.write(f"Deleted: {file_path}\n")
                    log_handle.write(f"  Size: {self._format_size(size)}\n")
                    log_handle.write(f"  Modified: {mtime}\n")
                    log_handle.write(f"  Reason: Redundant/intermediate file\n\n")

                file_path.unlink()

                if self.args.verbose:
                    self.logger.info(f"  Deleted: {file_path.name}")

            except Exception as e:
                self.logger.error(f"Failed to delete {file_path}: {e}")

        # Rename files — two-phase to avoid collisions when numbering shifts
        # Phase 1: rename every file to a temp name
        temp_map: List[Tuple[Path, Path]] = []
        for old_path, new_path in self.files_to_rename:
            try:
                tmp_path = old_path.with_name(old_path.name + '.__tmp__')
                old_path.rename(tmp_path)
                temp_map.append((tmp_path, new_path))
            except Exception as e:
                self.logger.error(f"Failed to stage rename {old_path}: {e}")

        # Phase 2: rename each temp file to its final name
        for tmp_path, new_path in temp_map:
            try:
                if log_handle:
                    log_handle.write(f"Renamed: {new_path.with_name(tmp_path.name)} → {new_path.name}\n")

                tmp_path.rename(new_path)

                if self.args.verbose:
                    self.logger.info(f"  Renamed: → {new_path.name}")

            except Exception as e:
                self.logger.error(f"Failed to finalise rename {tmp_path} → {new_path}: {e}")

        if log_handle:
            log_handle.close()
            self.console.print(f"\n[dim]Log saved to: {self.log_file}[/dim]")

    def _show_final_summary(self, subcommand: str, steps=()):
        """Show final summary after cleanup. `steps` are the archive flags that ran."""
        self.console.print()

        lines = []
        if subcommand == 'archive':
            if 'update' in steps:
                total_archived = (self.stats['archived_othd'] + self.stats['archived_oisd'] +
                                  self.stats['archived_rcv'])
                lines.append(f"Archived: {self.stats['archived_othd']} OTHD, "
                             f"{self.stats['archived_oisd']} OISD, "
                             f"{self.stats['archived_rcv']} RCV  (total {total_archived} files)")
            if 'verify' in steps:
                lines.append(("Verified: all files ok" if self.stats['verify_ok']
                              else "Verified: [red]problems found[/red]")
                             + (f"  [yellow]({self.stats['verify_lost']:,} tsId(s) lost)[/yellow]"
                                if self.stats['verify_lost'] else ""))
            if self.stats['verify_ok']:  # a failed --verify stops the later steps
                if 'clean' in steps:
                    lines.append(f"Deduplicated: {self.stats['othd_redundant']} OTHD, "
                                 f"{self.stats['oisd_redundant']} OISD removed  "
                                 f"({self._format_size(self.stats['othd_space_freed'] + self.stats['oisd_space_freed'])} freed)")
                if 'compile' in steps:
                    lines.append("Compiled: " + ("; ".join(self.stats['compiled']) or "nothing written"))
                if 'prune' in steps:
                    lines.append(f"Pruned: {self.stats['pruned']} part(s) removed  "
                                 f"({self._format_size(self.stats['pruned_space_freed'])} freed)")
                    if self.stats['pruned_moved']:
                        lines.append("Compiled data now in: " + ", ".join(self.stats['pruned_moved']))
        if subcommand == 'output':
            total_out = self.stats['out_deleted'] + self.stats['rst_deleted'] + self.stats['plt_deleted']
            lines.append(f"Output cleaned: {total_out} files removed  "
                         f"({self._format_size(self.stats['output_space_freed'])} freed)")
        if subcommand == 'plt':
            if getattr(self.args, 'delete_ascii', False):
                n = self.stats['plt_clean_deleted']
                lines.append(f"PLT deleted (run dir): {n} file{'s' if n != 1 else ''} removed  "
                             f"({self._format_size(self.stats['plt_clean_space_freed'])} freed)")
            if getattr(self.args, 'delete_binary', False):
                n = self.stats['plt_binary_deleted']
                lines.append(f"PLT deleted (binary/): {n} file{'s' if n != 1 else ''} removed  "
                             f"({self._format_size(self.stats['plt_binary_space_freed'])} freed)")

        if subcommand == 'vtu':
            n = self.stats['vtu_deleted']
            lines.append(f".vtu deleted (binary/): {n} file{'s' if n != 1 else ''} removed  "
                         f"({self._format_size(self.stats['vtu_space_freed'])} freed)")

        summary_text = "\n".join(lines) if lines else "Nothing to do"

        self.console.print(Panel(
            f"[bold green]Organization Complete![/bold green]\n\n{summary_text}",
            border_style="green",
            box=box.ROUNDED
        ))

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"
