## Problem 1

Commands will iterate over all cases from .cases file
╭─ …/cylinder_12/cases/bare_riser(ttl:59:15) [c:*]
╰─❯ case out --list
Using case: *
[ERROR] Case directory not found: *
╭─ …/cylinder_12/cases/bare_riser(ttl:59:10) [c:*]
╰─❯ pwd
Working directory: /media/arunperiyal/Works/phd/research/grooved_beam_structures/cylinder_12/cases/bare_riser
Case context: *

- `case out --list` without case context need not show help message. It may show that 'case not defined' or similar message.

- `case out --list` with case context * should have worked for all the case directories like other commands

## Problem 2
