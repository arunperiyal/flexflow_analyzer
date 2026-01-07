"""Installation utilities for FlexFlow."""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from flexflow.utils.colors import Colors


VERSION = "1.0.0"


def check_python():
    """Check if Python 3 is installed and display version."""
    try:
        python_version = sys.version.split()[0]
        print(f"{Colors.CYAN}[INFO]{Colors.RESET} Python version: {python_version}")
        return True
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to check Python version: {e}")
        return False


def check_dependencies():
    """Check and install required Python packages."""
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} Checking Python dependencies...")
    
    required_packages = ["numpy", "matplotlib", "markdown"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Missing packages: {', '.join(missing_packages)}")
        response = input("Would you like to install them now? (y/n): ").strip().lower()
        
        if response == 'y':
            print(f"{Colors.CYAN}[INFO]{Colors.RESET} Installing dependencies...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--user"] + missing_packages,
                    check=True
                )
                print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Dependencies installed successfully!")
            except subprocess.CalledProcessError as e:
                print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to install dependencies: {e}")
                print(f"You can try manually: pip3 install --user {' '.join(missing_packages)}")
                return False
        else:
            print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Skipping dependency installation. FlexFlow may not work correctly.")
    else:
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} All required Python packages are installed.")
    
    return True


def convert_docs_to_html(docs_dir, install_docs_dir):
    """Convert markdown documentation to HTML."""
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} Converting documentation to HTML...")
    
    if not os.path.exists(docs_dir):
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Documentation directory not found at {docs_dir}")
        return
    
    try:
        import markdown
    except ImportError:
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} markdown package not available, skipping HTML conversion")
        return
    
    # Create installation docs directory
    os.makedirs(install_docs_dir, exist_ok=True)
    
    # HTML template
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            color: #333;
        }}
        h1, h2, h3 {{ color: #2c3e50; }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        pre code {{ background: none; padding: 0; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{ background: #f4f4f4; }}
    </style>
</head>
<body>
{content}
</body>
</html>"""
    
    # Find all markdown files
    docs_path = Path(docs_dir)
    md_files = list(docs_path.rglob("*.md"))
    
    converted_count = 0
    for md_file in md_files:
        try:
            # Read markdown content
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Convert to HTML
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            
            # Get title from first heading or filename
            title = md_file.stem.replace('_', ' ').title()
            
            # Create full HTML document
            full_html = html_template.format(title=title, content=html_content)
            
            # Determine output path (preserve directory structure)
            rel_path = md_file.relative_to(docs_path)
            html_file = Path(install_docs_dir) / rel_path.with_suffix('.html')
            
            # Create parent directories if needed
            html_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write HTML file
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(full_html)
            
            converted_count += 1
            
        except Exception as e:
            print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Failed to convert {md_file.name}: {e}")
    
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Converted {converted_count} documentation files to HTML")
    print(f"Documentation installed to: {install_docs_dir}")


def create_wrapper_script(main_script, local_bin):
    """Create a wrapper script in ~/.local/bin."""
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} Creating wrapper script...")
    
    response = input(f"Would you like to create a symlink in {local_bin}? (y/n): ").strip().lower()
    
    if response == 'y':
        if not os.path.exists(local_bin):
            os.makedirs(local_bin)
            print(f"{Colors.CYAN}[INFO]{Colors.RESET} Created directory: {local_bin}")
        
        wrapper_script = os.path.join(local_bin, "flexflow")
        
        try:
            with open(wrapper_script, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write(f'python3 "{main_script}" "$@"\n')
            
            os.chmod(wrapper_script, 0o755)
            print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Created executable wrapper at {wrapper_script}")
            
            # Check if LOCAL_BIN is in PATH
            path_var = os.environ.get('PATH', '')
            if local_bin not in path_var:
                print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {local_bin} is not in your PATH")
                return True  # Needs PATH update
            
        except Exception as e:
            print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to create wrapper script: {e}")
    
    return False


def install_microsoft_fonts():
    """Install Microsoft fonts for Times New Roman, Arial, etc."""
    import subprocess
    
    print(f"\n{Colors.CYAN}Installing Microsoft fonts...{Colors.RESET}")
    print(f"This will install Times New Roman, Arial, Courier New, and other MS fonts")
    
    try:
        # Check if running on Debian/Ubuntu-based system
        result = subprocess.run(['which', 'apt-get'], capture_output=True, text=True)
        if not result.stdout.strip():
            print(f"{Colors.YELLOW}Warning:{Colors.RESET} apt-get not found")
            print(f"This installer works on Debian/Ubuntu-based systems")
            print(f"For other systems, please install MS fonts manually:")
            print(f"  - Fedora/RHEL: sudo dnf install curl cabextract xorg-x11-font-utils fontconfig")
            print(f"  - Arch: yay -S ttf-ms-fonts")
            return
        
        # Install ttf-mscorefonts-installer
        print(f"\n{Colors.YELLOW}Running:{Colors.RESET} sudo apt-get install -y ttf-mscorefonts-installer")
        print(f"You may be prompted for your sudo password...")
        
        # Pre-accept EULA
        subprocess.run([
            'sudo', 'debconf-set-selections'
        ], input=b'ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true\n')
        
        # Install package
        result = subprocess.run(
            ['sudo', 'apt-get', 'install', '-y', 'ttf-mscorefonts-installer'],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n{Colors.GREEN}✓{Colors.RESET} Microsoft fonts installed successfully!")
            
            # Update font cache
            print(f"\n{Colors.CYAN}Updating font cache...{Colors.RESET}")
            subprocess.run(['fc-cache', '-fv'], capture_output=True)
            print(f"{Colors.GREEN}✓{Colors.RESET} Font cache updated")
            
            print(f"\n{Colors.BOLD}Available fonts now include:{Colors.RESET}")
            print(f"  • Times New Roman")
            print(f"  • Arial")
            print(f"  • Courier New")
            print(f"  • Georgia")
            print(f"  • Verdana")
            print(f"  • And more...")
            
            print(f"\n{Colors.BOLD}Usage:{Colors.RESET}")
            print(f'  flexflow plot ... --fontname "Times New Roman"')
            
        else:
            print(f"\n{Colors.RED}Error:{Colors.RESET} Installation failed")
            print(f"You can try installing manually:")
            print(f"  {Colors.CYAN}sudo apt-get install ttf-mscorefonts-installer{Colors.RESET}")
            
    except FileNotFoundError:
        print(f"{Colors.RED}Error:{Colors.RESET} Required command not found")
        print(f"Please install manually")
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.RESET} {e}")
        print(f"Installation failed. You can try manually:")
        print(f"  {Colors.CYAN}sudo apt-get install ttf-mscorefonts-installer{Colors.RESET}")


def install():
    """Install flexflow command globally with all features from install.sh."""
    # Print header
    print(f"\n{Colors.BLUE}{'━' * 50}{Colors.RESET}")
    print(f"{Colors.BLUE}  FlexFlow Installation{Colors.RESET}")
    print(f"{Colors.BLUE}{'━' * 50}{Colors.RESET}\n")
    
    # Step 1: Check Python
    if not check_python():
        sys.exit(1)
    
    # Step 2: Check and install dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Step 3: Setup installation directories
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    home = os.path.expanduser('~')
    default_install_dir = os.path.join(home, '.local', 'share', 'flexflow')
    
    print(f"\n{Colors.BOLD}Installation Directory:{Colors.RESET}")
    print(f"Default: {Colors.YELLOW}{default_install_dir}{Colors.RESET}")
    
    response = input(f"\nPress Enter to use default, or enter custom path: ").strip()
    install_dir = response if response else default_install_dir
    install_dir = os.path.expanduser(install_dir)
    
    # Create installation directory
    try:
        os.makedirs(install_dir, exist_ok=True)
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Installation directory: {install_dir}")
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to create directory: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Step 4: Copy files
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Copying files...")
    
    try:
        # Copy main.py
        shutil.copy2(os.path.join(script_dir, 'main.py'), install_dir)
        main_script = os.path.join(install_dir, 'main.py')
        os.chmod(main_script, 0o755)
        
        # Copy module directory
        src_module = os.path.join(script_dir, 'module')
        dst_module = os.path.join(install_dir, 'module')
        if os.path.exists(dst_module):
            shutil.rmtree(dst_module)
        shutil.copytree(src_module, dst_module)
        
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Files copied successfully")
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to copy files: {e}")
        sys.exit(1)
    
    # Step 5: Convert and install documentation
    src_docs = os.path.join(script_dir, 'docs')
    dst_docs = os.path.join(install_dir, 'docs')
    if os.path.exists(src_docs):
        convert_docs_to_html(src_docs, dst_docs)
    
    # Step 6: Setup shell alias
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Setting up shell alias...")
    
    # Detect shell config file
    shell_config = None
    if 'ZSH_VERSION' in os.environ or os.path.exists(os.path.join(home, '.zshrc')):
        shell_config = os.path.join(home, '.zshrc')
    elif os.path.exists(os.path.join(home, '.bashrc')):
        shell_config = os.path.join(home, '.bashrc')
    elif os.path.exists(os.path.join(home, '.bash_profile')):
        shell_config = os.path.join(home, '.bash_profile')
    elif os.path.exists(os.path.join(home, '.profile')):
        shell_config = os.path.join(home, '.profile')
    
    if not shell_config:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} No shell configuration file found")
        sys.exit(1)
    
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} Detected shell configuration file: {shell_config}")
    
    # Check if alias already exists
    try:
        with open(shell_config, 'r') as f:
            content = f.read()
    except:
        content = ""
    
    alias_cmd = f'alias flexflow="python3 {main_script}"'
    
    if 'alias flexflow=' in content:
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} FlexFlow alias already exists in {shell_config}")
        response = input("Would you like to update it? (y/n): ").strip().lower()
        
        if response != 'y':
            print(f"{Colors.CYAN}[INFO]{Colors.RESET} Skipping alias addition.")
        else:
            # Remove old alias
            lines = content.split('\n')
            lines = [l for l in lines if 'alias flexflow=' not in l and 'FlexFlow alias' not in l]
            content = '\n'.join(lines)
            
            # Add new alias
            with open(shell_config, 'w') as f:
                f.write(content)
                if not content.endswith('\n'):
                    f.write('\n')
                f.write(f'\n# FlexFlow alias - added by install\n{alias_cmd}\n')
            
            print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Alias updated in {shell_config}")
    else:
        # Add new alias
        with open(shell_config, 'a') as f:
            f.write(f'\n# FlexFlow alias - added by install\n{alias_cmd}\n')
        
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Alias added to {shell_config}")
    
    # Step 7: Optional wrapper script in ~/.local/bin
    local_bin = os.path.join(home, '.local', 'bin')
    needs_path_update = create_wrapper_script(main_script, local_bin)
    
    if needs_path_update:
        # Add local bin to PATH
        with open(shell_config, 'a') as f:
            f.write(f'\n# Add local bin to PATH - added by FlexFlow install\n')
            f.write(f'export PATH="$HOME/.local/bin:$PATH"\n')
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Added {local_bin} to PATH in {shell_config}")
    
    # Step 8: Test installation
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Testing FlexFlow installation...")
    try:
        result = subprocess.run(
            [sys.executable, main_script, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} FlexFlow is working correctly!")
        else:
            print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} FlexFlow test returned non-zero exit code")
    except Exception as e:
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} FlexFlow test failed: {e}")
        print(f"Try running: python3 {main_script} --help")
    
    # Step 9: Shell completion installation
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Setting up shell autocompletion...")
    
    from flexflow.cli.completion import detect_shell, install_completion, get_completion_install_path
    
    detected_shell = detect_shell()
    if detected_shell:
        print(f"Detected shell: {detected_shell}")
        response = input(f"Install tab completion for {detected_shell}? (y/n): ").strip().lower()
        
        if response == 'y':
            try:
                if install_completion(detected_shell, verbose=True):
                    # Add source line to shell config
                    if detected_shell == 'bash':
                        completion_path = get_completion_install_path('bash')
                        source_line = f"\n# FlexFlow completion\n[[ -f {completion_path} ]] && source {completion_path}\n"
                        
                        # Check if already in shell_config
                        with open(shell_config, 'r') as f:
                            config_content = f.read()
                        
                        if 'FlexFlow completion' not in config_content:
                            with open(shell_config, 'a') as f:
                                f.write(source_line)
                            print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Added completion source to {shell_config}")
                    
                    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Shell completion installed!")
                    print(f"\n{Colors.YELLOW}Note:{Colors.RESET} Restart your shell or run:")
                    if detected_shell == 'bash':
                        print(f"  {Colors.CYAN}source ~/.bashrc{Colors.RESET}")
                    elif detected_shell == 'zsh':
                        print(f"  {Colors.CYAN}source ~/.zshrc{Colors.RESET}")
                    elif detected_shell == 'fish':
                        print(f"  {Colors.CYAN}Restart fish shell{Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Completion installation had issues, but you can still use:")
                    print(f"  {Colors.CYAN}flexflow --completion {detected_shell} > ~/flexflow-completion{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} Could not install completion: {e}")
                print(f"You can manually generate it with:")
                print(f"  {Colors.CYAN}flexflow --completion {detected_shell}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}[INFO]{Colors.RESET} Skipped shell completion installation")
    else:
        print(f"{Colors.YELLOW}[INFO]{Colors.RESET} Could not detect shell. Skipping autocompletion.")
        print(f"Supported shells: bash, zsh, fish")
    
    # Step 10: Optional Microsoft fonts
    print(f"\n{Colors.CYAN}Optional: Microsoft Fonts Installation{Colors.RESET}")
    print(f"Install Times New Roman, Arial, and other Microsoft fonts?")
    print(f"These fonts are useful for academic publications and professional plots.")
    print(f"\n{Colors.YELLOW}Note:{Colors.RESET} Requires internet connection and ~70MB download")
    
    response = input(f"\nInstall Microsoft fonts? (y/n): ").strip().lower()
    
    if response == 'y':
        install_microsoft_fonts()
    else:
        print(f"\n{Colors.YELLOW}Skipped{Colors.RESET} Microsoft fonts installation")
        print(f"To install later, run:")
        print(f"  {Colors.CYAN}sudo apt-get install ttf-mscorefonts-installer{Colors.RESET}")
    
    # Step 11: Show completion message
    print(f"\n{Colors.GREEN}{'━' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}  Installation Complete!{Colors.RESET}")
    print(f"{Colors.GREEN}{'━' * 50}{Colors.RESET}\n")
    
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} To start using FlexFlow, run one of the following:")
    print(f"  {Colors.CYAN}source {shell_config}{Colors.RESET}  # Then use 'flexflow' command")
    print(f"  {Colors.CYAN}python3 {main_script} --help{Colors.RESET}  # Direct invocation")
    
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Quick start:")
    print(f"  {Colors.CYAN}flexflow info <case_directory>{Colors.RESET}")
    print(f"  {Colors.CYAN}flexflow plot <case_directory> --data-type displacement --node 10 --component y{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} For more information:")
    print(f"  {Colors.CYAN}flexflow --help{Colors.RESET}")
    print(f"  {Colors.CYAN}flexflow docs{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Tab completion is available - try pressing TAB after typing:")
    print(f"  {Colors.CYAN}flexflow <TAB>{Colors.RESET}  # Shows available commands")
    print(f"  {Colors.CYAN}flexflow plot --<TAB>{Colors.RESET}  # Shows available options\n")


def uninstall():
    """Uninstall flexflow command"""
    home = os.path.expanduser('~')
    rc_files = []
    for rc in ['.bashrc', '.bash_profile', '.profile', '.zshrc']:
        path = os.path.join(home, rc)
        if os.path.exists(path):
            rc_files.append(path)
    
    removed = False
    for rc_file in rc_files:
        with open(rc_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        skip_next = False
        for i, line in enumerate(lines):
            if 'FlexFlow CLI alias' in line or 'FlexFlow alias' in line or 'FlexFlow completion' in line:
                skip_next = True
                removed = True
                continue
            if skip_next and ('alias flexflow=' in line or 'flexflow' in line and 'source' in line):
                skip_next = False
                continue
            new_lines.append(line)
        
        if removed:
            with open(rc_file, 'w') as f:
                f.writelines(new_lines)
            print(f"{Colors.GREEN}✓{Colors.RESET} Removed flexflow alias from {rc_file}")
    
    # Remove shell completions
    from flexflow.cli.completion import detect_shell, uninstall_completion
    
    print(f"\n{Colors.CYAN}[INFO]{Colors.RESET} Removing shell completions...")
    for shell in ['bash', 'zsh', 'fish']:
        if uninstall_completion(shell, verbose=False):
            print(f"{Colors.GREEN}✓{Colors.RESET} Removed {shell} completion")
    
    if not removed:
        print(f"{Colors.YELLOW}Warning:{Colors.RESET} flexflow alias not found")
    else:
        print(f"\n{Colors.GREEN}✓{Colors.RESET} FlexFlow uninstalled successfully!")


def update():
    """Update flexflow installation"""
    print(f"{Colors.CYAN}Updating FlexFlow...{Colors.RESET}")
    print(f"Current version: {VERSION}")
    print(f"\nTo update, pull the latest changes from the repository:")
    print(f"  {Colors.CYAN}git pull origin main{Colors.RESET}")
