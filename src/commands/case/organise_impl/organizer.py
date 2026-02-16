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


class FileInfo:
    """Information about a data file."""

    def __init__(self, path: Path, start_step: int, end_step: int, size: int, mtime: float):
        self.path = path
        self.start_step = start_step
        self.end_step = end_step
        self.size = size
        self.mtime = mtime
        self.is_redundant = False
        self.redundant_reason = None

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

    def _archive_run_data_files(self):
        """
        --archive: Move .othd, .oisd (and .rcv if present) from the run
        directory into othd_files/, oisd_files/, rcv_files/.
        """
        run_dir = self._get_run_dir_path()
        if not run_dir:
            self.console.print("[yellow]  No run directory found in simflow.config[/yellow]")
            return

        self.logger.info(f"Archiving data files from: {run_dir}")

        othd_files_found = list(run_dir.glob('*.othd'))
        oisd_files_found = list(run_dir.glob('*.oisd'))
        rcv_files_found = list(run_dir.glob('*.rcv'))

        if not othd_files_found and not oisd_files_found and not rcv_files_found:
            self.console.print("[dim]  No .othd/.oisd/.rcv files found in run directory[/dim]")
            return

        # Create destination directories
        othd_dest = self.case_dir / 'othd_files'
        oisd_dest = self.case_dir / 'oisd_files'
        othd_dest.mkdir(exist_ok=True)
        oisd_dest.mkdir(exist_ok=True)

        moved_count = 0

        for file in sorted(othd_files_found):
            dest_path = self._get_unique_filename(othd_dest, file.name)
            shutil.move(str(file), str(dest_path))
            self.console.print(f"  [green]↳[/green] {file.name} → othd_files/{dest_path.name}")
            self.stats['archived_othd'] += 1
            moved_count += 1

        for file in sorted(oisd_files_found):
            dest_path = self._get_unique_filename(oisd_dest, file.name)
            shutil.move(str(file), str(dest_path))
            self.console.print(f"  [green]↳[/green] {file.name} → oisd_files/{dest_path.name}")
            self.stats['archived_oisd'] += 1
            moved_count += 1

        if rcv_files_found:
            rcv_dest = self.case_dir / 'rcv_files'
            rcv_dest.mkdir(exist_ok=True)
            for file in sorted(rcv_files_found):
                dest_path = self._get_unique_filename(rcv_dest, file.name)
                shutil.move(str(file), str(dest_path))
                self.console.print(f"  [green]↳[/green] {file.name} → rcv_files/{dest_path.name}")
                self.stats['archived_rcv'] += 1
                moved_count += 1

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

    def organize(self):
        """Main organization workflow."""
        do_archive = getattr(self.args, 'archive', False)
        do_organise = getattr(self.args, 'organise', False)
        do_clean_output = getattr(self.args, 'clean_output', False)
        do_clean_plt = getattr(self.args, 'clean_plt', False)

        self.console.print()
        self.console.print(Panel(
            f"[bold cyan]Organizing Case:[/bold cyan] {self.case_dir.name}\n"
            f"[dim]Path: {self.case_dir}[/dim]",
            border_style="cyan",
            box=box.ROUNDED
        ))
        self.console.print()

        # --- ARCHIVE ---
        if do_archive:
            self.console.print("[bold]Step: Archive run data files[/bold]")
            self._archive_run_data_files()
            self.console.print()

        # --- ORGANISE (deduplicate OTHD/OISD) ---
        othd_files = []
        oisd_files = []

        if do_organise:
            self.console.print("[bold]Step: Deduplicate OTHD/OISD files[/bold]")
            self.logger.info("Analyzing OTHD files...")
            othd_files = self._analyze_data_files('othd')
            self._find_redundant_files(othd_files, 'OTHD')

            self.logger.info("Analyzing OISD files...")
            oisd_files = self._analyze_data_files('oisd')
            self._find_redundant_files(oisd_files, 'OISD')
            self.console.print()

        # --- CLEAN OUTPUT ---
        if do_clean_output:
            self.console.print("[bold]Step: Clean output directory[/bold]")
            self._analyze_output_directory()
            self.console.print()

        # --- CLEAN PLT ---
        if do_clean_plt:
            self.console.print("[bold]Step: Clean PLT files from run directory[/bold]")
            self._analyze_clean_plt()
            self.console.print()

        # Nothing to do beyond archiving (which runs without confirmation)
        has_deletions = len(self.files_to_delete) > 0

        if do_organise or do_clean_output or do_clean_plt:
            # Show summary before asking confirmation
            self._show_summary()

            if has_deletions and not self.args.no_confirm:
                if not self._confirm_deletion():
                    self.console.print("[yellow]Operation cancelled[/yellow]")
                    return

            if has_deletions:
                self._perform_deletions()

        # Rename OTHD/OISD files sequentially after deduplication
        if do_organise:
            self._rename_files(othd_files, oisd_files)

        # Final summary
        self._show_final_summary(do_archive, do_organise, do_clean_output, do_clean_plt)

    def _analyze_data_files(self, file_type: str) -> List[FileInfo]:
        """
        Analyze OTHD or OISD files.

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
                reader = reader_class(str(file_path))

                if len(reader.tsIds) == 0:
                    raise ValueError(f"No time steps found in {file_path.name}")

                start_step = min(reader.tsIds)
                end_step = max(reader.tsIds)
                size = file_path.stat().st_size
                mtime = file_path.stat().st_mtime

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
        if not files:
            return

        # Sort by start step, then by size (larger first), then by mtime (recent first)
        files.sort(key=lambda f: (f.start_step, -f.size, -f.mtime))

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

        # Collect redundant files
        for file in files:
            if file.is_redundant:
                self.files_to_delete.append(file.path)
                size = file.path.stat().st_size

                if file_type == 'OTHD':
                    self.stats['othd_redundant'] += 1
                    self.stats['othd_space_freed'] += size
                else:
                    self.stats['oisd_redundant'] += 1
                    self.stats['oisd_space_freed'] += size

                if self.args.verbose:
                    self.logger.info(f"  Redundant: {file.path.name} ({file.redundant_reason})")

    def _analyze_clean_plt(self):
        """
        --clean-plt: Mark PLT files in the run directory for deletion where
        binary/ has a corresponding file (same name) with a newer mtime.
        Skips files with no binary copy or where the binary copy is older.
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
            if not pattern.match(run_plt.name):
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

    def _analyze_output_directory(self):
        """Analyze output directory and find files to delete."""
        # Get frequency
        freq = self._get_frequency()
        if freq is None:
            self.logger.warning("Could not determine frequency, skipping output directory cleanup")
            return

        # Calculate keep_every: use provided value or default to 10 * freq
        if hasattr(self.args, 'keep_every') and self.args.keep_every is not None:
            keep_every = self.args.keep_every
        else:
            keep_every = 10

        keep_interval = freq * keep_every
        self.logger.info(f"Using freq={freq}, keep_every={keep_every}, keep_interval={keep_interval}")

        # Find output directories
        output_dirs = self._find_output_directories()
        if not output_dirs:
            self.logger.warning("No output directories found")
            return

        # Get problem name
        problem = self.case.problem_name

        # Analyze each directory
        for output_dir in output_dirs:
            self._analyze_single_output_dir(output_dir, problem, freq, keep_interval)

    def _find_output_directories(self) -> List[Path]:
        """Find output directories from simflow.config."""
        run_dir = self._get_run_dir_path()
        if run_dir is None:
            return []
        return [run_dir]

    def _analyze_single_output_dir(self, output_dir: Path, problem: str, freq: int, keep_interval: int):
        """Analyze a single output directory."""
        # Find out and rst files (plt files are handled by --clean-plt, not --clean-output)
        out_pattern = f'{problem}.*_*.out'
        rst_pattern = f'{problem}.*_*.rst'

        out_files = list(output_dir.glob(out_pattern))
        rst_files = list(output_dir.glob(rst_pattern))

        self.logger.info(f"Found {len(out_files)} .out files, {len(rst_files)} .rst files "
                        f"in {output_dir.name}")

        # Extract step numbers and check retention for .out and .rst files
        for file in out_files + rst_files:
            step = self._extract_step_from_filename(file.name, problem)
            if step is None:
                continue

            # Keep if multiple of keep_interval
            if step % keep_interval != 0:
                self.files_to_delete.append(file)
                size = file.stat().st_size

                if file.suffix == '.out':
                    self.stats['out_deleted'] += 1
                else:
                    self.stats['rst_deleted'] += 1

                self.stats['output_space_freed'] += size

                if self.args.verbose:
                    self.logger.info(f"  Delete: {file.name} (step {step} not multiple of {keep_interval})")

        # PLT files are handled exclusively by --clean-plt, not --clean-output

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

        # Filter out redundant files and sort by time step
        for file_type, files in [('OTHD', othd_files), ('OISD', oisd_files)]:
            if not files:
                continue

            kept_files = [f for f in files if not f.is_redundant]
            kept_files.sort(key=lambda f: f.start_step)

            # Generate new names
            problem = self.case.problem_name
            ext = 'othd' if file_type == 'OTHD' else 'oisd'

            for i, file_info in enumerate(kept_files, 1):
                old_path = file_info.path
                new_name = f'{problem}{i}.{ext}'
                new_path = old_path.parent / new_name

                if old_path.name != new_name:
                    self.files_to_rename.append((old_path, new_path))

                    if self.args.verbose:
                        self.logger.info(f"  Rename: {old_path.name} → {new_name}")

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

        if self.stats['output_space_freed'] > 0:
            table.add_row(
                "Output space to free",
                "",
                self._format_size(self.stats['output_space_freed'])
            )

        total_space = (self.stats['othd_space_freed'] +
                      self.stats['oisd_space_freed'] +
                      self.stats['output_space_freed'] +
                      self.stats['plt_clean_space_freed'])

        table.add_row(
            "[bold]Total space to free[/bold]",
            "",
            f"[bold]{self._format_size(total_space)}[/bold]"
        )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _confirm_deletion(self) -> bool:
        """Ask user to confirm deletion."""
        total_files = len(self.files_to_delete)
        total_space = (self.stats['othd_space_freed'] +
                      self.stats['oisd_space_freed'] +
                      self.stats['output_space_freed'] +
                      self.stats['plt_clean_space_freed'])

        self.console.print(
            f"[bold yellow]Delete {total_files} files "
            f"({self._format_size(total_space)})?[/bold yellow] [y/N]: ",
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
            log_handle = open(self.log_file, 'w')
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

        # Rename files
        for old_path, new_path in self.files_to_rename:
            try:
                if log_handle:
                    log_handle.write(f"Renamed: {old_path} → {new_path.name}\n")

                old_path.rename(new_path)

                if self.args.verbose:
                    self.logger.info(f"  Renamed: {old_path.name} → {new_path.name}")

            except Exception as e:
                self.logger.error(f"Failed to rename {old_path}: {e}")

        if log_handle:
            log_handle.close()
            self.console.print(f"\n[dim]Log saved to: {self.log_file}[/dim]")

    def _show_final_summary(self, do_archive: bool, do_organise: bool, do_clean_output: bool,
                            do_clean_plt: bool = False):
        """Show final summary after cleanup."""
        self.console.print()

        lines = []
        if do_archive:
            total_archived = (self.stats['archived_othd'] + self.stats['archived_oisd'] +
                              self.stats['archived_rcv'])
            lines.append(f"Archived: {self.stats['archived_othd']} OTHD, "
                         f"{self.stats['archived_oisd']} OISD, "
                         f"{self.stats['archived_rcv']} RCV  (total {total_archived} files)")
        if do_organise:
            lines.append(f"Deduplicated: {self.stats['othd_redundant']} OTHD, "
                         f"{self.stats['oisd_redundant']} OISD removed  "
                         f"({self._format_size(self.stats['othd_space_freed'] + self.stats['oisd_space_freed'])} freed)")
        if do_clean_output:
            total_out = self.stats['out_deleted'] + self.stats['rst_deleted'] + self.stats['plt_deleted']
            lines.append(f"Output cleaned: {total_out} files removed  "
                         f"({self._format_size(self.stats['output_space_freed'])} freed)")
        if do_clean_plt:
            n = self.stats['plt_clean_deleted']
            lines.append(f"PLT cleaned: {n} file{'s' if n != 1 else ''} removed from run dir  "
                         f"({self._format_size(self.stats['plt_clean_space_freed'])} freed)")

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
