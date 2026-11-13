"""
`auto`: the per-case workflow (docs/architecture/auto.md §13) run by one command.

    conf.py     the folder's .cases.yml: a remote's folder, auto's settings
    observe.py  one read-only snapshot per case: files, queue, cloud
    decide.py   the plan for a case, from its snapshot alone (no I/O)
"""
