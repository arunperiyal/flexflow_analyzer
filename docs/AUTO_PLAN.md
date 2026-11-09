# `auto` — plan

One command that looks at every case in a directory, works out what is safe
to do next (submit a post job, upload binary PLTs / history, later: tidy
output), and does it — with checks strict enough that no data can be lost.
It runs on the HPC login node with no agent: an algorithm, not judgment.

Status: plan only. Nothing here is built yet. **§13 is the current design**;
it supersedes §5–§7 where they differ.

---

## 1. Principles (the "no margin for error" rules)

These are rules for the whole design. Every step below follows them.

1. **Observe → Decide → Act, kept apart.**
   - *Observe* reads the disk, the queue and the remote into one snapshot per
     case. It only reads.
   - *Decide* is a pure function `plan(snapshot) -> [Action]`. No I/O, so it
     can be tested exhaustively with fake snapshots.
   - *Act* carries out one action at a time, and **checks the action's
     preconditions again right before it acts** (the disk can change between
     observe and act).
2. **Fail closed.** If anything is unknown, can't be parsed or looks
   inconsistent (squeue errored, `simflow.config` unreadable, step counts
   don't add up, the remote can't be reached), the case is **skipped, with
   the reason printed**. The command never guesses.
3. **Dry run by default.** `run auto` prints the plan. Only `run auto --apply`
   acts.
4. **Idempotent.** Running it twice in a row does nothing the second time.
   Every action is safe to repeat after a crash.
5. **Never delete in v1.** Version 1 only *adds* things: post jobs, remote
   copies. Deleting (`.out`, ASCII `.plt`, extra `.rst`) comes in a later
   phase, is opt-in, and needs a remote copy verified by checksum.
6. **One sweep per case at a time.** A per-case lock file `.auto/lock`,
   created with O_EXCL and holding host, pid and time, stops two sweeps
   (e.g. tmux on login03 and a manual run on login08) from acting on the
   same case at once. Not `flock`, which Lustre may not honour across nodes
   (see §10).
7. **Everything is written down.** Each action goes to `.auto/journal.jsonl`
   (what, why, preconditions seen, result) and gets one line in
   `.casestatus.md`'s log, so `case status` shows what auto did.

---

## 2. Gaps found in the existing code (fix these first)

Automation depends on checks that today are "good enough for a person
watching". These have to be tightened before anything acts on its own:

| # | Where | Problem | Why it matters unattended |
|---|-------|---------|---------------------------|
| G1 | `run/sq_impl/command.py` `get_queue_data` | Returns `''` when squeue **fails**, the same as an empty queue | A squeue hiccup would look like "nothing running", so auto would post or upload while the solver is still writing. Must raise or return `None`. |
| G2 | `case/status_impl` `_queued_jobs` | Matches a job to a case by **substring of the job name** (`CS4` matches `CS40`) | The wrong case looks busy, or worse, a busy case looks idle. Match by `WorkDir` (scontrol) resolved to the case path. |
| G3 | `organise_impl/organizer.py` `_analyze_single_output_dir` | Deletes a step's `.out` once `<problem>.<step>.plt` **exists**, even if it's empty, truncated (post job killed at walltime) or stale (made before a restart) | That's the one place data can be lost today. Use the PLT validity check below (§4.3). |
| G4 | `ssh_client.upload_file` (SFTP `put`) | Writes straight to the final name, and nothing is checked after | An interrupted upload leaves a short file under the real name. `--missing` catches a wrong size, but nothing compares content. |
| G5 | `postFlex.sh` send | Checks the size only (ssh path); rsync path has no post-check | Same as G4. Auto will verify these afterwards. |
| G6 | Uploads use **password** auth (paramiko) | Can't run unattended | Use key auth (BatchMode ssh/rsync, as `postFlex.sh` already does) for auto. |

G1–G3 are real risks even without auto; each is a small branch of its own.

---

## 3. What the snapshot holds (Observe)

For each case (from `.cases`, or one case path):

**Setup**: problem, run dir, `outFreq`, `nsg` (number of `.out`/`.rst` parts
per step), `maxTimeSteps`, restartFlag/restartTsId, `.restarts`, post script
present and up to date (supports `--remote`).

**Jobs** (one `squeue` + one `scontrol` per job, plus `sacct` for jobs that
finished since the last sweep):
- main / post / pre jobs whose **WorkDir is this case**, with state.
- the most recent finished post job and how it ended (COMPLETED / FAILED /
  TIMEOUT / CANCELLED), plus its `START_TIME..END_TIME` (from its
  `.casestatus.md` "post job … started" line or its slurm log).

**Solver progress**: last `tsId` in the live `.othd` (already in
`report_impl`).

**Per step** `t = outFreq, 2·outFreq, …` (one row per step):

| field | meaning |
|-------|---------|
| `out_parts` | how many `<p>.<t>_<k>.out` files exist, their sizes and newest mtime |
| `rst_parts` | same for `.rst` |
| `ascii_plt` | `<run>/<p>.<t>.plt`: size, mtime |
| `bin_plt` | `binary/<p>.<t>.plt`: size, mtime, **validity** (§4.3) |
| `remote` | the remote's size (and later checksum) for this file |
| `ledger` | what auto recorded last time (size, mtime, sha256, verified when) |

Remote state is fetched once per case (one `ls -l`/`stat` over ssh), not
once per file.

---

## 4. Definitions the decisions rest on

### 4.1 A step's `.out` is *settled*

All of:
- `out_parts == nsg`, and every part > 0 bytes;
- the solver is past it: **no main job running**, or last othd tsId ≥
  `t + outFreq` (the solver has started a later step), *and* the newest
  part's mtime is older than `settle_secs` (default 10 min);
- not stale after a restart: if `t > restartTsId`, the parts must be newer
  than the resumed run's start (the logic of `_stale_plts`, reused).

If `nsg` isn't known, **no step is settled** (fail closed), unlike
`select_restart` which accepts any count.

### 4.2 A post job is *in flight*

Any post job for this case that is PENDING, RUNNING, COMPLETING or
CONFIGURING; or a `.post_start_<jobid>` marker whose job is still in the
queue. While one is in flight, **no new post job is submitted for that case,
and files in its window are not uploaded** unless they are valid and their
mtime is older than `settle_secs`.

### 4.3 A binary PLT is *valid*

All of:
- starts with `#!TDV112`;
- its size equals the size the header implies (`fxplt.PltFile` already
  parses the header and detects truncation; add a header-only "expected
  size" function so 1000 files don't need full reads);
- cross-check: on one mesh, every binary PLT of a case is the same size. A
  file of another size is flagged as **suspect** even if the header check
  passes;
- not stale: made after the `.out` it came from (if those still exist), and
  after the restart when `t > restartTsId`;
- mtime older than `settle_secs` (no writer is still touching it).

A file that fails any check is **never** uploaded or counted as converted.
It goes in the report as *needs re-post*.

### 4.4 A remote copy is *verified*

Remote size equals the local size **and** the checksum matches (`sha256sum`
on the remote, else `md5sum`, else size only, marked `size-only` in the
ledger). Only `verified` counts for any later deletion. `size-only` never
does.

---

## 5. Decisions (Decide)

Per case, in order. Each action carries its preconditions, which Act checks
again just before acting.

| # | Action | When | Notes |
|---|--------|------|-------|
| D0 | **skip case** | lock held, config unreadable, squeue failed, `nsg` unknown, remote unreachable (for upload actions only) | reason printed; other cases continue |
| D1 | **submit `run post convert`** | settled steps have a valid-looking ASCII `.plt` but no valid binary | cheaper than `full` |
| D2 | **submit `run post full`** | settled steps have no valid binary PLT, and no post job is in flight | range = contiguous blocks of such steps: `--t1` first, `--t2` last *settled* step (never the step being written); at most `max_post_jobs` blocks per case (default 1) and `max_post_total` per sweep; with `--remote` if a remote is set, so files go out as they're made |
| D3 | **re-post** | binary PLT invalid/suspect, or last post job ended FAILED/TIMEOUT and its last files fail §4.3 | same as D2, but only those steps; listed in the report so a person sees it |
| D4 | **upload binary** | valid binary PLT, remote copy missing / different size / checksum mismatch / local file changed since the ledger | key auth; write to `.<name>.part`, check size + checksum, then rename (the `postFlex.sh` way) |
| D5 | **upload history** | archived/cleaned `.othd`/`.oisd` parts (which don't change) not on the remote | reuses `upload_history`; the live `.othd` is copied only as a snapshot, never treated as final |
| D6 | **verify** | files uploaded by post jobs (`post_sent_*.log`) with no checksum in the ledger | checksum both sides, record in the ledger |
| — | *later phase:* tidy | `.out` of steps whose binary PLT is valid **and** remote-verified; ASCII PLT whose binary is valid **and** verified; `.rst` thinning per `organise output` rules, but never the last two complete restart points | opt-in `--tidy`; asks to confirm unless `--yes` |

Explicitly **out of scope** for auto: restarting main jobs, editing
`simflow.config`, `organise history --clean/--prune`. These need a person.

---

## 6. Act

- Act order: verify → upload → post (uploads free nothing, but they finish
  quickly and work around the session timeout).
- Before each action: get the case lock, check its preconditions again, then
  act, then write to the journal and `.casestatus.md`.
- Post submission reuses `post_impl._job_exports` / `submit_postprocessing_job`
  (same `--t1/--t2` rounding and remote checks), called as a function, not
  through the shell.
- Upload: a new key-auth transport (`ssh`/`rsync` subprocess with
  `BatchMode=yes`) shared with `postFlex.sh`'s approach. Respects
  `login_cpu_limit` and the session-time budget (`budget.plan`, `--fit`
  behaviour: send what fits, the rest goes next sweep).
- Ctrl-C / SIGTERM: finish or roll back the current file (`.part` removed),
  write the journal, release the lock.

---

## 7. Command surface

*(Updated 2026-11-09 for the decisions in §11: a top-level `auto`, one
folder per run, cloud only, run by hand on the login node.)*

```
auto [case]                    # the plan for this folder's cases (or one case); changes nothing
auto --apply [case]            # carry it out once, then exit
auto --apply --only post,upload  # limit action kinds (post, plt, history, rst, inputs, files, verify)
auto --apply --fit             # upload only what fits in the session time left
auto --apply --max-post N      # cap post jobs this run (default 1)
auto log [case]                # what earlier runs did (.auto/journal.jsonl)
auto verified [case]           # local files whose cloud copy is md5-verified (safe for you to delete)
```

The folder's `.auto.conf` names the remote (`cloud`) and its path, and,
only if you want them, `qos`/`account`/`partition` for post jobs.

Plan output per case:

```
BR0SG0U2P0   running  step 4571 / 7000 (65%)   main 1220727 RUNNING
  .out settled to 4550 · PLT on cloud to 4000 · binary/ empty
  → post full  --t1 4050 --t2 4550  (11 steps)
  → upload history: live riser.othd, riser.oisd (snapshot, 12 MB)
BR0SG0U4P0   pending  main 1225965 PENDING, resumes from 8250
  · step 8300 (.out and binary/riser.8300.plt) is past the pending restart:
    provisional, not posted or uploaded until the new run passes it
  → upload rst set 8250 (120 files, 2.3 GB, ~23 min)
BR0SG0U5P0   stopped  no job; last step 8150 of 9000, 32 days ago → needs you
cloud: key login ok · 14 files to upload, 3.1 GB, ~31 min at 1.7 MB/s
```

Exit code: 0 all fine; 1 something was skipped or failed; 2 bad usage.

## 8. Tests (this is where "no margin" is earned)

- **Decide** is pure, so it's tested with built snapshots: running solver,
  restart overlap, half-written last step, `nsg` parts missing, post job
  killed at walltime, squeue error, two cases with similar names, remote
  size mismatch, ledger says uploaded but local file changed.
- **Invariant tests** run over many random snapshots, and must always hold:
  1. no post action covers a step that isn't settled;
  2. no post action while one is in flight for that case;
  3. no upload of an invalid or unsettled PLT;
  4. no action at all when squeue failed;
  5. (later) no delete without a `verified` remote copy.
- **Observe** tested on fake case trees in a temp dir (like the existing
  `test_scripts/`), with fake `squeue`/`scontrol`/`sacct` on `PATH`.
- **Act** tested against a local "remote" (ssh to localhost or a fake
  transport) with uploads interrupted part way.

---

## 9. Build order (one branch each)

1. **fix-queue-truth**: G1 + G2. A shared `jobs_for_case(case_dir)` by
   WorkDir; squeue errors raise.
2. **plt-validity**: header-only expected size in `fxplt`; `valid_plt()`;
   use it in `organise output` (G3) and `case check plt`.
3. **auto-observe**: snapshot + `run auto` dry-run table. Nothing acts yet.
   Run it on real cases for a while and compare with what you'd do by hand.
4. **auto-post**: D1–D3 with `--apply`.
5. **key-transport + ledger**: ssh/rsync upload with `.part` + checksum,
   `.auto/ledger.jsonl`; D4–D6.
6. **auto-report**: journal viewer (`auto log`), casestatus lines, the
   "verified on cloud, safe to delete" list.
7. *(later)* **auto-tidy**: opt-in deletion on verified copies only.

---

## 10. What the cluster probe found (2026-11-09, `tools/hpc_probe.sh`)

Run on login03, `/scratch/.../one_directional_cf/bare`, 7 cases.

**Answered**

- **`.out` naming (Q1)**: `<p>.<t>_<k>.out`, k = 0..nsg-1, exactly `nsg`
  parts per step (np = nsg = 120 in every case). No zero-size or incomplete
  steps found. `.rst` is the same. `riser.dbg.out` sits beside them and must
  never match the step pattern.
- **Running unattended (Q3)**: `crontab` is **not allowed**, `scrontab` is
  **disabled**. tmux (user-built), screen, nohup, setsid and `at` are there;
  no idle logout (`TMOUT` unset). → `run auto watch` in tmux on a login node
  is the main path. Keep in mind there are several login nodes (login03 here),
  so the session lives on one of them and dies if it reboots. Fallback: a
  1-core job on `shared` that runs one sweep and resubmits itself with
  `--begin=now+30minutes`.
- **Finished jobs leave squeue after 5 minutes** (`MinJobAge = 300`). → Any
  job that ended has to come from `sacct`, which keeps 30+ days.
- **squeue error reporting is inconsistent**: an invalid job id gives exit 1,
  but an invalid user gives **exit 0** and only a message on stderr. → Treat
  *any* stderr output from squeue as a failure (G1), not just the exit code.
- **Job names can't be trusted**: `BR0SG0U2P0/postFlex.sh` has
  `-J postBR0SG0U1P0`, and `BR0SG0U7P0/postFlex.sh` has `-J postBR0SG0U6P0`
  (scripts copied from another case). `%Z` (WorkDir) is reliable. → G2 is
  confirmed: match by WorkDir only. Auto should also *report* a job-name
  mismatch as a warning.
- **`.casestatus.md` `state:` is stale**: every case says `new`, including
  ones that are running. → Never use it for decisions; work out the state
  from the queue and files.
- **Filesystem**: Lustre, clock skew 0 s, so mtimes are usable.
- **Checksums are cheap**: sha256 of a 155 MB PLT takes 0.6 s (248 MB/s) on
  the login node.
- **Binary PLT ≈ 155 MB per step**, size differs slightly per case (per
  mesh), so the "same size as the rest" check is per case.
- **Solver speed**: a step every ~1 600 s (outFreq 5) to ~11 700 s
  (outFreq 50). A 10-minute `settle_secs` is safe.

**Things the plan didn't account for**

1. **binary/ is emptied after upload.** Most cases have 0 or 1 PLT in
   `binary/`, while `.out` remain for several steps. "No binary PLT here"
   does **not** mean "not converted". Before submitting a post job, auto
   must check the **remote** (and the ledger) too. Remote listing becomes a
   precondition of D2, not just of D4. If the remote can't be reached, no
   post decisions are made for that case.
2. **Steps that a queued restart will compute again.** `BR0SG0U4P0` has
   `.out` up to 8300, and a main job is pending to resume from 8250. Steps
   8251..8300 will be overwritten. → New rule: steps after the
   `restartTsId` of a **pending or running** main job are *provisional*.
   They aren't posted until that job has passed them again.
3. **Disk quota.** 1.58 TB of the 2 TB quota is used (79%). A post job
   writes ASCII PLTs (bigger than binary) before converting. If the quota
   fills, the *solver* fails too. → New precondition for D2: estimate the
   post job's peak usage (steps × ASCII PLT size) and refuse if it would go
   above a set limit (default 90% of quota). `lfs quota` gives the numbers.
4. **CPU limit shared with main jobs.** The `iitkgp_freeq` QOS caps you at
   `cpu=400`. Three 120-core mains = 360, so one 36-core post fits and a
   second one doesn't. A pending post can hold back a main. → Default
   `max_post_total = 1` at a time across all cases, and auto never submits a
   post while a main is pending for lack of CPUs (to be confirmed by the
   follow-up run).
5. **Stopped and failed cases** (e.g. `BR0SG0U5P0`: no job, last `.out` 32
   days old, not at maxTimeSteps; `BR0SG0U7P0`: main FAILED after 16 s).
   Auto lists these as *needs a person*. It doesn't restart them.
6. **Python 3.7 on the cluster** (`/home/apps/anaconda3`). The follow-up run
   checks which Python flexflow actually runs with there. If it's 3.7, the
   new code must avoid 3.8+ syntax.

**Follow-up run (login08, `ONLY=remotes`)**

- **Remote login: only the ssh alias works.** Key login with
  `user@ip` from `remotes.json` is refused on every remote. Through the
  `~/.ssh/config` alias it works for `wsl`, `bluelotus`, `greenlotus`.
  → Auto always connects through the alias (as `run post --remote` already
  does via `_ssh_alias`), and never through the user/ip/password in
  `remotes.json`. A remote with no working alias is not usable by auto.
- `cloud` (sshd@10.24.3.58, the NAS): no key login at all (alias refused
  too). `airavata`: unreachable from the login node (timeout).
- **QOS**: all jobs but one run under `iitkgp_freeq` (`cpu=400` per user,
  100 submits). `ritwikna_fve` (seen once, for `mainCH4SG3U5P1`) has no CPU
  cap, priority 10000, MaxWall 3 days. Posts could go under `ritwikna_fve`
  so they don't take CPUs from the mains — that's your decision.
- **`at` is not allowed** either (`/etc/at.allow` exists, you aren't in it).
  So unattended = tmux/screen on a login node, or a self-resubmitting job.
- **Several login nodes** (login03 and login08 so far): a tmux session lives
  on the node it started on. The journal and lock must live on the shared
  filesystem (they do: `.auto/` in each case), so two sweeps on two login
  nodes still can't collide. `flock` on Lustre needs the `flock` mount
  option, so the lock is a lock **file created with O_EXCL** holding host,
  pid and time, plus a stale-lock rule (older than the longest sweep and
  the pid is gone on that host).
- **flexflow's Python on the cluster** wasn't found: the launcher activates
  conda env `flexflow_env`, which isn't under `~/miniconda3/envs` etc. The
  probe now also looks in `~/.conda/envs` and `.condarc`.

**Still open**

- Remote tools (`sha256sum`/`md5sum`/`rsync`, path writable, free space) on
  the alias remotes: the follow-up only checked the login through the alias.
  The probe now runs the full test through it. Re-run with `ONLY=remotes`.
- Which remote(s) auto uploads to (`cloud` needs key setup first).
- Which QOS post jobs should use.
- Q4 command name, Q6 history upload in v1: your decision.

---

## 11. Decisions (2026-11-09)

From the third probe run and the user's answers. Where these differ from
§1–§9, these win.

**Probe (login08)**
- `cloud` key login works through the alias: armv7l NAS, **md5sum only (no
  sha256sum)**, rsync and python3 present, path exists and is writable,
  3.5 TB free. → Verification checksum is **md5**, on both sides.
- flexflow runs on Python 3.12 on the cluster (`~/.conda/envs/flexflow_env`).
  No 3.7 limit.
- bluelotus' path in remotes.json doesn't exist (typo `strcutures`); wsl is
  89% full. Neither is used by auto.

**Decisions**
- **Command**: a new top-level command `auto` (it uses `case`, `run`,
  `data` underneath).
- **Scope**: one folder per run: the cases in the current folder's `.cases`.
  One tmux loop per folder.
- **Destination**: `cloud` only. Set per folder in `.auto.conf` next to
  `.cases`:
  ```
  remote = cloud
  path   = /shares/arunperiyal/.../one_directional_cf/bare
  ```
  A case goes to `<path>/<case name>`. Without `.auto.conf` the folder is
  skipped; the remotes.json path is never used for auto.
- **Who uploads**: `auto`, run by you on the login node. **Post jobs do not
  send** (compute nodes may not reach cloud, and the NAS resets its
  authorised keys). `auto` never submits post with `--remote`.
- **Key resets on the NAS**: every sweep starts with a login test. If it
  fails, nothing is uploaded and the report says so first. Password login
  from remotes.json (as `case upload` does) is the way in when `auto` runs
  as a SLURM job, and the fallback when the NAS has dropped the key
  (whether both work from a compute node: `ONLY=job` probe).
- **Queue**: post jobs are submitted with the script's own header and your
  default account/QOS. `auto` adds `--qos`/`--account`/`--partition` only
  when you set them in `.auto.conf`.
- **What is uploaded** (all md5-verified):
  - binary PLTs;
  - history: archived/cleaned parts once, plus a refreshed snapshot of the
    live `.othd`/`.oisd` each sweep (no `organise history` run by auto);
  - the newest **complete** `.rst` set (all `nsg` parts, settled, not past a
    pending restart). cloud keeps the **two newest** sets; the older one is
    deleted from cloud only after the newer one is verified there. This is
    the only delete auto ever does, and only on cloud;
  - input files once (`.def` and every `File(...)` it names,
    `simflow.config`, job scripts, `simflow_env.sh`);
  - flexflow's own case files: `othd.*.map`, `domain.yml`, `.restarts`,
    `.casestatus.md`.
- **Local deletion**: none. The report lists which local files are verified
  on cloud, so you can delete them yourself.
- **Files already on cloud** from manual uploads: on the first sweep, md5
  is computed on cloud for each one found and compared with the local file;
  a match goes in the ledger as verified, a mismatch is uploaded again.
- **Folders on cloud**: `auto` creates `<path>/<case>` and its subfolders
  when they are missing.
- **Post timing**: the simplest rule: a post job is submitted only after the
  case's main job has **ended** (it's no longer in squeue, and sacct shows how
  it ended). It covers the settled steps that have no verified PLT (on cloud
  or valid in binary/), up to the step the next restart resumes from. At
  most one post job per case, and per run of `auto` (`--max-post`). While a
  main job is running or pending, its case gets no post job. *(What counts as
  "ended": see open questions.)*
- **No tmux** (it doesn't work well on the server). See open questions for
  how a long upload survives a dropped ssh session.

**Probe from a compute node (job 1227072 on cn018, `shared`; login08 for
comparison)**

| | login08 | cn018 (in a job) |
|---|---|---|
| remotes.json, ~/.ssh/config, .cases readable; case folder writable | yes | yes |
| flexflow python 3.12 + modules import | yes | yes |
| squeue / sacct / sbatch (`--test-only`) | work | work |
| TCP 22 to cloud, wsl, bluelotus, greenlotus | open | open |
| cloud key login (alias) | ok | ok |
| cloud password login (remotes.json) | ok, 1.3 s | ok, 0.2 s |
| 50 MB upload to cloud | 28.8 s, **1.7 MB/s** | 4.7 s, **10.6 MB/s** |
| md5sum on the NAS | 108 MB/s | 111 MB/s |
| md5 after upload | matches | matches |

One sample each. The login figure was taken under `renice 15` on a shared
login node, so it may be pessimistic. Still, a compute node is ~6x faster:
a 155 MB PLT takes ~15 s from cn018 against ~90 s from the login node.
md5 on the NAS costs ~1.5 s per PLT, so checking files already on cloud
on the first sweep is cheap (~2.5 min per 100 PLTs).

**Where `auto` runs: by hand, on the login node, when you log in.**
(Decided 2026-11-09.) A self-resubmitting job was considered and dropped:
cron, scrontab and at are all disabled for users, which reads as the admins
not wanting user-scheduled automation, and the published guidelines name
the login node as the place to transfer data. So:
- `auto` shows the plan for the folder; `auto --apply` carries it out once,
  then exits. There is no `auto watch` loop and no `auto` job.
- Uploads run at login-node speed (~1.7 MB/s measured, ~90 s per 155 MB
  PLT), so a backlog takes a while. The plan shows the estimated time, and
  `--fit` / the session-time budget (existing `case upload` behaviour)
  sends what fits and leaves the rest for the next login. (No tmux: see the open questions for dropped sessions.)
- A dropped session or Ctrl-C mid-file leaves only a `.part` file on cloud;
  the next run sends that file again from the start. Nothing is ever
  counted as uploaded until md5 matches.
- `login_cpu_limit` and low priority (renice/ionice) apply, as for
  `case upload`.
- Post jobs are still submitted to SLURM as usual; only the checking and
  uploading run on the login node.
- Possible later addition, only if the HPC team approves: a one-off `auto`
  job chained with `--dependency=afterany:<main job>` (§12).

---

## 12. Later: a chained `auto` job (not built now)

Only if the PARAM Shakti team confirms it's allowed (draft question in the
conversation of 2026-11-09). Nothing in v1 depends on it.

- `run main` (and `run main restart`) gets `--auto`: after submitting the
  main job, it also submits a 1-core job on `shared`:
  `sbatch --dependency=afterany:<main id> -J auto<case> ... auto --apply <case>`.
- That job runs once, when the main job ends (finished, out of walltime,
  failed or cancelled). It does exactly what `auto --apply <case>` does by
  hand: post job if due, uploads, verification. It never resubmits itself.
- If the main job is cancelled before it starts, SLURM drops the
  dependent job too (`afterany` never fires); nothing else is needed.
- Uploads from the compute node ran at ~10.6 MB/s in the probe (vs ~1.7 on
  the login node), with password login from remotes.json (the NAS may drop
  the key).
- Uses the same lock file and journal as a run by hand, so a run by hand and
  a chained job can't act on the same case at once.
- CPU cost: 1 core for the length of the uploads, once per main job.

---

## 13. `auto`, built on the user's own workflow (2026-11-09)

**This section supersedes §5–§7 and the "Local deletion: none" decision in
§11.** `auto` does what the user does by hand today, in the same order and
with the same commands, but runs each step only when its safety check
passes, and remembers between logins how far each case got.

### 13.1 The workflow `auto` follows (as described by the user)

*Cases that are not running*
1. `run sq find` → which cases are running.
2. `case check run` → does the run directory still hold a history file?
3. If yes and not running: `case organise history --update` (run dir →
   `othd_files/archive`, `oisd_files/archive`).
4. `case organise history --clean`, then `--compile`.
5. Upload the history to cloud (mapped path).
6. Not running + history was in the run dir ⇒ there are `.out` not yet
   converted: `run post`, with first/last step taken from the newest `.othd`
   in `archive/`.
7. Post job done ⇒ `case organise plt --delete-ascii`.
8. Upload binary PLTs to cloud.
9. Delete the binary PLTs once they're on cloud.
10. Delete the `.out` (PLTs exist now); keep `.rst` every N steps (usually
    500): `case organise output --keep-freq 500`.
11. Upload the kept `.rst` (to resume later, elsewhere).

*Cases that are running*
12–14. Find running cases that take a lot of disk (outFreq 5 writes many
    `.out`/`.rst`): `case report`.
15. Running ⇒ no `organise history --update`.
16. Take first/last step of the live `.othd` in the run dir; `run post`.
17. Post done ⇒ delete ASCII PLT, upload binary PLT, check it's on cloud,
    delete binary PLT, delete `.out` up to the last converted step, thin
    `.rst`.
18. Next case.

### 13.2 What `auto` adds: one pipeline per case, carried across logins

A post job takes hours, so one `auto apply` can't take a case through every
step. Each case moves through **stages**; each `auto apply` advances every
case as far as its checks allow and records the stage in
`<case>/.auto/state.json`. The next login picks up from there.

| stage | what | runs when (all of these hold) | command used |
|---|---|---|---|
| **H1 archive** | move run-dir history to `archive/` | no main job of the case is RUNNING, PENDING or COMPLETING (any active state; squeue, by WorkDir), checked again just before the move. No waiting on the file's mtime (13.9) | `case organise history --update` |
| **H2 clean+compile** | `--clean`, `--compile` | H1 done (or nothing to move) and `archive/` has a part not yet in `cleaned/` | `case organise history --clean --compile` |
| **H3 upload history** | archive/cleaned parts + compiled file; for a running case a snapshot of the live `.othd/.oisd` | cloud login ok; local file differs from the ledger | upgraded `case upload history` |
| **P1 post** | submit post for steps `[t1, t2]` | no post job of the case in flight; **not running**: t1..t2 = first/last step of the newest `archive/` part, **running**: first step of the live `.othd`..last *settled* step; steps past a pending restart's `restartTsId` excluded; every step's `.out` complete (all `nsg` parts); quota headroom | `run post full` (or `convert` when ASCII PLT exist) |
| **P2 post done** | check the result | sacct says the post job COMPLETED; every step in `[t1, t2]` has a **valid** binary PLT (§4.3). FAILED/TIMEOUT or a missing/invalid PLT ⇒ case stops here with *needs you* | — |
| **C1 delete ASCII** | ASCII PLT in run dir | P2 ok for that step (binary valid and newer) | `case organise plt --delete-ascii` |
| **U1 upload PLT** | binary PLTs `[t1, t2]` | P2 ok | upgraded `case upload binary` |
| **V1 verify PLT** | md5 on cloud = local md5 | U1 done | new |
| **C2 delete binary** | local binary PLTs | **V1 verified** for that file (ledger) | upgraded `case organise plt --delete-binary --verified` |
| **C3 delete .out** | `.out` of steps ≤ t2 | that step's PLT is **V1 verified on cloud** (or valid in binary/); not the step being written; not past a pending restart | upgraded `case organise output --keep-freq K` |
| **C4 thin .rst** | `.rst` not on the `keep_rst` grid (`.auto.conf`, your value; unset: no thinning) | never: the newest complete set, the set at `restartTsId` of a pending/running main, or any set past it | same |
| **U2 upload .rst** | kept `.rst` sets | complete (all `nsg`), settled | upgraded `case upload rst` |
| **U3 inputs/files** | `.def` + `File(...)`, config, job scripts, `.map`, `domain.yml`, `.restarts`, `.casestatus.md` | changed since the ledger | upgraded `case upload` |

Order inside one `auto apply`: per case H1→H2→H3, then P2→C1→U1→V1→C2→C3→C4→U2
for a post that finished, then P1 for new steps, then U3. Uploads go last
in the run so the quick local steps (and post submissions) aren't held up by
slow transfers.

**Running cases first by disk use** (steps 12–14): `auto show` sorts the
running cases by run-dir size (as `case report` measures it) and marks the
ones over `disk_alert` (`.auto.conf`, e.g. 200 GB). Every running case
with settled, unconverted steps gets a post; the size decides order and
which ones are flagged.

### 13.3 Data-loss traps in the manual workflow that `auto` must guard

These are safe when a person does them, looking. Automated as-is, they can
lose data:

1. **H1 on a case whose main job is pending.** `mainFlex.sh` archives the
   run-dir `.othd` itself when it starts. If the job starts while
   `--update` is moving files, both pick run numbers at once. And on a
   *running* case, `--update` moves the file the solver is writing (same
   inode on Lustre, so the solver keeps writing into `archive/`). → H1 only
   when no main job is running, pending or completing (queue read again
   right before the move), and `organise history --update`
   itself gets the same check (upgrade U-3).
2. **Keeping `.rst` "every 500" deletes a restart point.** `BR0SG0U4P0`
   has a main job pending that resumes from **8250**, which isn't a multiple
   of 500. `case organise output --keep-freq 500` would delete
   `riser.8250_*.rst`, and the restart would fail. → C4 always keeps the
   set at the `restartTsId` of a pending/running main and the newest
   complete set (upgrade U-5).
3. **Deleting `.out` once a PLT "exists"** (G3): an empty, cut-short or
   pre-restart PLT counts today. → C3 requires the PLT to be verified on
   cloud (md5) or valid locally (upgrade U-5).
4. **Deleting binary PLT after upload** (step 9): today
   `--delete-binary` is unconditional. → C2 deletes only files whose md5 on
   cloud matches (upgrade U-4).
5. **Post range from the newest archive part** (step 6): if that run was
   resumed from a restart, its first steps overlap the previous run's. The
   overlap is the new run's data, so converting it is right; but its last
   steps may be recomputed by a *pending* restart (trap 2's case). → P1
   stops at the pending job's `restartTsId`.
6. **Running case, last step** (step 16): the last `tsId` in the live
   `.othd` is the step being computed; its `.out` may be half-written. → P1
   uses the last *settled* step (§4.1), not the last tsId.

### 13.4 Subcommands

```
auto show [case]            # plan per case: stage, what's next, what blocks it (changes nothing)
auto apply [case]           # do what `show` lists, once, then exit
     --only history,post,upload,clean   # only these kinds of step
     --no-delete            # everything except C1–C4
     --fit                  # upload only what fits in the session time left
     --max-post N           # post jobs this run (default 1)
     --yes                  # don't ask before deleting
auto log [case]             # what earlier runs did (.auto/journal.jsonl)
auto status [case]          # stage of each case + an upload still running (see 13.6)
auto verified [case]        # files whose cloud copy matches md5 (and which are already deleted locally)
auto config                 # show/edit .auto.conf: remote, path, keep_rst, disk_alert, qos...
```

`auto apply` lists every deletion it is about to make (count, size, the
check that cleared it) and asks once before doing them, unless `--yes`.

`.auto.conf` (next to `.cases`):
```
remote     = cloud
path       = /shares/arunperiyal/phd/research/grooved_beam_structures/cylinder_12/cases/one_directional_cf/bare
keep_rst   = 500          # .rst grid kept by C4: your value, any N; unset = .rst not thinned
disk_alert = 200G         # flag running cases above this
# qos / account / partition: only if set; otherwise the post script's header
```

### 13.5 Upgrades to existing commands (each its own branch)

| id | command | upgrade |
|---|---|---|
| U-1 | `run sq`, `case status` | G1 + G2: squeue errors (any stderr) raise; jobs matched to a case by WorkDir; shared `jobs_for_case()` incl. sacct for ended jobs |
| U-2 | `run post` | callable from Python returning the job id; `--t1/--t2` taken from an `.othd` (`--from-othd PATH`); records the window in `.auto/state.json` |
| U-3 | `case organise history --update` | refuses while a main job of the case is running, pending or completing (override `--force`) |
| U-4 | `case organise plt --delete-binary` | `--verified`: only files whose md5 on cloud matches the ledger |
| U-5 | `case organise output` | `.out` only when the PLT is valid (G3) / verified on cloud; never the `.rst` at a pending/running restart, nor the newest complete set; `--keep-freq` from `.auto.conf` |
| U-6 | `case upload` | folder mapping from `.auto.conf`; key login via alias, password fallback; `.part` + rename; md5 check; ledger `.auto/ledger.jsonl`; creates folders |
| U-7 | new `src/core/plt_valid.py` | header-only expected size (from `fxplt`), size vs the case's other PLTs |
| U-8 | new `src/core/settled.py` | §4.1 settled steps, restart-provisional steps |
| U-9 | `case report` | run-dir size reused by `auto show` ordering |

`auto` calls these as Python functions, not through the shell, so it gets
results back and the same checks run whether you type the command or
`auto` does.

### 13.6 Build order (replaces §9)

1. U-1 queue truth.
2. U-7 + U-8 PLT validity and settled steps; fix G3 in `organise output`.
3. Dummy cases + fake SLURM + fake cloud (`dummy/`, generated by a script).
4. `auto show` (read-only), run against the dummy cases and then the real
   ones for a while.
5. U-6 upload with md5 + ledger; `auto apply --only upload`.
6. U-3 + history stages; `auto apply --only history`.
7. U-2 + post stages P1/P2.
8. U-4 + U-5 + delete stages, behind the confirmation.
9. `auto log`, `auto status`, `auto verified`, `auto config`.

### 13.7 Answers (2026-11-09) — these override the table in 13.2

1. **Deleting**: `auto apply` asks **once, at the start**, after showing the
   whole plan, including the deletions that will happen *if* their checks
   pass later in the run (uploads come first and take a while, so it
   doesn't stop half-way to ask). `--yes` skips the question. A deletion
   whose check fails is skipped and reported, never forced.
2. **`.rst` to cloud**: only the **newest complete set**, and only if cloud
   doesn't already have it (md5). Nothing is ever deleted on cloud (this
   replaces "keep two" from §11).
3. **No tmux needed**: you stay logged in until uploads finish. Uploads run
   in the foreground with a progress bar; a dropped session leaves only a
   `.part` file, sent again next time.
4. **What triggers a post job** is the state of the files, not how the main
   job ended. P1 runs for a case when *all* of these hold:
   - there are steps whose `.out` are complete (all `nsg` parts) and
     settled (§4.1);
   - those steps have **no PLT verified on cloud** and no valid binary PLT
     locally (and no ASCII PLT, else it's `convert`);
   - they aren't past the `restartTsId` of a pending/running main job;
   - no post job of the case is in flight.
   The run-dir history file (step 2–3 of the workflow) and the newest
   archive part only *suggest* the range; the cloud check decides it. If
   every step is already on cloud, no post job.
   This applies to running cases too (steps 12–17), with the last settled
   step as the end.
5. **Queued restart**: yes, post the finished run's steps up to the pending
   job's `restartTsId` while it waits, after the cloud check in 4.
6. **ASCII PLT are deleted after the binary PLT is verified on cloud**, not
   before (so a missing binary can be remade from the ASCII file).

New stage order for a case whose post job has finished:

```
P2 post done → U1 upload binary → V1 md5 on cloud
             → C1 delete ASCII PLT     (binary verified on cloud)
             → C2 delete binary PLT    (verified on cloud)
             → C3 delete .out          (PLT verified on cloud)
             → C4 thin .rst            (keep grid, restart point, newest set)
             → U2 upload newest .rst set (if not on cloud)
```

### 13.8 The post rule, per run (2026-11-09, replaces point 4 of 13.7)

The unit is a **run**, not a step:
- the `.othd` in the run directory, when there is one (running, queued,
  or ended and not yet moved by H1);
- else the newest part in `othd_files/archive/`, **never `cleaned/`**: a
  cleaned part is rewritten by `--clean` (steps a later run computed again
  are cut), so its first/last tsId are not the run's (13.10);
- neither: no post decision; *needs you* ("no archive/ part to take the
  window from").

Its first and last tsId, rounded to outFreq, give the range `[t1, t2]`,
trimmed to the last settled step (§4.1) and to the `restartTsId` of a
pending/running main job.

| binary PLTs of `[t1, t2]` on cloud | `auto` does |
|---|---|
| **none** | submit one post job for `[t1, t2]` (`convert` if ASCII PLT are already there) |
| **all** | nothing; the run is done |
| **an unbroken stretch `[t1, k]`** (typical for a running case posted on an earlier login) | submit one post job for `(k, t2]` |
| **some, with holes** | no post job; the case is listed under *needs you* with the missing steps. You decide (e.g. `run post full --t1 .. --t2 ..`) |

A case that is running or queued can get a post job too. Never while a
post job of that case is pending, running or completing.

**Inputs must be there (2026-11-09).** A post job fails without its inputs,
so before submitting, every step of the range to post must have either
- all `nsg` parts of `<p>.<t>_<k>.out`, each > 0 bytes and settled → `run post full`, or
- the ASCII `<p>.<t>.plt` in the run directory → `run post convert`.

If any step in the range has neither, no post job: the case goes under
*needs you* with those steps ("no PLT on cloud and no .out here"). That
means the data is somewhere else or lost; only a person can tell.

### 13.9 No waiting before moving the history (2026-11-09)

H1 used to wait until the run-dir `.othd` had not changed for 10 minutes.
Dropped: once no main job of the case is RUNNING, PENDING or COMPLETING,
nothing in the queue can be writing it (COMPLETING covers a job that is
ending and still writing; a job that has left the queue has written its
files). The one race that matters, a main job submitted while `auto` is
moving the files, is closed by reading the queue again just before the
move, not by waiting.

Not covered: a solver started outside a batch job of the case directory
(e.g. `mpiSimflow` in an interactive `salloc` session started elsewhere).
That is not how cases are run.

The `.out` "settled" rule in the post decision (§4.1) stays: a running
case's newest step may be half-written, so it counts only once the solver
has moved past it.

### 13.10 Post window from archive/, never cleaned/; keep_rst is yours (2026-11-09)

- **Window source.** The run whose PLTs are checked and posted is the run
  directory's `.othd`, else the newest part in `othd_files/archive/`. Never
  a `cleaned/` part: `--clean` rewrites it, cutting the steps a later run
  computed again, so its range is not the run's. With neither, the case is
  listed under *needs you*. The probe found four `bare` cases with no
  `archive/` (pruned after `--clean`: U2P0, U3P0, U5P0, U6P0); a finished
  one of those (U3P0, U5P0) gets no automatic post.
- **`.rst` grid.** Thinning keeps the steps divisible by `keep_rst` from
  `.auto.conf`, which you set (500 is only an example). Without it, `auto`
  thins nothing and says so. The restart point of a queued job, the newest
  complete set and a set still being written are kept whatever the grid
  (as `case organise output` now does).
