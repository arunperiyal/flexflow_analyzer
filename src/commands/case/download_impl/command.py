"""Case upload command implementation."""

import json
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from src.utils.ssh_client import SSHClientWrapper
from src.utils.remote_config import RemoteConfig
from ...case_iteration import is_wildcard_case, load_cases_from_directory
from src.utils.colors import Colors
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.table import Table
from rich import box

# Loose files worth carrying with a case: what defines the run, and the othd maps
# that keep its history readable once the mesh file is gone. Globs, so they hold
# whatever the case calls its problem.
DEFAULT_UPLOAD_FILES = ["simflow.config", "*.def", "*.geo", "*.map"]

# A timestep in a binary/ filename: riser.5000.plt, and the .vtu sidecars that
# sit beside it (riser.5000.vtu, riser.5000.z1.vtu). The first dotted number is
# the step; a name without one -- a script, a summary .csv -- carries no step at
# all and so cannot be placed in a time window.
STEP_IN_NAME = re.compile(r"\.(\d+)\.")


def step_of(name: str) -> Optional[int]:
    """The timestep a binary/ filename carries, or None if it carries none."""
    match = STEP_IN_NAME.search(name)
    return int(match.group(1)) if match else None


def resolve_step_window(t1, t2) -> Optional[tuple]:
    """--t1/--t2 -> the inclusive (lo, hi) window of steps, or None for all.

    The same reading as `field extract` and `field render` give the same two
    flags: both bounds make a range, and one alone names that single step. Two
    meanings for one flag in one program would be worse than the surprise of
    either.
    """
    if t1 is None and t2 is None:
        return None
    if t1 is not None and t2 is not None:
        lo, hi = sorted((float(t1), float(t2)))
        return (lo, hi)
    only = float(t1 if t1 is not None else t2)
    return (only, only)


def select_steps(names: List[str], window: Optional[tuple]) -> tuple:
    """Split `names` into (kept, no_step) for a step window.

    Without a window everything is kept. With one, a file is kept when its step
    falls inside it, and a file with no step at all is set aside rather than
    silently swept along: asking for one timestep should not drag the whole
    post-processing script collection across the wire.
    """
    if window is None:
        return sorted(names), []
    lo, hi = window
    kept, no_step = [], []
    for name in names:
        step = step_of(name)
        if step is None:
            no_step.append(name)
        elif lo <= step <= hi:
            kept.append(name)
    return sorted(kept), sorted(no_step)


def show_upload_help() -> None:
    """Print help for case upload command."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Upload Command{Colors.RESET}

Upload case directories from local machine to a remote server.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case upload [{Colors.YELLOW}case{Colors.RESET}] --to {Colors.YELLOW}REMOTE{Colors.RESET} [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case{Colors.RESET}                   Local case directory path (use * for all cases in .cases)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--to REMOTE{Colors.RESET}            Remote machine name (required)
    {Colors.YELLOW}--dir DIRS{Colors.RESET}             Comma-separated directories to upload
                           (default: othd_files,oisd_files,binary)
    {Colors.YELLOW}--files [PATTERNS]{Colors.RESET}     Loose files from the case root, as comma-separated
                           globs (default: simflow.config,*.def,*.geo,*.map)
    {Colors.YELLOW}--binary{Colors.RESET}               binary/ only -- with --t1/--t2, only the timesteps
                           in that range
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              With --binary: first timestep (alone: only that step)
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              With --binary: last timestep
    {Colors.YELLOW}--remote-path PATH{Colors.RESET}     Override remote base path (default: remote config path)
    {Colors.YELLOW}--force{Colors.RESET}                Create remote directories if they do not exist
    {Colors.YELLOW}--resume{Colors.RESET}               Resume the last interrupted upload
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Uploads one or more case directories to a configured remote server via
    SFTP. The remote server must be registered with 'remote add'.

    Use 'use remote:<name>' in the interactive shell to set a default remote
    so --to can be omitted.

    Wildcard mode ('case upload *') uploads all cases listed in the .cases
    file in the current directory.

{Colors.BOLD}FILES:{Colors.RESET}
    --files carries the small things that describe a case rather than its data:
    what defines the run, its settings, and any othd maps. They are globs, so
    the defaults hold whatever a case calls its problem.

    Given {Colors.BOLD}without --dir{Colors.RESET} it uploads only those files -- the default
    directories include binary/, which is the opposite of a quick definition
    push. Give both to send data and files together.

    Only files sitting directly in the case root are matched; a recursive
    match would sweep up the very data --files exists to avoid.

{Colors.BOLD}TIMESTEPS:{Colors.RESET}
    A case's binary/ is nearly all of its size, and most of it is timesteps you
    already have. {Colors.YELLOW}--binary{Colors.RESET} carries that directory alone; with
    {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} it carries only the steps in the range, matching them
    on the number in the filename (riser.5000.plt, and the .vtu sidecars beside
    it). A file with no step in its name -- a script, a summary table -- is left
    where it is, and the count of those is reported.

    The two flags read as they do everywhere else in FlexFlow: both bounds make
    a range, one alone names that single step. They need {Colors.YELLOW}--binary{Colors.RESET}, since
    nothing else in a case is written per step. The t1/t2 context supplies them:
    {Colors.DIM}use t1:1000 t2:5000{Colors.RESET}, then {Colors.DIM}case upload CS4SG1U1 --binary{Colors.RESET}.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    case upload CS4SG1U1 --to server --binary --t1 1000 --t2 5000
    case upload CS4SG1U1 --to server --binary --t1 5000
    case upload CS4SG1U1 --to server --files
    case upload CS4SG1U1 --to server --files "*.map"
    case upload * --to server --files --force
    case upload CS4SG1U1 --to server --dir binary --files

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set remote context:    use remote:myserver
    Then run:              case upload CS4SG1U1
""")


def show_download_help() -> None:
    """Print help for case download command."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Download Command{Colors.RESET}

Download case directories from a remote server to the local machine.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case download [{Colors.YELLOW}case{Colors.RESET}] --from {Colors.YELLOW}REMOTE{Colors.RESET} [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case{Colors.RESET}                   Local case directory path (destination; use * for all cases in .cases)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--from REMOTE{Colors.RESET}          Remote machine name (required)
    {Colors.YELLOW}--dir DIRS{Colors.RESET}             Comma-separated directories to download
                           (default: othd_files,oisd_files,binary)
    {Colors.YELLOW}--files [PATTERNS]{Colors.RESET}     Loose files from the remote case root, as
                           comma-separated globs
                           (default: simflow.config,*.def,*.geo,*.map)
    {Colors.YELLOW}--binary{Colors.RESET}               binary/ only -- with --t1/--t2, only the timesteps
                           in that range
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              With --binary: first timestep (alone: only that step)
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              With --binary: last timestep
    {Colors.YELLOW}--remote-path PATH{Colors.RESET}     Override remote base path (default: remote config path)
    {Colors.YELLOW}--force{Colors.RESET}                Create the local case directory if it does not exist
    {Colors.YELLOW}--resume{Colors.RESET}               Resume the last interrupted download
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Downloads one or more case directories from a configured remote server via
    SFTP into the local case directory. The remote server must be registered
    with 'remote add'.

    Use 'use remote:<name>' in the interactive shell to set a default remote
    so --from can be omitted.

    Wildcard mode ('case download *') downloads all cases listed in the .cases
    file in the current directory.

{Colors.BOLD}FILES:{Colors.RESET}
    --files fetches the small things that describe a case rather than its data:
    what defines the run, its settings, and any othd maps. Patterns are matched
    against the remote case root only -- subdirectories are left alone.

    Given {Colors.BOLD}without --dir{Colors.RESET} it downloads only those files, so a case's
    definition can be pulled without its data directories.

{Colors.BOLD}TIMESTEPS:{Colors.RESET}
    A case's binary/ is nearly all of its size, and most of it is timesteps you
    already have. {Colors.YELLOW}--binary{Colors.RESET} carries that directory alone; with
    {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} it carries only the steps in the range, matching them
    on the number in the filename (riser.5000.plt, and the .vtu sidecars beside
    it). A file with no step in its name -- a script, a summary table -- is left
    where it is, and the count of those is reported.

    The two flags read as they do everywhere else in FlexFlow: both bounds make
    a range, one alone names that single step. They need {Colors.YELLOW}--binary{Colors.RESET}, since
    nothing else in a case is written per step. The t1/t2 context supplies them:
    {Colors.DIM}use t1:1000 t2:5000{Colors.RESET}, then {Colors.DIM}case download CS4SG1U1 --binary{Colors.RESET}.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    case download CS4SG1U1 --from server --binary --t1 1000 --t2 5000
    case download CS4SG1U1 --from server --binary --t1 5000
    case download CS4SG1U1 --from server --files
    case download CS4SG1U1 --from server --files "*.map"
    case download * --from server --files --force

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set remote context:    use remote:myserver
    Then run:              case download CS4SG1U1
""")


class CaseUploadCommand:
    """Upload case directories from local machine to remote server."""

    def __init__(self):
        self.console = Console()
        self.remote_config = RemoteConfig()


    def _get_transfer_state_file(self) -> Path:
        """Return the path used to persist resumable transfer state."""
        state_dir = Path.home() / '.flexflow'
        state_dir.mkdir(exist_ok=True)
        return state_dir / 'transfer_state.json'

    def _load_transfer_state(self) -> Optional[dict]:
        """Load the current transfer state from disk."""
        state_file = self._get_transfer_state_file()
        if not state_file.exists():
            return None
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _save_transfer_state(self, state: dict) -> None:
        """Persist transfer state to disk."""
        state_file = self._get_transfer_state_file()
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def _clear_transfer_state(self) -> None:
        """Remove any persisted transfer state."""
        try:
            self._get_transfer_state_file().unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def _get_arg(self, args, name: str, default=None):
        """Read a parsed argument without Mock fallthrough creating truthy values."""
        return getattr(args, '__dict__', {}).get(name, default)

    def _target_key(self, case_path: str, directory: str) -> str:
        """Build a stable key for a case-directory transfer target."""
        return f"{os.path.abspath(case_path)}::{directory}"

    def _normalize_case_entries(self, cases: List[dict]) -> List[dict]:
        """Normalize wildcard case entries into absolute path records."""
        entries: List[dict] = []
        for case_entry in cases:
            entry_path = case_entry.get('path')
            if not entry_path:
                continue
            entries.append({
                'name': case_entry.get('name') or Path(entry_path).name,
                'path': os.path.abspath(entry_path),
            })
        return entries

    def _build_single_case_entries(self, case_path: str) -> List[dict]:
        """Build a single-case transfer entry list."""
        return [{'name': Path(case_path).name, 'path': os.path.abspath(case_path)}]

    def _build_transfer_state(
        self,
        direction: str,
        remote_name: str,
        remote_base: str,
        case_selection: str,
        case_entries: List[dict],
        directories: List[str],
        force: bool,
        wildcard: bool,
        file_patterns: Optional[List[str]] = None,
        step_window: Optional[tuple] = None,
    ) -> dict:
        """Construct a new resumable transfer state document."""
        return {
            'direction': direction,
            'status': 'in_progress',
            'remote_name': remote_name,
            'remote_base_path': remote_base,
            'case_selection': case_selection,
            'case_mode': 'wildcard' if wildcard else 'single',
            'directories': directories,
            'file_patterns': list(file_patterns or []),
            'force': force,
            'step_window': list(step_window) if step_window else None,
            'cases': case_entries,
            'completed_targets': [],
        }

    def _load_resume_state(self, expected_direction: str) -> Optional[dict]:
        """Load a resumable transfer state, if one exists for this direction."""
        state = self._load_transfer_state()
        if not state:
            return None
        if state.get('direction') != expected_direction:
            return None
        if state.get('status') not in {'in_progress', 'interrupted'}:
            return None
        if not isinstance(state.get('cases'), list) or not state.get('directories'):
            return None
        return state

    def _finalize_transfer_state(self, state: dict, success: bool) -> None:
        """Persist or clear the transfer state after a run completes."""
        if success:
            self._clear_transfer_state()
            return
        state['status'] = 'interrupted'
        self._save_transfer_state(state)

    def _mark_transfer_target_complete(self, state: dict, target_key: str) -> None:
        """Record a completed directory target and persist the updated state."""
        completed = set(state.get('completed_targets', []))
        completed.add(target_key)
        state['completed_targets'] = sorted(completed)
        state['status'] = 'in_progress'
        self._save_transfer_state(state)

    def _validate_resume_inputs(
        self,
        direction: str,
        args,
        state: dict,
    ) -> Optional[str]:
        """Validate resume arguments against the saved state, if explicitly provided."""
        upload_remote = self._get_arg(args, 'to')
        download_remote = self._get_arg(args, 'from_remote')
        case_arg = self._get_arg(args, 'case')

        if direction == 'upload' and upload_remote and upload_remote != state.get('remote_name'):
            return f"[red]Error:[/red] Resume state is for remote '{state.get('remote_name')}', not '{upload_remote}'."
        if direction == 'download' and download_remote and download_remote != state.get('remote_name'):
            return f"[red]Error:[/red] Resume state is for remote '{state.get('remote_name')}', not '{download_remote}'."

        if case_arg and case_arg != state.get('case_selection'):
            return (
                f"[red]Error:[/red] Resume state is for case selection '{state.get('case_selection')}', "
                f"not '{case_arg}'."
            )
        return None

    def _execute_transfer(self, args, direction: str) -> int:
        """Shared implementation for resumable case upload/download."""
        is_upload = direction == 'upload'
        help_fn = show_upload_help if is_upload else show_download_help
        remote_arg_name = 'to' if is_upload else 'from_remote'
        remote_prompt = '--to' if is_upload else '--from'
        action_label = 'Upload' if is_upload else 'Download'
        target_label = 'upload' if is_upload else 'download'

        if self._get_arg(args, 'help', False) is True or self._get_arg(args, 'examples', False) is True:
            help_fn()
            return 0

        resume_requested = bool(self._get_arg(args, 'resume', False))
        state = None
        completed_targets = set()

        if resume_requested:
            state = self._load_resume_state(direction)
            if not state:
                self.console.print(
                    f"[red]Error:[/red] No interrupted {target_label} found to resume."
                )
                return 1
            resume_error = self._validate_resume_inputs(direction, args, state)
            if resume_error:
                self.console.print(resume_error)
                return 1

            remote_name = state['remote_name']
            remote_base = state['remote_base_path']
            force_enabled = bool(state.get('force', False))
            directories = list(state.get('directories', []))
            file_patterns = list(state.get('file_patterns', []))
            case_entries = list(state.get('cases', []))
            case_selection = state.get('case_selection', '')
            wildcard = state.get('case_mode') == 'wildcard'
            completed_targets = set(state.get('completed_targets', []))
            saved_window = state.get('step_window')
            step_window = tuple(saved_window) if saved_window else None
        else:
            case_selection = self.validate_case_path(self._get_arg(args, 'case'))
            if not case_selection:
                return 1

            remote_name = self._get_arg(args, remote_arg_name)
            if not remote_name and not is_upload:
                remote_name = self._get_arg(args, 'to')
            if not remote_name:
                self.console.print(
                    f"[red]Error:[/red] Remote machine not provided. Use {remote_prompt} or 'use remote:<name>' in interactive shell."
                )
                return 1

            force_enabled = bool(self._get_arg(args, 'force', False))
            file_patterns = self.parse_files(self._get_arg(args, 'files'))
            dir_arg = self._get_arg(args, 'dir')
            binary_only = bool(self._get_arg(args, 'binary', False))
            step_window = resolve_step_window(self._get_arg(args, 't1'),
                                              self._get_arg(args, 't2'))
            if step_window and not binary_only:
                self.console.print(
                    "[red]Error:[/red] --t1/--t2 select timesteps inside binary/, "
                    "so they need --binary. Nothing else in a case is written "
                    "per step."
                )
                return 1
            if binary_only and not dir_arg:
                # --binary on its own means binary/ alone, the way --files on its
                # own means the files alone.
                directories = ['binary']
            else:
                directories = [] if (file_patterns and not dir_arg) \
                    else self.parse_directories(dir_arg)
            remote = self.validate_remote(remote_name)
            if not remote:
                return 1
            remote_base = self.get_remote_base_path(remote, self._get_arg(args, 'remote_path'))
            wildcard = is_wildcard_case(case_selection)

            if wildcard:
                base_dir = self._get_cases_base_dir()
                cases = load_cases_from_directory(base_dir)
                if not cases:
                    self.console.print(
                        f"[red]Error:[/red] No cases found in .cases at {base_dir}"
                    )
                    return 1
                case_entries = self._normalize_case_entries(cases)
            else:
                if is_upload:
                    if not os.path.exists(case_selection):
                        self.console.print(
                            f"[red]Error:[/red] Local case path not found: {case_selection}"
                        )
                        return 1
                    if not os.path.isdir(case_selection):
                        self.console.print(
                            f"[red]Error:[/red] Local case path is not a directory: {case_selection}"
                        )
                        return 1
                else:
                    if not self._ensure_local_case_dir(case_selection, force_enabled):
                        return 1
                case_entries = self._build_single_case_entries(case_selection)

            state = self._build_transfer_state(
                direction,
                remote_name,
                remote_base,
                case_selection,
                case_entries,
                directories,
                force_enabled,
                wildcard,
                file_patterns,
                step_window,
            )
            self._save_transfer_state(state)

        remote = self.validate_remote(remote_name)
        if not remote:
            return 1

        if not case_entries:
            self.console.print(f"[red]Error:[/red] No case entries available for {target_label}.")
            return 1

        targets_per_case = len(directories) + (1 if file_patterns else 0)
        total_targets = len(case_entries) * targets_per_case
        remaining_targets = total_targets - len(completed_targets)
        resume_note = ' (resuming)' if resume_requested else ''

        self.console.print()
        self.console.print(f"[bold cyan]Case {action_label} Summary[/bold cyan]{resume_note}")
        self.console.print()

        table = Table(box=box.SIMPLE, show_header=True, header_style='bold yellow')
        table.add_column('Parameter', style='cyan')
        table.add_column('Value', style='white')
        table.add_row('Case Selection', case_selection)
        table.add_row('Cases', str(len(case_entries)))
        table.add_row('Remote Machine', remote_name)
        table.add_row('Remote Host', f"{remote['user']}@{remote['ip']}:{remote['port']}")
        table.add_row('Remote Base Path', remote_base)
        table.add_row('Directories', ', '.join(directories) or '(none)')
        if file_patterns:
            table.add_row('Files', ', '.join(file_patterns))
        if step_window:
            lo, hi = step_window
            table.add_row('Timesteps',
                          f"{lo:g}" if lo == hi else f"{lo:g} .. {hi:g}")
        table.add_row('Force Create Missing Dir', 'Yes' if force_enabled else 'No')
        if resume_requested:
            table.add_row('Completed Targets', str(len(completed_targets)))
            table.add_row('Remaining Targets', str(remaining_targets))
        self.console.print(table)
        self.console.print()

        try:
            ssh = SSHClientWrapper(
                host=remote['ip'],
                username=remote['user'],
                password=remote['password'],
                port=remote.get('port', 22)
            )

            self.console.print('[cyan]Connecting to remote server...[/cyan]')
            ssh.connect()
            self.console.print('[green]✓[/green] Connected successfully')
            self.console.print()

            success_count = len(completed_targets)
            all_targets: list[dict] = []
            for entry in case_entries:
                entry_path = entry.get('path')
                if not entry_path:
                    continue
                remote_case_path = self.construct_remote_case_path(remote_base, entry_path)
                for directory in directories:
                    all_targets.append({
                        'case_name': entry.get('name') or Path(entry_path).name,
                        'case_path': entry_path,
                        'remote_case_path': remote_case_path,
                        'directory': directory,
                        'kind': 'dir',
                        'key': self._target_key(entry_path, directory),
                    })
                if file_patterns:
                    all_targets.append({
                        'case_name': entry.get('name') or Path(entry_path).name,
                        'case_path': entry_path,
                        'remote_case_path': remote_case_path,
                        'directory': 'files',
                        'kind': 'files',
                        'key': self._target_key(entry_path, '__files__'),
                    })

            for idx, target in enumerate(all_targets, 1):
                if target['key'] in completed_targets:
                    continue

                if len(case_entries) > 1:
                    self.console.print(
                        f"[bold]Case {target['case_name']}[/bold] [cyan]{idx}/{len(all_targets)}[/cyan]"
                    )

                if target.get('kind') == 'files':
                    transfer = self.upload_files if is_upload else self.download_files
                    ok = transfer(
                        ssh,
                        target['remote_case_path'],
                        target['case_path'],
                        file_patterns,
                        force=force_enabled,
                    )
                elif step_window and target['directory'] == 'binary':
                    if is_upload:
                        ok = self.upload_binary_range(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                            force=force_enabled,
                        )
                    else:
                        ok = self.download_binary_range(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                        )
                elif is_upload:
                    ok = self.upload_directory(
                        ssh,
                        target['remote_case_path'],
                        target['case_path'],
                        target['directory'],
                        force=force_enabled,
                    )
                else:
                    ok = self.download_case_directory(
                        ssh,
                        target['remote_case_path'],
                        target['case_path'],
                        target['directory'],
                    )

                if ok:
                    success_count += 1
                    completed_targets.add(target['key'])
                    state['completed_targets'] = sorted(completed_targets)
                    self._save_transfer_state(state)

                if len(case_entries) > 1:
                    self.console.print()

            ssh.disconnect()
            self.console.print()

            all_completed = success_count == total_targets and total_targets > 0
            if all_completed:
                self.console.print(
                    f"[green]✓[/green] {action_label} complete: {success_count}/{total_targets} target(s)"
                )
                self._clear_transfer_state()
                return 0

            self.console.print(
                f"[yellow]Incomplete:[/yellow] {success_count}/{total_targets} target(s) finished. Use --resume to continue."
            )
            self._finalize_transfer_state(state, success=False)
            return 1

        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")
            if state is not None:
                self._finalize_transfer_state(state, success=False)
            return 1

    def validate_remote(self, remote_name: str) -> Optional[dict]:
        """
        Validate and retrieve remote configuration.

        Args:
            remote_name: Name of the remote machine

        Returns:
            Remote configuration dict or None if invalid
        """
        if not self.remote_config.remote_exists(remote_name):
            self.console.print(f"[red]Error:[/red] Remote '{remote_name}' not found.")
            return None

        return self.remote_config.get_remote(remote_name)

    def _get_cases_base_dir(self) -> Path:
        """Return directory used to resolve .cases for wildcard mode."""
        from src.cli.interactive import InteractiveShell

        if hasattr(InteractiveShell, "_instance") and InteractiveShell._instance:
            return InteractiveShell._instance._current_dir
        return Path.cwd()

    def validate_case_path(self, case_path: str) -> Optional[str]:
        """
        Validate and resolve case path.

        Args:
            case_path: Case path (relative or absolute)

        Returns:
            Absolute case path or None if invalid
        """
        if not case_path:
            self.console.print("[red]Error:[/red] Case path not provided.")
            return None

        case_path = os.path.expanduser(case_path)
        return case_path

    def parse_files(self, files_arg) -> List[str]:
        """Glob patterns for loose files to upload from the case root.

        `--files` on its own takes the defaults: the case definition and its
        settings, plus any othd maps. They are globs rather than <problem>.def and
        friends so the same defaults work whatever a case calls its problem.
        """
        if files_arg in (None, False):
            return []
        if files_arg is True:
            return list(DEFAULT_UPLOAD_FILES)
        patterns = [p.strip() for p in str(files_arg).split(",") if p.strip()]
        return patterns or list(DEFAULT_UPLOAD_FILES)

    def resolve_files(self, case_path: str, patterns: List[str]) -> List[str]:
        """Names in the case root matching `patterns`, de-duplicated and sorted.

        Only files directly in the case root: these are the small definition and
        map files that sit beside the data directories, and a recursive match
        would sweep up the very data --files exists to avoid.
        """
        root = Path(case_path)
        names = set()
        for pattern in patterns:
            for match in root.glob(pattern):
                if match.is_file() and match.parent == root:
                    names.add(match.name)
        return sorted(names)

    def parse_directories(self, dirs_arg: Optional[str]) -> List[str]:
        """
        Parse comma-separated directory list.

        Args:
            dirs_arg: Comma-separated string of directories

        Returns:
            List of directory names
        """
        if not dirs_arg:
            return ["othd_files", "oisd_files", "binary"]

        dirs = [d.strip() for d in dirs_arg.split(",") if d.strip()]
        return dirs if dirs else ["othd_files", "oisd_files", "binary"]

    def get_remote_base_path(self, remote: dict, override_path: Optional[str]) -> str:
        """
        Determine remote base path.

        Args:
            remote: Remote configuration dict
            override_path: Optional override path

        Returns:
            Remote base path
        """
        if override_path:
            return os.path.expanduser(override_path)

        # Use remote's configured path
        remote_path = remote.get("path")
        if remote_path:
            return remote_path

        # Default to home directory
        return "~"

    def construct_remote_case_path(
        self,
        remote_base: str,
        case_path: str
    ) -> str:
        """
        Construct remote case path.

        Args:
            remote_base: Remote base path
            case_path: Local case path (to extract case name)

        Returns:
            Remote case path
        """
        case_name = os.path.basename(case_path.rstrip("/"))
        return f"{remote_base}/{case_name}"

    def resolve_remote_files(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        patterns: List[str],
    ) -> List[str]:
        """Names in the remote case root matching `patterns`, de-duplicated and sorted.

        The listing has to come from the remote, so this is the mirror of
        resolve_files() rather than a shared helper: subdirectories are dropped so
        a name like `binary` never gets pulled as if it were a file.
        """
        from fnmatch import fnmatch

        try:
            entries = ssh.list_remote_dir(remote_case_path)
        except Exception as exc:
            self.console.print(f"[yellow]Warning:[/yellow] Could not list {remote_case_path}: {exc}")
            return []
        names = {name for name in entries
                 if any(fnmatch(name, pattern) for pattern in patterns)}
        return sorted(name for name in names
                      if not ssh.remote_is_dir(f"{remote_case_path}/{name}"))

    def download_files(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        patterns: List[str],
        force: bool = False
    ) -> bool:
        """Download loose files from the remote case root into the local case root.

        Matching nothing is reported and treated as done: a remote case that has
        no maps yet is not a failure.
        """
        if not ssh.remote_path_exists(remote_case_path):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote directory not found: {remote_case_path}"
            )
            return False

        names = self.resolve_remote_files(ssh, remote_case_path, patterns)
        if not names:
            self.console.print(
                f"[yellow]Warning:[/yellow] No files matching {', '.join(patterns)} "
                f"in {remote_case_path}"
            )
            return True

        os.makedirs(local_case_path, exist_ok=True)
        self.console.print(f"[cyan]Downloading:[/cyan] {len(names)} file(s)")
        for name in names:
            ssh.download_file(f"{remote_case_path}/{name}",
                              os.path.join(local_case_path, name))
            self.console.print(f"    [dim]{name}[/dim]")
        self.console.print(
            f"[green]✓[/green] Downloaded {len(names)} file(s) to {local_case_path}"
        )
        return True

    def upload_files(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        patterns: List[str],
        force: bool = False
    ) -> bool:
        """Upload loose files from the case root into the remote case root.

        Returns False only when the case directory itself could not be used;
        matching nothing is reported and treated as done, since a case that has
        no maps yet is not a failure.
        """
        names = self.resolve_files(local_case_path, patterns)
        if not names:
            self.console.print(
                f"[yellow]Warning:[/yellow] No files matching {', '.join(patterns)} "
                f"in {local_case_path}"
            )
            return True

        if not ssh.remote_path_exists(remote_case_path):
            if not force:
                self.console.print(
                    f"[yellow]Warning:[/yellow] Remote directory not found: {remote_case_path}"
                )
                self.console.print("[dim]Use --force to create remote directories[/dim]")
                return False
            self.console.print(f"[cyan]Creating:[/cyan] Remote directory {remote_case_path}")
            if not ssh.make_remote_dir(remote_case_path):
                self.console.print(
                    f"[red]Error:[/red] Failed to create remote directory: {remote_case_path}"
                )
                return False

        self.console.print(f"[cyan]Uploading:[/cyan] {len(names)} file(s)")
        total_bytes = sum(os.path.getsize(os.path.join(local_case_path, n)) for n in names)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Transferring files...", total=total_bytes or None)
            done = 0
            for name in names:
                local_file = os.path.join(local_case_path, name)
                ssh.upload_file(local_file, f"{remote_case_path}/{name}")
                done += os.path.getsize(local_file)
                progress.update(task, completed=done, description=f"Transferred {name}")

        self.console.print(
            f"[green]✓[/green] Uploaded {len(names)} file(s) to {remote_case_path}"
        )
        for name in names:
            self.console.print(f"    [dim]{name}[/dim]")
        return True

    def upload_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str,
        force: bool = False
    ) -> bool:
        """
        Upload a single directory from local case to remote case.

        Args:
            ssh: SSH client wrapper
            remote_case_path: Destination case path on remote
            local_case_path: Source local case path
            directory_name: Name of directory to upload (e.g., "othd_files")
            force: Create remote directory if it doesn't exist

        Returns:
            True if successful, False otherwise
        """
        local_dir = os.path.join(local_case_path, directory_name)
        remote_dir = f"{remote_case_path}/{directory_name}"

        # Check if local source directory exists
        if not os.path.exists(local_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local directory not found: {local_dir}"
            )
            return False

        if not os.path.isdir(local_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local path is not a directory: {local_dir}"
            )
            return False

        # Check/create remote destination directory
        if not ssh.remote_path_exists(remote_dir):
            if force:
                # Try to create the remote directory
                self.console.print(
                    f"[cyan]Creating:[/cyan] Remote directory {remote_dir}"
                )
                if not ssh.make_remote_dir(remote_dir):
                    self.console.print(
                        f"[red]Error:[/red] Failed to create remote directory: {remote_dir}"
                    )
                    return False
                self.console.print(
                    f"[green]✓[/green] Created remote directory: {remote_dir}"
                )
            else:
                self.console.print(
                    f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
                )
                self.console.print(
                    f"[dim]Use --force to create remote directories[/dim]"
                )
                return False

        if not ssh.remote_is_dir(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote path is not a directory: {remote_dir}"
            )
            return False

        self.console.print(f"[cyan]Uploading:[/cyan] {directory_name}")

        try:
            total_bytes = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(local_dir)
                for f in files
            )

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(
                    f"Transferring {directory_name}...",
                    total=total_bytes or None,
                )

                state = {"done": 0, "last": 0}

                def update_progress(transferred, _file_total):
                    if transferred < state["last"]:
                        state["done"] += state["last"]
                    state["last"] = transferred
                    progress.update(task, completed=state["done"] + transferred)

                files_count = ssh.upload_directory(
                    local_dir,
                    remote_dir,
                    callback=update_progress,
                )

                progress.update(task, completed=total_bytes)

            self.console.print(
                f"[green]✓[/green] Uploaded {files_count} files to {remote_dir}"
            )
            return True

        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to upload {directory_name}: {e}")
            return False

    def download_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str,
        force: bool = False,
    ) -> bool:
        """Backward-compatible alias used by older tests/imports."""
        return self.upload_directory(ssh, remote_case_path, local_case_path, directory_name, force=force)

    def upload_binary_range(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        window: Optional[tuple],
        force: bool = False,
    ) -> bool:
        """Upload binary/, restricted to the timesteps inside `window`.

        File by file rather than whole-directory, because that is what a window
        means: a case's binary/ is the bulk of it, and the point of naming a
        time range is not to move the rest.
        """
        local_dir = os.path.join(local_case_path, "binary")
        remote_dir = f"{remote_case_path}/binary"

        if not os.path.isdir(local_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local directory not found: {local_dir}"
            )
            return False

        names = [n for n in os.listdir(local_dir)
                 if os.path.isfile(os.path.join(local_dir, n))]
        kept, no_step = select_steps(names, window)
        if not self._report_selection(kept, no_step, window, local_dir):
            return True

        if not ssh.remote_path_exists(remote_dir):
            if not force:
                self.console.print(
                    f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
                )
                self.console.print("[dim]Use --force to create remote directories[/dim]")
                return False
            self.console.print(f"[cyan]Creating:[/cyan] Remote directory {remote_dir}")
            if not ssh.make_remote_dir(remote_dir):
                self.console.print(
                    f"[red]Error:[/red] Failed to create remote directory: {remote_dir}"
                )
                return False

        total_bytes = sum(os.path.getsize(os.path.join(local_dir, n)) for n in kept)
        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("Transferring binary...", total=total_bytes or None)
                done = 0
                for name in kept:
                    local_file = os.path.join(local_dir, name)
                    ssh.upload_file(local_file, f"{remote_dir}/{name}")
                    done += os.path.getsize(local_file)
                    progress.update(task, completed=done, description=f"Transferred {name}")
            self.console.print(
                f"[green]\u2713[/green] Uploaded {len(kept)} file(s) to {remote_dir}"
            )
            return True
        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to upload binary: {e}")
            return False

    def download_binary_range(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        window: Optional[tuple],
    ) -> bool:
        """Download binary/, restricted to the timesteps inside `window`."""
        remote_dir = f"{remote_case_path}/binary"
        local_dir = os.path.join(local_case_path, "binary")

        if not ssh.remote_path_exists(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
            )
            return False
        if not ssh.remote_is_dir(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote path is not a directory: {remote_dir}"
            )
            return False

        try:
            entries = ssh.list_remote_dir(remote_dir)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
            return False

        # Only names carrying a step can be placed in the window, and those are
        # never directories, so the remote stat per entry that resolve_remote_files
        # does is not needed here.
        kept, no_step = select_steps(entries, window)
        if not self._report_selection(kept, no_step, window, remote_dir):
            return True

        os.makedirs(local_dir, exist_ok=True)
        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("Transferring binary...", total=None)
                state = {"done": 0, "last": 0}

                def update_progress(transferred, _file_total):
                    if transferred < state["last"]:
                        state["done"] += state["last"]
                    state["last"] = transferred
                    progress.update(task, completed=state["done"] + transferred)

                for name in kept:
                    ssh.download_file(f"{remote_dir}/{name}",
                                      os.path.join(local_dir, name),
                                      callback=update_progress)
            self.console.print(
                f"[green]\u2713[/green] Downloaded {len(kept)} file(s) to {local_dir}"
            )
            return True
        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to download binary: {e}")
            return False

    def _report_selection(self, kept, no_step, window, where) -> bool:
        """Say what the window picked out. False when there is nothing to move."""
        if window:
            lo, hi = window
            span = f"step {lo:g}" if lo == hi else f"steps {lo:g}..{hi:g}"
            self.console.print(f"[cyan]Selecting:[/cyan] {span} in binary/")
        if no_step:
            self.console.print(
                f"[dim]    skipping {len(no_step)} file(s) with no timestep in "
                f"the name[/dim]"
            )
        if not kept:
            self.console.print(
                f"[yellow]Warning:[/yellow] No files in that step range in {where}"
            )
            return False
        return True

    def download_case_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str,
    ) -> bool:
        """
        Download a single directory from a remote case to the local case.

        Args:
            ssh: SSH client wrapper
            remote_case_path: Source case path on remote
            local_case_path: Destination local case path
            directory_name: Name of directory to download (e.g., "othd_files")

        Returns:
            True if successful, False otherwise
        """
        remote_dir = f"{remote_case_path}/{directory_name}"
        local_dir = os.path.join(local_case_path, directory_name)

        # The remote source directory must exist; we cannot create it.
        if not ssh.remote_path_exists(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
            )
            return False

        if not ssh.remote_is_dir(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote path is not a directory: {remote_dir}"
            )
            return False

        self.console.print(f"[cyan]Downloading:[/cyan] {directory_name}")

        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                # Remote total size is unknown up front, so track bytes as they arrive.
                task = progress.add_task(
                    f"Transferring {directory_name}...",
                    total=None,
                )

                state = {"done": 0, "last": 0}

                def update_progress(transferred, _file_total):
                    if transferred < state["last"]:
                        state["done"] += state["last"]
                    state["last"] = transferred
                    progress.update(task, completed=state["done"] + transferred)

                files_count = ssh.download_directory(
                    remote_dir,
                    local_dir,
                    callback=update_progress,
                )

            self.console.print(
                f"[green]✓[/green] Downloaded {files_count} files to {local_dir}"
            )
            return True

        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to download {directory_name}: {e}")
            return False

    def execute_upload(self, args) -> int:
        """
        Execute case upload command.

        Args:
            args: Parsed arguments

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        return self._execute_transfer(args, 'upload')

        if hasattr(args, "help") and args.help:
            show_upload_help()
            return 0

        if hasattr(args, "examples") and args.examples:
            show_upload_help()
            return 0

        # Validate case path
        case_path = self.validate_case_path(args.case)
        if not case_path:
            return 1

        if not args.to:
            self.console.print(
                "[red]Error:[/red] Remote machine not provided. Use --to or 'use remote:<name>' in interactive shell."
            )
            return 1

        force_enabled = bool(getattr(args, "force", False))

        # Validate remote
        remote = self.validate_remote(args.to)
        if not remote:
            return 1

        # Parse directories to upload
        directories = self.parse_directories(args.dir)

        # Get remote base path
        remote_base = self.get_remote_base_path(remote, args.remote_path)

        # Wildcard mode: iterate all cases from .cases
        if is_wildcard_case(case_path):
            base_dir = self._get_cases_base_dir()
            cases = load_cases_from_directory(base_dir)
            if not cases:
                self.console.print(
                    f"[red]Error:[/red] No cases found in .cases at {base_dir}"
                )
                return 1

            self.console.print()
            self.console.print(
                f"[bold cyan]Case Upload Summary[/bold cyan] [dim](wildcard mode: {len(cases)} cases)[/dim]"
            )
            self.console.print()

            table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Case Selection", "* (all cases from .cases)")
            table.add_row("Cases Base Dir", str(base_dir))
            table.add_row("Remote Machine", args.to)
            table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
            table.add_row("Remote Base Path", remote_base)
            table.add_row("Directories", ", ".join(directories))
            table.add_row("Force Create Missing Dir", "Yes" if force_enabled else "No")
            self.console.print(table)
            self.console.print()

            try:
                ssh = SSHClientWrapper(
                    host=remote["ip"],
                    username=remote["user"],
                    password=remote["password"],
                    port=remote.get("port", 22)
                )

                self.console.print("[cyan]Connecting to remote server...[/cyan]")
                ssh.connect()
                self.console.print("[green]✓[/green] Connected successfully")
                self.console.print()

                success_count = 0
                total_targets = len(cases) * len(directories)

                for idx, case_entry in enumerate(cases, 1):
                    entry_path = case_entry.get("path")
                    entry_name = case_entry.get("name", f"case-{idx}")

                    self.console.print(
                        f"[bold]Case {idx}/{len(cases)}:[/bold] [cyan]{entry_name}[/cyan]"
                    )

                    if not entry_path:
                        self.console.print("[yellow]Warning:[/yellow] Missing case path in .cases entry")
                        self.console.print()
                        continue

                    if not os.path.exists(entry_path) or not os.path.isdir(entry_path):
                        self.console.print(
                            f"[yellow]Warning:[/yellow] Local case directory not found: {entry_path}"
                        )
                        self.console.print()
                        continue

                    remote_case_path = self.construct_remote_case_path(remote_base, entry_path)
                    self.console.print(f"[dim]Remote case path: {remote_case_path}[/dim]")

                    for directory in directories:
                        if self.upload_directory(
                            ssh,
                            remote_case_path,
                            entry_path,
                            directory,
                            force=force_enabled
                        ):
                            success_count += 1
                    self.console.print()

                ssh.disconnect()
                self.console.print(
                    f"[green]✓[/green] Upload complete: {success_count}/{total_targets} directories"
                )
                return 0 if success_count > 0 else 1

            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                return 1

        if not os.path.exists(case_path):
            self.console.print(f"[red]Error:[/red] Local case path not found: {case_path}")
            return 1
        if not os.path.isdir(case_path):
            self.console.print(f"[red]Error:[/red] Local case path is not a directory: {case_path}")
            return 1

        # Construct remote case path
        remote_case_path = self.construct_remote_case_path(remote_base, case_path)

        # Show summary
        self.console.print()
        self.console.print("[bold cyan]Case Upload Summary[/bold cyan]")
        self.console.print()

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Local Case Path", case_path)
        table.add_row("Remote Machine", args.to)
        table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
        table.add_row("Remote Case Path", remote_case_path)
        table.add_row("Directories", ", ".join(directories))
        table.add_row("Force Create Missing Dir", "Yes" if force_enabled else "No")

        self.console.print(table)
        self.console.print()

        # Connect to remote and upload
        try:
            ssh = SSHClientWrapper(
                host=remote["ip"],
                username=remote["user"],
                password=remote["password"],
                port=remote.get("port", 22)
            )

            self.console.print("[cyan]Connecting to remote server...[/cyan]")
            ssh.connect()
            self.console.print("[green]✓[/green] Connected successfully")
            self.console.print()

            # Upload each directory
            success_count = 0
            for directory in directories:
                if self.upload_directory(
                    ssh,
                    remote_case_path,
                    case_path,
                    directory,
                    force=force_enabled
                ):
                    success_count += 1

            ssh.disconnect()
            self.console.print()
            self.console.print(
                f"[green]✓[/green] Upload complete: {success_count}/{len(directories)} directories"
            )
            return 0 if success_count > 0 else 1

        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")
            return 1

    def execute_download(self, args) -> int:
        """
        Execute case download command (remote -> local).

        Args:
            args: Parsed arguments

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        return self._execute_transfer(args, 'download')

        if getattr(args, "help", False) or getattr(args, "examples", False):
            show_download_help()
            return 0

        # Validate case path (destination)
        case_path = self.validate_case_path(args.case)
        if not case_path:
            return 1

        remote_name = getattr(args, "from_remote", None)
        if not remote_name:
            self.console.print(
                "[red]Error:[/red] Remote machine not provided. Use --from or 'use remote:<name>' in interactive shell."
            )
            return 1

        force_enabled = bool(getattr(args, "force", False))

        # Validate remote
        remote = self.validate_remote(remote_name)
        if not remote:
            return 1

        # Parse directories to download
        directories = self.parse_directories(args.dir)

        # Get remote base path
        remote_base = self.get_remote_base_path(remote, args.remote_path)

        # Wildcard mode: iterate all cases from .cases
        if is_wildcard_case(case_path):
            base_dir = self._get_cases_base_dir()
            cases = load_cases_from_directory(base_dir)
            if not cases:
                self.console.print(
                    f"[red]Error:[/red] No cases found in .cases at {base_dir}"
                )
                return 1

            self.console.print()
            self.console.print(
                f"[bold cyan]Case Download Summary[/bold cyan] [dim](wildcard mode: {len(cases)} cases)[/dim]"
            )
            self.console.print()

            table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Case Selection", "* (all cases from .cases)")
            table.add_row("Cases Base Dir", str(base_dir))
            table.add_row("Remote Machine", remote_name)
            table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
            table.add_row("Remote Base Path", remote_base)
            table.add_row("Directories", ", ".join(directories))
            table.add_row("Create Missing Local Dir", "Yes" if force_enabled else "No")
            self.console.print(table)
            self.console.print()

            try:
                ssh = SSHClientWrapper(
                    host=remote["ip"],
                    username=remote["user"],
                    password=remote["password"],
                    port=remote.get("port", 22)
                )

                self.console.print("[cyan]Connecting to remote server...[/cyan]")
                ssh.connect()
                self.console.print("[green]✓[/green] Connected successfully")
                self.console.print()

                success_count = 0
                total_targets = len(cases) * len(directories)

                for idx, case_entry in enumerate(cases, 1):
                    entry_path = case_entry.get("path")
                    entry_name = case_entry.get("name", f"case-{idx}")

                    self.console.print(
                        f"[bold]Case {idx}/{len(cases)}:[/bold] [cyan]{entry_name}[/cyan]"
                    )

                    if not entry_path:
                        self.console.print("[yellow]Warning:[/yellow] Missing case path in .cases entry")
                        self.console.print()
                        continue

                    if not self._ensure_local_case_dir(entry_path, force_enabled):
                        self.console.print()
                        continue

                    remote_case_path = self.construct_remote_case_path(remote_base, entry_path)
                    self.console.print(f"[dim]Remote case path: {remote_case_path}[/dim]")

                    for directory in directories:
                        if self.download_case_directory(
                            ssh,
                            remote_case_path,
                            entry_path,
                            directory,
                        ):
                            success_count += 1
                    self.console.print()

                ssh.disconnect()
                self.console.print(
                    f"[green]✓[/green] Download complete: {success_count}/{total_targets} directories"
                )
                return 0 if success_count > 0 else 1

            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                return 1

        # Single-case mode
        if not self._ensure_local_case_dir(case_path, force_enabled):
            return 1

        # Construct remote case path
        remote_case_path = self.construct_remote_case_path(remote_base, case_path)

        # Show summary
        self.console.print()
        self.console.print("[bold cyan]Case Download Summary[/bold cyan]")
        self.console.print()

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Local Case Path", case_path)
        table.add_row("Remote Machine", remote_name)
        table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
        table.add_row("Remote Case Path", remote_case_path)
        table.add_row("Directories", ", ".join(directories))
        table.add_row("Create Missing Local Dir", "Yes" if force_enabled else "No")

        self.console.print(table)
        self.console.print()

        # Connect to remote and download
        try:
            ssh = SSHClientWrapper(
                host=remote["ip"],
                username=remote["user"],
                password=remote["password"],
                port=remote.get("port", 22)
            )

            self.console.print("[cyan]Connecting to remote server...[/cyan]")
            ssh.connect()
            self.console.print("[green]✓[/green] Connected successfully")
            self.console.print()

            # Download each directory
            success_count = 0
            for directory in directories:
                if self.download_case_directory(
                    ssh,
                    remote_case_path,
                    case_path,
                    directory,
                ):
                    success_count += 1

            ssh.disconnect()
            self.console.print()
            self.console.print(
                f"[green]✓[/green] Download complete: {success_count}/{len(directories)} directories"
            )
            return 0 if success_count > 0 else 1

        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")
            return 1

    def _ensure_local_case_dir(self, case_path: str, force: bool) -> bool:
        """
        Ensure the local destination case directory exists.

        With force, create it (and parents) if missing; otherwise warn and skip.
        Returns True if the directory is present (or was created), else False.
        """
        if os.path.isdir(case_path):
            return True
        if os.path.exists(case_path):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local case path is not a directory: {case_path}"
            )
            return False
        if force:
            try:
                os.makedirs(case_path, exist_ok=True)
                self.console.print(f"[green]✓[/green] Created local case directory: {case_path}")
                return True
            except OSError as e:
                self.console.print(
                    f"[red]Error:[/red] Failed to create local case directory {case_path}: {e}"
                )
                return False
        self.console.print(
            f"[yellow]Warning:[/yellow] Local case directory not found: {case_path}"
        )
        self.console.print("[dim]Use --force to create the local directory[/dim]")
        return False


# Backward-compatible alias for older imports/tests.
CaseDownloadCommand = CaseUploadCommand


# Create command instance
command = CaseUploadCommand()


def execute_upload(args) -> int:
    """Execute upload command."""
    return command.execute_upload(args)


def execute_download(args) -> int:
    """Execute download command (remote -> local)."""
    return command.execute_download(args)
