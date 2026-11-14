"""Case upload command implementation."""

import json
import os
import re
import sys
import time
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
from . import budget
from .history import (HistoryTransferMixin, HISTORY_SETS, LIVE, history_label, history_sets,
                      history_target)

# Loose files worth carrying with a case: what defines the run, and the othd maps
# that keep its history readable once the mesh file is gone. Globs, so they hold
# whatever the case calls its problem.
DEFAULT_UPLOAD_FILES = ["simflow.config", "*.def", "*.geo", "*.map"]

# The transfer targets for `case upload rst|input`: not a directory of the case.
# rst: the restart files of some steps in its run directory. input: what the
# preprocessor reads, which every launch of mpiSimflow runs again (solStart.c)
# -- <problem>.def and the files it names with File(...) -- so a restart needs
# these unchanged, while the .sgd/.cas it writes from them are rebuilt anyway.
RST_TARGET = '__rst__'
INPUT_TARGET = '__input__'
RESTART_TARGETS = {'rst': RST_TARGET}
RESTART_KIND = {target: kind for kind, target in RESTART_TARGETS.items()}
TARGET_LABEL = {RST_TARGET: 'restart files (.rst)',
                INPUT_TARGET: 'input files (.def and its File(...))'}

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


def select_steps(names: List[str], window: Optional[tuple],
                 freq: Optional[int] = None) -> tuple:
    """Split `names` into (kept, no_step) for a step window and frequency.

    Without either everything is kept. With one, a file is kept when its step
    falls inside the window and is a multiple of freq -- the same thinning as
    `field` sweeps give --freq. A file with no step at all is set aside rather
    than silently swept along: asking for one timestep should not drag the
    whole post-processing script collection across the wire.
    """
    if window is None and not freq:
        return sorted(names), []
    lo, hi = window if window else (float('-inf'), float('inf'))
    kept, no_step = [], []
    for name in names:
        step = step_of(name)
        if step is None:
            no_step.append(name)
        elif lo <= step <= hi and (not freq or step % freq == 0):
            kept.append(name)
    return sorted(kept), sorted(no_step)


def select_missing(names: List[str], here: Dict[str, int], there: Dict[str, int]) -> tuple:
    """(missing, resized): the names in `here` ({name: size} on the sending
    side) that `there` lacks, and those it holds at another size -- a copy cut
    short by an interrupted transfer is no more there than a lost one."""
    missing = [n for n in names if n not in there]
    resized = [n for n in names if n in there and there[n] != here[n]]
    return missing, resized


def select_restart(names: List[str], problem: str, window: Optional[tuple],
                   nsg: Optional[int]) -> tuple:
    """The .rst files of the steps in `window`: (complete, incomplete).

    A restart from step T reads one {problem}.T_<k>.rst per subgrid -- nsg of
    them (simflow.config) -- so a step is complete with all nsg (any at all
    when nsg is not known). Both results are dicts {step: [names]}. No window
    means every step.
    """
    lo, hi = window if window else (float('-inf'), float('inf'))
    pattern = re.compile(re.escape(problem) + r"\.(\d+)_(\d+)\.rst$")
    steps: dict = {}
    for name in names:
        match = pattern.match(name)
        if match and lo <= int(match.group(1)) <= hi:
            steps.setdefault(int(match.group(1)), []).append(name)
    complete, incomplete = {}, {}
    for step, files in sorted(steps.items()):
        ok = not nsg or len(files) == nsg
        (complete if ok else incomplete)[step] = sorted(files, key=_restart_order)
    return complete, incomplete


def def_inputs(def_path) -> List[str]:
    """What a .def names with File(...), once each, in order (commented lines
    skipped): the mesh, the boundary node and surface lists, and any other
    file the preprocessor reads. Paths are relative to the case."""
    from src.core.def_config import DefConfig
    return DefConfig(def_path).file_references


def _by_directory(names: List[str]) -> dict:
    """{directory relative to the case: [file names in it]}, '' for the root."""
    groups: dict = {}
    for name in names:
        sub, base = os.path.split(os.path.normpath(name))
        groups.setdefault(sub, []).append(base)
    return groups


def _restart_order(name: str):
    """The .rst files by subgrid number."""
    match = re.search(r"_(\d+)\.rst$", name)
    return int(match.group(1)) if match else 0


def show_upload_help() -> None:
    """Print help for case upload command."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Upload Command{Colors.RESET}

Upload case directories from local machine to a remote server.

Whatever is carried, the case's notes ({Colors.CYAN}.casestatus.md{Colors.RESET}, `case status`) go
too: copied if the remote has none, else merged -- the notes of the copy
changed last, the log lines of both, in time order.
So do the restarts ({Colors.CYAN}.restarts{Colors.RESET}, `case organise history`): copied, or
the remote gets the restarts it lacks.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case upload [{Colors.YELLOW}case{Colors.RESET}] --remote {Colors.YELLOW}REMOTE{Colors.RESET} [options]
    flexflow case upload plt [{Colors.YELLOW}case{Colors.RESET}] [--t1 STEP] [--t2 STEP] [options]
    flexflow case upload rst [{Colors.YELLOW}case{Colors.RESET}] [--t1 STEP] [--t2 STEP] [options]
    flexflow case upload input [{Colors.YELLOW}case{Colors.RESET}] [options]
    flexflow case upload history [{Colors.YELLOW}case{Colors.RESET}] [--archive] [--cleaned] [--compiled] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}plt{Colors.RESET}                    The binary PLTs in binary/ only -- with --t1/--t2,
                           only the timesteps in that range (`binary`, the
                           old word for it, still works)
    {Colors.YELLOW}rst{Colors.RESET}                    The nsg <problem>.<step>_<k>.rst of every step (or
                           --t1..--t2) in the run directory
    {Colors.YELLOW}input{Colors.RESET}                  <problem>.def and every file it names with File(...):
                           the mesh, .nbc, .srf ... (what a restart needs unchanged)
    {Colors.YELLOW}history{Colors.RESET}                The OTHD/OISD history (`case organise history`):
                           archive/, cleaned/ and the compiled file
    {Colors.YELLOW}case{Colors.RESET}                   Local case directory path (use * for all cases in .cases.yml)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--remote REMOTE{Colors.RESET}        Remote machine name (required)
    {Colors.YELLOW}--dir DIRS{Colors.RESET}             Comma-separated directories to upload
                           (default: othd_files,oisd_files,binary)
    {Colors.YELLOW}--files [PATTERNS]{Colors.RESET}     Loose files from the case root, as comma-separated
                           globs (default: simflow.config,*.def,*.geo,*.map)
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              plt/rst: first timestep (alone: only that step)
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              plt/rst: last timestep
    {Colors.YELLOW}--freq N{Colors.RESET}               plt/rst: only steps that are multiples of N
    {Colors.YELLOW}--missing{Colors.RESET}              plt/rst: only the files the remote lacks (or holds at another size)
    {Colors.YELLOW}--fit{Colors.RESET}                  plt: only the steps that fit in the session's time left
    {Colors.YELLOW}--no-time-check{Colors.RESET}        plt: do not check against the session timeout
    {Colors.YELLOW}--archive{Colors.RESET}              history: only archive/ (combinable; none: all three)
    {Colors.YELLOW}--cleaned{Colors.RESET}              history: only cleaned/
    {Colors.YELLOW}--compiled{Colors.RESET}             history: only the compiled file
    {Colors.YELLOW}--live{Colors.RESET}                 history: the run directory's .othd/.oisd as they are now,
                           while a job is still writing them (a snapshot, not compared)
    {Colors.YELLOW}--remote-path PATH{Colors.RESET}     The folder holding the cases on the remote; the case goes to
                         PATH/<case>. Default: the remote's folder in the case folder's
                         .cases.yml (remotes: {{NAME: DIR}}), else `remote set-path`
    {Colors.YELLOW}--force{Colors.RESET}                Create remote directories if they do not exist
    {Colors.YELLOW}--resume{Colors.RESET}               Resume the last interrupted upload
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Uploads one or more case directories to a configured remote server via
    SFTP. The remote server must be registered with 'remote add'.

    Use 'use remote:<name>' in the interactive shell to set a default remote
    so --remote can be omitted.

    Wildcard mode ('case upload *') uploads all cases listed in the .cases.yml
    file in the current directory.

{Colors.BOLD}CHECKED COPIES:{Colors.RESET}
    Every file is sent the way `auto apply` sends it: to a temporary name
    (.<name>.part), compared with the local file by size and md5, and only
    then renamed to its real name. A copy that differs or was cut short is
    removed and the upload stops with an error; an older copy under the real
    name is left as it was. A remote without md5sum is compared by size
    only, and the last line of the upload says so.

    Each checked file is written to <folder of cases>/auto_logs/ledger.json
    (size, md5, when the local file was written, where the copy is), the
    record `auto` keeps of what is safely on the remote.

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
    already have. {Colors.YELLOW}case upload plt{Colors.RESET} carries that directory alone; with
    {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} it carries only the steps in the range, matching them
    on the number in the filename (riser.5000.plt, and the .vtu sidecars beside
    it). A file with no step in its name -- a script, a summary table -- is left
    where it is, and the count of those is reported.

    The two flags read as they do everywhere else in FlexFlow: both bounds make
    a range, one alone names that single step. They need {Colors.YELLOW}plt{Colors.RESET} or {Colors.YELLOW}rst{Colors.RESET},
    since nothing else in a case is written per step. The t1/t2 context
    supplies them: {Colors.DIM}use t1:1000 t2:5000{Colors.RESET}, then {Colors.DIM}case upload plt CS4SG1U1{Colors.RESET}.

    {Colors.YELLOW}--missing{Colors.RESET} carries only the selected files the remote binary/ lacks,
    or holds at another size (a copy an interrupted transfer cut short), and
    says how many were already there. It compares names and sizes, not
    contents, and goes with --t1/--t2.

{Colors.BOLD}RESTART FILES:{Colors.RESET}
    To restart a run from step T the remote run directory needs one
    <problem>.T_<k>.rst per subgrid. {Colors.YELLOW}case upload rst --t1 T{Colors.RESET} sends them from
    the local run directory (simflow.config 'dir') to the same directory under
    the remote case; without --t1/--t2 every step there is. A step with fewer
    .rst files than nsg cannot restart a run: it is reported and not sent.

    Every launch of mpiSimflow runs the preprocessor again, which reads
    <problem>.def and the files it names and rewrites the .sgd/.cas from them
    -- so those are not needed, but the inputs are, unchanged: the .rst only
    fits the mesh it was written on. {Colors.YELLOW}case upload input{Colors.RESET} sends the .def and
    every File(...) in it, at the same paths under the remote case. If one is
    missing nothing is sent. simflow.config is not among them, so the remote's
    restart settings stay as they are (--files carries it).

{Colors.BOLD}SESSION TIMEOUT:{Colors.RESET}
    In the shell, plt is set against the time the session has left, at
    {Colors.YELLOW}set transfer_speed{Colors.RESET} Mbps (default 10). When it will not finish, the
    steps that fit are offered as --t2: send all anyway, only those, or stop.
    The rest goes later with the next --t1, or --missing. {Colors.YELLOW}--fit{Colors.RESET} takes
    the cut without asking. A finished transfer prints the rate it reached.

{Colors.BOLD}LOGIN NODES:{Colors.RESET}
    SFTP holds a core near 100% for as long as a transfer runs, and a login
    node's watchdog kills that (and may lock the account). On a host named
    login* outside a Slurm job, every transfer is held under
    {Colors.YELLOW}set login_cpu_limit{Colors.RESET} % of a core (default 70; 0: no limit); it
    says so once when it starts pausing. FLEXFLOW_LOGIN_NODE=1/0 overrides
    the detection.

{Colors.BOLD}HISTORY:{Colors.RESET}
    {Colors.YELLOW}case upload history{Colors.RESET} carries what `case organise history` keeps, in
    othd_files/ and oisd_files/ alike: archive/{{problem}}N, cleaned/{{problem}}N
    and the compiled {{problem}}.othd|oisd. {Colors.YELLOW}--archive{Colors.RESET}, {Colors.YELLOW}--cleaned{Colors.RESET} and
    {Colors.YELLOW}--compiled{Colors.RESET} pick sets (combinable); without one all three go.
    Parts still in the old flat layout (othd_files/{{problem}}N) go with
    --archive, to the same place. problem comes from the local simflow.config.

    A file replaces the one of its name on the other side, except an archived
    run that is already there at the same size: those never change. Nothing
    is deleted, so a prune on one side is not repeated on the other.

    The compiled file goes after the runs. The readers (plot, case show, the
    web app) take it only while it is newer than archive/, cleaned/ and every
    run; so when it was not up to date where it came from, or the other side
    has runs it does not, it is made older than them there, and the readers
    take the runs until the next `case organise history --compile`.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    case upload history CS4SG1U1 --remote server
    case upload history CS4SG1U1 --remote server --cleaned --compiled
    case upload history CS4SG1U1 --remote server --live          # a running job's history, as it is now
    case upload plt CS4SG1U1 --remote server --t1 1000 --t2 5000
    case upload plt CS4SG1U1 --remote server --t1 5000
    case upload plt CS4SG1U1 --remote server --missing
    case upload input CS4SG1U1 --remote server
    case upload rst CS4SG1U1 --remote server --t1 4000
    case upload rst CS4SG1U1 --remote server --freq 1000 --missing   # every 1000 steps, what is not there
    case upload rst CS4SG1U1 --remote server --t1 3000 --t2 4000 --force
    case upload rst CS4SG1U1 --remote server
    case upload CS4SG1U1 --remote server --files
    case upload CS4SG1U1 --remote server --files "*.map"
    case upload * --remote server --files --force
    case upload CS4SG1U1 --remote server --dir binary --files

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set remote context:    use remote:myserver
    Then run:              case upload CS4SG1U1
""")


def show_download_help() -> None:
    """Print help for case download command."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Download Command{Colors.RESET}

Download case directories from a remote server to the local machine.

Whatever is carried, the case's notes ({Colors.CYAN}.casestatus.md{Colors.RESET}, `case status`) come
too: copied if there are none here, else merged -- the notes of the copy
changed last, the log lines of both (the job scripts' among them), in time
order.
So do the restarts ({Colors.CYAN}.restarts{Colors.RESET}, `case organise history`): copied, or
the restarts found only on the remote are added here.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case download [{Colors.YELLOW}case{Colors.RESET}] --remote {Colors.YELLOW}REMOTE{Colors.RESET} [options]
    flexflow case download plt [{Colors.YELLOW}case{Colors.RESET}] [--t1 STEP] [--t2 STEP] [--freq N] [options]
    flexflow case download rst [{Colors.YELLOW}case{Colors.RESET}] [--t1 STEP] [--t2 STEP] [options]
    flexflow case download input [{Colors.YELLOW}case{Colors.RESET}] [options]
    flexflow case download history [{Colors.YELLOW}case{Colors.RESET}] [--archive] [--cleaned] [--compiled] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}plt{Colors.RESET}                    binary/ only -- with --t1/--t2, only the timesteps
                           in that range
    {Colors.YELLOW}rst{Colors.RESET}                    The nsg <problem>.<step>_<k>.rst of every step (or
                           --t1..--t2) in the remote run directory
    {Colors.YELLOW}input{Colors.RESET}                  The remote <problem>.def and every file it names with
                           File(...): the mesh, .nbc, .srf ...
    {Colors.YELLOW}history{Colors.RESET}                The remote OTHD/OISD history (`case organise history`):
                           archive/, cleaned/ and the compiled file
    {Colors.YELLOW}case{Colors.RESET}                   Local case directory path (destination; use * for all cases in .cases.yml)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--remote REMOTE{Colors.RESET}        Remote machine name (required)
    {Colors.YELLOW}--dir DIRS{Colors.RESET}             Comma-separated directories to download
                           (default: othd_files,oisd_files,binary)
    {Colors.YELLOW}--files [PATTERNS]{Colors.RESET}     Loose files from the remote case root, as
                           comma-separated globs
                           (default: simflow.config,*.def,*.geo,*.map)
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              plt/rst: first timestep (alone: only that step)
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              plt/rst: last timestep
    {Colors.YELLOW}--missing{Colors.RESET}              plt/rst: only the files missing here (or at another size)
    {Colors.YELLOW}--fit{Colors.RESET}                  plt: only the steps that fit in the session's time left
    {Colors.YELLOW}--no-time-check{Colors.RESET}        plt: do not check against the session timeout
    {Colors.YELLOW}--archive{Colors.RESET}              history: only archive/ (combinable; none: all three)
    {Colors.YELLOW}--cleaned{Colors.RESET}              history: only cleaned/
    {Colors.YELLOW}--compiled{Colors.RESET}             history: only the compiled file
    {Colors.YELLOW}--freq N{Colors.RESET}               plt/rst: only steps that are multiples of N
    {Colors.YELLOW}--remote-path PATH{Colors.RESET}     The folder holding the cases on the remote; the case goes to
                         PATH/<case>. Default: the remote's folder in the case folder's
                         .cases.yml (remotes: {{NAME: DIR}}), else `remote set-path`
    {Colors.YELLOW}--force{Colors.RESET}                Create the local case directory if it does not exist
    {Colors.YELLOW}--resume{Colors.RESET}               Resume the last interrupted download
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Downloads one or more case directories from a configured remote server via
    SFTP into the local case directory. The remote server must be registered
    with 'remote add'.

    Use 'use remote:<name>' in the interactive shell to set a default remote
    so --remote can be omitted.

    Wildcard mode ('case download *') downloads all cases listed in the .cases.yml
    file in the current directory.

{Colors.BOLD}FILES:{Colors.RESET}
    --files fetches the small things that describe a case rather than its data:
    what defines the run, its settings, and any othd maps. Patterns are matched
    against the remote case root only -- subdirectories are left alone.

    Given {Colors.BOLD}without --dir{Colors.RESET} it downloads only those files, so a case's
    definition can be pulled without its data directories.

{Colors.BOLD}TIMESTEPS:{Colors.RESET}
    A case's binary/ is nearly all of its size, and most of it is timesteps you
    already have. {Colors.YELLOW}case download plt{Colors.RESET} carries that directory alone;
    with {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} it carries only the steps in the range, matching
    them on the number in the filename (riser.5000.plt, and the .vtu sidecars
    beside it). A file with no step in its name -- a script, a summary table --
    is left where it is, and the count of those is reported.

    The two flags read as they do everywhere else in FlexFlow: both bounds make
    a range, one alone names that single step. They need {Colors.YELLOW}plt{Colors.RESET} or {Colors.YELLOW}rst{Colors.RESET},
    since nothing else in a case is written per step. The t1/t2 context
    supplies them: {Colors.DIM}use t1:1000 t2:5000{Colors.RESET}, then {Colors.DIM}case download plt CS4SG1U1{Colors.RESET}.

    {Colors.YELLOW}--freq N{Colors.RESET} thins what is left to the steps that are multiples of N,
    as it does for `field` sweeps -- with or without a range. It also comes
    from the freq context, but only with plt.

    {Colors.YELLOW}--missing{Colors.RESET} carries only the selected files the local binary/ lacks,
    or holds at another size (a copy an interrupted transfer cut short), and
    says how many were already there. It compares names and sizes, not
    contents, and goes with --t1/--t2/--freq.

{Colors.BOLD}RESTART FILES:{Colors.RESET}
    {Colors.YELLOW}case download rst --t1 T{Colors.RESET} fetches the nsg files <problem>.T_<k>.rst
    from the remote run directory into the same directory here (created if
    needed); without --t1/--t2 every step there is. problem, dir and nsg are
    read from the remote simflow.config -- the run that wrote the files -- or
    the local one when the remote has none. A step short of .rst files is
    reported and not fetched.

    {Colors.YELLOW}case download input{Colors.RESET} fetches the remote <problem>.def and every file it
    names with File(...) -- the mesh and boundary files a restart needs
    unchanged -- at the same paths here. If one is missing on the remote,
    nothing is fetched.

{Colors.BOLD}SESSION TIMEOUT:{Colors.RESET}
    In the shell, plt is set against the time the session has left, at
    {Colors.YELLOW}set transfer_speed{Colors.RESET} Mbps (default 10). When it will not finish, the
    steps that fit are offered as --t2: send all anyway, only those, or stop.
    The rest goes later with the next --t1, or --missing. {Colors.YELLOW}--fit{Colors.RESET} takes
    the cut without asking. A finished transfer prints the rate it reached.

{Colors.BOLD}LOGIN NODES:{Colors.RESET}
    SFTP holds a core near 100% for as long as a transfer runs, and a login
    node's watchdog kills that (and may lock the account). On a host named
    login* outside a Slurm job, every transfer is held under
    {Colors.YELLOW}set login_cpu_limit{Colors.RESET} % of a core (default 70; 0: no limit); it
    says so once when it starts pausing. FLEXFLOW_LOGIN_NODE=1/0 overrides
    the detection.

{Colors.BOLD}HISTORY:{Colors.RESET}
    {Colors.YELLOW}case download history{Colors.RESET} carries what `case organise history` keeps, in
    othd_files/ and oisd_files/ alike: archive/{{problem}}N, cleaned/{{problem}}N
    and the compiled {{problem}}.othd|oisd. {Colors.YELLOW}--archive{Colors.RESET}, {Colors.YELLOW}--cleaned{Colors.RESET} and
    {Colors.YELLOW}--compiled{Colors.RESET} pick sets (combinable); without one all three go.
    Parts still in the old flat layout (othd_files/{{problem}}N) go with
    --archive, to the same place. problem comes from the remote
    (else the local) simflow.config.

    A file replaces the one of its name on the other side, except an archived
    run that is already there at the same size: those never change. Nothing
    is deleted, so a prune on one side is not repeated on the other.

    The compiled file goes after the runs. The readers (plot, case show, the
    web app) take it only while it is newer than archive/, cleaned/ and every
    run; so when it was not up to date where it came from, or the other side
    has runs it does not, it is made older than them there, and the readers
    take the runs until the next `case organise history --compile`.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    case download history CS4SG1U1 --remote server
    case download history CS4SG1U1 --remote server --compiled
    case download history * --remote server --cleaned --compiled
    case download plt CS4SG1U1 --remote server --t1 1000 --t2 5000
    case download plt CS4SG1U1 --remote server --t1 1000 --t2 5000 --freq 500
    case download plt CS4SG1U1 --remote server --freq 1000
    case download plt CS4SG1U1 --remote server --t1 5000
    case download plt CS4SG1U1 --remote server --missing
    case download plt CS4SG1U1 --remote server --t1 3000 --t2 5000 --missing
    case download input CS4SG1U1 --remote server
    case download rst CS4SG1U1 --remote server --t1 4000
    case download rst CS4SG1U1 --remote server
    case download CS4SG1U1 --remote server --files
    case download CS4SG1U1 --remote server --files "*.map"
    case download * --remote server --files --force

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set remote context:    use remote:myserver
    Then run:              case download CS4SG1U1
""")


class CaseUploadCommand(HistoryTransferMixin):
    """Upload case directories from local machine to remote server."""

    def __init__(self):
        self.console = Console()
        self.remote_config = RemoteConfig()
        self._sent = {}             # how the files sent were checked: {'md5': n, 'size': n}
        self._sending = None        # (remote name, local case path) of the target in hand
        self._ledgers = {}          # {folder of cases: Ledger}

    def _send(self, ssh, local_file: str, remote_file: str, callback=None,
              snapshot: bool = False) -> None:
        """One file to the remote, the way `auto` sends it (core/transfer):
        to a temporary name, compared with the local file by size and md5,
        then renamed. IOError when it fails; nothing is then left under the
        real name. A file of the case in hand is written to the ledger of the
        case's folder. `snapshot`: a file a job is still writing, sent as it
        is and not compared."""
        from src.core.transfer.cloud import send_checked
        mtime = os.stat(local_file).st_mtime
        res = send_checked(ssh, local_file, remote_file, callback=callback, mkdir=False,
                           snapshot=snapshot)
        if not res.ok:
            raise IOError(f"{os.path.basename(local_file)}: {res.detail}")
        self._sent[res.verified] = self._sent.get(res.verified, 0) + 1
        if not self._sending:
            return
        remote_name, case_path = self._sending
        case_dir = Path(case_path).resolve()
        try:
            rel = Path(local_file).resolve().relative_to(case_dir).as_posix()
        except ValueError:
            return
        if not snapshot and os.stat(local_file).st_mtime != mtime:
            return                  # written again while it went: not a checked copy
        from src.core.transfer.ledger import Ledger
        ledger = self._ledgers.get(case_dir.parent)
        if ledger is None:
            ledger = self._ledgers[case_dir.parent] = Ledger(case_dir.parent)
        ledger.record(remote_name, case_dir.name, rel, res.size, res.md5, res.verified,
                      mtime=None if snapshot else mtime, path=remote_file)

    def _report_checks(self) -> None:
        """How the files of this upload were checked."""
        md5, size = self._sent.get('md5', 0), self._sent.get('size', 0)
        if not md5 and not size:
            return
        parts = [f"{md5} by md5"] if md5 else []
        if size:
            parts.append(f"{size} by size only (no md5sum on the remote)")
        self.console.print(f"[dim]Checked on the remote: {', '.join(parts)}[/dim]")


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
        step_freq: Optional[int] = None,
        mode: Optional[str] = None,
        missing: bool = False,
    ) -> dict:
        """Construct a new resumable transfer state document."""
        return {
            'direction': direction,
            'mode': mode,
            'status': 'in_progress',
            'remote_name': remote_name,
            'remote_base_path': remote_base,
            'case_selection': case_selection,
            'case_mode': 'wildcard' if wildcard else 'single',
            'directories': directories,
            'file_patterns': list(file_patterns or []),
            'force': force,
            'step_window': list(step_window) if step_window else None,
            'step_freq': step_freq,
            'missing': missing,
            'time_policy': getattr(self, '_time_policy', 'ask'),
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

    def _transfer_mode(self, args, direction: str):
        """(mode, problem): binary/rst/input/history/None from the first word, or what is wrong.

        `case upload CS4` puts the case in the first positional; it is moved to
        `case` (the parser does not fill the case context in that situation).
        """
        if self._get_arg(args, 'binary', False):
            return None, (f"--binary is now a word: `case {direction} plt` "
                          f"(with --t1/--t2 as before).")
        what = self._get_arg(args, 'what')
        if what == 'plt':
            what = 'binary'         # the mode is named after the folder; `binary` still works
        if what in ('binary', 'rst', 'input', 'history'):
            return what, None
        if what is not None:
            case = self._get_arg(args, 'case')
            if case is not None:
                return None, (f"'{what}' is not binary, rst, input or history (did you mean "
                              f"`case {direction} binary {case}`?)")
            args.case = what
        return None, None

    def _execute_transfer(self, args, direction: str) -> int:
        """Shared implementation for resumable case upload/download."""
        is_upload = direction == 'upload'
        help_fn = show_upload_help if is_upload else show_download_help
        remote_arg_name = 'to' if is_upload else 'from_remote'
        remote_prompt = '--remote'
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
            step_freq = state.get('step_freq')
            missing = bool(state.get('missing', False))
            self._time_policy = state.get('time_policy', 'ask')
            mode = state.get('mode') or ('binary' if step_window or step_freq else None)
        else:
            mode, problem = self._transfer_mode(args, direction)
            if problem:
                self.console.print(f"[red]Error:[/red] {problem}")
                return 1
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
            step_window = resolve_step_window(self._get_arg(args, 't1'),
                                              self._get_arg(args, 't2'))
            step_freq = self._get_arg(args, 'freq')
            missing = bool(self._get_arg(args, 'missing', False))
            self._time_policy = ('fit' if self._get_arg(args, 'fit', False) else
                                 'ignore' if self._get_arg(args, 'no_time_check', False)
                                 else 'ask')
            if self._time_policy != 'ask' and mode != 'binary':
                self.console.print(
                    f"[red]Error:[/red] --fit/--no-time-check plan binary/ against the "
                    f"session timeout; use `case {direction} plt`."
                )
                return 1
            if missing and mode not in ('binary', 'rst'):
                self.console.print(
                    f"[red]Error:[/red] --missing compares binary/ or the .rst files on both "
                    f"sides; use `case {direction} plt --missing` or `rst --missing`."
                )
                return 1
            if step_window and not mode:
                self.console.print(
                    f"[red]Error:[/red] --t1/--t2 select timesteps, so they need "
                    f"`case {direction} plt` or `rst`. "
                    f"Nothing else in a case is written per step."
                )
                return 1
            if step_freq is not None and not mode:
                self.console.print(
                    f"[red]Error:[/red] --freq needs `case {direction} plt` or `rst` "
                    f"(it thins the steps)."
                )
                return 1
            if mode == 'input' and (step_window or step_freq is not None):
                self.console.print(
                    "[red]Error:[/red] the input files are not per step; "
                    "drop --t1/--t2/--freq."
                )
                return 1
            sets = [s for s in HISTORY_SETS if self._get_arg(args, s, False)]
            if is_upload and self._get_arg(args, 'live', False):
                sets.append(LIVE)
            if sets and mode != 'history':
                self.console.print(
                    f"[red]Error:[/red] --{'/--'.join(sets)} pick the history sets; "
                    f"use `case {direction} history`."
                )
                return 1
            if mode == 'history' and (step_window or step_freq is not None):
                self.console.print(
                    "[red]Error:[/red] the history files hold every step; "
                    "drop --t1/--t2/--freq."
                )
                return 1
            if mode in ('rst', 'input', 'history') and (dir_arg or file_patterns):
                what = {'rst': 'the .rst files', 'input': 'the .def and its File(...)',
                        'history': 'the OTHD/OISD history'}[mode]
                self.console.print(
                    f"[red]Error:[/red] `case {direction} {mode}` carries {what} "
                    f"only; {direction} --dir/--files separately."
                )
                return 1
            if step_freq is not None and step_freq <= 0:
                self.console.print(
                    f"[red]Error:[/red] --freq must be a positive integer, got {step_freq}"
                )
                return 1
            if mode in RESTART_TARGETS:
                directories = [RESTART_TARGETS[mode]]
            elif mode == 'input':
                directories = [INPUT_TARGET]
            elif mode == 'history':
                directories = [history_target(sets or HISTORY_SETS)]
            elif mode == 'binary' and not dir_arg:
                # binary on its own means binary/ alone, the way --files on its
                # own means the files alone.
                directories = ['binary']
            else:
                directories = [] if (file_patterns and not dir_arg) \
                    else self.parse_directories(dir_arg)
            remote = self.validate_remote(remote_name)
            if not remote:
                return 1
            wildcard = is_wildcard_case(case_selection)
            remote_base = self.get_remote_base_path(
                remote, self._get_arg(args, 'remote_path'),
                self._get_cases_base_dir() if wildcard
                else Path(os.path.abspath(str(case_selection).rstrip('/'))).parent)

            if wildcard:
                base_dir = self._get_cases_base_dir()
                cases = load_cases_from_directory(base_dir)
                if not cases:
                    self.console.print(
                        f"[red]Error:[/red] No cases found in .cases.yml at {base_dir}"
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
                step_freq,
                mode,
                missing,
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
        table.add_row('Directories', ', '.join(
            TARGET_LABEL.get(d) or history_label(d) or d for d in directories) or '(none)')
        if file_patterns:
            table.add_row('Files', ', '.join(file_patterns))
        if step_window:
            lo, hi = step_window
            table.add_row('Timesteps',
                          f"{lo:g}" if lo == hi else f"{lo:g} .. {hi:g}")
        if step_freq:
            table.add_row('Every', f"{step_freq} steps")
        if missing:
            table.add_row('Only', 'files missing on the other side')
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
                remote_case_path = self.construct_remote_case_path(
                    remote_base, entry_path, remote, self._get_arg(args, 'remote_path'))
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

            self._sent = {}
            for idx, target in enumerate(all_targets, 1):
                if target['key'] in completed_targets:
                    continue
                self._sending = (remote_name, target['case_path']) if is_upload else None

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
                elif history_sets(target['directory']) is not None:
                    sets = history_sets(target['directory'])
                    if is_upload:
                        ok = self.upload_history(ssh, target['remote_case_path'],
                                                 target['case_path'], sets, force=force_enabled)
                    else:
                        ok = self.download_history(ssh, target['remote_case_path'],
                                                   target['case_path'], sets)
                elif target['directory'] == INPUT_TARGET:
                    if is_upload:
                        ok = self.upload_input(ssh, target['remote_case_path'],
                                               target['case_path'], force=force_enabled)
                    else:
                        ok = self.download_input(ssh, target['remote_case_path'],
                                                 target['case_path'])
                elif target['directory'] in RESTART_KIND:
                    kind = RESTART_KIND[target['directory']]
                    if is_upload:
                        ok = self.upload_restart(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                            force=force_enabled,
                            kind=kind,
                            freq=step_freq,
                            missing=missing,
                        )
                    else:
                        ok = self.download_restart(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                            kind=kind,
                            freq=step_freq,
                            missing=missing,
                        )
                elif (step_window or step_freq or missing) and target['directory'] == 'binary':
                    if is_upload:
                        ok = self.upload_binary_range(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                            force=force_enabled,
                            missing=missing,
                            freq=step_freq,
                        )
                    else:
                        ok = self.download_binary_range(
                            ssh,
                            target['remote_case_path'],
                            target['case_path'],
                            step_window,
                            freq=step_freq,
                            missing=missing,
                        )
                elif mode == 'binary' and target['directory'] == 'binary' \
                        and (cut := self._whole_binary_check(ssh, target, is_upload)) != 'go':
                    ok = False if cut is None else self._send_cut(ssh, target, is_upload,
                                                                   cut, force_enabled)
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

            # The case's notes travel with it, whatever was carried
            synced = set()
            for target in all_targets:
                if target['case_path'] not in synced:
                    synced.add(target['case_path'])
                    self.sync_case_status(ssh, target['remote_case_path'],
                                          target['case_path'], is_upload)
                    self.sync_restarts(ssh, target['remote_case_path'],
                                       target['case_path'], is_upload)

            ssh.disconnect()
            self._sending = None
            if is_upload:
                self._report_checks()
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

    def sync_case_status(self, ssh, remote_case_path: str, local_case_path: str,
                         is_upload: bool) -> None:
        """Carry .casestatus.md (`case status`) to the other side, merged.

        A plain copy would lose lines: the cluster's job scripts log to its
        copy while you write in yours. So with both copies there, the one
        changed last gives the header and notes and the log is the entries of
        both, in time order. Only the destination is written -- the source
        catches up on a transfer the other way. Never fails the transfer.
        """
        from ....core import case_status as cs
        local = Path(local_case_path) / cs.FILENAME
        remote = f"{remote_case_path}/{cs.FILENAME}"
        try:
            here = local.read_text(errors='replace') if local.is_file() else None
            there = there_mtime = None
            if ssh.remote_path_exists(remote):
                with ssh.sftp_client.open(remote) as f:
                    there = f.read().decode(errors='replace')
                there_mtime = ssh.sftp_client.stat(remote).st_mtime
            if here is None and there is None:
                return
            source, dest = (here, there) if is_upload else (there, here)
            if source is None:
                return                  # nothing to send; the other copy stays
            if dest is None:
                text, how = source, "copied"
            else:
                here_newer = local.stat().st_mtime >= (there_mtime or 0)
                newer, older = (here, there) if here_newer else (there, here)
                text = cs.merge(newer, older)
                if text == dest:
                    self.console.print(f"[dim]{cs.FILENAME}: already up to date[/dim]")
                    return
                added = len(cs.log_entries(text)) - len(cs.log_entries(dest))
                how = (f"merged ({'notes from ' + ('here' if here_newer else 'the remote')}"
                       f"{f', {added} log line(s) added' if added > 0 else ''})")
            if is_upload:
                import tempfile
                fd, tmp = tempfile.mkstemp(suffix='.md')
                try:
                    with os.fdopen(fd, 'w') as f:
                        f.write(text)
                    ssh.upload_file(tmp, remote)
                finally:
                    os.unlink(tmp)
            else:
                cs._write(local, text)
            self.console.print(f"[green]✓[/green] {cs.FILENAME}: {how}")
        except Exception as exc:
            self.console.print(f"[yellow]⚠[/yellow]  {cs.FILENAME} not carried: {exc}")

    def sync_restarts(self, ssh, remote_case_path: str, local_case_path: str,
                      is_upload: bool) -> None:
        """Carry .restarts (`case organise history`) to the other side.

        The restarts are found from the archive parts, which --prune deletes:
        a copy that has been pruned holds rows no compile can find again. So
        the destination gets the rows of both copies, a restart it already has
        keeping its line. Only the destination is written; never fails the
        transfer.
        """
        from ....core import restarts
        local = Path(local_case_path) / restarts.FILENAME
        remote = f"{remote_case_path}/{restarts.FILENAME}"
        try:
            here = local.read_text(errors='replace') if local.is_file() else None
            there = None
            if ssh.remote_path_exists(remote):
                with ssh.sftp_client.open(remote) as f:
                    there = f.read().decode(errors='replace')
            source, dest = (here, there) if is_upload else (there, here)
            if source is None:
                return                  # nothing to send; the other copy stays
            if dest is None:
                text, how = source, f"copied ({len(restarts.parse(source))} restart(s))"
            else:
                rows = restarts.merge(dest, source)
                added = len(rows) - len(restarts.parse(dest))
                if added == 0:
                    self.console.print(f"[dim]{restarts.FILENAME}: already up to date[/dim]")
                    return
                text = restarts.render(rows, Path(local_case_path).resolve().name)
                how = f"merged ({added} restart(s) added)"
            if is_upload:
                import tempfile
                fd, tmp = tempfile.mkstemp(suffix='.restarts')
                try:
                    with os.fdopen(fd, 'w') as f:
                        f.write(text)
                    ssh.upload_file(tmp, remote)
                finally:
                    os.unlink(tmp)
            else:
                tmp = local.with_name(local.name + '.tmp')
                tmp.write_text(text)
                tmp.replace(local)
            self.console.print(f"[green]✓[/green] {restarts.FILENAME}: {how}")
        except Exception as exc:
            self.console.print(f"[yellow]⚠[/yellow]  {restarts.FILENAME} not carried: {exc}")

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
        """Return directory used to resolve .cases.yml for wildcard mode."""
        from src.cli.context import current_dir
        return current_dir()

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

    def get_remote_base_path(self, remote: dict, override_path: Optional[str],
                             folder=None) -> str:
        """
        The folder on the remote that holds these cases: --remote-path; else
        the remote's folder in `folder`'s .cases.yml (`remotes: {name: DIR}`);
        else the remote's `remote set-path`; else the remote home (~).
        """
        if override_path:
            return os.path.expanduser(override_path)
        if folder is not None:
            from src.core import cases_file
            try:
                listed = cases_file.read(folder).remotes.get(remote.get("name"))
            except cases_file.CasesFileError:
                listed = None
            if listed and listed != 'EDIT_ME':
                return listed

        # Use remote's configured path
        remote_path = remote.get("path")
        if remote_path:
            return remote_path

        # Default to home directory
        return "~"

    def construct_remote_case_path(
        self,
        remote_base: str,
        case_path: str,
        remote: Optional[dict] = None,
        override_path: Optional[str] = None,
    ) -> str:
        """
        <base>/<case name> on the remote. Given `remote` (and no override),
        the base is looked up again from the case's own folder's .cases.yml,
        so cases from several folders each go to their own folder there;
        otherwise `remote_base` is used as it is.
        """
        case_path = str(case_path)
        if remote is not None and not override_path:
            folder = Path(os.path.abspath(case_path.rstrip("/"))).parent
            remote_base = self.get_remote_base_path(remote, None, folder)
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
                self._send(ssh, local_file, f"{remote_case_path}/{name}")
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

                files_count = 0
                for root, subdirs, files in os.walk(local_dir):
                    sub = os.path.relpath(root, local_dir).replace(os.sep, '/')
                    there = remote_dir if sub == '.' else f"{remote_dir}/{sub}"
                    for name in subdirs:
                        ssh.make_remote_dir(f"{there}/{name}")
                    for name in sorted(files):
                        self._send(ssh, os.path.join(root, name), f"{there}/{name}",
                                   callback=update_progress)
                        files_count += 1

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
        missing: bool = False,
        freq: Optional[int] = None,
    ) -> bool:
        """Upload binary/, restricted to the timesteps inside `window` that are
        multiples of `freq` -- and with `missing`, to the files the remote binary/ lacks.

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
        kept, no_step = select_steps(names, window, freq)
        if not self._report_selection(kept, no_step, window, local_dir, freq):
            return True
        if missing:
            here = {n: os.path.getsize(os.path.join(local_dir, n)) for n in kept}
            try:
                there = (ssh.remote_file_sizes(remote_dir)
                         if ssh.remote_path_exists(remote_dir) else {})
            except Exception as exc:
                self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
                return False
            kept = self._report_missing(kept, here, there, remote_dir)
            if not kept:
                return True

        sizes = {n: os.path.getsize(os.path.join(local_dir, n)) for n in kept}
        kept = self._apply_time_check(sizes, 'upload')
        if kept is None:
            return False
        return self._upload_names(ssh, local_dir, remote_dir, kept, force, 'binary')

    def _report_missing(self, kept, here, there, where) -> List[str]:
        """Say how many of `kept` `where` lacks, and return those."""
        absent, resized = select_missing(kept, here, there)
        have = len(kept) - len(absent) - len(resized)
        note = f", {len(resized)} at another size" if resized else ""
        self.console.print(f"[cyan]Missing:[/cyan] {len(absent) + len(resized)} of "
                           f"{len(kept)} file(s) in {where}{note}; {have} already there")
        return sorted(absent + resized)

    def _upload_names(self, ssh, local_dir: str, remote_dir: str, names: List[str],
                      force: bool, label: str) -> bool:
        """Upload these files of local_dir into remote_dir, with one progress bar."""
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

        total_bytes = sum(os.path.getsize(os.path.join(local_dir, n)) for n in names)
        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(f"Transferring {label}...", total=total_bytes or None)
                done = 0
                started = time.monotonic()
                for name in names:
                    local_file = os.path.join(local_dir, name)
                    self._send(ssh, local_file, f"{remote_dir}/{name}")
                    done += os.path.getsize(local_file)
                    progress.update(task, completed=done, description=f"Transferred {name}")
            self.console.print(
                f"[green]\u2713[/green] Uploaded {len(names)} file(s) to {remote_dir}"
            )
            self._report_rate(done, time.monotonic() - started)
            return True
        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to upload {label}: {e}")
            return False

    def _restart_layout(self, cfg_path: str, where: str):
        """(problem, run dir relative to the case, nsg) from a simflow.config,
        or None after saying what is missing."""
        from src.core.simflow_config import SimflowConfig
        cfg = SimflowConfig(cfg_path)
        problem, run_dir = cfg.problem, cfg.run_dir_str
        if not problem or not run_dir:
            self.console.print(f"[red]Error:[/red] simflow.config in {where} needs "
                               f"'problem' and 'dir' to find the restart files")
            return None
        if os.path.isabs(run_dir):
            self.console.print(f"[red]Error:[/red] dir = {run_dir} is absolute; the other "
                               f"side's run directory can only be found from a path "
                               f"relative to the case")
            return None
        return problem, Path(os.path.normpath(run_dir)).as_posix(), cfg.nsg

    def _pick_restart(self, names: List[str], problem: str, window: Optional[tuple],
                      nsg: Optional[int], run_dir: str, where: str,
                      kind: str = 'rst', freq: Optional[int] = None) -> List[str]:
        """The .rst files of the steps in `window` (all steps without one) that are
        multiples of `freq`, after reporting what was found and what is missing.
        [] when there is nothing that can be used."""
        complete, incomplete = select_restart(names, problem, window, nsg)
        if freq:
            complete = {t: f for t, f in complete.items() if t % freq == 0}
            incomplete = {t: f for t, f in incomplete.items() if t % freq == 0}
        if window is None:
            span = "every step"
        else:
            lo, hi = window
            span = f"step {lo:g}" if lo == hi else f"steps {lo:g}..{hi:g}"
        if freq:
            span += f", every {freq}"
        self.console.print(f"[cyan]Selecting:[/cyan] .{kind} files of {span} in {run_dir}/")
        if not nsg:
            self.console.print("[yellow]Warning:[/yellow] nsg is not set in simflow.config; "
                               "cannot check that every subgrid's .rst is there")
        for step, files in incomplete.items():
            self.console.print(f"[yellow]  skipping step {step}:[/yellow] "
                               f"{len(files)}/{nsg} .rst -- not enough to restart from")
        if not complete:
            self.console.print(f"[red]Error:[/red] No complete .rst step for {span} in {where}")
            return []
        for step, files in complete.items():
            self.console.print(f"  step {step}: {len(files)} .rst")
        return [n for files in complete.values() for n in files]

    def _input_names(self, def_path: str, problem: str, exists, where: str):
        """The .def and the files it names, or None after saying which are
        missing (the preprocessor stops at the first it cannot open, so part
        of the set restarts nothing). `exists` checks a path relative to the
        case on the side that sends."""
        names = def_inputs(def_path)
        bad = [n for n in names if os.path.isabs(n) or n.startswith('..')]
        if bad:
            self.console.print(f"[red]Error:[/red] {problem}.def names files outside the "
                               f"case ({', '.join(bad)}); they cannot be placed on the "
                               f"other side")
            return None
        missing = [n for n in names if not exists(n)]
        self.console.print(f"[cyan]Selecting:[/cyan] {problem}.def and the "
                           f"{len(names)} file(s) it names with File(...)")
        if missing:
            self.console.print(f"[red]Error:[/red] {len(missing)} of them missing in {where}: "
                               f"{', '.join(missing)}; nothing sent")
            return None
        return [f"{problem}.def"] + names

    def upload_input(self, ssh, remote_case_path: str, local_case_path: str,
                     force: bool = False) -> bool:
        """Upload <problem>.def and every file it names with File(...) to the
        same paths under the remote case: what the preprocessor reads on every
        launch, so what a restart needs unchanged."""
        from src.core.simflow_config import SimflowConfig
        problem = SimflowConfig(os.path.join(local_case_path, 'simflow.config')).problem
        if not problem:
            self.console.print(f"[red]Error:[/red] simflow.config in {local_case_path} "
                               f"needs 'problem' to find the .def")
            return False
        def_path = os.path.join(local_case_path, f"{problem}.def")
        if not os.path.isfile(def_path):
            self.console.print(f"[red]Error:[/red] {problem}.def not found in {local_case_path}")
            return False
        names = self._input_names(
            def_path, problem, lambda n: os.path.isfile(os.path.join(local_case_path, n)),
            local_case_path)
        if not names:
            return False
        ok = True
        for sub, group in _by_directory(names).items():
            remote_dir = f"{remote_case_path}/{sub}" if sub else remote_case_path
            if sub and ssh.remote_path_exists(remote_case_path) \
                    and not ssh.remote_path_exists(remote_dir):
                ssh.make_remote_dir(remote_dir)       # a directory the .def names
            ok &= self._upload_names(ssh, os.path.join(local_case_path, sub), remote_dir,
                                     group, force, "input files")
        return ok

    def download_input(self, ssh, remote_case_path: str, local_case_path: str) -> bool:
        """Download the remote <problem>.def and every file it names with
        File(...) to the same paths here. problem comes from the remote
        simflow.config, or the local one when the remote has none."""
        import tempfile
        from src.core.simflow_config import SimflowConfig
        tmp = None
        try:
            cfg_path = os.path.join(local_case_path, 'simflow.config')
            remote_cfg = f"{remote_case_path}/simflow.config"
            if ssh.remote_path_exists(remote_cfg):
                fd, tmp = tempfile.mkstemp(suffix='.config')
                os.close(fd)
                ssh.download_file(remote_cfg, tmp)
                cfg_path = tmp
            problem = SimflowConfig(cfg_path).problem
            if not problem:
                self.console.print("[red]Error:[/red] simflow.config needs 'problem' "
                                   "to find the .def")
                return False
            remote_def = f"{remote_case_path}/{problem}.def"
            if not ssh.remote_path_exists(remote_def):
                self.console.print(f"[red]Error:[/red] {remote_def} not found")
                return False
            fd, def_tmp = tempfile.mkstemp(suffix='.def')
            os.close(fd)
            try:
                ssh.download_file(remote_def, def_tmp)
                names = self._input_names(
                    def_tmp, problem,
                    lambda n: ssh.remote_path_exists(f"{remote_case_path}/{n}"),
                    remote_case_path)
            finally:
                os.unlink(def_tmp)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not read the remote .def: {exc}")
            return False
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        if not names:
            return False
        ok = True
        for sub, group in _by_directory(names).items():
            remote_dir = f"{remote_case_path}/{sub}" if sub else remote_case_path
            ok &= self._download_names(ssh, remote_dir, os.path.join(local_case_path, sub),
                                       group, "input files")
        return ok

    def upload_restart(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        window: Optional[tuple],
        force: bool = False,
        kind: str = 'rst',
        freq: Optional[int] = None,
        missing: bool = False,
    ) -> bool:
        """Upload the .rst files (nsg per step) of the steps in `window` --
        every step when None -- that are multiples of `freq`, from the case's run
        directory to the same directory on the remote; with `missing`, only the
        files the remote lacks or holds at another size.

        A step missing some of its .rst files cannot restart a run, so it is
        reported and left behind.
        """
        layout = self._restart_layout(os.path.join(local_case_path, 'simflow.config'),
                                      local_case_path)
        if not layout:
            return False
        problem, run_dir, nsg = layout
        local_dir = os.path.join(local_case_path, run_dir)
        if not os.path.isdir(local_dir):
            self.console.print(f"[red]Error:[/red] Run directory not found: {local_dir}")
            return False
        names = self._pick_restart(os.listdir(local_dir), problem, window, nsg, run_dir,
                                   local_dir, kind, freq)
        if not names:
            return False
        remote_dir = f"{remote_case_path}/{run_dir}"
        if missing:
            here = {n: os.path.getsize(os.path.join(local_dir, n)) for n in names}
            try:
                there = (ssh.remote_file_sizes(remote_dir)
                         if ssh.remote_path_exists(remote_dir) else {})
            except Exception as exc:
                self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
                return False
            names = self._report_missing(names, here, there, remote_dir)
            if not names:
                return True
        return self._upload_names(ssh, local_dir, remote_dir, names, force, f".{kind} files")

    def download_restart(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        window: Optional[tuple],
        kind: str = 'rst',
        freq: Optional[int] = None,
        missing: bool = False,
    ) -> bool:
        """Download the .rst files (nsg per step) of the steps in `window` --
        every step when None -- that are multiples of `freq`, from the remote case's
        run directory to the same directory here; with `missing`, only the files
        this side lacks or holds at another size.

        problem, dir and nsg come from the remote simflow.config -- the run that
        wrote the files -- or the local one when the remote has none.
        """
        import tempfile
        remote_cfg = f"{remote_case_path}/simflow.config"
        cfg_path, where = os.path.join(local_case_path, 'simflow.config'), local_case_path
        tmp = None
        try:
            if ssh.remote_path_exists(remote_cfg):
                fd, tmp = tempfile.mkstemp(suffix='.config')
                os.close(fd)
                ssh.download_file(remote_cfg, tmp)
                cfg_path, where = tmp, remote_case_path
            layout = self._restart_layout(cfg_path, where)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not read {remote_cfg}: {exc}")
            return False
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        if not layout:
            return False
        problem, run_dir, nsg = layout
        remote_dir = f"{remote_case_path}/{run_dir}"
        if not ssh.remote_path_exists(remote_dir):
            self.console.print(f"[red]Error:[/red] Remote run directory not found: {remote_dir}")
            return False
        try:
            entries = ssh.list_remote_dir(remote_dir)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
            return False
        names = self._pick_restart(entries, problem, window, nsg, run_dir, remote_dir, kind, freq)
        if not names:
            return False
        local_dir = os.path.join(local_case_path, run_dir)
        if missing:
            try:
                sizes = ssh.remote_file_sizes(remote_dir)
            except Exception as exc:
                self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
                return False
            have = {n: os.path.getsize(os.path.join(local_dir, n))
                    for n in (os.listdir(local_dir) if os.path.isdir(local_dir) else [])
                    if os.path.isfile(os.path.join(local_dir, n))}
            names = self._report_missing(names, {n: sizes.get(n, 0) for n in names}, have,
                                         local_dir)
            if not names:
                return True
        return self._download_names(ssh, remote_dir, local_dir, names, f".{kind} files")

    def download_binary_range(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        window: Optional[tuple],
        freq: Optional[int] = None,
        missing: bool = False,
    ) -> bool:
        """Download binary/, restricted to the timesteps inside `window` that
        are multiples of `freq` -- and with `missing`, to the files the local
        binary/ lacks."""
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
            # With --missing the listing brings the sizes, and so which entries
            # are files: without a window every name is kept, directories too.
            sizes = ssh.remote_file_sizes(remote_dir)
            entries = list(sizes) if missing else ssh.list_remote_dir(remote_dir)
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] Could not list {remote_dir}: {exc}")
            return False

        # Only names carrying a step can be placed in the window, and those are
        # never directories, so the remote stat per entry that resolve_remote_files
        # does is not needed here.
        kept, no_step = select_steps(entries, window, freq)
        if not self._report_selection(kept, no_step, window, remote_dir, freq):
            return True
        if missing:
            names = os.listdir(local_dir) if os.path.isdir(local_dir) else []
            there = {n: os.path.getsize(os.path.join(local_dir, n)) for n in names
                     if os.path.isfile(os.path.join(local_dir, n))}
            kept = self._report_missing(kept, sizes, there, local_dir)
            if not kept:
                return True

        kept = self._apply_time_check({n: sizes.get(n, 0) for n in kept}, 'download')
        if kept is None:
            return False
        return self._download_names(ssh, remote_dir, local_dir, kept, 'binary')

    def _download_names(self, ssh, remote_dir: str, local_dir: str, names: List[str],
                        label: str) -> bool:
        """Download these files of remote_dir into local_dir, with one progress bar."""
        os.makedirs(local_dir, exist_ok=True)
        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(f"Transferring {label}...", total=None)
                state = {"done": 0, "last": 0}

                def update_progress(transferred, _file_total):
                    if transferred < state["last"]:
                        state["done"] += state["last"]
                    state["last"] = transferred
                    progress.update(task, completed=state["done"] + transferred)

                started = time.monotonic()
                for name in names:
                    ssh.download_file(f"{remote_dir}/{name}",
                                      os.path.join(local_dir, name),
                                      callback=update_progress)
            self.console.print(
                f"[green]\u2713[/green] Downloaded {len(names)} file(s) to {local_dir}"
            )
            self._report_rate(state["done"] + state["last"], time.monotonic() - started)
            return True
        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to download {label}: {e}")
            return False

    # -- the session timeout ------------------------------------------------------

    def _check_time(self, sizes: Dict[str, int], direction: str):
        """
        Set the selection against the time the session has left (budget.py).

        Returns 'go' to send it all, (first, last) to send only those steps,
        or None to send nothing. --fit takes the cut without asking,
        --no-time-check skips the check; without a terminal to ask at, the
        warning is printed and everything is sent as asked.
        """
        from shellkit import current_runtime
        policy = getattr(self, '_time_policy', 'ask')
        rt = current_runtime()
        if policy == 'ignore' or rt is None or not sizes:
            return 'go'
        speed = rt.settings.get('transfer_speed') if 'transfer_speed' in rt.settings.specs \
            else budget.DEFAULT_MBPS
        # an older shellkit has no session timeout: nothing to check against
        left = rt.time_left() if hasattr(rt, 'time_left') else None
        if left is None and not hasattr(rt, 'time_left'):
            return 'go'
        p = budget.plan(sizes, left, speed, step_of)
        if p is None or p.fits:
            return 'go'

        say = self.console.print
        say(f"[yellow]Session timeout:[/yellow] {p.files} file(s), {budget.size(p.nbytes)}: "
            f"about {budget.duration(p.seconds)} at {p.mbps:g} Mbps, and "
            f"{budget.duration(p.left)} is left in this session.")
        if p.cut is None:
            say("    Not even the first step fits. `set timeout 60` gives a longer "
                "session; `set transfer_speed N` if the link is faster.")
            if policy == 'fit':
                say("[dim]    --fit: nothing sent.[/dim]")
                return None
            return 'go' if self._ask("Send it all anyway?", ('y',)) == 'y' else None

        c = p.cut
        say(f"    Up to [cyan]--t2 {c.last}[/cyan] fits: steps {c.first}..{c.last}, "
            f"{c.files} file(s), {budget.size(c.nbytes)}, about "
            f"{budget.duration(budget.seconds_for(c.nbytes, p.mbps))}.")
        say(f"[dim]    --t1 {c.first} --t2 {c.last} now; the rest later with "
            f"--t1 {c.last + 1}, or --missing.[/dim]")
        if policy == 'fit':
            say(f"[dim]    --fit: sending steps {c.first}..{c.last}.[/dim]")
            return (c.first, c.last)
        answer = self._ask(f"Send all anyway [y], only up to --t2 {c.last} [t], "
                           f"or stop [N]?", ('y', 't'))
        if answer == 't':
            return (c.first, c.last)
        return 'go' if answer == 'y' else None

    def _ask(self, question: str, accepted) -> Optional[str]:
        """One of `accepted`, or None for no. With no terminal to ask at, 'y':
        the transfer goes ahead as it was asked for, the warning said."""
        if not sys.stdin.isatty():
            self.console.print("[dim]    (no terminal to ask at: sending it all)[/dim]")
            return 'y'
        try:
            answer = self.console.input(f"    {question} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        return answer[:1] if answer[:1] in accepted else None

    def _apply_time_check(self, sizes: Dict[str, int], direction: str) -> Optional[List[str]]:
        """The names of `sizes` to send after _check_time, or None for none."""
        verdict = self._check_time(sizes, direction)
        if verdict is None:
            self.console.print("[dim]Nothing sent.[/dim]")
            return None
        names = sorted(sizes)
        if verdict == 'go':
            return names
        lo, hi = verdict
        return [n for n in names if step_of(n) is not None and lo <= step_of(n) <= hi]

    def _whole_binary_check(self, ssh, target, is_upload):
        """_check_time for a whole binary/ (no window, no --missing)."""
        try:
            if is_upload:
                local_dir = os.path.join(target['case_path'], 'binary')
                sizes = {}
                for root, _dirs, files in os.walk(local_dir):
                    for name in files:
                        path = os.path.join(root, name)
                        sizes[os.path.relpath(path, local_dir)] = os.path.getsize(path)
            else:
                remote_dir = f"{target['remote_case_path']}/binary"
                sizes = (ssh.remote_file_sizes(remote_dir)
                         if ssh.remote_path_exists(remote_dir) else {})
        except Exception:
            return 'go'          # the transfer itself will say what is wrong
        verdict = self._check_time(sizes, 'upload' if is_upload else 'download')
        if verdict is None:
            self.console.print("[dim]Nothing sent.[/dim]")
        return verdict

    def _send_cut(self, ssh, target, is_upload, window, force) -> bool:
        """binary/ cut to the steps that fit, without asking again."""
        policy, self._time_policy = getattr(self, '_time_policy', 'ask'), 'ignore'
        try:
            if is_upload:
                return self.upload_binary_range(ssh, target['remote_case_path'],
                                                target['case_path'], window, force=force)
            return self.download_binary_range(ssh, target['remote_case_path'],
                                              target['case_path'], window)
        finally:
            self._time_policy = policy

    def _report_rate(self, nbytes: int, seconds: float) -> None:
        """The rate a transfer reached, against `transfer_speed` when it is
        far off -- the number to set for the next plan."""
        from shellkit import current_runtime
        if nbytes < budget.RATE_MIN_BYTES:
            return
        rate = budget.mbps_of(nbytes, seconds)
        if rate is None:
            return
        rt = current_runtime()
        planned = (rt.settings.get('transfer_speed')
                   if rt is not None and 'transfer_speed' in rt.settings.specs else None)
        note = ""
        if planned and abs(rate - planned) > 0.25 * planned:
            note = f"; planned with {planned:g}: `set transfer_speed {rate:.3g}` to plan with this"
        self.console.print(f"[dim]    {rate:.3g} Mbps{note}[/dim]")

    def _report_selection(self, kept, no_step, window, where, freq=None) -> bool:
        """Say what the window picked out. False when there is nothing to move."""
        if window or freq:
            span = "all steps"
            if window:
                lo, hi = window
                span = f"step {lo:g}" if lo == hi else f"steps {lo:g}..{hi:g}"
            every = f", every {freq}" if freq else ""
            self.console.print(f"[cyan]Selecting:[/cyan] {span}{every} in binary/")
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
                "[red]Error:[/red] Remote machine not provided. Use --remote or 'use remote:<name>' in interactive shell."
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
        remote_base = self.get_remote_base_path(
            remote, args.remote_path,
            self._get_cases_base_dir() if is_wildcard_case(case_path)
            else Path(os.path.abspath(str(case_path).rstrip('/'))).parent)

        # Wildcard mode: iterate all cases from .cases.yml
        if is_wildcard_case(case_path):
            base_dir = self._get_cases_base_dir()
            cases = load_cases_from_directory(base_dir)
            if not cases:
                self.console.print(
                    f"[red]Error:[/red] No cases found in .cases.yml at {base_dir}"
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
            table.add_row("Case Selection", "* (all cases from .cases.yml)")
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
                        self.console.print("[yellow]Warning:[/yellow] Missing case path in .cases.yml entry")
                        self.console.print()
                        continue

                    if not self._ensure_local_case_dir(entry_path, force_enabled):
                        self.console.print()
                        continue

                    remote_case_path = self.construct_remote_case_path(
                        remote_base, entry_path, remote, args.remote_path)
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
        remote_case_path = self.construct_remote_case_path(
            remote_base, case_path, remote, args.remote_path)

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
