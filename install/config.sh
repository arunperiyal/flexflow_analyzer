#!/bin/bash
# FlexFlow Installation Configuration
# Contains all configuration variables and constants

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export CYAN='\033[0;36m'
export NC='\033[0m' # No Color

# Configuration
export CONDA_ENV_NAME="flexflow_env"
export PYTHON_VERSION="3.12"
export INSTALL_DIR_LOCAL="$HOME/.local/share/flexflow"
export INSTALL_DIR_SYSTEM="/usr/local/share/flexflow"
export BIN_DIR_LOCAL="$HOME/.local/bin"
export BIN_DIR_SYSTEM="/usr/local/bin"

# Script directory (will be set by main install.sh)
export SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export FLEXFLOW_DIR="$SCRIPT_DIR"
export INSTALL_LIB_DIR="$SCRIPT_DIR/install"
