"""
The SLURM queue, read so that a decision can rest on it.

Two rules, both learnt from the cluster:

1. **A failed read is an error, never an empty queue.** squeue reports some
   problems with exit 1 (an invalid job id) and others with exit 0 and a
   message on stderr (an invalid user). Either way the caller gets a
   QueueError -- an empty list means the queue really holds nothing of yours.
   Anything that would act on a case "because nothing is running" must not
   act when the queue could not be read.

2. **A job belongs to the case it was submitted from.** run pre/main/post
   all submit with the case directory as the working directory, so squeue's
   %Z names the case. Job names are not used: scripts get copied between
   cases with their `#SBATCH -J` unchanged (postFlex.sh of one case named
   after another), and one case name can be the start of another's (CS4 and
   CS40).

    jobs = read_queue()                    # QueueError if squeue fails
    mine = jobs_for_case(case_dir, jobs)   # by working directory
    [j for j in mine if j.kind == 'main' and j.active]
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

# %Z last: a working directory is the field most likely to hold odd characters
FORMAT = '%i|%j|%T|%P|%Z'
FIELDS = 5
TIMEOUT = 30

# States in which a job still holds or will take the case's files. Anything
# else (COMPLETED, FAILED, ...) only shows for MinJobAge after it ended.
ACTIVE_STATES = frozenset({
    'PENDING', 'CONFIGURING', 'RUNNING', 'COMPLETING', 'SUSPENDED',
    'REQUEUED', 'REQUEUE_HOLD', 'REQUEUE_FED', 'RESIZING', 'SIGNALING',
    'STAGE_OUT', 'STOPPED',
})

KINDS = ('main', 'post', 'pre')


class QueueError(RuntimeError):
    """squeue could not be run, failed, or said something we cannot read."""


@dataclass(frozen=True)
class Job:
    jobid: str
    name: str
    state: str
    partition: str
    workdir: str

    @property
    def kind(self) -> str:
        """main / post / pre from the job name's prefix (mainCASE, postCASE,
        preCASE as the templates name them), else 'other'. Only a label: which
        case a job belongs to comes from its working directory."""
        for kind in KINDS:
            if self.name.startswith(kind):
                return kind
        return 'other'

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def pending(self) -> bool:
        return self.state == 'PENDING'

    def named_for(self, case_name: str) -> bool:
        """Whether the job name is <kind><case_name>; False flags a script
        copied from another case without renaming its job."""
        return self.kind != 'other' and self.name == f"{self.kind}{case_name}"


def available() -> bool:
    return shutil.which('squeue') is not None


def read_queue(user: Optional[str] = None, all_users: bool = False) -> List[Job]:
    """Your jobs in the queue (everyone's with all_users).

    Raises QueueError when squeue is missing, times out, exits non-zero,
    writes anything to stderr, or prints a line that does not parse.
    """
    if not available():
        raise QueueError("squeue not found (not on a SLURM cluster?)")
    cmd = ['squeue', '--noheader', '--format', FORMAT]
    if not all_users:
        user = user or os.environ.get('USER', '')
        if not user:
            raise QueueError("$USER is not set, so squeue cannot be limited to your jobs")
        cmd += ['-u', user]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise QueueError(f"squeue did not answer within {TIMEOUT} s")
    except OSError as e:
        raise QueueError(f"could not run squeue: {e}")
    err = result.stderr.strip()
    if result.returncode != 0 or err:
        why = err.splitlines()[0] if err else f"exit {result.returncode}"
        raise QueueError(f"squeue failed: {why}")
    return parse_queue(result.stdout)


def parse_queue(text: str) -> List[Job]:
    """Jobs from `squeue --noheader --format FORMAT` output; QueueError on a
    line that does not have every field (a half-read queue is no queue)."""
    jobs = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split('|', FIELDS - 1)
        if len(parts) != FIELDS:
            raise QueueError(f"unexpected squeue line: {line!r}")
        jobid, name, state, partition, workdir = (p.strip() for p in parts)
        if not jobid:
            raise QueueError(f"squeue line without a job id: {line!r}")
        jobs.append(Job(jobid, name, state, partition, workdir))
    return jobs


def _real(path) -> str:
    return os.path.realpath(os.path.expanduser(str(path)))


def jobs_for_case(case_dir, jobs: Iterable[Job]) -> List[Job]:
    """The jobs whose working directory is case_dir (symlinks resolved)."""
    target = _real(case_dir)
    return [j for j in jobs if j.workdir and _real(j.workdir) == target]


def case_jobs(case_dir, user: Optional[str] = None) -> List[Job]:
    """read_queue() narrowed to one case; raises QueueError like it."""
    return jobs_for_case(case_dir, read_queue(user))
