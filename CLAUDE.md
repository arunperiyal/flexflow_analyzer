# CLAUDE.md

FlexFlow Manager: a command-line shell (`ff`) and a Flask web UI for creating,
running and analysing FlexFlow riser simulations on an HPC cluster. Python,
built on the `shellkit` shell framework.

## Commands

```bash
python3 main.py                 # the interactive shell
python3 main.py case show C1    # one command
python3 main.py --ui            # the web UI
python3 -m pytest test_scripts -q
```

## Rules

Loaded from `.claude/rules/`:

- `git-workflow.md`: plan first; one branch per phase, one commit per task;
  plain commit messages; `prompt.md` stays untracked.
- `output.md`: no Claude Artifacts; where documents go.

## Where to look

| For | Read |
|---|---|
| Where code is and how a command is laid out | `.claude/context/code-map.md` |
| The plan: phases and tasks | `docs/development/PLAN.md` |
| Documentation index | `docs/README.md` |
| Design of `auto` and the web UI | `docs/architecture/auto.md`, `docs/architecture/webapp.md` |
| Notes handed over from the last session | `.claude/context/NEXT_SESSION.md` |
