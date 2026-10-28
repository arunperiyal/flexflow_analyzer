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

from .history import HistoryMixin
from rich.table import Table
from rich.panel import Panel
from rich import box


class CaseOrganizer(HistoryMixin):
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
            'migrated': 0,   # history: parts moved from the old flat layout
            'cleaned': 0,
            'compiled': [],  # one line per compiled file, for the final summary
            'verify_ok': True,
            'verify_lost': 0,
            'pruned': 0,
            'pruned_space_freed': 0,
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

    def organize(self, subcommand: str):
        """
        Main organization workflow for one subcommand.

        Parameters:
        -----------
        subcommand : str
            'history', 'output', 'plt' or 'vtu'
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

        # --- HISTORY --- (its own flow, see history.py)
        if subcommand == 'history':
            self._organize_history(t1, t2)
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

    def _show_summary(self):
        """Show summary before deletion."""
        table = Table(title="Cleanup Summary", box=box.ROUNDED, show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="yellow")
        table.add_column("Space", justify="right", style="green")

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
        return (self.stats['output_space_freed'] +
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
        """Show final summary after cleanup. `steps` are the history flags that ran."""
        self.console.print()

        lines = []
        if subcommand == 'history':
            lines += self._history_summary(steps)
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
