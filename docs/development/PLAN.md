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

### Phase 5: the two failing render tests (branch `web-render-tests`)

`test_render_iso_produces_a_real_png` and
`test_render_slice_produces_a_real_png` in `test_scripts/test_web_field_render.py`
fail on `main`: the job reports `iso/iso_100.png`, then serving it gives 404.

- [ ] Find why the PNG the job lists is not served (path the job writes
      against the path the route reads)
- [ ] Fix it, with the two tests passing

### Phase 6: `auto apply`, the delete stage (branch `auto-delete`)

Design: `docs/architecture/auto.md` §13 (§13.3 traps, §13.12 restart sets).
Reports already list these actions as `[not built yet]`. Rule above all:
nothing is deleted without a verified copy, and one question is asked before
deleting (`--yes` skips it).

- [ ] Add the design of the delete stage as a new section at the end of
      `auto.md`
- [ ] Decide: ASCII PLT and binary PLT deletable only when the md5 on the
      remote matches the ledger
- [ ] Decide: `.out` of verified steps
- [ ] Decide: `.rst` thinning to `keep_rst` / `keep_newest_rst`
- [ ] Guard: nothing above a restart point is deleted until its step has been
      posted again from the new run
- [ ] Executor: carry out the deletions, behind one question, written to the
      run log and `.casestatus.md`
- [ ] `auto apply --only delete` and `--dry-run` for it; replace the
      `[not built yet]` text in the reports
- [ ] A dummy case and a test for each rule (`tools/make_dummy.py`)
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

---

## Template for a new phase

```
### Phase N: <what> (branch `<kebab-case-name>`)

Design: <where the design is, or two lines of it>.

- [ ] <task: one commit>
- [ ] <task: one commit>
- [ ] Tests, help text, completion, `CHANGELOG.md`
```
