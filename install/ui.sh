#!/bin/bash
# FlexFlow Installation UI Functions
# Contains all user interface and display functions

# Source configuration
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

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
