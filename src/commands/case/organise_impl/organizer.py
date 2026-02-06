"""
Case organization logic

Handles cleaning and organizing case directories.
"""

import os
import re
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
            'othd_total': 0,
            'othd_redundant': 0,
            'othd_space_freed': 0,
            'oisd_total': 0,
            'oisd_redundant': 0,
            'oisd_space_freed': 0,
            'out_deleted': 0,
            'rst_deleted': 0,
            'output_space_freed': 0,
        }

        # Files to delete/rename
        self.files_to_delete: List[Path] = []
        self.files_to_rename: List[Tuple[Path, Path]] = []  # (old, new)

        # Log file
        self.log_file = None
        if args.log:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = self.case_dir / f'organise_log_{timestamp}.txt'

    def organize(self):
        """Main organization workflow."""
        self.console.print()
        self.console.print(Panel(
            f"[bold cyan]Organizing Case:[/bold cyan] {self.case_dir.name}\n"
            f"[dim]Path: {self.case_dir}[/dim]",
            border_style="cyan",
            box=box.ROUNDED
        ))
        self.console.print()

        # Determine what to clean
        clean_othd = not (self.args.clean_oisd or self.args.clean_output)
        clean_oisd = not (self.args.clean_othd or self.args.clean_output)
        clean_output = not (self.args.clean_othd or self.args.clean_oisd)

        if self.args.clean_othd:
            clean_othd, clean_oisd, clean_output = True, False, False
        elif self.args.clean_oisd:
            clean_othd, clean_oisd, clean_output = False, True, False
        elif self.args.clean_output:
            clean_othd, clean_oisd, clean_output = False, False, True

        # Analyze files
        othd_files = []
        oisd_files = []

        if clean_othd:
            self.logger.info("Analyzing OTHD files...")
            othd_files = self._analyze_data_files('othd')
            self._find_redundant_files(othd_files, 'OTHD')

        if clean_oisd:
            self.logger.info("Analyzing OISD files...")
            oisd_files = self._analyze_data_files('oisd')
            self._find_redundant_files(oisd_files, 'OISD')

        if clean_output:
            self.logger.info("Analyzing output directory...")
            self._analyze_output_directory()

        # Show summary
        if self.args.dry_run:
            self._show_dry_run_summary()
        else:
            self._show_summary()

            # Ask for confirmation
            if not self.args.no_confirm:
                if not self._confirm_deletion():
                    self.console.print("[yellow]Operation cancelled[/yellow]")
                    return

            # Perform deletions
            self._perform_deletions()

            # Rename files
            if clean_othd or clean_oisd:
                self._rename_files(othd_files if clean_othd else [],
                                 oisd_files if clean_oisd else [])

            # Show final summary
            self._show_final_summary()

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

    def _analyze_output_directory(self):
        """Analyze output directory and find files to delete."""
        # Get frequency
        freq = self._get_frequency()
        if freq is None:
            self.logger.warning("Could not determine frequency, skipping output directory cleanup")
            return

        keep_interval = freq * getattr(self.args, 'keep_every', 10)
        self.logger.info(f"Using freq={freq}, keep_interval={keep_interval}")

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
        """Find output directories (RUN_*)."""
        # Look for RUN_* directories at case level
        run_dirs = list(self.case_dir.glob('RUN_*'))

        if not run_dirs:
            return []

        if len(run_dirs) == 1:
            return run_dirs

        # Multiple directories - ask user
        self.console.print(f"\n[yellow]Found {len(run_dirs)} output directories:[/yellow]")
        for i, dir in enumerate(run_dirs, 1):
            self.console.print(f"  {i}. {dir.name}")

        self.console.print("\n[bold]Which directories to clean?[/bold]")
        self.console.print("  Options: all, 1, 2, 3, 1,2, etc.")

        response = input("Your choice: ").strip().lower()

        if response == 'all':
            return run_dirs

        try:
            indices = [int(x.strip()) - 1 for x in response.split(',')]
            selected = [run_dirs[i] for i in indices if 0 <= i < len(run_dirs)]
            return selected
        except:
            self.logger.warning("Invalid selection, using all directories")
            return run_dirs

    def _analyze_single_output_dir(self, output_dir: Path, problem: str, freq: int, keep_interval: int):
        """Analyze a single output directory."""
        # Find out and rst files
        out_pattern = f'{problem}.*_*.out'
        rst_pattern = f'{problem}.*_*.rst'

        out_files = list(output_dir.glob(out_pattern))
        rst_files = list(output_dir.glob(rst_pattern))

        self.logger.info(f"Found {len(out_files)} .out files and {len(rst_files)} .rst files in {output_dir.name}")

        # Extract step numbers and check retention
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

    def _get_frequency(self) -> Optional[int]:
        """Get output frequency from config or auto-detect."""
        # Try command line override
        if hasattr(self.args, 'freq') and self.args.freq:
            return self.args.freq

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

        if self.stats['output_space_freed'] > 0:
            table.add_row(
                "Output space to free",
                "",
                self._format_size(self.stats['output_space_freed'])
            )

        total_space = (self.stats['othd_space_freed'] +
                      self.stats['oisd_space_freed'] +
                      self.stats['output_space_freed'])

        table.add_row(
            "[bold]Total space to free[/bold]",
            "",
            f"[bold]{self._format_size(total_space)}[/bold]"
        )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _show_dry_run_summary(self):
        """Show dry-run summary."""
        self.console.print()
        self.console.print(Panel(
            "[bold yellow]DRY RUN MODE[/bold yellow]\n"
            "No files will be deleted. Showing what would happen:",
            border_style="yellow",
            box=box.ROUNDED
        ))
        self.console.print()

        self._show_summary()

        if self.files_to_delete:
            self.console.print("[bold]Files that would be deleted:[/bold]")
            for file in self.files_to_delete[:20]:  # Show first 20
                self.console.print(f"  [red]✗[/red] {file}")
            if len(self.files_to_delete) > 20:
                self.console.print(f"  [dim]... and {len(self.files_to_delete) - 20} more[/dim]")

        if self.files_to_rename:
            self.console.print(f"\n[bold]Files that would be renamed:[/bold] {len(self.files_to_rename)}")

    def _confirm_deletion(self) -> bool:
        """Ask user to confirm deletion."""
        total_files = len(self.files_to_delete)
        total_space = (self.stats['othd_space_freed'] +
                      self.stats['oisd_space_freed'] +
                      self.stats['output_space_freed'])

        if total_files == 0:
            self.console.print("[green]No files to delete[/green]")
            return False

        self.console.print(
            f"[bold yellow]Delete {total_files} files "
            f"({self._format_size(total_space)})?[/bold yellow] [y/N]: ",
            end=""
        )

        response = input().strip().lower()
        return response in ['y', 'yes']

    def _perform_deletions(self):
        """Perform actual file deletions."""
        if not self.files_to_delete:
            self.console.print("[green]No files to delete[/green]")
            return

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

    def _show_final_summary(self):
        """Show final summary after cleanup."""
        self.console.print()
        self.console.print(Panel(
            "[bold green]Organization Complete![/bold green]",
            border_style="green",
            box=box.ROUNDED
        ))

        self._show_summary()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"
