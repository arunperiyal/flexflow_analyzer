#!/bin/bash

# FlexFlow Installation Script
# This script sets up the FlexFlow environment and creates an alias for easy access

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_PY="${SCRIPT_DIR}/main.py"

# Function to print colored messages
print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  FlexFlow Installation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to check if Python 3 is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3 first."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_info "Python version: ${PYTHON_VERSION}"
}

# Function to check and install required Python packages
check_dependencies() {
    print_info "Checking Python dependencies..."
    
    REQUIRED_PACKAGES=("numpy" "matplotlib")
    MISSING_PACKAGES=()
    
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if ! python3 -c "import $package" &> /dev/null; then
            MISSING_PACKAGES+=("$package")
        fi
    done
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        print_warning "Missing packages: ${MISSING_PACKAGES[*]}"
        read -p "Would you like to install them now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installing dependencies..."
            pip3 install --user "${MISSING_PACKAGES[@]}"
            print_success "Dependencies installed successfully!"
        else
            print_warning "Skipping dependency installation. FlexFlow may not work correctly."
        fi
    else
        print_success "All required Python packages are installed."
    fi
}

# Function to make main.py executable
make_executable() {
    if [ ! -f "$MAIN_PY" ]; then
        print_error "main.py not found at ${MAIN_PY}"
        exit 1
    fi
    
    chmod +x "$MAIN_PY"
    print_success "Made main.py executable"
}

# Function to detect shell configuration file
detect_shell_config() {
    if [ -n "$ZSH_VERSION" ]; then
        echo "$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        if [ -f "$HOME/.bashrc" ]; then
            echo "$HOME/.bashrc"
        else
            echo "$HOME/.bash_profile"
        fi
    else
        # Default to .bashrc
        echo "$HOME/.bashrc"
    fi
}

# Function to add alias to shell configuration
add_alias() {
    SHELL_CONFIG=$(detect_shell_config)
    print_info "Detected shell configuration file: ${SHELL_CONFIG}"
    
    # Check if alias already exists
    if grep -q "alias flexflow=" "$SHELL_CONFIG" 2>/dev/null; then
        print_warning "FlexFlow alias already exists in ${SHELL_CONFIG}"
        read -p "Would you like to update it? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping alias addition."
            return
        fi
        # Remove old alias
        sed -i.backup '/alias flexflow=/d' "$SHELL_CONFIG"
    fi
    
    # Add alias to shell config
    echo "" >> "$SHELL_CONFIG"
    echo "# FlexFlow alias - added by install.sh" >> "$SHELL_CONFIG"
    echo "alias flexflow='python3 ${MAIN_PY}'" >> "$SHELL_CONFIG"
    
    print_success "Alias added to ${SHELL_CONFIG}"
    print_info "Run 'source ${SHELL_CONFIG}' or restart your terminal to use the 'flexflow' command"
}

# Function to create a symlink in user's local bin (optional)
create_symlink() {
    LOCAL_BIN="$HOME/.local/bin"
    
    read -p "Would you like to create a symlink in ${LOCAL_BIN}? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ ! -d "$LOCAL_BIN" ]; then
            mkdir -p "$LOCAL_BIN"
            print_info "Created directory: ${LOCAL_BIN}"
        fi
        
        # Create a wrapper script
        WRAPPER_SCRIPT="${LOCAL_BIN}/flexflow"
        cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
python3 "${MAIN_PY}" "\$@"
EOF
        chmod +x "$WRAPPER_SCRIPT"
        
        print_success "Created executable wrapper at ${WRAPPER_SCRIPT}"
        
        # Check if LOCAL_BIN is in PATH
        if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
            print_warning "${LOCAL_BIN} is not in your PATH"
            SHELL_CONFIG=$(detect_shell_config)
            echo "" >> "$SHELL_CONFIG"
            echo "# Add local bin to PATH - added by FlexFlow install.sh" >> "$SHELL_CONFIG"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_CONFIG"
            print_success "Added ${LOCAL_BIN} to PATH in ${SHELL_CONFIG}"
        fi
    fi
}

# Function to test installation
test_installation() {
    print_info "Testing FlexFlow installation..."
    
    if python3 "$MAIN_PY" --version &> /dev/null; then
        print_success "FlexFlow is working correctly!"
    else
        print_warning "FlexFlow test failed. Try running: python3 ${MAIN_PY} --help"
    fi
}

# Function to display completion message
show_completion() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    print_info "To start using FlexFlow, run one of the following:"
    echo -e "  ${CYAN}source $(detect_shell_config)${NC}  # Then use 'flexflow' command"
    echo -e "  ${CYAN}python3 ${MAIN_PY} --help${NC}  # Direct invocation"
    echo ""
    print_info "Quick start:"
    echo -e "  ${CYAN}flexflow info <case_directory>${NC}"
    echo -e "  ${CYAN}flexflow plot <case_directory> --data-type displacement --node 10 --component y${NC}"
    echo ""
    print_info "For more information:"
    echo -e "  ${CYAN}flexflow --help${NC}"
    echo -e "  ${CYAN}flexflow --examples${NC}"
    echo ""
}

# Main installation flow
main() {
    print_header
    echo ""
    
    check_python
    check_dependencies
    make_executable
    add_alias
    create_symlink
    test_installation
    show_completion
}

# Run main function
main
