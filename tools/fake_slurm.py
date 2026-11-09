#!/usr/bin/env python3
"""
A stand-in for SLURM, for trying flexflow on a machine without it.

Linked into <dummy>/bin as squeue, sacct, sbatch, scontrol and scancel by
tools/make_dummy.py; which one runs is taken from the name it is called by.
State lives in <dummy>/slurm/ (or $FAKE_SLURM_DIR):

    queue.json      jobs in the queue: what squeue and scontrol show
    history.json    jobs that ended: what sacct adds
    submitted.log   one JSON line per sbatch call (args, script, exports)
    fail            when present, squeue/sacct/scontrol print its text on
                    stderr and exit 1, as a cluster whose controller is down

It behaves as PARAM Shakti did in tools/hpc_probe.sh: squeue reports an
unknown user on stderr with exit 0, an unknown job id with exit 1; a job
that ends leaves the queue (sacct keeps it).

To move a test along:

    fake-slurm list                  queue and history
    fake-slurm start ID              PENDING -> RUNNING
    fake-slurm finish ID [STATE]     leave the queue as COMPLETED (or TIMEOUT,
                                     FAILED, CANCELLED, ...)
    fake-slurm fail on|off           make squeue/sacct/scontrol fail
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path


# --- state -------------------------------------------------------------------

def state_dir() -> Path:
    env = os.environ.get('FAKE_SLURM_DIR')
    if env:
        return Path(env)
    # <dummy>/bin/<name> -> <dummy>/slurm (the link's own path, not its target)
    return Path(os.path.abspath(sys.argv[0])).parent.parent / 'slurm'


def load(name):
    path = state_dir() / name
    return json.loads(path.read_text()) if path.exists() else []


def save(name, data):
    path = state_dir() / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def next_id() -> int:
    ids = [int(j['jobid']) for j in load('queue.json') + load('history.json')]
    return max(ids, default=1_300_000) + 1


def failing():
    path = state_dir() / 'fail'
    if path.exists():
        print(path.read_text().strip() or 'slurm_load_jobs error: Unable to contact slurm controller',
              file=sys.stderr)
        sys.exit(1)


def stamp(t) -> str:
    return datetime.fromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S') if t else 'Unknown'


def elapsed(seconds) -> str:
    seconds = max(0, int(seconds))
    d, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    m, s = divmod(rest, 60)
    return f"{d}-{h:02d}:{m:02d}:{s:02d}" if d else f"{h:02d}:{m:02d}:{s:02d}"


# --- squeue ------------------------------------------------------------------

SQUEUE_FIELDS = {
    'i': lambda j: j['jobid'],
    'A': lambda j: j['jobid'],
    'j': lambda j: j['name'],
    'T': lambda j: j['state'],
    't': lambda j: {'RUNNING': 'R', 'PENDING': 'PD', 'COMPLETING': 'CG'}.get(j['state'], j['state'][:2]),
    'M': lambda j: elapsed(time.time() - j['start']) if j.get('start') else '0:00',
    'D': lambda j: str(j.get('nodes', 1)),
    'P': lambda j: j.get('partition', 'medium'),
    'C': lambda j: str(j.get('cpus', 1)),
    'm': lambda j: j.get('memory', '0'),
    'V': lambda j: stamp(j.get('submit')),
    'R': lambda j: j.get('reason', 'None') if j['state'] == 'PENDING' else j.get('nodelist', 'cn001'),
    'E': lambda j: j.get('dependency', '(null)'),
    'Z': lambda j: j['workdir'],
    'u': lambda j: j.get('user', os.environ.get('USER', 'user')),
}


def render(fmt, job):
    return re.sub(r'%\.?\d*([a-zA-Z])',
                  lambda m: str(SQUEUE_FIELDS.get(m.group(1), lambda j: '')(job)), fmt)


def squeue(argv):
    failing()
    user = None
    fmt = '%i %P %j %u %t %M %D %R'
    header = True
    jobs_wanted = None
    it = iter(argv)
    for arg in it:
        if arg in ('-u', '--user'):
            user = next(it)
        elif arg.startswith('--user='):
            user = arg.split('=', 1)[1]
        elif arg in ('-h', '--noheader'):
            header = False
        elif arg in ('-o', '--format'):
            fmt = next(it)
        elif arg.startswith('--format='):
            fmt = arg.split('=', 1)[1]
        elif arg in ('-j', '--jobs'):
            jobs_wanted = next(it).split(',')
        elif arg.startswith('--jobs='):
            jobs_wanted = arg.split('=', 1)[1].split(',')
    me = os.environ.get('USER', 'user')
    if user is not None and user != me:
        # what squeue does on PARAM Shakti: error on stderr, exit 0
        print(f"squeue: error: Invalid user: {user}", file=sys.stderr)
        return 0
    jobs = load('queue.json')
    if jobs_wanted is not None:
        jobs = [j for j in jobs if j['jobid'] in jobs_wanted]
        if not jobs:
            print("slurm_load_jobs error: Invalid job id specified", file=sys.stderr)
            return 1
    if header:
        print(re.sub(r'%\.?\d*([a-zA-Z])', lambda m: m.group(1).upper(), fmt))
    for job in jobs:
        print(render(fmt, job))
    return 0


# --- sacct -------------------------------------------------------------------

SACCT_FIELDS = {
    'jobid': lambda j: j['jobid'],
    'jobname': lambda j: j['name'],
    'state': lambda j: j['state'],
    'exitcode': lambda j: j.get('exitcode', '0:0'),
    'elapsed': lambda j: elapsed((j.get('end') or time.time()) - j['start']) if j.get('start') else '00:00:00',
    'start': lambda j: stamp(j.get('start')),
    'end': lambda j: stamp(j.get('end')),
    'submit': lambda j: stamp(j.get('submit')),
    'workdir': lambda j: j['workdir'],
    'account': lambda j: j.get('account', os.environ.get('USER', 'user')),
    'qos': lambda j: j.get('qos', 'normal'),
    'partition': lambda j: j.get('partition', 'medium'),
    'alloccpus': lambda j: str(j.get('cpus', 1)),
}


def sacct(argv):
    failing()
    fields = ['jobid', 'jobname', 'state', 'exitcode']
    header = True
    parsable = False
    jobs_wanted = None
    it = iter(argv)
    for arg in it:
        if arg in ('-n', '--noheader'):
            header = False
        elif arg in ('-P', '--parsable2', '-p', '--parsable'):
            parsable = True
        elif arg in ('-o', '--format'):
            fields = next(it).split(',')
        elif arg.startswith('--format='):
            fields = arg.split('=', 1)[1].split(',')
        elif arg in ('-j', '--jobs'):
            jobs_wanted = next(it).split(',')
        elif arg in ('-u', '--user', '-S', '--starttime', '-E', '--endtime'):
            next(it)
    names = [re.sub(r'%\d+$', '', f).lower() for f in fields]
    jobs = load('history.json') + load('queue.json')
    if jobs_wanted is not None:
        jobs = [j for j in jobs if j['jobid'] in jobs_wanted]
    sep = '|' if parsable else '  '
    if header:
        print(sep.join(fields))
    for job in sorted(jobs, key=lambda j: int(j['jobid'])):
        print(sep.join(SACCT_FIELDS.get(n, lambda j: '')(job) for n in names))
    return 0


# --- sbatch ------------------------------------------------------------------

def sbatch(argv):
    opts, script, script_args = {}, None, []
    test_only = False
    it = iter(argv)
    for arg in it:
        if script is not None:
            script_args.append(arg)
        elif arg == '--test-only':
            test_only = True
        elif arg in ('-J', '--job-name', '-p', '--partition', '-d', '--dependency',
                     '--export', '-A', '--account', '--qos', '-t', '--time', '-n', '--ntasks',
                     '-D', '--chdir', '--wrap', '-o', '--output'):
            opts[arg.lstrip('-')] = next(it)
        elif arg.startswith('--') and '=' in arg:
            key, value = arg[2:].split('=', 1)
            opts[key] = value
        elif arg.startswith('-'):
            opts[arg.lstrip('-')] = True
        else:
            script = arg
    directives = {}
    if script:
        for line in Path(script).read_text().splitlines():
            m = re.match(r'#SBATCH\s+(-\w|--[\w-]+)[\s=]+(\S+)', line)
            if m:
                directives[m.group(1).lstrip('-')] = m.group(2)
    name = opts.get('job-name') or opts.get('J') or directives.get('J') \
        or directives.get('job-name') or (Path(script).name if script else 'wrap')
    partition = opts.get('partition') or opts.get('p') or directives.get('p') or 'medium'
    jobid = str(next_id())
    if test_only:
        print(f"sbatch: Job {jobid} to start at {stamp(time.time() + 60)} using 1 processors "
              f"on nodes cn001 in partition {partition}", file=sys.stderr)
        return 0
    if script is None and 'wrap' not in opts:
        print("sbatch: error: Batch job submission failed: no script", file=sys.stderr)
        return 1
    workdir = os.path.abspath(opts.get('chdir') or opts.get('D') or os.getcwd())
    dep = opts.get('dependency') or opts.get('d')
    job = dict(jobid=jobid, name=name, state='PENDING', partition=partition,
               workdir=workdir, submit=time.time(), start=None,
               reason='Dependency' if dep else 'Priority',
               dependency=dep or '(null)', cpus=int(directives.get('n', 1)))
    queue = load('queue.json')
    queue.append(job)
    save('queue.json', queue)
    with open(state_dir() / 'submitted.log', 'a') as log:
        log.write(json.dumps(dict(jobid=jobid, name=name, workdir=workdir, script=script,
                                  args=script_args, options=opts)) + '\n')
    print(f"Submitted batch job {jobid}")
    return 0


# --- scontrol / scancel ------------------------------------------------------

def scontrol(argv):
    failing()
    if argv[:2] == ['show', 'config']:
        print("MinJobAge               = 300 sec\nScronParameters         = (null)")
        return 0
    if argv[:2] == ['show', 'job'] and len(argv) > 2:
        job = next((j for j in load('queue.json') if j['jobid'] == argv[2]), None)
        if job is None:
            print("slurm_load_jobs error: Invalid job id specified", file=sys.stderr)
            return 1
        print(f"JobId={job['jobid']} JobName={job['name']}\n"
              f"   JobState={job['state']} Reason={job.get('reason', 'None')}\n"
              f"   Partition={job.get('partition', 'medium')} NumCPUs={job.get('cpus', 1)}\n"
              f"   SubmitTime={stamp(job.get('submit'))} StartTime={stamp(job.get('start'))}\n"
              f"   WorkDir={job['workdir']}\n"
              f"   StdOut={job['workdir']}/slurm-{job['jobid']}.out")
        return 0
    print("scontrol: error: only 'show job ID' and 'show config' are faked", file=sys.stderr)
    return 1


def end_job(jobid, state):
    queue = load('queue.json')
    job = next((j for j in queue if j['jobid'] == jobid), None)
    if job is None:
        return False
    queue.remove(job)
    job.update(state=state, end=time.time(), start=job.get('start') or time.time(),
               exitcode='0:0' if state == 'COMPLETED' else '1:0')
    history = load('history.json')
    history.append(job)
    save('queue.json', queue)
    save('history.json', history)
    return True


def scancel(argv):
    names = None
    ids = []
    it = iter(argv)
    for arg in it:
        if arg in ('-n', '--name'):
            names = next(it)
        elif arg.startswith('--name='):
            names = arg.split('=', 1)[1]
        else:
            ids.append(arg)
    if names:
        ids += [j['jobid'] for j in load('queue.json') if j['name'] == names]
    for jobid in ids:
        if not end_job(jobid, 'CANCELLED'):
            print(f"scancel: error: Kill job error on job id {jobid}: Invalid job id specified",
                  file=sys.stderr)
            return 1
    return 0


# --- the test driver ---------------------------------------------------------

def control(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == 'list':
        for title, name in (('queue', 'queue.json'), ('history', 'history.json')):
            print(f"{title}:")
            for j in load(name):
                print(f"  {j['jobid']}  {j['name']:<16} {j['state']:<10} {j['workdir']}")
        return 0
    if cmd == 'start' and rest:
        queue = load('queue.json')
        for j in queue:
            if j['jobid'] == rest[0]:
                j.update(state='RUNNING', start=time.time(), reason='None')
                save('queue.json', queue)
                return 0
        print(f"no job {rest[0]} in the queue", file=sys.stderr)
        return 1
    if cmd == 'finish' and rest:
        state = rest[1].upper() if len(rest) > 1 else 'COMPLETED'
        if end_job(rest[0], state):
            return 0
        print(f"no job {rest[0]} in the queue", file=sys.stderr)
        return 1
    if cmd == 'fail' and rest:
        path = state_dir() / 'fail'
        if rest[0] == 'on':
            path.write_text(' '.join(rest[1:]) or
                            'slurm_load_jobs error: Unable to contact slurm controller (connect failure)')
        else:
            path.unlink(missing_ok=True)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


COMMANDS = {'squeue': squeue, 'sacct': sacct, 'sbatch': sbatch, 'scontrol': scontrol,
            'scancel': scancel, 'fake-slurm': control, 'fake_slurm.py': control}

if __name__ == '__main__':
    command = COMMANDS.get(os.path.basename(sys.argv[0]), control)
    sys.exit(command(sys.argv[1:]))
