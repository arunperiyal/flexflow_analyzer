# Plan

The one plan file of this project. Work is listed as **phases**, each split
into **tasks**.

- A phase is one feature or one coherent piece of work. It gets **one branch**,
  cut from `main`, named as shown beside the phase.
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

**On hold until Phases 12 to 17 are done**, then to be redone on top of them.
The first design (`auto.md` §13.13, commit `1abbe95`) had `auto` delete files
itself from an explicit list. The direction set on 2026-11-13 is different:
`auto apply` runs the same commands `auto show` lists, so the md5 check
belongs to `case check plt --verify` (Phase 13) and the refusal to delete an
unchecked file belongs to `case organise plt` / `case organise output`
(Phase 14).

- [x] Write the design as §13.13 at the end of `auto.md`
- [~] Review of §13.13 by the user: overtaken by the new direction
- [ ] Rewrite §13.13 as a new section at the end of `auto.md`: deleting is
      done by the hand commands; keep its rules (md5 at the time of deleting,
      "written after", the restart guard, fail closed, restart-set keeps)
- [~] Is deleting part of `auto apply all`, or only with a flag: settled
      2026-11-13. `auto apply` organises, uploads and deletes as one
      conditional sequence; `--dry-run` shows it without uploading or
      deleting
- [ ] Still to settle with the user: cases that need you; the cost of the md5
- [ ] `auto apply plt` and `auto apply output` run the delete commands, after
      the question with totals
- [ ] Dummy cases and a test for each rule: copy differs, size-only copy,
      `.out` newer than its PLT (restart), queued restart, post in flight,
      restart-set keeps, a case that needs you
- [ ] Help text, `docs/architecture/auto_flow.html`, the web flowchart,
      `CHANGELOG.md`

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

- [ ] `auto log`: read back the run logs in `<folder>/auto_logs/`
- [ ] `auto status`: polish the layout
- [ ] With a queued restart, `Complete` / `Also kept` should not count the
      earlier run's newer restart set
- [ ] Tests, help text, completion, `CHANGELOG.md`

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
- `auto apply` has the targets `history`, `plt`, `output`, `input`, `rst`
  and `all`.
- `auto apply` is not only for deleting: it organises, uploads and deletes
  in a conditional sequence. `--dry-run` uploads and deletes nothing and
  prints the sequence in full. `auto show` stays as it is: state,
  observation and action.
- `case organise plt` always verifies. There is no `--unverified` flag.

Order of work: 12, 13, 14, 15, 16, 17, then Phase 6. Phases 12 to 14 change
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
- **`decide()` is one function of about 530 lines** and `report.build()` one
  of about 310, each covering history, PLT, `.out`, `.rst` and inputs in a
  row. `auto apply plt` needs the PLT part on its own.
- **Parsing.** `auto` takes `what` and `[case]` as positionals. A target word
  after `apply` (`history`, `plt`, `output`, `all`) has to be told apart from
  a case name.

### Phase 12: one checked transfer for `case upload` and `auto` (branch `checked-transfer`)

Refactor. After it, a file sent by hand and a file sent by `auto` go the same
way and leave the same record.

- [x] Move the remote access of `core/auto/cloud.py` (listing, `put` with
      temporary name, md5, rename) to a core module of its own, with a
      function that returns the md5 of a named remote file
- [ ] Move the ledger next to it; entries also record the local file's
      `mtime`
- [ ] `case upload binary`, `rst`, `history`, `input` and `--files` send
      through it: md5-checked, temporary name then rename, written to the
      ledger of the case folder
- [ ] `case upload --to REMOTE` and `case download --from REMOTE` become
      `--remote REMOTE`, the name `run post` and `auto` already use
- [ ] `executor.do_upload` uses the same function; `auto` tests unchanged
- [ ] Tests for `case upload` against a local "cloud": a copy that differs,
      a remote without `md5sum` (size only), a transfer cut short
- [ ] Help text, `docs/usage/`, `CHANGELOG.md`

### Phase 13: `case upload plt` and `case check plt --verify` (branch `plt-verify`)

- [ ] `case upload plt` and `case download plt`: the new name of the `binary`
      mode. `binary` stays as an alias that still works; help, completion and
      docs show `plt`
- [ ] `case check plt <case> --verify [--remote REMOTE] [--t1 --t2 --freq]`: for
      every PLT in `binary/` that the remote also holds, compare size and md5
      (local now, remote now); write the result to the ledger; list verified,
      differing, not on the remote, only on the remote
- [ ] Exit code and a one-line summary that `auto` can read (all verified or
      not)
- [ ] Tests: all match, one differs, one missing there, remote without
      `md5sum`, a restart that made a local PLT newer than its remote copy
- [ ] Help text, completion, `docs/usage/`, `CHANGELOG.md`

### Phase 14: hand deletions that need a checked copy (branch `organise-verified`)

U-4 and U-5 of `auto.md` §13.5. After it, the delete commands are safe to
print in `auto show` and safe for `auto apply` to run.

The chain (settled 2026-11-13): `.out` needs a verified ASCII PLT, an ASCII
PLT needs a verified binary PLT, a binary PLT needs its copy on the remote.
The commands always verify; there is no flag to skip it.

- [ ] To confirm with the user before the first commit: when one step of
      the series has no next file, is that step alone kept, or is nothing
      deleted
- [ ] A check that an ASCII PLT is whole: its size, and the node and element
      counts of its header against the file (beside `core/plt_valid.py`)
- [ ] One function for "what stands in for this file": the next link in the
      chain, local or remote, falling through a missing link to the one after
- [ ] `case organise plt --delete-binary`: deletes only the files with a
      verified copy on the remote (ledger entry whose size and `mtime` still
      match the local file); the others are listed and left
- [ ] `case organise plt --delete-ascii`: deletes only where the binary PLT
      of the step is verified: whole, and written after the ASCII file
- [ ] `--freq` applies to `--delete-ascii` as well as `--delete-binary`
- [ ] `case organise output`: a `.out` goes only when the ASCII PLT of its
      step is verified and was written after the `.out` (or the link after
      it, when there is no ASCII PLT); never for a step
      above the restart point of a queued job
- [ ] Tests for each rule, including a restart that rewrote the `.out`
- [ ] Help text, `docs/usage/case-organise.md`, `CHANGELOG.md`

### Phase 15: `auto` refactor, steps as data (branch `auto-steps`)

Refactor, no change in what `auto show` prints or `auto apply` does. Every
existing `auto` test must pass unchanged at each commit.

- [ ] A `Step` record: target (`history`, `plt`, `output`, `inputs`), the
      command as text, what to call to run it, and a note (why, or what it
      waits for). The plan carries a list of them, in order
- [ ] Split `decide()` into one function per target, called in order by a
      short `decide()`
- [ ] Split `report.build()` the same way; the Action lines come from the
      plan's steps
- [ ] `apply` runs the plan's steps (replacing `_intended()` and the
      `KINDS` loop), so show and apply cannot disagree
- [ ] A test that, for every dummy case, the commands `auto show` lists are
      the commands `auto apply --dry-run` lists

### Phase 16: `auto show`, Action lists only commands (branch `auto-show-commands`)

- [ ] PLT files: `case check plt --verify`; `run post convert` / `run post
      full` when binary PLTs are not made; `case upload plt ... --freq N
      --remote REMOTE` with `--missing` only when the remote lacks some;
      `case organise plt --delete-ascii ...`; `case organise plt
      --delete-binary ...`. No `auto apply: ...` sentences and no `[not built yet]`
- [ ] History: `case organise history ...`, `case upload history ...`; the
      copy of a live `.othd` / `.oisd` becomes a command too
- [ ] OUT files: `case organise output ...`
- [ ] RST files: `case upload rst ...`, `case organise output --keep-out
      --keep-freq N --keep-newest N ...`
- [ ] Inputs and case files: `case upload <case> --files ...`
- [ ] What is not a command (waiting for a job, a reason) moves out of
      Action into a row of its own (`Waiting`, `Why`)
- [ ] `auto commands` prints the same list; tests on the dummy cases
- [ ] `docs/architecture/auto_flow.html`, the web flowchart, `CHANGELOG.md`

### Phase 17: `auto apply <target>` (branch `auto-apply-targets`)

- [ ] `auto apply history [case]`, `plt`, `output`, `input`, `rst` and
      `all`: each runs the steps of its target (organise, upload, delete),
      in the order `auto show` lists them, each step only if the one before
      it succeeded
- [ ] `auto apply` with no target does nothing and lists the targets
- [ ] `--dry-run` (as in `auto apply all --dry-run`): uploads and deletes
      nothing, and prints every step with what it would send or delete
- [ ] `--only` for `apply` goes (or stays as an alias for one release)
- [ ] Parsing: a target word against a case of the same name; completion
- [ ] Tests, help text, `docs/architecture/auto.md` (a new section at the
      end), `CHANGELOG.md`

---

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

---

## Template for a new phase

```
### Phase N: <what> (branch `<kebab-case-name>`)

Design: <where the design is, or two lines of it>.

- [ ] <task: one commit>
- [ ] <task: one commit>
- [ ] Tests, help text, completion, `CHANGELOG.md`
```
