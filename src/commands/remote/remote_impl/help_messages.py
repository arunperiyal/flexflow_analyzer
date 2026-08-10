"""Help messages for the remote command and its subcommands."""

from src.utils.colors import Colors


def print_remote_help():
    """Print help for the remote command group."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote — Manage remote machines{Colors.RESET}

Record the machines a case can be sent to or fetched from, so
{Colors.YELLOW}case upload{Colors.RESET} / {Colors.YELLOW}case download{Colors.RESET} need only a name.

{Colors.BOLD}USAGE:{Colors.RESET}
    remote <subcommand> [options]

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}add{Colors.RESET}           Add a new remote machine
    {Colors.YELLOW}modify{Colors.RESET}        Update the connection details of a remote
    {Colors.YELLOW}delete{Colors.RESET}        Delete a remote machine
    {Colors.YELLOW}list{Colors.RESET}          Show all configured remotes
    {Colors.YELLOW}set-path{Colors.RESET}      Set the base path a remote's cases live under

    {Colors.DIM}Run a subcommand with no arguments, or with -h, for its own help.{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote add hpc1 --user john --ip 192.168.1.100 --password secret --path /home/john/cases
    remote list
    remote modify hpc1 --port 2222
    remote set-path hpc1 --path /scratch/john/new_location
    remote delete hpc1

{Colors.BOLD}NOTES:{Colors.RESET}

  - Remotes are stored in {Colors.YELLOW}~/.flexflow/remotes.json{Colors.RESET}, {Colors.BOLD}passwords in plain
    text{Colors.RESET}. Do not use an account whose password protects anything else.
  - {Colors.YELLOW}use remote:<name>{Colors.RESET} sets the remote for the session, so case
    upload/download need no --to/--from.
""")


def print_add_help():
    """Print help for remote add."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote add — Add a remote machine{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote add <name> --user <user> --ip <ip> --password <pass> [--port <port>] [--path <path>]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<name>{Colors.RESET}             What to call this machine here. It is the name given
                       to {Colors.YELLOW}case upload --to{Colors.RESET}, {Colors.YELLOW}case download --from{Colors.RESET} and
                       {Colors.YELLOW}use remote:<name>{Colors.RESET}, not the machine's hostname.

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--user <user>{Colors.RESET}      SSH username
    {Colors.YELLOW}--ip <ip>{Colors.RESET}          IPv4 address of the machine (e.g. 192.168.1.100)
    {Colors.YELLOW}--password <pass>{Colors.RESET}  SSH password

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--port <port>{Colors.RESET}      SSH port (default: 22)
    {Colors.YELLOW}--path <path>{Colors.RESET}      Base directory on the remote that case directories
                       sit under. Can be set later with {Colors.YELLOW}remote set-path{Colors.RESET}, or
                       overridden per transfer with --remote-path.
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote add hpc1 --user john --ip 192.168.1.100 --password secret --path /home/john/cases
    remote add hpc2 --user john --ip 10.0.0.7 --password secret --port 2222

{Colors.BOLD}NOTES:{Colors.RESET}

  - The password is stored {Colors.BOLD}in plain text{Colors.RESET} in ~/.flexflow/remotes.json.
  - Nothing is contacted here: the details are recorded, not verified. A wrong
    user or password shows up on the first upload or download.
  - A name that already exists is an error rather than an overwrite -- use
    {Colors.YELLOW}remote modify{Colors.RESET} to change one.
""")


def print_modify_help():
    """Print help for remote modify."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote modify — Update a remote's connection details{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote modify <name> [--user <user>] [--ip <ip>] [--password <pass>] [--port <port>]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<name>{Colors.RESET}             The remote to update, as shown by {Colors.YELLOW}remote list{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--user <user>{Colors.RESET}      New SSH username
    {Colors.YELLOW}--ip <ip>{Colors.RESET}          New IPv4 address
    {Colors.YELLOW}--password <pass>{Colors.RESET}  New SSH password
    {Colors.YELLOW}--port <port>{Colors.RESET}      New SSH port
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

    {Colors.DIM}Give at least one. Only the fields named are changed; the rest are kept.{Colors.RESET}

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote modify hpc1 --port 2222
    remote modify hpc1 --user jane --password newsecret

{Colors.BOLD}NOTES:{Colors.RESET}

  - The base path is {Colors.BOLD}not{Colors.RESET} changed here. Use {Colors.YELLOW}remote set-path{Colors.RESET} for it.
  - The name cannot be changed. Add the machine again under the new name and
    delete the old entry.
""")


def print_delete_help():
    """Print help for remote delete."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote delete — Delete a remote machine{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote delete <name>

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<name>{Colors.RESET}             The remote to delete, as shown by {Colors.YELLOW}remote list{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote delete hpc1

{Colors.BOLD}NOTES:{Colors.RESET}

  - You are asked to confirm, and the entry cannot be recovered afterwards.
  - Only the local entry goes. Nothing on the remote machine is touched, and
    cases already uploaded there stay where they are.
""")


def print_list_help():
    """Print help for remote list."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote list — Show the configured remotes{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote list

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}OUTPUT:{Colors.RESET}

    A table of {Colors.YELLOW}Name, User, IP, Port, Path{Colors.RESET} -- one row per machine. The Name
    column is what {Colors.YELLOW}case upload --to{Colors.RESET} and {Colors.YELLOW}case download --from{Colors.RESET} take.
    Passwords are not shown.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote list
""")


def print_set_path_help():
    """Print help for remote set-path."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote set-path — Set a remote's base path{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote set-path <name> --path <path>

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<name>{Colors.RESET}             The remote to update, as shown by {Colors.YELLOW}remote list{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--path <path>{Colors.RESET}      Base directory on the remote that case directories
                       sit under. An upload of case C goes to <path>/C.
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote set-path hpc1 --path /scratch/john/cases

{Colors.BOLD}NOTES:{Colors.RESET}

  - The path is recorded as given, not checked against the machine.
  - {Colors.YELLOW}case upload --remote-path{Colors.RESET} overrides it for a single transfer without
    changing what is stored here.
""")
