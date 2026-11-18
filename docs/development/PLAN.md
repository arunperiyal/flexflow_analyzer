# Plan

The one plan file of this project. Work is listed as **phases**, each split
into **tasks**.

- A phase is one feature or one coherent piece of work. It gets **one branch**,
  cut from `main` by the user, named as shown beside the phase.
- A task is one step that can be checked on its own. It gets **one commit**,
  and its box is ticked in that same commit.
- A new feature is added here, as a phase with tasks, before any of it is
  built. Add it after the last phase and give it the next number; numbers are
  never reused.
- A phase is merged into `main` when all its tasks are ticked, then moved to
  [Done](#done) as a single line.
- Ideas that are not ready to be split into tasks go in [Backlog](#backlog).

Status marks: `[ ]` to do, `[x]` done, `[~]` dropped (say why).

---

## Open phases

### Phase 6: `auto apply`, deleting (branch `auto-delete`)

Built first, before Phases 12 to 17 changed `auto` to run the commands `auto
show` lists; merged with them on 2026-11-16 (the delete stage reads
`plan.ctx['delete']`, the new code reads `plan.steps`). The first design
(`auto.md` §13.13, commit `1abbe95`) has `auto` delete files itself from an
explicit list, each checked again by md5 right before it goes. The direction
set on 2026-11-13 is that `auto apply` runs the same commands `auto show`
lists, so the md5 check belongs to `case check plt --verify` (Phase 13) and
the refusal to delete an unchecked file to `case organise plt` / `case
organise out` (Phase 14). Both paths now exist side by side.

- [x] Write the design as §13.13 at the end of `auto.md`
- [x] **Review of §13.13 by the user.** Nothing below is built before it
- [x] Remote md5 of a named file (`cloud.py`: `LocalCloud`, `SftpCloud`);
      ledger entries record the local `mtime` and `deleted`
- [x] Decide: the candidates of C1–C4 as explicit file lists in `plan.ctx`,
      with the "written after" rule and the data-related *needs you* hold-back
- [x] Executor `do_delete`: per-file checks right before each unlink, run log
      lines, the `.casestatus.md` line, the ledger
- [x] `auto apply --delete` and `--only delete`: order
      `history → upload → delete → post`, the plan listing, the question with
      totals, `--dry-run`
- [x] Reports (`auto show`, `auto commands`): replace the `[not built yet]`
      text
- [x] Dummy cases and a test for each rule: copy differs, size-only copy,
      `.out` newer than its PLT (restart), queued restart, post in flight,
      restart-set keeps, a case that needs you
- [x] Help text, completion, `docs/architecture/auto_flow.html`, the web
      flowchart, `CHANGELOG.md`
- [ ] Reconcile the two delete paths: have `do_delete` call the chain commands
      (`case organise ...`) it now duplicates, keeping the "written after"
      rule, the queued-restart hold-back and the one question with totals


### Phase 7: `auto`, the steady check (branch `auto-steady`)

`data check steady` exists; `auto` does not use it yet. `auto` never queues
main jobs.

- [ ] Design section at the end of `auto.md`: settings under `auto:` in
      `.cases.yml` (variable, last N frames, tolerance)
- [ ] Observe: run the steady check over the last N frames of OTHD/OISD, only
      for cases that reached `maxTimeSteps`
- [ ] Decide and report: not steady goes to "Needs you" with
      `def time maxTimeSteps <N>` then `run main restart <last step>`
- [ ] Dummy cases (steady, not steady) and tests
- [ ] Help text and `CHANGELOG.md`

### Phase 8: `auto log` and `auto status` polish (branch `auto-log`)

- [x] `auto log [case] [--list] [--log N]`: read back the run logs in
      `<folder>/auto_logs/` (newest by default, one case's lines, `--list` for
      every run, `--log N` for the Nth newest)
- [x] `auto status`: polish the layout (the job column names the job id; a footer
      counts the cases, those with something to do and those that need you, as
      `auto show` does)
- [x] With a queued restart, `Complete` / `Also kept` should not count the
      earlier run's newer restart set
- [x] Tests, help text, completion, `CHANGELOG.md`

### Phase 9: files for FlowReel (branch `flowreel-export`)

Design: `docs/architecture/flowreel.md`. Check the key names against FlowReel's
own `docs/PLAN.md` before writing code; they may have changed.

- [ ] A `flowreel.yml` writer in the `field` command
- [ ] All probes of a body in one CSV
- [ ] The pendulum as CSV
- [ ] VTU for FlowReel, with `field extract`
- [ ] Tests, help text, a usage page in `docs/usage/`, `CHANGELOG.md`

### Phase 10: documentation that installs and development notes (branch `docs-install`)

- [ ] Installer (`src/installer/install.py`): copy the non-markdown files of
      `docs/` too (`auto_flow.html`, the SVGs)
- [ ] Installer: turn `.md` links into `.html` links in the converted pages
- [ ] `src/templates/example_case_multi.yaml` points at
      `examples/case_multi_with_globals.yaml`, which git ignores: track the
      example or drop the pointer
- [ ] `docs/development/testing.md`: how to run the tests, what
      `examples/BR0SG0U1P0` is needed for
- [ ] `docs/development/tools.md`: `make_dummy.py`, `fake_slurm.py`,
      `hpc_probe.sh`
- [ ] Bring `.claude/context/NEXT_SESSION.md` up to date (only when the user
      asks: it still names the old doc paths)

### Phase 11: web UI, close the old checklist (branch `webapp-checklist`)

`docs/architecture/webapp.md` §11 lists its phases with every box unticked,
but most of it is built (the package, the picker, panels, `web start` /
`web stop`, export, and more that §12 called out of scope: field render, FFT,
spatial plots).

- [ ] Go through §11 against the code and tick what exists
- [ ] Move what is left into this file as a new phase, and replace §11 with a
      pointer here
- [ ] Rewrite §12 "Out of scope" to match what the web UI now does

### Phases 12 to 17: `auto` as a sequence of visible commands

Asked for on 2026-11-13. The aim: the user can read in `auto show` the exact
commands `auto apply` will run, in order, and run any of them by hand.

For the PLT section, the Action list becomes commands only, for example:

```
1: case check plt <case> --verify
2: case upload plt <case> --t1 8950 --t2 9900 --freq 50 --remote cloud
3: case organise plt <case> --delete-ascii --t1 8950 --t2 9900 --freq 50
4: case organise plt <case> --delete-binary --t1 8950 --t2 9900 --freq 50
```

- `case check plt --verify` does not exist yet. It verifies every PLT in
  `binary/` against the remote directory.
- When the binary PLTs are not made yet, the second command is
  `run post convert` (or `run post full`).
- `case upload binary` is renamed `case upload plt`, to be specific.
- `--missing` is added only when the remote lacks some of the PLTs.
- The same change for History, OUT files, RST files, and Inputs and case
  files.

Settled with the user on 2026-11-13:

- **The deletion chain.** A `.out` may be deleted when the ASCII PLT of its
  step is verified. An ASCII PLT may be deleted when the binary PLT of its
  step is verified. A binary PLT may be deleted when the remote directory
  holds its copy.
- An ASCII PLT is verified by its size and by the node and element counts in
  its header.
- A later link stands in for a missing one: with no ASCII PLT, the `.out`
  goes on the verified binary PLT; with no binary PLT, on the remote copy.
- Every step that has `.out` files gets its PLT made and uploaded; nothing
  is thinned out. `--freq` is the spacing of the series. Before deleting,
  the command confirms that the series from `--t1` to `--t2` has its next
  file in the chain, in the local or the remote directory.
- `case upload --to` and `case download --from` are renamed `--remote`.
- **Repair goes back along the chain** (2026-11-13). A broken binary PLT
  means a broken remote copy too: it is made again from the ASCII PLT (`run
  post convert`); if the ASCII PLT is broken as well, from the `.out` files
  (`run post full`). `auto show` prints that command.
- An ASCII PLT can only be checked by its size and header; a binary PLT is
  always checked by md5, read back from the remote when it has no `md5sum`.
  Time is not the concern; a safe copy on the remote is.
- An empty local `binary/` with the PLTs on the remote is a normal state:
  the local files were deleted to save space (and the ASCII PLTs and `.out`
  may be gone too, or not).
- A folder whose `.cases.yml` has no block for the remote says so: the
  remote is not set and its path is not set.
- `auto apply` has the targets `history`, `plt`, `output`, `input`, `rst`
  and `all`.
- `auto apply` is not only for deleting: it organises, uploads and deletes
  in a conditional sequence. `--dry-run` uploads and deletes nothing and
  prints the sequence in full. `auto show` stays as it is: state,
  observation and action.
- `case organise plt` always verifies. There is no `--unverified` flag.

Order of work: 12, 13, 18, 14, 19, 15 and 16 (done), 17, 20, then Phase 6. Phases 12 to 14 change
hand commands and are useful on their own; 15 is a refactor with no change in
behaviour; 16 and 17 are what the user sees.

What the code check found (why 12, 14 and 15 are needed):

- **Two upload paths.** `case upload` (`case/download_impl/command.py`, 2660
  lines) sends without an md5 check, a temporary name or the ledger. `auto
  apply` does not call it: it has its own path (`core/auto/cloud.py` `put`,
  `executor.do_upload`) with all three. So the `case upload ...` line that
  `auto show` prints is not what `auto apply` runs, and running it by hand is
  weaker.
- **Hand deletions are not guarded.** `case organise plt --delete-binary` is
  unconditional, and `--delete-ascii` only asks for a newer file in
  `binary/`. Neither knows about the remote copy.
- **Show and apply describe the work separately.** `report.build()` writes
  the Action lines as text (some are commands, some start with
  `auto apply: ` or `wait:`, and `commands()` filters by that prefix);
  `apply._intended()` writes its own list. Nothing makes the two agree.
- **`decide()` was one function of about 530 lines** and `report.build()` one
  of about 310, each covering history, PLT, `.out`, `.rst` and inputs in a
  row. `auto apply plt` needs the PLT part on its own. (Split in Phase 15.)
- **Parsing.** `auto` takes `what` and `[case]` as positionals. A target word
  after `apply` (`history`, `plt`, `output`, `all`) has to be told apart from
  a case name.

### Phase 17: `auto apply <target>` (branch `auto-apply-targets`)

- [x] `auto apply history [case]`, `plt`, `output`, `input`, `rst` and
      `all`: each runs the steps of its target (organise, upload, delete),
      in the order `auto show` lists them, each step only if the one before
      it succeeded
- [x] `auto apply` with no target does nothing and lists the targets
- [x] `--dry-run` (as in `auto apply all --dry-run`): uploads and deletes
      nothing, and prints every step with what it would send or delete
- [x] `--only` for `apply` goes (or stays as an alias for one release)
- [x] Parsing: a target word against a case of the same name (shell completion of the targets not done)
- [x] Tests, help text, `docs/architecture/auto.md` (a new section at the
      end), `CHANGELOG.md`

### Phase 20: `case organise out` and `case organise rst` (branch `organise-out-rst`)

Asked for on 2026-11-14, after reading an `auto show` whose `.out` and `.rst`
actions were both `case organise output ...` with opposite flags (`--all-out`
for the `.out` files, `--keep-out` for the `.rst`). Two words say what each
command touches. To be built after Phase 17, before Phase 6, so that Phase 6
deletes with the final command names.

- [x] `case organise out`: what `case organise output` does to the `.out`
      files (the `--all-out` path, the chain rules of Phase 14, `--t1` / `--t2`, `--remote`; no `--keep-freq`)
- [x] `case organise rst`: what it does to the `.rst` files (the `--keep-out`
      path: `--keep-freq`, `--keep-newest`, `--t1` / `--t2`); no `--keep-out`
      flag is left
- [x] The `output` subcommand is removed, with its flags `--all-out` and
      `--keep-out`; the old word gives a one-line error that names the new
      ones
- [x] `auto show`, `auto commands` and `auto apply` print and run the new
      commands (`decide.py` steps `delete-out` and `thin-rst`; the `apply`
      targets `output` and `rst` stay as they are); the dummy cases, tests,
      completion, help text, `docs/usage/`, `docs/architecture/auto_flow.html`,
      the web flowchart and `CHANGELOG.md` follow

### Phase 21: `plot --archive N` (branch `plot-archive`)

Asked for on 2026-11-17, after a `plot --gnu` of `fixed/bare` showed one
spike near step 2750, where `riser5` and `riser6` both restart inside
`riser3`. To see whether the spike is in the solver's files or made by the
compile, `plot` must be able to read single archived runs. `plot` with no
flag keeps reading the whole history (compiled file while fresh, else the
runs; `core/history.read_files`).

- [x] `core/history.parse_runs()`: `1,3` / `2-4` / `1,3-5` to a list of run
      numbers; ascending only, else an error that says so (Phase 22 uses it
      too); `pick_archived()` takes the files
- [x] `plot --archive LIST`: read `othd_files/archive/` and
      `oisd_files/archive/` runs of those numbers, in order, instead of the
      whole history; a bare `--archive` is every archived run; a number not
      in `archive/` is an error that lists the ones there. The file
      choice goes through `shared.find_files` / `scan_kinds` / `select`
- [x] The title and the `reading` line say which archive runs were read
- [x] Dummy case with overlapping runs, tests, help text, completion,
      `CHANGELOG.md`

### Phase 22: `case organise history --clean 1,2,3` (branch `organise-clean-select`)

Asked for on 2026-11-17. `--clean` decides itself which runs make the
history; with abandoned branches (`riser4`, `riser5` of `fixed/bare`) the user
must choose. `archive/` is the store and is never changed by `--clean`;
`cleaned/` is derived and temporary, so `--clean LIST` replaces it: files not
in the new set are removed, the named runs are written renamed `1..N` in the
order given. Design agreed on 2026-11-17 (user's words: "clean is a temporary
directory between archive and the compiled file").

- [x] `core/history`: `cleaned/.runs.json` (`{"cleaned": {N: archive M},
      "skipped": [...]}`: read, write, remove); `runs()` / `read_files()` read
      through it: a cleaned file counts as its source run, the skipped runs
      are ignored, an archive run that came after is a new run
- [x] `--clean LIST` (syntax of Phase 21, ascending only): the plan reads only
      those runs; `cleaned/` is made to hold exactly `1..N`; the record is
      written; mapping, overlaps and gaps are printed; the question lists the
      files removed and written (`--no-confirm`, `--dry-run` as today)
- [x] `--compile`, `--verify` and the "up to date" check judge `cleaned/`
      against the selection in the record
- [x] `--prune` refuses while a record is present and says why; a plain
      `--clean` (all runs) asks, clears the record and cleans everything
- [x] Tests (selection, rename order, removal of the old files, readers,
      compile, verify, prune refusal, plain `--clean` after a selection),
      help text, completion, `docs/usage/case-organise.md`, `CHANGELOG.md`

### Phase 23: `plot --run` (branch `plot-run`)

Comment 6 of `version comment` (2026-11-11) and asked again on 2026-11-17:
`plot` reads only the history (`othd_files/`, `oisd_files/`); it cannot show
what a job is writing now, before `case organise history --update` moves it
into `archive/`. `plot` with no flag keeps reading the whole history.

- [x] `plot --run`: read the `.othd` / `.oisd` of the case's run directory
      (`dir:` of `simflow.config`, e.g. `RUN_1`) instead of the history; a
      cut-off last step (a job still writing) is left out, as `--clean` does;
      an empty run directory is an error that says so
- [x] `--run` and `--archive` exclude each other, with an error that says so;
      the title and the `reading` line name the run directory
- [x] Tests (a dummy run directory, a half-written last step, both flags),
      help text, completion, `CHANGELOG.md`

### Phase 24: help examples and the carried `.casestatus.md` (branch `help-and-carry`)

From `version comment` 1 (2026-11-01) and 2 (2026-11-10).

- [x] Examples in the `help_messages.py` files and `docs/usage/` start with
      the command, not `flexflow ` (about 220 lines); one pass, then a test
      that no help text has the prefix
- [x] `case download` / `case upload` of a case whose folder is missing on
      the remote: `.casestatus.md` and `.restarts` are skipped with one line
      that says why (upload the case first), instead of `[Errno 2] No such
      file` twice; the run still ends `Incomplete: n/m` only for what really
      failed. Decided: no empty case folder is made on the remote for the
      notes alone
- [x] Tests, `CHANGELOG.md`

### Phase 25: shellkit, `version comment clear` and `\` continuation

From `version comment` 5 (2026-11-10) and the request of 2026-11-17. The
`version` builtin and the shell are in shellkit (a separate repository,
pinned in `requirements.txt` (v0.1.6 had `version comment --remove N` and no
clear-all), so the work was there and FlexFlow only moved the pin, to v0.1.7.
Shellkit has no changelog file; its changes are in `DESIGN.md` there.

- [x] shellkit: `version comment clear` clears every comment (asks first
      unless `--yes`); `version comment clear 2` / `clear 2 4` clears those
      numbers and says so for a number that is not there; `--remove` stays;
      tests, help text, its changelog
- [x] shellkit: a line ending in `\` continues on the next line (prompt shows
      a continuation mark), in the interactive shell; tests
- [x] shellkit tagged (v0.1.7), the pin in `requirements.txt` here raised,
      the suite run against it

---

### Phase 26: `auto show` posts steps a finished post job was never given (branch `auto-post-window`)

From the user's `auto show` of CS4SG3U1P0 (2026-11-18): a post job that ended
COMPLETED while the main job was still writing `.out` made `auto` say "ended
COMPLETED after the .out of steps ... were written, yet they have no whole
PLT" and suggest no `run post`, for steps written while that job ran. With no
`post job N started: steps a..b` line, the window of the job came only from
the local `binary/` PLTs, which are empty once uploaded.

- [x] The window of a post job with no log line also comes from the PLTs on
      the remote written while it ran (`snap.cloud_mtime`), not only from
      `binary/`; test with an emptied `binary/`
- [x] Tests, `CHANGELOG.md`

### Phase 27: `run sq` is easier to use (branch `run-sq-usage`)

From the user (2026-11-18): `run sq` is a little confusing to use. One command
does four jobs, told apart by the first word: the queue (`run sq`), a refresh
loop (`run sq watch [N]`), a search (`run sq find KEY`) and one job
(`run sq <job_id> [--out] [-n N]`). `--by-dir` and the many `--sort` names
(14, with aliases such as `id`, `job-id`, `jobid`) are not easy to tell apart.

- [ ] Decide with the user what confuses them: the four modes in one command,
      the option names, the output columns, or the help. Ask for the commands
      they typed and expected
- [ ] Rework the usage and help text: a short "what do you want to do" list
      first (see my jobs, watch, find a case's jobs, see one job and its log),
      then the options
- [ ] Rename or fold the confusing parts the user picks (for example `find`
      beside `--by-dir`, or the `--sort` aliases), keeping the old words
      working with a note
- [ ] Mistyped input is explained: `run sq watch abc`, `run sq find` with no
      key, a job id that is not in the queue
- [ ] Tests, help text, completion, `CHANGELOG.md`

### Phase 12: `case check --remote`, verify against the remote (branch `check-remote`)

Found on a real case (`BR0SG0U1P0`, PLTs moved to the remote by hand; none
left here). `case check plt` printed "no riser.<step>.plt ... 1400 expected",
and `case organise output --all-out` (no remote chosen) said "The remote was
not asked" and kept the `.out` of step 5740 with "Convert them first (run post
full)", though the PLT was on the remote. Both looked only on this machine.

- [ ] Design: how `check` reads the remote (the `remote` / `.cases.yml`
      folder as `auto` does, read-only), and what a file moved by hand counts
      as; add it as a section at the end of `auto.md` or a short note in
      `docs/architecture/`
- [ ] Rename `case check out` to `case check output` (parser, help, completion,
      `case check all`, docs); keep `out` as an alias for now
- [ ] `case check history --remote NAME`: compare the history files here with
      the remote's
- [ ] `case check plt --remote NAME`: a `remote` row next to `binary/` and
      `./RUN_n/`; without a remote, say the remote was not looked at, not
      "no PLT; N expected"
- [ ] `case check output --remote NAME`: for each `.out`, whether its PLT is
      here or on the remote; steps with neither are listed as "convert first"
- [ ] `case organise output`: before deleting `.out` files, look for their
      PLTs on the remote (`--remote` or `use remote:`; one remote in
      `.cases.yml`: use it); "Convert them first" only for steps with a PLT
      nowhere. The "not asked" line says what to type
- [ ] Dummy case (PLTs on the remote only, none local) and tests for each
- [ ] Help text, completion, `CHANGELOG.md`

## Backlog

Not split into tasks yet. Each needs a decision before it becomes a phase.

- **Chained `auto` job** (`auto.md` §12): a one-core job submitted with
  `run main --auto` that runs `auto apply` when the main job ends. Only if the
  HPC team allows it; cron, scrontab and `at` are disabled there.
- **`.rst` size check**: a restart part cut short inside a complete set is
  not detected. Also md5 of files already on the remote on the first run.
- **Job names on `fixed/bare`**: jobs are `mainBR0fixed` / `postBR0fixed`, not
  `main<case>`. Per-case setting in `.cases.yml`, or rename the jobs.
- **Web UI open questions** (`webapp.md` §13): OISD beside OTHD in the plot
  dialog; a `stride` for long histories; a `plate` body type; saved workspaces
  as `workspace.json`.
- **The `config` command**: `src/commands/config/` (`config template`) is not
  registered in `src/cli/app.py`, and `template` does the same job. Remove it
  or register it.
- **Stale shell completion**: `src/cli/completion.py` still offers commands
  that no longer exist (`info`, `new`, `preview`, `statistics`, `config`).
- **Project layout**: rename `test_scripts/` to `tests/`; a `pyproject.toml`
  with the pytest settings.

## Open branches

As of 2026-11-17, after Phases 21 to 24 were merged. To work on later.

| Branch | Phase | State |
|---|---|---|
| `docs-install` | 10 | 4 commits not in `main` (installed documentation, development testing tools, next-session notes); 37 commits behind `main`, so merge or rebase `main` first. On `origin` |
| `flowreel-export` | 9 | 1 commit not in `main` (`Add FlowReel body export`); 37 commits behind `main`, same. On `origin` |
| `auto-post-window` | 26 | Merged into `main` (`ff0dd3d`) and kept on `origin` on purpose, as the reference if this bug returns: `auto show` suggests no `run post` and prints `Post job N ended COMPLETED after the .out of steps ... were written, yet they have no whole PLT`, for `.out` the post job was never given (it ended while the main job still wrote them). Cause: with no `post job N started: steps a..b` log line, the job's window was read only from `binary/`, empty once uploaded; the fix (`f169a78`, `_post` in `src/core/auto/decide.py`) also reads the remote PLTs' write times. Still unfixed: a remote that got its PLTs from a later upload, not from the post job, has mtimes outside the window and gives the old alarm |

- The user merges both open branches; Claude resolves conflicts when asked.
- 115 merged local branches are still there (Phase 4's open item); the user
  deletes them when they like.

## Waiting on the user

As noted on 2026-11-11; may be out of date.

- First real run of the additive steps on the cluster:
  `auto apply BR0SG0U1P0 --remote cloud --only upload --dry-run`, then without
  `--dry-run`; bring back `auto_logs/auto_<time>.log` and `auto show`.
- `BR0SG0U6P0`: `archive/` is empty locally; restore with
  `case download history BR0SG0U6P0 --archive --from cloud`.

---

## Done

| Phase | Branch | What |
|---|---|---|
| 1 | `docs-reorganise` | Docs sorted into `installation/`, `usage/`, `architecture/`; case-create notes merged; dead links fixed; index added; `docs` command fixed |
| 2 | `claude-context` | `.claude/rules/`, `.claude/context/code-map.md`, short `CLAUDE.md` |
| 3 | `plan-file` | This file; `problems.md` removed (its problem was fixed in `389ef30`); the `prompt.md` note (`run post --remote`, `--t1` / `--t2`) found already built |
| 4 | `repo-cleanup` | Removed `module_backup/`, `main_old.py`, the shadowed command files, root `mainFlex.sh` and `sample.yaml`; `.gitignore` tidied. The `config` command was left (backlog). Still open, on the user's word: delete the local branches already merged |
| 5 | `web-render-tests` | The two failing render tests: the route they fetched was removed on purpose in `70d5224`; the tests now go through `save` and `render-file/<token>` |
| 12 | `checked-transfer` | `case upload` and `auto` send through one checked path (`src/core/transfer/`: temporary name, size and md5, rename) and one ledger, whose entries now hold the local `mtime` and the remote `path`; `--to` / `--from` became `--remote`; the crash of `case upload --help` fixed |
| 13 | `plt-verify` | `case upload plt` / `case download plt` (the old word `binary` still works); `case check plt --verify --remote NAME` compares each binary PLT with its remote copy by size and md5, writes the ledger and exits 0 only when all are verified (`verify_plts()` in `src/core/transfer/verify.py`) |
| 18 | `plt-verify-chain` | `case check plt --verify` after the user's review: md5 by reading the copy back when the remote has no `md5sum`; PLTs only on the remote compared with the ledger's record (an emptied `binary/` is fine); steps in neither place listed; a broken PLT says how to make it again (`run post convert`, else `run post full`); a remote that is not set says so |
| 14 | `organise-verified` | Deleting along the chain (`core/chain.py`): `.out` on a verified ASCII PLT (`core/plt_ascii.py`), an ASCII PLT on a verified binary PLT, a binary PLT on a remote copy with the same md5 read at that moment (`--remote`); a missing link is passed over; a step with nothing to stand in is kept and reported, the others go. `--freq` for `--delete-ascii`. Left open: the queued-restart rule is left to `auto` (Phase 6) |
| 19 | `organise-review` | After the user's review of Phase 14: the ASCII check reads the real simPlt header and counts in blocks; `--all-out` checks each `.out` (it now does what the plain command does); `--freq` is accepted with `--delete-ascii` (the flag check had still refused it) |
| 15 | `auto-steps` | Refactor, no change in what `auto` prints or does: the plan carries `plan.steps` (`PlanStep`: target, kind, key, command, files); `decide()` and `report.build()` are split into one function per part; the report's command lines and `auto apply` both read the steps; `test_auto_steps.py` holds them together on every dummy case. `apply` still runs history, upload, post in that order with the uploads as one transfer; per-target order is Phase 17 |
| 16 | `auto-show-commands` | Every Action of `auto show` is a command, in the order `apply` takes them (`auto.md` §13.14): check, post, upload, deletes for PLT; the same for History, OUT, RST and Inputs. Waits and reasons are rows (`Waiting`, `Why`, `Delete`, `Thin`, `By hand`). New: `case upload history --live`. The check and delete steps are in `plan.steps` (kinds `check`, `delete`) but `apply` does not run them yet. Not done: `auto_flow.html` was left as it is (it draws the decisions, not the Action lines) |

---

## Template for a new phase

```
### Phase N: <what> (branch `<kebab-case-name>`)

Design: <where the design is, or two lines of it>.

- [ ] <task: one commit>
- [ ] <task: one commit>
- [x] Tests, help text, completion, `CHANGELOG.md`
```
