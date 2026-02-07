#!/bin/bash
#
# FlexFlow Interactive Installation Script
#
# This script orchestrates the FlexFlow installation process by sourcing
# modular installation functions from the install/ directory.
#
# Usage:
#   ./install.sh              # Install FlexFlow
#   ./install.sh --uninstall  # Uninstall FlexFlow
#   ./install.sh --help       # Show help message

set -e  # Exit on error

# Script directory
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FLEXFLOW_DIR="$SCRIPT_DIR"

# Source installation modules
source "$SCRIPT_DIR/install/config.sh"
source "$SCRIPT_DIR/install/ui.sh"
source "$SCRIPT_DIR/install/conda.sh"
source "$SCRIPT_DIR/install/installer.sh"
source "$SCRIPT_DIR/install/uninstaller.sh"

# Main installation flow
main() {
    # Check for uninstall flag
    if [ "$1" = "--uninstall" ] || [ "$1" = "-u" ]; then
        uninstall_flexflow
        exit 0
    fi

    # Show help if requested
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "FlexFlow Installation Script"
        echo
        echo "Usage:"
        echo "  ./install.sh              Install FlexFlow with conda environment"
        echo "  ./install.sh --uninstall  Remove FlexFlow installation"
        echo "  ./install.sh --help       Show this help message"
        echo
        echo "Environment:"
        echo "  Conda Environment: $CONDA_ENV_NAME"
        echo "  Python Version:    $PYTHON_VERSION"
        echo
        echo "For more information, see INSTALL.md"
        exit 0
    fi

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

    # Show summary
    print_summary
}

# Run main function with arguments
main "$@"
