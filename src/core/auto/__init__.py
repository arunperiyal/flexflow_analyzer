"""
`auto`: the per-case workflow (docs/AUTO_PLAN.md §13) run by one command.

    conf.py     .auto.conf, the folder's settings
    cloud.py    what is already on the remote (a folder, or over SFTP)
    observe.py  one read-only snapshot per case: files, queue, cloud
    decide.py   the plan for a case, from its snapshot alone (no I/O)
"""
