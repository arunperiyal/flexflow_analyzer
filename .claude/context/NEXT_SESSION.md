# Next session

Where the work stands on 2026-11-14 and what comes next. The plan is
`docs/development/PLAN.md` (one file: open phases, backlog, a Done table);
read it first. The rules are in `.claude/rules/`; the code map is
`.claude/context/code-map.md`.

## State of the repository

- `main` is **more than 80 commits ahead of `origin/main`** (last push:
  `b699d46`). Nothing from this stretch of work is pushed.
- Tests: `python3 -m pytest test_scripts -q`, 1586 passing on `main`, about
  two minutes. Some tests read untracked case data in `examples/`; a fresh
  worktree needs those cases linked in.
- **Copilot (GitHub Copilot CLI) worked in the main checkout**, which was
  left on its branch `docs-install`. Check `git branch --show-current` and
  whether a `copilot` process is still open before switching branches there;
  a temporary `git worktree` avoids disturbing it. Its instructions are in
  `.github/copilot-instructions.md`.
- Two Copilot branches are **not merged and not reviewed**:
  - `docs-install` (Phase 10, 4 commits). One commit edits this file, which
    its instructions told it to skip; drop that change when merging.
  - `flowreel-export` (Phase 9, 1 commit).
  Both will conflict with `main` in `PLAN.md` and `CHANGELOG.md`.
- About 90 old local branches are merged into `main`; delete them only on
  the user's word.

## What was built since the last notes (phases 1 to 5, 12 to 16, 18, 19)

| What | Where |
|---|---|
| Docs sorted into `docs/{installation,usage,architecture,development}/`, index `docs/README.md`; rules and context for Claude in `.claude/`; dead code removed | Done table, phases 1 to 4 |
| One checked upload for `case upload` and `auto`: temporary name, size and md5, rename; one ledger with the local `mtime` and the remote `path` | `src/core/transfer/{cloud,ledger}.py` |
| `case upload --to` and `case download --from` are now `--remote`; `case upload plt` / `download plt` (the old word `binary` still works); `case upload history --live` | `src/commands/case/download_impl/` |
| `case check plt <case> --verify --remote NAME`: each binary PLT against its remote copy by md5 (read back when the remote has no `md5sum`); remote-only PLTs against the ledger; steps in neither place; how to rebuild a broken PLT | `src/core/transfer/verify.py`, `src/commands/case/check_impl/verify.py` |
| The deletion chain, used by `case organise output`, `plt --delete-ascii`, `plt --delete-binary` | `src/core/chain.py`, `src/core/plt_ascii.py`, `organise_impl/organizer.py` |
| `auto`: the plan carries `plan.steps` (`PlanStep`); `decide()` and `report.build()` split into one function per part | `src/core/auto/{decide,report}.py` |
| `auto show`: every Action is a command, in the order `apply` takes them; waits and reasons are rows | `auto.md` §13.14 |

## Decisions the user took (2026-11-13 and 14)

- **`auto show` lists the commands `auto apply` runs**, so the sequence can
  be read and any command run by hand. `auto apply` organises, uploads and
  deletes as one conditional sequence, not only deletes.
- **The chain.** A `.out` may go when its ASCII PLT is verified; an ASCII PLT
  when its binary PLT is verified; a binary PLT when its copy on the remote
  has the same md5. A missing link is passed over to the next one.
- **A gap:** when one step of a range has nothing to stand in for it, that
  step is kept and reported and the others are deleted.
- **Repair goes back along the chain:** a broken binary PLT is made again
  from the ASCII PLT (`run post convert`), a broken ASCII PLT from the `.out`
  (`run post full`).
- **Always verify.** No flag skips the check: no `--unverified`, and
  `case organise output --all-out` stays but checks.
- **Time is not the concern, a safe copy is:** md5 on both sides, read at
  the moment of deleting.
- An empty local `binary/` with the PLTs on the remote is a normal state.
- Every step with `.out` gets its PLT made and uploaded; `--freq` is the
  spacing of the series, not a way to thin it.
- `auto apply` targets: `history`, `plt`, `output`, `input`, `rst`, `all`;
  `--dry-run` uploads and deletes nothing and prints every step.

## Next to build

1. **Phase 17, `auto apply <target>`** (branch `auto-apply-targets`): run
   `plan.steps` in the order shown, per target, each step only if the one
   before succeeded; no target does nothing and lists the targets;
   `--dry-run`; `--only` goes or stays as an alias. `apply` today still runs
   history, then all uploads as one transfer, then the first post job, and
   skips the steps of kind `check` and `delete`.
2. **Phase 6, deleting in `auto apply`** (branch `auto-delete`): on top of
   17, `apply` runs the delete commands after one question with totals.
   Rewrite `auto.md` §13.13 as a new section at the end. The hand commands do
   not read the SLURM queue, so the rule "nothing above the restart point of
   a queued job" belongs here. Remove the `By hand` rows from the report
   when `apply` deletes.
3. Then Phase 7 (steady check), Phase 8 (`auto log`, `auto status`), Phase
   11 (web UI checklist), and the backlog in the plan.

## Open points

- **Not tried on real data.** Everything was tested on stand-in remotes and
  dummy cases. The ASCII check was built from the header and first line the
  user pasted from `riser.5750.plt` (`NODES = 1630573, ELEMENTS=1590192,
  DATAPACKING=POINT`), on a synthetic file. First real runs to ask for:
  `case check plt <case> --verify --remote cloud`, then `case organise plt
  <case> --delete-ascii --dry-run`.
- Uploads record "size only" on a remote without `md5sum`; only `--verify`
  and `--delete-binary` read the copy back for an md5. The user was asked
  whether uploads should read back too; not answered.
- `docs/architecture/auto_flow.html` was not updated for phases 14 to 16.
- Still to settle for Phase 6: what `apply` does with a case that needs you,
  and the cost of the md5 on a large case.

## Waiting on the user (cluster), from 2026-11-11, may be out of date

- First real run of the additive steps: `auto apply BR0SG0U1P0 --remote
  cloud --dry-run`, then without `--dry-run`; bring back
  `auto_logs/auto_<time>.log` and `auto show`.
- The job-name flag on `fixed/bare` (`mainBR0fixed` against the
  `main<case>` convention).
- `BR0SG0U6P0`: `archive/` is empty locally; restore with `case download
  history BR0SG0U6P0 --archive --remote cloud`.

## Rules the user set (also in memory and `.claude/rules/`)

- Plan first: a phase in `PLAN.md` split into tasks; one branch per phase
  cut from `main`; one commit per task, ticking the task in the same commit.
- Plain commit messages: no mention of Claude, no `Co-Authored-By`.
  `prompt.md` stays untracked. Push only when asked.
- Never Claude Artifacts: standalone HTML files in the repo instead.
- Update this file only when the user says so.
- Data safety first: fail closed, nothing deleted without a verified copy,
  ask once before deleting.
- Every improvement from a real `auto show` becomes a dummy case plus a test.
- `auto.md` and `webapp.md` are cited by section number: add at the end,
  never renumber.
