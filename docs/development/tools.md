# Development tools

These scripts support local development and cluster checks. They are not
required by the installed `flexflow` command.

## `make_dummy.py`

Build disposable cases for trying `auto` without an HPC cluster:

```bash
python3 tools/make_dummy.py
source dummy/env.sh
cd dummy/bare
flexflow auto show '*' --remote local
```

Use `--root DIR` to put the generated tree elsewhere. Running it again
rebuilds the dummy state. The generated `dummy/` directory is ignored by git.

## `fake_slurm.py`

`make_dummy.py` links this script as `squeue`, `sacct`, `sbatch`, `scontrol`
and `scancel`. Inspect or change the simulated queue with:

```bash
fake-slurm list
fake-slurm start JOB_ID
fake-slurm finish JOB_ID [STATE]
fake-slurm fail on
fake-slurm fail off
```

State is kept in `dummy/slurm/`, or in the directory named by
`FAKE_SLURM_DIR`.

## `hpc_probe.sh`

Run this read-only probe on a login or compute node:

```bash
bash tools/hpc_probe.sh [CASES_DIR] [REMOTE ...]
```

It records its report under `~/flexflow_probe_<host>_<time>.txt`. Set
`ONLY=remotes`, `ONLY=node` or `ONLY=job` for a narrower check.
`PROBE_REMOTE`, `SIZE_MB`, `PROBE_PARTITION` and `WAIT` control the remote
upload and optional SLURM checks. The probe does not delete case data; its
temporary upload is removed when the check finishes.
