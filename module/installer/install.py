"""Installation utilities for FlexFlow."""

import os
import sys
from module.utils.colors import Colors


VERSION = "1.0.0"


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
    """Install flexflow command globally"""
    import shutil
    
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    home = os.path.expanduser('~')
    default_install_dir = os.path.join(home, '.local', 'share', 'flexflow')
    
    # Interactive installation directory selection
    print(f"{Colors.CYAN}FlexFlow Installation{Colors.RESET}")
    print(f"\n{Colors.BOLD}Installation Directory:{Colors.RESET}")
    print(f"Default: {Colors.YELLOW}{default_install_dir}{Colors.RESET}")
    
    response = input(f"\nPress Enter to use default, or enter custom path: ").strip()
    install_dir = response if response else default_install_dir
    install_dir = os.path.expanduser(install_dir)
    
    # Create installation directory
    try:
        os.makedirs(install_dir, exist_ok=True)
        print(f"\n{Colors.GREEN}✓{Colors.RESET} Installation directory: {install_dir}")
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.RESET} Failed to create directory: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Copy files to installation directory
    print(f"\n{Colors.CYAN}Copying files...{Colors.RESET}")
    
    # Copy main.py
    shutil.copy2(os.path.join(script_dir, 'main.py'), install_dir)
    
    # Copy module directory
    src_module = os.path.join(script_dir, 'module')
    dst_module = os.path.join(install_dir, 'module')
    if os.path.exists(dst_module):
        shutil.rmtree(dst_module)
    shutil.copytree(src_module, dst_module)
    
    main_script = os.path.join(install_dir, 'main.py')
    os.chmod(main_script, 0o755)
    
    print(f"{Colors.GREEN}✓{Colors.RESET} Files copied successfully")
    
    # Find shell rc file
    rc_files = []
    for rc in ['.bashrc', '.bash_profile', '.profile', '.zshrc']:
        path = os.path.join(home, rc)
        if os.path.exists(path):
            rc_files.append(path)
    
    if not rc_files:
        print(f"{Colors.RED}Error:{Colors.RESET} No shell RC file found", file=sys.stderr)
        sys.exit(1)
    
    # Create alias command
    alias_cmd = f'alias flexflow="python3 {main_script}"'
    
    # Add to first RC file found
    rc_file = rc_files[0]
    
    # Check if alias already exists
    with open(rc_file, 'r') as f:
        content = f.read()
    
    if 'alias flexflow=' in content:
        print(f"\n{Colors.YELLOW}Warning:{Colors.RESET} flexflow alias already exists in {rc_file}")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Installation cancelled")
            sys.exit(0)
        
        # Remove old alias
        lines = content.split('\n')
        lines = [l for l in lines if 'alias flexflow=' not in l and 'FlexFlow CLI alias' not in l]
        content = '\n'.join(lines)
    
    # Add new alias
    with open(rc_file, 'w') as f:
        f.write(content)
        if not content.endswith('\n'):
            f.write('\n')
        f.write(f'\n# FlexFlow CLI alias\n{alias_cmd}\n')
    
    print(f"\n{Colors.GREEN}✓{Colors.RESET} FlexFlow installed successfully!")
    print(f"\nInstallation directory: {Colors.BOLD}{install_dir}{Colors.RESET}")
    print(f"Alias added to: {Colors.BOLD}{rc_file}{Colors.RESET}")
    
    # Ask about Microsoft fonts installation
    print(f"\n{Colors.CYAN}Optional: Microsoft Fonts Installation{Colors.RESET}")
    print(f"Install Times New Roman, Arial, and other Microsoft fonts?")
    print(f"These fonts are useful for academic publications and professional plots.")
    print(f"\n{Colors.YELLOW}Note:{Colors.RESET} Requires internet connection and ~70MB download")
    
    response = input(f"\nInstall Microsoft fonts? (y/n): ").strip().lower()
    
    if response == 'y':
        install_microsoft_fonts()
    else:
        print(f"\n{Colors.YELLOW}Skipped{Colors.RESET} Microsoft fonts installation")
        print(f"You can still use 'serif' for Times-like fonts")
        print(f"To install later, run:")
        print(f"  {Colors.CYAN}sudo apt-get install ttf-mscorefonts-installer{Colors.RESET}")
    
    print(f"\nTo use flexflow command, run:")
    print(f"  {Colors.CYAN}source {rc_file}{Colors.RESET}")
    print(f"\nOr restart your terminal.")


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
            if 'FlexFlow CLI alias' in line:
                skip_next = True
                removed = True
                continue
            if skip_next and 'alias flexflow=' in line:
                skip_next = False
                continue
            new_lines.append(line)
        
        if removed:
            with open(rc_file, 'w') as f:
                f.writelines(new_lines)
            print(f"{Colors.GREEN}✓{Colors.RESET} Removed flexflow alias from {rc_file}")
    
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
