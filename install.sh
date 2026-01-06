#!/bin/bash
#
# FlexFlow Interactive Installation Script
# 
# This script will:
#   1. Check for Anaconda/Miniconda installation
#   2. Create Python 3.12 environment (tecplot312)
#   3. Install Python dependencies
#   4. Install FlexFlow (copy to system or create alias)
#   5. Setup shell completion
#   6. Configure shell aliases
#
# Usage: ./install.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLEXFLOW_DIR="$SCRIPT_DIR"

# Configuration
CONDA_ENV_NAME="tecplot312"
PYTHON_VERSION="3.12"
INSTALL_DIR_LOCAL="$HOME/.local/share/flexflow"
INSTALL_DIR_SYSTEM="/usr/local/share/flexflow"
BIN_DIR_LOCAL="$HOME/.local/bin"
BIN_DIR_SYSTEM="/usr/local/bin"

# Functions
print_header() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                                      ║${NC}"
    echo -e "${CYAN}║              FlexFlow Interactive Installation                       ║${NC}"
    echo -e "${CYAN}║                                                                      ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo
}

print_step() {
    echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}\n"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi
    
    while true; do
        read -p "$prompt" answer
        answer=${answer:-$default}
        case ${answer:0:1} in
            y|Y ) return 0 ;;
            n|N ) return 1 ;;
            * ) echo "Please answer yes or no." ;;
        esac
    done
}

check_conda() {
    print_step "Step 1: Checking for Conda installation"
    
    if command -v conda &> /dev/null; then
        CONDA_PATH=$(command -v conda)
        CONDA_DIR=$(dirname $(dirname "$CONDA_PATH"))
        print_success "Found Conda at: $CONDA_DIR"
        
        # Source conda
        if [ -f "$CONDA_DIR/etc/profile.d/conda.sh" ]; then
            source "$CONDA_DIR/etc/profile.d/conda.sh"
        elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
        elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
        fi
        
        conda --version
        return 0
    else
        print_warning "Conda not found in PATH"
        
        # Check common installation locations
        if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            print_info "Found Miniconda at: $HOME/miniconda3"
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
            print_success "Conda loaded successfully"
            conda --version
            return 0
        elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
            print_info "Found Anaconda at: $HOME/anaconda3"
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
            print_success "Conda loaded successfully"
            conda --version
            return 0
        else
            print_error "Conda not found!"
            echo
            echo "Please install Miniconda or Anaconda first:"
            echo "  Miniconda: https://docs.conda.io/en/latest/miniconda.html"
            echo "  Anaconda:  https://www.anaconda.com/products/distribution"
            echo
            return 1
        fi
    fi
}

create_conda_env() {
    print_step "Step 2: Setting up Python $PYTHON_VERSION environment"
    
    # Check if environment already exists
    if conda env list | grep -q "^$CONDA_ENV_NAME "; then
        print_info "Environment '$CONDA_ENV_NAME' already exists"
        
        if ask_yes_no "Do you want to recreate it?"; then
            print_info "Removing existing environment..."
            conda env remove -n "$CONDA_ENV_NAME" -y
        else
            print_info "Using existing environment"
            return 0
        fi
    fi
    
    print_info "Creating conda environment: $CONDA_ENV_NAME (Python $PYTHON_VERSION)"
    conda create -n "$CONDA_ENV_NAME" python="$PYTHON_VERSION" -y
    print_success "Environment created successfully"
}

install_dependencies() {
    print_step "Step 3: Installing Python dependencies"
    
    print_info "Activating environment: $CONDA_ENV_NAME"
    conda activate "$CONDA_ENV_NAME"
    
    print_info "Installing required packages..."
    
    # Core dependencies
    PACKAGES=(
        "numpy"
        "matplotlib"
        "pandas"
        "pyyaml"
        "rich"
        "tqdm"
        "pytecplot"
    )
    
    pip install "${PACKAGES[@]}"
    
    print_success "All dependencies installed"
}

choose_installation_type() {
    print_step "Step 4: Choose installation type"
    
    echo "Please choose an installation method:"
    echo
    echo "  1) Fast alias (Recommended for development)"
    echo "     - Uses source code directly"
    echo "     - Instant startup (0.4s)"
    echo "     - Easy to update"
    echo
    echo "  2) User installation (~/.local/bin)"
    echo "     - Installs for current user only"
    echo "     - No sudo required"
    echo
    echo "  3) System installation (/usr/local/bin)"
    echo "     - Available to all users"
    echo "     - Requires sudo"
    echo
    echo "  4) Both fast alias + wrapper"
    echo "     - Alias 'ff' for fast use"
    echo "     - Command 'flexflow' for convenience"
    echo
    
    read -p "Enter your choice [1-4]: " choice
    echo
    
    case $choice in
        1) INSTALL_TYPE="alias" ;;
        2) INSTALL_TYPE="user" ;;
        3) INSTALL_TYPE="system" ;;
        4) INSTALL_TYPE="both" ;;
        *) 
            print_warning "Invalid choice, using alias (recommended)"
            INSTALL_TYPE="alias"
            ;;
    esac
    
    print_info "Selected: $INSTALL_TYPE"
}

install_alias() {
    print_step "Installing fast alias"
    
    # Detect shell
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.bashrc"
    fi
    
    print_info "Detected shell config: $SHELL_RC"
    
    # Check if conda initialization exists
    if ! grep -q "conda initialize" "$SHELL_RC" 2>/dev/null; then
        print_info "Adding conda initialization to $SHELL_RC"
        
        # Find conda installation
        if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            CONDA_INIT="$HOME/miniconda3/etc/profile.d/conda.sh"
        elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
            CONDA_INIT="$HOME/anaconda3/etc/profile.d/conda.sh"
        fi
        
        if [ -n "$CONDA_INIT" ]; then
            cat >> "$SHELL_RC" << EOF

# >>> conda initialize >>>
# Added by FlexFlow installer
if [ -f "$CONDA_INIT" ]; then
    . "$CONDA_INIT"
fi
# <<< conda initialize <<<
EOF
        fi
    fi
    
    # Add FlexFlow aliases
    print_info "Adding FlexFlow aliases..."
    
    # Remove old aliases if they exist
    sed -i '/# FlexFlow aliases/,/# End FlexFlow aliases/d' "$SHELL_RC" 2>/dev/null || true
    
    cat >> "$SHELL_RC" << EOF

# FlexFlow aliases (added by installer)
# Fast version - uses source directly (0.4s startup)
alias ff='conda activate $CONDA_ENV_NAME && python "$FLEXFLOW_DIR/main.py"'

# Alternative fast alias (if you prefer full name)
alias flexflow-dev='conda activate $CONDA_ENV_NAME && python "$FLEXFLOW_DIR/main.py"'
# End FlexFlow aliases

EOF
    
    print_success "Aliases added to $SHELL_RC"
    print_info "Aliases created:"
    echo "  - ff              (fast, recommended)"
    echo "  - flexflow-dev    (same as ff)"
}

install_wrapper() {
    print_step "Installing FlexFlow wrapper"
    
    local install_dir="$1"
    local bin_dir="$2"
    local needs_sudo="$3"
    
    print_info "Installation directory: $install_dir"
    print_info "Binary directory: $bin_dir"
    
    # Create wrapper script
    local wrapper_script="$FLEXFLOW_DIR/flexflow_wrapper_new.sh"
    
    cat > "$wrapper_script" << 'EOF'
#!/bin/bash
# FlexFlow Wrapper with Automatic Python 3.12
FLEXFLOW_DIR="__FLEXFLOW_DIR__"
CONDA_ENV="__CONDA_ENV__"

# Activate conda quietly
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
fi

conda activate "$CONDA_ENV" 2>/dev/null

# Run FlexFlow
exec python "$FLEXFLOW_DIR/main.py" "$@"
EOF
    
    # Replace placeholders
    sed -i "s|__FLEXFLOW_DIR__|$FLEXFLOW_DIR|g" "$wrapper_script"
    sed -i "s|__CONDA_ENV__|$CONDA_ENV_NAME|g" "$wrapper_script"
    
    chmod +x "$wrapper_script"
    
    # Copy wrapper to bin directory
    if [ "$needs_sudo" = "yes" ]; then
        print_info "Installing system-wide (requires sudo)..."
        sudo mkdir -p "$bin_dir"
        sudo cp "$wrapper_script" "$bin_dir/flexflow"
        sudo chmod +x "$bin_dir/flexflow"
    else
        print_info "Installing for current user..."
        mkdir -p "$bin_dir"
        cp "$wrapper_script" "$bin_dir/flexflow"
        chmod +x "$bin_dir/flexflow"
        
        # Check if ~/.local/bin is in PATH
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            print_warning "~/.local/bin is not in your PATH"
            
            if ask_yes_no "Add it to PATH now?"; then
                if [ -n "$ZSH_VERSION" ]; then
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
                else
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
                fi
                print_success "Added to PATH"
            fi
        fi
    fi
    
    rm -f "$wrapper_script"
    print_success "FlexFlow wrapper installed to: $bin_dir/flexflow"
}

setup_completion() {
    print_step "Step 5: Setting up shell completion"
    
    if ask_yes_no "Do you want to setup tab completion?"; then
        print_info "Generating completion script..."
        
        # Create completion directory
        mkdir -p "$HOME/.bash_completion.d"
        
        # Generate completion
        conda activate "$CONDA_ENV_NAME" 2>/dev/null
        python "$FLEXFLOW_DIR/main.py" --completion bash > "$HOME/.bash_completion.d/flexflow_completion" 2>/dev/null || true
        
        # Add to shell config
        if [ -n "$ZSH_VERSION" ]; then
            SHELL_RC="$HOME/.zshrc"
        else
            SHELL_RC="$HOME/.bashrc"
        fi
        
        if ! grep -q "flexflow_completion" "$SHELL_RC" 2>/dev/null; then
            cat >> "$SHELL_RC" << 'EOF'

# FlexFlow completion
if [ -f "$HOME/.bash_completion.d/flexflow_completion" ]; then
    source "$HOME/.bash_completion.d/flexflow_completion"
fi
EOF
        fi
        
        print_success "Completion setup complete"
    else
        print_info "Skipping completion setup"
    fi
}

perform_installation() {
    case $INSTALL_TYPE in
        alias)
            install_alias
            ;;
        user)
            install_wrapper "$INSTALL_DIR_LOCAL" "$BIN_DIR_LOCAL" "no"
            ;;
        system)
            install_wrapper "$INSTALL_DIR_SYSTEM" "$BIN_DIR_SYSTEM" "yes"
            ;;
        both)
            install_alias
            install_wrapper "$BIN_DIR_LOCAL" "$BIN_DIR_LOCAL" "no"
            ;;
    esac
}

print_summary() {
    print_step "Installation Complete!"
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}║                  FlexFlow Successfully Installed!                    ║${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    print_info "Installation Summary:"
    echo
    echo "  Python Environment: $CONDA_ENV_NAME (Python $PYTHON_VERSION)"
    echo "  Installation Type:  $INSTALL_TYPE"
    echo "  FlexFlow Location:  $FLEXFLOW_DIR"
    echo
    
    print_info "Next Steps:"
    echo
    
    case $INSTALL_TYPE in
        alias|both)
            echo "1. Reload your shell:"
            if [ -n "$ZSH_VERSION" ]; then
                echo "   source ~/.zshrc"
            else
                echo "   source ~/.bashrc"
            fi
            echo
            echo "2. Test FlexFlow:"
            echo "   ff -v                    # Fast version (0.4s)"
            echo "   ff case show CS4SG1U1"
            ;;
        user|system)
            echo "1. Reload your shell or open a new terminal"
            echo
            echo "2. Test FlexFlow:"
            echo "   flexflow -v"
            echo "   flexflow case show CS4SG1U1"
            ;;
    esac
    
    echo
    print_info "Documentation:"
    echo "  Quick Start:  docs/guides/STANDALONE_SUCCESS.md"
    echo "  Full Guide:   docs/INDEX.md"
    echo "  Performance:  docs/technical/STARTUP_PERFORMANCE.md"
    echo
    
    print_success "Happy analyzing! 🎉"
}

# Main installation flow
main() {
    print_header
    
    # Check prerequisites
    if ! check_conda; then
        exit 1
    fi
    
    # Create environment and install dependencies
    create_conda_env
    install_dependencies
    
    # Choose and perform installation
    choose_installation_type
    perform_installation
    setup_completion
    
    # Show summary
    print_summary
}

# Run main function
main
