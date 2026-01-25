#!/bin/bash
# FlexFlow Uninstallation Functions
# Functions for removing FlexFlow installation

# Source dependencies
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ui.sh"
source "$(dirname "${BASH_SOURCE[0]}")/conda.sh"

uninstall_flexflow() {
    print_header

    print_step "FlexFlow Uninstallation"

    echo "This will remove:"
    echo "  • FlexFlow aliases from shell config files"
    echo "  • FlexFlow wrapper script from ~/.local/bin"
    echo "  • FlexFlow shell completion"
    echo "  • Conda environment: $CONDA_ENV_NAME"
    echo

    if ! ask_yes_no "Do you want to proceed with uninstallation?"; then
        print_info "Uninstallation cancelled"
        exit 0
    fi

    # Remove aliases from shell config files
    print_step "Removing aliases and configuration"

    for rc_file in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.profile"; do
        if [ -f "$rc_file" ]; then
            # Remove FlexFlow aliases
            if grep -q "FlexFlow aliases" "$rc_file" 2>/dev/null; then
                sed -i '/# FlexFlow aliases/,/# End FlexFlow aliases/d' "$rc_file" 2>/dev/null || true
                print_success "Removed aliases from $rc_file"
            fi

            # Remove FlexFlow completion
            if grep -q "FlexFlow completion" "$rc_file" 2>/dev/null; then
                sed -i '/# FlexFlow completion/,/^fi$/d' "$rc_file" 2>/dev/null || true
                print_success "Removed completion from $rc_file"
            fi

            # Remove conda initialize added by FlexFlow
            if grep -q "Added by FlexFlow installer" "$rc_file" 2>/dev/null; then
                sed -i '/# >>> conda initialize >>>/,/# <<< conda initialize <<</d' "$rc_file" 2>/dev/null || true
                print_success "Removed conda initialization from $rc_file"
            fi

            # Remove PATH addition
            if grep -q "Add local bin to PATH - added by FlexFlow" "$rc_file" 2>/dev/null; then
                sed -i '/# Add local bin to PATH - added by FlexFlow/,/^export PATH=/d' "$rc_file" 2>/dev/null || true
                print_success "Removed PATH modification from $rc_file"
            fi
        fi
    done

    # Remove wrapper script
    print_step "Removing wrapper scripts"

    if [ -f "$HOME/.local/bin/flexflow" ]; then
        rm -f "$HOME/.local/bin/flexflow"
        print_success "Removed $HOME/.local/bin/flexflow"
    fi

    if [ -f "/usr/local/bin/flexflow" ]; then
        print_info "Removing system-wide installation (requires sudo)..."
        sudo rm -f "/usr/local/bin/flexflow"
        print_success "Removed /usr/local/bin/flexflow"
    fi

    # Remove completion files
    print_step "Removing shell completion files"

    for completion_file in "$HOME/.bash_completion.d/flexflow_completion" \
                          "$HOME/.config/fish/completions/flexflow.fish" \
                          "$HOME/.zsh/completion/_flexflow"; do
        if [ -f "$completion_file" ]; then
            rm -f "$completion_file"
            print_success "Removed $(basename $completion_file)"
        fi
    done

    # Remove conda environment
    remove_conda_env

    # Summary
    print_step "Uninstallation Complete"

    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}║                FlexFlow Successfully Uninstalled!                    ║${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo

    print_info "Next Steps:"
    echo
    echo "1. Reload your shell or open a new terminal"
    echo "2. The 'ff' and 'flexflow' commands should no longer be available"
    echo

    if [ -d "$FLEXFLOW_DIR" ]; then
        print_info "The FlexFlow source code is still in: $FLEXFLOW_DIR"
        print_info "You can delete it manually if you no longer need it"
    fi

    echo
    print_success "Goodbye! 👋"
}
