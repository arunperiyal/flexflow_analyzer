# Planning and git workflow

## Plan first

- There is one plan file: `docs/development/PLAN.md`. Do not create other
  plan files.
- Before building any new feature, add it to the plan as a **phase** split
  into **tasks**. Then build it.
- A phase is one feature or one coherent piece of work. A task is one step of
  it that can be committed and checked on its own.
- When a task is done, tick it in the plan in the same commit.

## Who does what in git

The user creates branches, merges them, pushes and opens pull requests.
Claude does none of these, even when asked in passing, unless the user says
so for that one action.

- **Start of a phase:** check `git branch --show-current`. If it is `main`,
  or a branch already merged, stop and give the user the branch name from the
  plan (short kebab-case, no prefix, e.g. `auto-show`) to create. Do not edit
  before the user is on the phase's branch.
- **One commit per task**, made by Claude on the user's branch. Commit
  messages are plain: what changed, in the style of `git log`. No mention of
  Claude and no `Co-Authored-By` trailer.
- Never start an unrelated feature on the branch in progress; say so and let
  the user merge it first.
- **Conflicts:** when the user has a merge or rebase in progress and asks,
  Claude resolves the files, stages them and runs the tests. The user makes
  the merge commit.
- `prompt.md` and `bug-report.md` in the repo root are the user's notes. They
  stay untracked; never stage them.

## Testing

- Claude runs `python3 -m pytest test_scripts -q` before each commit that
  changes code, and a dummy case plus a test for every fix.
- The user tests on the cluster and real data, and reports what is wrong in
  `bug-report.md`. At the start of a session Claude reads it, fixes what is
  open, and notes the commit beside each entry. An entry is closed by the
  user, after trying it again.

## Before a commit

- Run `python3 -m pytest test_scripts -q` when code changed.
- A user-visible change gets an entry under `## Unreleased` in `CHANGELOG.md`.
