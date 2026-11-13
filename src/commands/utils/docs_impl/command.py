"""Documentation command implementation."""

import os
import sys
import subprocess
from src.utils.colors import Colors


def find_docs_directory():
    """Find the docs directory in installation or source."""
    # Try current directory first (for development)
    # this file is src/commands/utils/docs_impl/command.py: the root is 4 folders up
    here = os.path.dirname(os.path.abspath(__file__))
    script_dir = os.path.abspath(os.path.join(here, '..', '..', '..', '..'))
    docs_dir = os.path.join(script_dir, 'docs')
    
    if os.path.exists(docs_dir):
        return docs_dir
    
    # Try installation directory
    home = os.path.expanduser('~')
    install_docs = os.path.join(home, '.local', 'share', 'flexflow', 'docs')
    
    if os.path.exists(install_docs):
        return install_docs
    
    return None


def open_file(filepath):
    """Open file with appropriate viewer (HTML or markdown)."""
    if not os.path.exists(filepath):
        print(f"{Colors.RED}Error:{Colors.RESET} File not found: {filepath}", file=sys.stderr)
        return False
    
    # Try different methods to open the file
    try:
        # Try xdg-open (Linux)
        if subprocess.run(['which', 'xdg-open'], capture_output=True).returncode == 0:
            subprocess.Popen(['xdg-open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"{Colors.GREEN}✓{Colors.RESET} Opened documentation in browser")
            return True
        
        # Try open (macOS)
        if subprocess.run(['which', 'open'], capture_output=True).returncode == 0:
            subprocess.Popen(['open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"{Colors.GREEN}✓{Colors.RESET} Opened documentation in browser")
            return True
        
        # If HTML and no GUI opener available, try text browser
        if filepath.endswith('.html'):
            for browser in ['lynx', 'w3m', 'links']:
                if subprocess.run(['which', browser], capture_output=True).returncode == 0:
                    subprocess.run([browser, filepath])
                    return True
        
        # Try common terminal pagers for markdown
        for viewer in ['bat', 'less', 'more', 'cat']:
            if subprocess.run(['which', viewer], capture_output=True).returncode == 0:
                if viewer == 'bat':
                    subprocess.run(['bat', '--style=plain', filepath])
                elif viewer in ['less', 'more']:
                    subprocess.run([viewer, filepath])
                else:
                    subprocess.run([viewer, filepath])
                return True
        
        # Fallback: print to stdout
        with open(filepath, 'r') as f:
            print(f.read())
        return True
        
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.RESET} Failed to open file: {e}", file=sys.stderr)
        return False


# topic -> (file under docs/, without extension; what it is)
TOPICS = {
    'index':     ('README', 'Index of all documentation'),
    'main':      ('usage/USAGE', 'Main usage guide'),
    'usage':     ('usage/USAGE', "Same as 'main'"),
    'reference': ('usage/REFERENCE', 'One-page command reference'),
    'run':       ('usage/run', 'The run commands (pre, main, post, ...)'),
    'create':    ('usage/case-create', 'case create: time parameters and global defaults'),
    'organise':  ('usage/case-organise', 'case organise, step by step'),
    'install':   ('installation/INSTALL', 'Installation guide'),
    'structure': ('architecture/case-structure', 'Layout of a case directory'),
    'auto':      ('architecture/auto', 'Design of the auto command'),
    'webapp':    ('architecture/webapp', 'Design of the web UI'),
}


def list_available_docs(docs_dir):
    """List all available documentation files."""
    print(f"\n{Colors.BOLD}Available Documentation:{Colors.RESET}\n")

    for key, (_, description) in TOPICS.items():
        print(f"  {Colors.CYAN}{key:12s}{Colors.RESET} - {description}")

    print(f"\n{Colors.BOLD}Usage:{Colors.RESET}")
    print(f"  flexflow docs <name>")
    print(f"  flexflow docs main")
    print(f"  flexflow docs run")


def docs_command(args):
    """Show documentation."""
    docs_dir = find_docs_directory()
    
    if not docs_dir:
        print(f"{Colors.RED}Error:{Colors.RESET} Documentation directory not found", file=sys.stderr)
        print(f"\nPlease reinstall FlexFlow with --install flag to include documentation.")
        return 1
    
    # If no topic specified, list available docs
    if not args.topic:
        list_available_docs(docs_dir)
        return 0
    
    topic = args.topic.lower()
    
    if topic not in TOPICS:
        print(f"{Colors.RED}Error:{Colors.RESET} Unknown documentation topic: {topic}", file=sys.stderr)
        print(f"\n{Colors.BOLD}Available topics:{Colors.RESET}")
        for key in TOPICS:
            print(f"  • {key}")
        return 1
    
    doc_path = TOPICS[topic][0]
    
    # Try HTML first (installed version), then markdown (source version)
    html_path = os.path.join(docs_dir, f"{doc_path}.html")
    md_path = os.path.join(docs_dir, f"{doc_path}.md")
    
    filepath = None
    if os.path.exists(html_path):
        filepath = html_path
    elif os.path.exists(md_path):
        filepath = md_path
    else:
        print(f"{Colors.RED}Error:{Colors.RESET} Documentation file not found", file=sys.stderr)
        print(f"  Tried: {html_path}")
        print(f"         {md_path}")
        return 1
    
    print(f"{Colors.CYAN}Opening documentation:{Colors.RESET} {topic}")
    print(f"{Colors.DIM}File: {filepath}{Colors.RESET}\n")
    
    if open_file(filepath):
        return 0
    else:
        return 1
