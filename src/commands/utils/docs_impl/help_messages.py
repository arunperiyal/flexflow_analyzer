"""Help messages for docs command."""

from src.utils.colors import Colors


def show_docs_help():
    """Display help for docs command."""
    print(f"""
{Colors.BOLD}USAGE{Colors.RESET}
    flexflow docs [TOPIC]

{Colors.BOLD}DESCRIPTION{Colors.RESET}
    View FlexFlow documentation.
    
    Opens the specified documentation topic using the system's default markdown
    viewer or terminal pager. If no viewer is available, prints to stdout.

{Colors.BOLD}ARGUMENTS{Colors.RESET}
    TOPIC                Documentation topic to view
    
{Colors.BOLD}AVAILABLE TOPICS{Colors.RESET}
    index                Index of all documentation
    main                 Main usage guide (USAGE.md)
    usage                Same as 'main'
    reference            One-page command reference
    run                  The run commands (pre, main, post, ...)
    create               case create: time parameters and global defaults
    organise             case organise, step by step
    install              Installation guide
    structure            Layout of a case directory
    auto                 Design of the auto command
    webapp               Design of the web UI

{Colors.BOLD}EXAMPLES{Colors.RESET}
    # List all available documentation
    flexflow docs
    
    # View main usage guide
    flexflow docs main
    
    # View the run commands
    flexflow docs run
    
    # View the design of the auto command
    flexflow docs auto

{Colors.BOLD}NOTES{Colors.RESET}
    • Documentation is included when installing with --install flag
    • Uses system default markdown viewer if available
    • Falls back to terminal pagers (bat, less, more) or stdout
    • Documentation is also available in the docs/ directory

{Colors.BOLD}VIEWERS{Colors.RESET}
    The command tries the following viewers in order:
    1. xdg-open (Linux default)
    2. open (macOS default)
    3. bat (syntax highlighting)
    4. less (terminal pager)
    5. more (terminal pager)
    6. cat (plain text)
""")
