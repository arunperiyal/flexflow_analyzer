# Next session

Where the `auto` work stands (2026-11-11) and what comes next. The design is
`docs/architecture/auto.md`; **§13 is the current design** and §13.7–13.12
hold the decisions taken since. `docs/architecture/auto_flow.html` and Help ->
Flowchart (web UI) draw it. `main` is pushed at d2516ab; the "Job log" section
(log tail of a failed job) is on branch `auto-job-log-tail`, not merged yet.

## Built

| what | where |
|---|---|
| Queue reads fail loudly; jobs belong to cases by working directory | `src/core/slurm.py` |
| PLT validity from the header; settled `.out` steps | `src/core/plt_valid.py`, `src/core/settled.py` |
| `.cases.yml` (cases, remotes with a folder each, `auto:` keep_rst, keep_newest_rst, upload_rst, disk_alert, qos/account/partition) | `src/core/cases_file.py`, `src/core/auto/conf.py` |
| `auto init`, `auto show`, `auto commands`, `auto status`, `auto apply` (history, upload, post only; `--dry-run`, `--yes`, `--only`) | `src/commands/auto/` |
| Observe (files, queue, sacct, remote listing, ledger) -> Decide (pure) -> Report -> Act | `src/core/auto/{observe,decide,report,executor}.py` |
| Stretches of equal output spacing, lost steps, provisional steps after a queued restart | `src/core/auto/stretches.py`, `decide.py` |
| md5-checked uploads (temp name + rename), ledger, run log in `<folder>/auto_logs/`, folder lock | `cloud.py`, `ledger.py`, `runlog.py` |
| Restart sets: `keep_rst` kept here, `upload_rst` sent (plus the final set of a finished run), `keep_newest_rst` (default 2) | `decide.py`, `organise_impl/organizer.py` |
| After a restart from T: PLTs/sets above T from before the restart are the earlier run's (not trusted, posted/sent again); a copy counts only if `auto` sent it after the restart job started (ledger) | `decide.py` (`restarted`, `stale_plt`, `stale_rst`) |
| History larger on the remote than here is never offered for upload | `decide.py` (`hist_shrink`) |
| `run main` notes `restartTsId N` / `restartFlag off` in `.casestatus.md` | `run/main_impl/command.py` |
| "Job log": last 15 lines of `slurm-<id>.out` of a main/post job that ended badly (branch `auto-job-log-tail`) | `observe.py` (`_tail`), `report.py` |
| 12 dummy cases, fake SLURM, local "cloud" | `tools/make_dummy.py`, `tools/fake_slurm.py` |

Try it locally: `python3 tools/make_dummy.py && source dummy/env.sh && cd dummy/bare && flexflow auto show '*' --remote local`.

Tests: `python3 -m pytest -q test_scripts` (miniconda base python has pytest;
the flexflow_env one does not). Expected: all pass except two
`test_web_field_render.py` tests that already failed on main before this work.

## Waiting on the user (cluster)

- Run `auto apply BR0SG0U1P0 --remote cloud --only upload --dry-run`, then without `--dry-run`, and bring back `auto_logs/auto_<time>.log` plus `auto show` afterwards. First real run of the additive steps.
- Decide the job-name flag on `fixed/bare` (jobs `mainBR0fixed`/`postBR0fixed` vs the `main<case>` convention): per-case setting in `.cases.yml`, or rename the jobs.
- `BR0SG0U6P0`: `archive/` is empty locally (runs 1–8 only on cloud); restore with `case download history BR0SG0U6P0 --archive --from cloud`. Local `cleaned/riser1` differs from the cloud's.

## Next to build

1. **Delete stage** of `auto apply` behind one question (`--yes` skips): ASCII PLT and binary PLT only when the md5 on the cloud matches the ledger, `.out` of verified steps, `.rst` thinning to `keep_rst`/`keep_newest_rst`. Nothing above a restart point is deleted until its step has been posted again from the new run. Reports already list these as `[not built yet]`.
2. **Steady check**: `data check steady` over the last N frames of OTHD/OISD, only for cases that reached `maxTimeSteps`; per-folder settings under `auto:` in `.cases.yml`. Not steady -> "Needs you" with `def time maxTimeSteps <N>` then `run main restart <last step>`. `auto` never queues main jobs.
3. `auto log` (reads `auto_logs/`), polish of `auto status`.
4. Display: with a queued restart, `Complete`/`Also kept` still count the earlier run's newer set (not deleted, only shown).
5. Maybe: size-consistency check of `.rst` parts (a part cut short inside a complete set is not detected); md5 of files already on the remote on the first run.

## Open questions

- A chained `auto` SLURM job only if the HPC team allows it (§12); cron, scrontab and `at` are disabled.
- Running commands on the cluster from here: only read-only, in a session the user opens, every action confirmed.

## Rules the user set (also in memory / CLAUDE.md)

- No Claude/Co-Authored-By in commit messages; `prompt.md` stays untracked.
- One feature per branch; merge when the user says so; push only when asked.
- Never Claude Artifacts: standalone HTML files in the repo instead.
- Data safety first: fail closed, nothing deleted without a verified copy, ask once before deleting.
- Every improvement from a real `auto show` becomes a dummy case plus a test.
