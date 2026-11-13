# Planning and git workflow

## Plan first

- There is one plan file: `docs/development/PLAN.md`. Do not create other
  plan files.
- Before building any new feature, add it to the plan as a **phase** split
  into **tasks**. Then build it.
- A phase is one feature or one coherent piece of work. A task is one step of
  it that can be committed and checked on its own.
- When a task is done, tick it in the plan in the same commit.

## Branches and commits

- **One branch per phase.** Cut it from `main` before the first edit, even
  when HEAD is already on `main`. Names are short kebab-case with no prefix
  (`auto-show`, `case-domain`).
- **One commit per task.** Do not mix two tasks in a commit.
- Never start an unrelated feature on the branch in progress. Merge that
  branch into `main` first (`git merge --no-ff <branch> -m "Merge <words>"`),
  then cut a new one.
- Commit messages are plain: what changed, in the style of `git log`. No
  mention of Claude and no `Co-Authored-By` trailer.
- `prompt.md` in the repo root is the user's task note. It stays untracked;
  never stage it.
- Do not push unless asked.

## Before a commit

- Run `python3 -m pytest test_scripts -q` when code changed.
- A user-visible change gets an entry under `## Unreleased` in `CHANGELOG.md`.
