#!/bin/bash
# FlexFlow Installation Methods
# Functions for different installation types (alias, user, system)

# Source dependencies
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ui.sh"

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
    export INSTALL_TYPE
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
    local wrapper_script="$FLEXFLOW_DIR/flexflow_wrapper_temp.sh"
    
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
