# Next session

Where the `auto` work stands (2026-11-10) and what comes next. The design is
`docs/AUTO_PLAN.md`; **§13 is the current design** and §13.7–13.11 hold the
decisions taken since. `docs/auto_flow.html` and Help -> Flowchart (web UI)
draw it. Everything below is merged into `main` and pushed (7c15337).

## Built

| what | where |
|---|---|
| Queue reads fail loudly (stderr with exit 0 counts); jobs belong to cases by working directory, not name | `src/core/slurm.py` (`read_queue`, `jobs_for_case`, `read_ended` via sacct) |
| `case organise output` keeps restart points (restartTsId, newest complete set, newest incomplete set) and deletes `.out` only for a whole binary PLT written after them | `organise_impl/organizer.py` |
| PLT validity from the header (exact expected size; a test cuts at every byte); settled `.out` steps | `src/core/plt_valid.py`, `src/core/settled.py` |
| `case check plt` reports broken PLTs | `check_impl/command.py` |
| `.cases.yml` replaces `.cases` and `.auto.conf`: `cases`, `remotes` (folder per remote), `auto` (keep_rst, disk_alert, qos/account/partition). `case add` rewrites only `cases`. Old `.cases` is **not** read | `src/core/cases_file.py` |
| upload/download/`run post --remote`: remote folder = `--remote-path`, else the case folder's `.cases.yml`, else `remote set-path` | `download_impl/command.py` |
| `auto init --remote NAME [--path DIR] [--keep-rst N] [--disk-alert SIZE] [--force]` | `src/commands/auto/init.py` |
| `auto show [case] --remote NAME` (or `use case:` / `use case:*`, `use remote:`); read-only; per-case blocks + summary table | `src/commands/auto/show.py`, `src/core/auto/{conf,cloud,observe,decide}.py` |
| Dummy cases + fake SLURM + local "cloud" | `tools/make_dummy.py` (`dummy/`, git-ignored), `tools/fake_slurm.py` |
| Cluster probe | `tools/hpc_probe.sh` (`ONLY=remotes`, `ONLY=node`, `ONLY=job`) |

Try it locally: `python3 tools/make_dummy.py && source dummy/env.sh && cd dummy/bare && flexflow auto show '*' --remote local`
(each case should get what `dummy/README.md` says).

Tests: `python3 -m pytest -q test_scripts` (miniconda base python has pytest;
the flexflow_env one does not). Expected: all pass except two
`test_web_field_render.py` tests that already failed on main before this work.

## Waiting on the user (cluster)

After `git pull` in `~/install/pkgs/flexflow_analyzer`, in each folder of cases:

```
flexflow case add                 # makes .cases.yml (old .cases is no longer read)
flexflow auto init --remote cloud --path /shares/.../<folder> --keep-rst 500
sacct -X -n -P -S now-3days --format=JobID,JobName%200,State,End,WorkDir | head
flexflow auto show '*' --remote cloud 2>&1 | tee ~/auto_show_<folder>.txt
```

Then go through the output case by case against what the user would do by hand.
Not yet seen on the cluster:
- whether sacct returns **WorkDir** (if not, `auto show` makes no post decisions);
- the SFTP listing of the NAS (`cloud`, password from remotes.json);
- the `post job N started: steps A..B` lines in `.casestatus.md` (written only by the current postFlex.sh template).

## Next to build (§13.6 order)

5. Upload with md5 + ledger (`.auto/ledger.jsonl` per case): `.part` then rename, md5 on the NAS (no sha256sum there), files already on the cloud md5-checked on the first run; `auto apply --only upload`.
6. History stages: `organise history --update` refuses while a main job is running/pending/completing; re-read the queue right before the move.
7. Post stages (submit through `run post`'s code, record job id + window).
8. Delete stages behind one question at the start (`--yes` skips): ASCII PLT and binary PLT only when md5 on the cloud matches, `.out` of verified steps, `.rst` thinning to `auto.keep_rst`.
9. `auto log` (journal `.auto/journal.jsonl`), maybe `auto status`.

## Open questions / offers not yet answered

- `auto show`: say the remote's status (connected, N case folders listed) and per case how much is on the remote; an option to md5-check files already there (~1.5 s per 155 MB PLT on the NAS).
- Make `case organise history --prune` refuse (or warn): every case must keep `archive/` and `cleaned/` (§13.11).
- A chained `auto` SLURM job (`--dependency=afterany:<main>`) only if the HPC team allows it (§12). cron, scrontab and `at` are disabled for the user.
- Running commands on the cluster from here: only read-only, in a session the user opens (2FA), every action confirmed (see the end of the 2026-11-10 conversation).

## Rules the user set (also in memory / CLAUDE.md)

- No Claude/Co-Authored-By in commit messages; `prompt.md` stays untracked.
- One feature per branch; merge when the user says so; push only when asked.
- Never Claude Artifacts: standalone HTML files in the repo instead.
- Data safety first: fail closed, nothing deleted without a verified copy, ask once before deleting.
