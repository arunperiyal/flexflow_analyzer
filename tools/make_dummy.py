#!/usr/bin/env python3
"""
Build dummy/: a folder of small fake cases, each in a different state, with a
fake SLURM and a fake cloud, to try `auto` (and the other commands) on a
machine without the cluster.

    python3 tools/make_dummy.py            # (re)build dummy/ in the repo root
    python3 tools/make_dummy.py --root DIR
    source dummy/env.sh                    # put the fake squeue/sbatch/... first on PATH

Everything is generated: run it again to get back to the starting state
after a test changed things. dummy/README.md lists the cases and what `auto`
should make of each.

The cases follow the bare folder on PARAM Shakti (probe of 2026-11-09),
scaled down: problem riser, nsg = 4 parts per step (np 4), outFreq 50
(case10: 5), maxTimeSteps 1000. Binary PLTs are small but genuine TDV112
files, so the PLT checks read them as they read real ones.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'test_scripts'))

from plt_files import plt_bytes            # noqa: E402

NSG = 4
DAY = 86400
NOW = time.time()


# --- files -------------------------------------------------------------------

def touch(path, when):
    os.utime(path, (when, when))


def write(path, text, when=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    if when is not None:
        touch(path, when)
    return path


def othd(ts_ids, run_no):
    """OTHD with one probe; the displacement's x is the run number, so the
    run each step came from can be seen after --clean/--compile."""
    head = "mask 455\nnOths 1\n"
    return head + "".join(f"tsId {t}\ntime {t * 0.05:.10e}\nothId 0\nothFlag 1\n"
                          f"aleDisp 3 1\n{run_no} {t * 1e-4:.6e} 0.0\n" for t in ts_ids)


def oisd(ts_ids):
    v = "3 1\n0.0 0.0 0.0\n"
    return "nOsfs 1\n" + "".join(
        f"tsId {t}\ntime {t * 0.05:.10e}\nosgId 0\nosdFlag 1\ntotArea 3.7695e+01\n"
        f"totMassFlux 4.8e-09\ntotMomFlux {v}totTrac 3 1\n5.9e-04 {-6.07 + t * 1e-4:.6e} 2.98e+05\n"
        f"totMoment {v}aveVel {v}avePres 3.2325e+02\naveEddy 4.95e-05\naveAleDisp {v}"
        for t in ts_ids)


def config(problem='riser', out_freq=50, restart=None):
    lines = [f"problem = {problem}" if problem else "# problem missing on purpose",
             f"np\t= {NSG}", f"nsg \t= {NSG}", "fmt \t= ascii", "pDir\t= .", "dir\t= ./RUN_1",
             "cnn\t= riser.fluid.cnn", "nen\t= 8", f"outFreq\t= {out_freq}", "verbose\t= 1"]
    if restart is not None:
        lines += [f"restartTsId = {restart}", "restartFlag = 1"]
    return "\n".join(lines) + "\n"


DEF = """nodeCoordinates {{
    coordinates             = File( "riser.crd" )
}}

elementGroup( "interior" ) {{
    elements                = File( "riser.fluid.cnn" )
    shape                   = eightNodeBrick
}}

timeSteppingControl{{
    maxTimeSteps              = {max_steps}
    initialTimeIncrement      = 0.05
}}

outputSimulation{{
    outFreq                   = {out_freq}
}}

outputRestart{{
    outFreq                   = {out_freq}
}}
"""


def job_script(kind, case_name):
    text = (REPO / 'src' / 'templates' / 'scripts' / f'{kind}Flex.sh').read_text()
    return text.replace('{CASE_NAME}', case_name)


class Case:
    def __init__(self, root, name, *, out_freq=50, max_steps=1000, restart=None,
                 problem='riser', post_name=None, state='new', log=()):
        self.dir = root / name
        self.name = name
        self.freq = out_freq
        self.run = self.dir / 'RUN_1'
        self.run.mkdir(parents=True)
        old = NOW - 30 * DAY
        write(self.dir / 'simflow.config', config(problem, out_freq, restart), old)
        write(self.dir / 'riser.def', DEF.format(max_steps=max_steps, out_freq=out_freq), old)
        write(self.dir / 'riser.crd', "0 0.0 0.0 0.0\n", old)
        write(self.dir / 'riser.fluid.cnn', "0 1 2 3 4 5 6 7\n", old)
        write(self.dir / 'riser.geo', "// geometry\n", old)
        write(self.dir / 'simflow_env.sh', "# paths to the solver; fake\n", old)
        write(self.dir / 'mainFlex.sh', job_script('main', name), old)
        write(self.dir / 'postFlex.sh', job_script('post', post_name or name), old)
        for script in ('mainFlex.sh', 'postFlex.sh'):
            (self.dir / script).chmod(0o755)
        write(self.dir / 'othd.riser_probe.map', "# othId node x y z\n0 24 0.0 0.0 1.0\n", old)
        write(self.dir / 'domain.yml', "version: 1\n", old)
        write(self.run / 'riser.dbg.out', "debug output, not a step\n", old)
        entries = "\n".join(f"- {stamp}  {line}" for stamp, line in log)
        write(self.dir / '.casestatus.md',
              f"---\nstate: {state}\ntags: []\n---\n# {name}\n\n## Notes\n\n## Log\n{entries}\n", old)

    # steps
    def steps(self, first, last):
        return list(range(first, last + 1, self.freq))

    def outs(self, steps, when, parts=NSG):
        for i, t in enumerate(steps):
            for k in range(parts):
                write(self.run / f'riser.{t}_{k}.out', f"field of step {t}, part {k}\n", when + i)

    def rsts(self, steps, when, parts=NSG):
        for i, t in enumerate(steps):
            for k in range(parts):
                write(self.run / f'riser.{t}_{k}.rst', f"restart of step {t}, part {k}\n", when + i)

    def plts(self, steps, when, folder='binary', cut=None):
        for i, t in enumerate(steps):
            data = plt_bytes()
            write(self.dir / folder / f'riser.{t}.plt', data if cut is None else data[:cut], when + i)

    # history
    def live(self, ts_ids, when):
        write(self.run / 'riser.othd', othd(ts_ids, 'live'), when)
        write(self.run / 'riser.oisd', oisd(ts_ids), when)

    def archive(self, run_no, ts_ids, when):
        for ext, text in (('othd', othd(ts_ids, run_no)), ('oisd', oisd(ts_ids))):
            write(self.dir / f'{ext}_files' / 'archive' / f'riser{run_no}.{ext}', text, when)

    def organise(self, *steps):
        """Run the real `case organise history` steps on this case."""
        import io
        from argparse import Namespace
        from types import SimpleNamespace
        from rich.console import Console
        from src.commands.case.organise_impl.organizer import CaseOrganizer

        class Quiet:
            def __getattr__(self, name):
                return lambda *a, **k: None
        args = Namespace(update=False, verify=False, clean=False, compile=False, prune=False,
                         dry_run=False, no_confirm=True, log=False, verbose=False, t1=None, t2=None)
        for step in steps:
            setattr(args, step, True)
        case = SimpleNamespace(case_directory=str(self.dir), problem_name='riser',
                               config={'dir': './RUN_1'})
        CaseOrganizer(case, args, Quiet(), Console(file=io.StringIO())).organize('history')


def cloud_copy(case, cloud_root, steps=(), history=True):
    """What is already on the cloud for this case: binary PLTs of `steps`,
    and the history folders as they stand."""
    dest = cloud_root / case.name
    dest.mkdir(parents=True, exist_ok=True)
    for t in steps:
        write(dest / 'binary' / f'riser.{t}.plt', plt_bytes(), NOW - 5 * DAY)
    if history:
        for ext in ('othd', 'oisd'):
            src = case.dir / f'{ext}_files'
            if src.exists():
                shutil.copytree(src, dest / f'{ext}_files', dirs_exist_ok=True)


# --- the cases ---------------------------------------------------------------

def build(root: Path):
    bare = root / 'bare'
    cloud = root / 'cloud' / 'bare'
    slurm = root / 'slurm'
    for d in (bare, cloud, slurm, root / 'bin'):
        d.mkdir(parents=True)
    queue, history = [], []
    jobid = iter(range(1_300_101, 1_400_000))

    def job(case, kind, state, *, name=None, ended_days=None, ran=3 * DAY, reason='Priority',
            exitcode=None, cpus=None):
        j = dict(jobid=str(next(jobid)), name=name or f"{kind}{case.name}", state=state,
                 partition='medium' if kind == 'main' else 'shared',
                 workdir=str(case.dir), cpus=cpus or (NSG if kind == 'main' else 1),
                 qos='iitkgp_freeq', account=os.environ.get('USER', 'user'))
        if state in ('PENDING',):
            j.update(submit=NOW - DAY, start=None, reason=reason)
        elif state in ('RUNNING', 'COMPLETING'):
            j.update(submit=NOW - 2 * DAY, start=NOW - DAY, reason='None')
        else:
            end = NOW - (ended_days or 1) * DAY
            j.update(submit=end - ran - 3600, start=end - ran, end=end,
                     exitcode=exitcode or ('0:0' if state == 'COMPLETED' else '1:0'))
        (queue if state in ('PENDING', 'RUNNING', 'COMPLETING') else history).append(j)
        return j

    old, week, day2, day1 = NOW - 20 * DAY, NOW - 7 * DAY, NOW - 2 * DAY, NOW - DAY
    cases = []

    # case1 -- finished and tidy: everything on the cloud, nothing to do
    c = Case(bare, 'case1', state='done', log=[('2026-10-20 10:00', 'main job ended at 1000')])
    c.archive(1, range(1, 1001), week)
    c.organise('clean', 'compile')
    c.rsts(c.steps(200, 1000)[::4], week)                  # the 200 grid only
    cloud_copy(c, cloud, c.steps(50, 1000))
    job(c, 'main', 'COMPLETED', ended_days=7)
    job(c, 'post', 'COMPLETED', ended_days=6, ran=3600)
    cases.append(('case1', 'finished, everything converted, uploaded and tidied',
                  'nothing to do'))

    # case2 -- running; PLTs behind the solver
    c = Case(bare, 'case2', restart=400)
    c.archive(1, range(1, 431), week)                      # the first run reached 430
    c.organise('clean', 'compile')
    c.rsts([200, 400], week)
    c.live(range(401, 653), NOW - 300)                     # solver at 652
    c.outs(c.steps(450, 600), day2)
    c.outs([650], NOW - 400, parts=3)                      # step 650 still being written
    c.rsts(c.steps(450, 600), day2)
    cloud_copy(c, cloud, c.steps(50, 400))
    job(c, 'main', 'RUNNING')
    cases.append(('case2', 'main RUNNING, live .othd at 652, .out 450-600 complete, 650 has '
                  '3 of 4 parts; cloud has PLTs up to 400',
                  'post 450-600 from the live .othd (650 not settled); history left in place'))

    # case3 -- main queued to resume from 700; old run's history still in the run dir
    c = Case(bare, 'case3', restart=700)
    c.archive(1, range(1, 521), week)
    c.organise('clean', 'compile')
    c.live(range(501, 761), day2)                          # the run that ended at 760
    c.outs(c.steps(550, 750), day2)
    c.rsts([200, 400] + c.steps(550, 750), day2)
    c.plts([750], day1)                                    # an older post made 750
    cloud_copy(c, cloud, c.steps(50, 500))
    job(c, 'main', 'TIMEOUT', ended_days=1)
    job(c, 'main', 'PENDING', reason='Priority')
    cases.append(('case3', 'main PENDING, resumes from 700 (not on the 200 grid); the ended '
                  'run\'s .othd is still in RUN_1; .out 550-750; binary/riser.750.plt; cloud '
                  'up to 500',
                  'history left in place (job queued); post 550-700; 750 provisional; '
                  '.rst of 700 kept'))

    # case4 -- a post job is running
    c = Case(bare, 'case4')
    c.archive(1, range(1, 801), day2)
    c.organise('clean', 'compile')
    c.outs(c.steps(650, 800), day2)
    c.rsts([200, 400, 600] + c.steps(650, 800), day2)
    cloud_copy(c, cloud, c.steps(50, 600))
    job(c, 'main', 'TIMEOUT', ended_days=2)
    job(c, 'post', 'RUNNING')
    cases.append(('case4', 'main ended (TIMEOUT); post job RUNNING; cloud up to 600',
                  'wait for the post job'))

    # case5 -- run ended at the walltime, history still in the run dir
    c = Case(bare, 'case5', restart=300)
    c.archive(1, range(1, 311), week)
    c.organise('clean', 'compile')
    c.live(range(301, 521), day1)
    c.outs(c.steps(350, 500), day1)
    c.rsts([200] + c.steps(350, 500), day1)
    cloud_copy(c, cloud, c.steps(50, 300))
    job(c, 'main', 'TIMEOUT', ended_days=1)
    cases.append(('case5', 'main ended (TIMEOUT) yesterday; its .othd still in RUN_1; '
                  '.out 350-500; cloud up to 300',
                  'history: --update (riser2), --clean, --compile, upload; post 350-500'))

    # case6 -- the post job was killed at the walltime
    c = Case(bare, 'case6')
    c.archive(1, range(1, 601), week)
    c.organise('clean', 'compile')
    c.outs(c.steps(450, 600), week)
    c.rsts([200, 400] + c.steps(450, 600), week)
    c.plts([450, 500], day2)
    c.plts([550], day2, cut=200)                           # cut short mid-write
    cloud_copy(c, cloud, c.steps(50, 400))
    job(c, 'main', 'TIMEOUT', ended_days=6)
    job(c, 'post', 'TIMEOUT', ended_days=2, ran=DAY)
    cases.append(('case6', 'post job ended TIMEOUT: binary/ has 450, 500, a cut-short 550, '
                  'no 600; cloud up to 400',
                  'needs you: post ended badly (550 broken, 600 missing)'))

    # case7 -- main failed at once; postFlex.sh copied from case6
    c = Case(bare, 'case7', post_name='case6')
    job(c, 'main', 'FAILED', ended_days=2, ran=16)
    cases.append(('case7', 'main FAILED after 16 s, no output; postFlex.sh is named '
                  'postcase6', 'needs you: main failed; job name flagged'))

    # case8 -- finished, but archive/ was pruned: breaks the folder rule
    # (every case keeps archive/ and cleaned/)
    c = Case(bare, 'case8')
    c.archive(1, range(1, 1001), week)
    c.organise('clean', 'compile', 'prune')
    c.outs(c.steps(950, 1000), week)
    c.rsts([200, 400, 600, 800, 1000], week)
    cloud_copy(c, cloud, c.steps(50, 900))
    job(c, 'main', 'COMPLETED', ended_days=7)
    cases.append(('case8', 'finished (1000); archive/ pruned, only cleaned/ (against the '
                  'folder rule); .out 950-1000; cloud up to 900',
                  'needs you: archive/ pruned or missing; no post decision until it is '
                  'restored (case download history --archive)'))

    # case9 -- broken simflow.config
    c = Case(bare, 'case9', problem=None)
    cases.append(('case9', 'simflow.config has no problem line', 'skipped, with the reason'))

    # case10 -- running at outFreq 5, and its job is named maincase1
    c = Case(bare, 'case10', out_freq=5, max_steps=500)
    c.live(range(1, 123), NOW - 200)                       # solver at 122
    c.outs(c.steps(5, 115), day1)
    c.outs([120], NOW - 200, parts=2)
    c.rsts(c.steps(5, 120), day1)
    job(c, 'main', 'RUNNING', name='maincase1')            # a script copied from case1
    cases.append(('case10', 'main RUNNING at outFreq 5 (many .out/.rst), job named maincase1; '
                  'nothing on cloud',
                  'post 5-115 from the live .othd; case1 must NOT look running'))

    # case11 -- holes on the cloud
    c = Case(bare, 'case11')
    c.archive(1, range(1, 701), week)
    c.organise('clean', 'compile')
    c.outs(c.steps(650, 700), week)
    c.rsts([200, 400, 600, 650, 700], week)
    cloud_copy(c, cloud, c.steps(50, 400) + c.steps(500, 600))
    job(c, 'main', 'TIMEOUT', ended_days=5)
    cases.append(('case11', 'ended (TIMEOUT at 700); cloud has 50-400 and 500-600 (450 '
                  'missing); .out only 650-700', 'needs you: holes on the cloud (450)'))

    # the folder
    (bare / '.cases').write_text(json.dumps(
        [{'name': name, 'path': str(bare / name)} for name, _, _ in cases], indent=2))
    (bare / '.auto.conf').write_text(
        "# what `auto` uses for this folder\n"
        "remote     = local\n"
        f"path       = {cloud}\n"
        "keep_rst   = 200\n"
        "disk_alert = 1M\n")
    (slurm / 'queue.json').write_text(json.dumps(queue, indent=1))
    (slurm / 'history.json').write_text(json.dumps(history, indent=1))

    # fake SLURM: links to tools/fake_slurm.py
    target = os.path.relpath(REPO / 'tools' / 'fake_slurm.py', root / 'bin')
    for name in ('squeue', 'sacct', 'sbatch', 'scontrol', 'scancel', 'fake-slurm'):
        (root / 'bin' / name).symlink_to(target)
    (root / 'env.sh').write_text(
        "# source dummy/env.sh: the fake SLURM first on PATH\n"
        f'export PATH="{root / "bin"}:$PATH"\n'
        f'export FAKE_SLURM_DIR="{slurm}"\n')
    write_readme(root, cases, queue, history)


def write_readme(root, cases, queue, history):
    rows = "\n".join(f"| {n} | {what} | {expect} |" for n, what, expect in cases)
    jobs = "\n".join(f"| {j['jobid']} | {j['name']} | {j['state']} | "
                     f"{Path(j['workdir']).name} |" for j in queue + history)
    (root / 'README.md').write_text(f"""# dummy cases

Generated by `python3 tools/make_dummy.py` -- run it again to start over.
Not tracked by git.

```
source dummy/env.sh          # fake squeue, sacct, sbatch, scontrol, scancel first on PATH
cd dummy/bare
fake-slurm list              # the queue and the ended jobs
fake-slurm start ID          # PENDING -> RUNNING
fake-slurm finish ID TIMEOUT # leave the queue (COMPLETED, FAILED, CANCELLED, ...)
fake-slurm fail on           # squeue/sacct/scontrol fail until `fail off`
```

`bare/` holds the cases (problem riser, nsg = 4, outFreq 50, maxTimeSteps
1000), `cloud/bare/` what is already "on the cloud" (`.auto.conf`: remote
`local`, i.e. a folder), `slurm/` the fake queue (`submitted.log` records every
sbatch).

| case | state | what `auto` should do |
|---|---|---|
{rows}

## jobs

| id | name | state | case |
|---|---|---|---|
{jobs}
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--root', default=str(REPO / 'dummy'),
                        help='where to build it (default: dummy/ in the repo); replaced if it exists')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if root.exists():
        if not (root / 'README.md').exists() and any(root.iterdir()):
            sys.exit(f"{root} exists and does not look like a dummy folder; not replacing it")
        shutil.rmtree(root)
    root.mkdir(parents=True)
    build(root)
    print(f"Built {root}: {len(list((root / 'bare').iterdir())) - 2} cases. "
          f"See {root / 'README.md'}.")


if __name__ == '__main__':
    main()
