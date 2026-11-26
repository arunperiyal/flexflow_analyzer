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

### Phase 30: `case organise out` with PLTs only on the remote, unrecorded (branch `unrecorded-remote-plt`)

Found on a real case (`CH4SG3U3P1`, the cluster, `binary/` empty here). `case
check plt --verify` finds 180 PLTs on the remote and none here: 15 (8300 to
9000) "as recorded when verified", 165 (50 to 8250) "no record of a verified
copy to compare with" (PLTs that got there by hand, not by `case upload`).
`case organise out --t1 8050 --t2 8300` then keeps every `.out` with two
messages, both saying less than the truth:

- 8050 to 8250: "Keeping .out of 5 step(s) with no riser.<step>.plt yet ...
  Convert them first (run post full ...)". **Wrong:** the PLTs are on the
  remote. The chain (`core/chain.py`, `remote_copies` in `RemoteCopies.load`)
  takes only the recorded copies (`verified + kept_there`); an unrecorded one
  (`only_there`) is left out, so the step reads as "no PLT anywhere" and the
  advice is to post it again, which is not needed.
- 8300: "the copy of riser.8300.plt on the remote is not newer than its .out".
  The record's time is when the local file was written (`mtime` of the ledger
  entry); the `.out` is newer than that. It may be right (a restart wrote the
  `.out` again after the PLT) or not (the `.out` touched later); the message
  gives no times, so the user cannot tell which.

The rule that a PLT must be verified and newer than the `.out` stays: it is
what keeps a restart's new `.out` from being deleted on the strength of the
earlier run's PLT. What is missing is the way out for a copy that is there but
unrecorded, and the right words.

- [ ] Name it as it is: a step with an unrecorded copy on the remote is "on the
      remote, not recorded", not "no PLT yet", in `case organise out`, `plt`
      and `auto show` (`found`/`why` in `core/chain.py`, the `none` and `bad`
      messages in `organizer.py`)
- [ ] Say how to get a record: for each step the command that makes the
      remote copy count (see the next task), instead of "post again"
- [ ] A way to record copies that are only there, with the user vouching:
      `case check plt --remote --adopt [--t1 A --t2 B]` writes the ledger
      entry from the remote's size, md5 and write time (it cannot compare with
      a local file: it says so), and says what it did not prove. Decide with
      the user whether this, or `--trust-remote` on `case organise out`, or
      downloading the PLT to check it, is the way
- [ ] The "not newer than its .out" message gives both times (the PLT's and the
      `.out`'s) and the likely cause (a restart wrote the `.out` again), and
      what to do (post that step again)
- [ ] `auto` is not changed: it never adopts a copy by itself; `auto show`
      reads "not recorded" as a thing for the user (a `needs` item with the
      command)
- [ ] Tests (a dummy case with unrecorded, recorded and older-than-`.out`
      copies on the folder remote), help text, `CHANGELOG.md`

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
- [x] Help text, completion, `CHANGELOG.md`

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

As of 2026-11-26, after Phase 44. To work on later.

| Branch | Phase | State |
|---|---|---|
| `docs-install` | 10 | 4 commits not in `main` (installed documentation, development testing tools, next-session notes); 112 commits behind `main`, so merge or rebase `main` first. On `origin` |
| `flowreel-export` | 9 | 1 commit not in `main` (`Add FlowReel body export`); 112 commits behind `main`, same. On `origin` |
| `auto-post-window` | 26 | Merged into `main` (`ff0dd3d`) and kept on `origin` on purpose, as the reference if this bug returns: `auto show` suggests no `run post` and prints `Post job N ended COMPLETED after the .out of steps ... were written, yet they have no whole PLT`, for `.out` the post job was never given (it ended while the main job still wrote them). Cause: with no `post job N started: steps a..b` log line, the job's window was read only from `binary/`, empty once uploaded; the fix (`f169a78`, `_post` in `src/core/auto/decide.py`) also reads the remote PLTs' write times. Still unfixed: a remote that got its PLTs from a later upload, not from the post job, has mtimes outside the window and gives the old alarm |

- The user merges both open branches; Claude resolves conflicts when asked.
- 115 merged local branches are still there (Phase 4's open item); the user
  deletes them when they like.

## Waiting on the user

As noted on 2026-11-26.

- First real run of the additive steps on the cluster:
  `auto apply all --case BR0SG0U1P0 --remote cloud --only upload --dry-run`, then without
  `--dry-run`; bring back `auto_logs/auto_<time>.log` and `auto show`.
- `BR0SG0U6P0`: `archive/` is empty locally; restore with
  `case download history --case BR0SG0U6P0 --archive --remote cloud`.
- The new command forms (Phases 33 to 44) on real data: `case organise out --no-verify --t1 N`,
  `data check steady --case * --var dy | data stats --func rms`,
  `auto status --case * --only needs | case show`, and Tab after `history`, `auto apply`, `run post`.

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
| 35 | `out-no-verify` | `case organise out --no-verify`: deletes every `.out` in `--t1`/`--t2` without a PLT standing in; needs a range, lists the steps with no PLT (their field data is lost), asks first (`--yes`, `--dry-run`); `rst` refuses it and `auto` never passes it |
| 33 | `steady-rows` | `data check steady` offers `{case, t1}` (and `var` when several are checked) to the command after a `\|`: `data check steady \| data stats --func rms`; a variable with no steady start offers nothing and says so |
| 34 | `status-rows` | `auto status --only needs\|todo\|running\|all` offers `{case}` per case to the command after a `\|` (`auto.md` §13.19) |
| 36 | `plt-completion` | `case organise plt\|history` Tab offered only directories with the case from `use case:`; superseded by Phase 37 (the case is a flag, the first word is an action) |
| 37 | `command-levels` | `.claude/rules/command-design.md`; `case organise` takes `--case NAME`, never a word; flags typed in full; the values used are printed, typed or `use`; `auto` writes the new lines (§13.20) |
| 38 | `flag-rules` | Every parser `allow_abbrev=False`; a typed `--t1`/`--t2` displaces `use last:`/`time:` and says so; `--last` typed with `--t1`/`--t2` is refused |
| 39 | `case-flag-case` | `--case` for `case show`, `run`, `out`, `check *`, `status`, `upload`, `download`, `domain` |
| 40 | `other-flag-case` | `--case` for `data`, `plot`, `field`; `BaseCommand.run` refuses a stray word and names the flag |
| 41 | `names-as-flags` | `case create --name`, `remote ... --name`, `check`/`field check --file`, `template --output`, `def var --name --value`, `def time\|freq KIND --value` |
| 42 | `walk-test` | `test_scripts/test_command_rules.py` walks the whole parser tree and checks the command rules; `docs TOPIC` completes its topics |
| 43 | `run-flag-case` | `run`: `--case`, `--job`, `--script`, `--interval`, `--key`, `--name`, `--sbatch-args`; the modes stay words |
| 44 | `auto-flag-case` | `auto`: `--case NAME`, the target of `apply` stays a word (§13.21) |
| 8 | `auto-log` | `auto log` reads back the logs of `auto apply`; `auto status` is one line per case |
| 12 to 17 | | `auto` as a sequence of visible commands: `auto show` lists the exact commands `auto apply` runs, in order (Phases 13 to 16, 18, 19 and 17 in this table; Phase 12 is still open) |
| 17 | `auto-apply-targets` | `auto apply <target>`: history, plt, output, input, rst or all (§13.15) |
| 20 | `organise-out-rst` | `case organise out` and `rst` as subcommands of their own (§13.16) |
| 21 | `plot-archive` | `plot --archive N` |
| 22 | `organise-clean-select` | `case organise history clean 1,2,3`: clean a selection of archive runs |
| 23 | `plot-run` | `plot --run` |
| 24 | `help-and-carry` | Help examples; the carried `.casestatus.md` |
| 25 | | shellkit port: `version comment clear`, `\` continuation |
| 26 | `auto-post-window` | `auto show` no longer posts steps a finished post job was never given |
| 28 | `no-verify` | `case organise plt binary --no-verify`: delete whole binary PLTs without asking the remote |
| 29 | `auto-vtu` | `auto` cleans up the `.vtu` caches (§13.17) |
| 31 | `flag-vocabulary` | One flag vocabulary for `case`, `run` and `auto`: actions are words, `--yes`, one remote is the default (§13.18) |
| 32 | `pipe-rows` | Pipe rows between commands (shellkit 0.1.8): `data stats --func maxloc \| case download plt` |

---

## Template for a new phase

```
### Phase N: <what> (branch `<kebab-case-name>`)

Design: <where the design is, or two lines of it>.

- [ ] <task: one commit>
- [ ] <task: one commit>
- [x] Tests, help text, completion, `CHANGELOG.md`
```
