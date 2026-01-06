#!/bin/bash
# FlexFlow Wrapper with Automatic Python 3.12 for Tecplot Operations
#
# This wrapper automatically detects Tecplot-related commands and uses
# Python 3.12 when needed, without requiring manual environment activation.

# Determine if this is a Tecplot command
is_tecplot_cmd=false
if [ $# -gt 0 ]; then
    case "$1" in
        field|tecplot)
            is_tecplot_cmd=true
            ;;
        convert|extract)
            # Legacy flat commands
            is_tecplot_cmd=true
            ;;
    esac
fi

# Find Python 3.12
PYTHON312=""

# Check conda tecplot312 environment
CONDA_BASE="${HOME}/miniconda3"
if [ -f "${CONDA_BASE}/envs/tecplot312/bin/python" ]; then
    PYTHON312="${CONDA_BASE}/envs/tecplot312/bin/python"
elif [ -f "${HOME}/anaconda3/envs/tecplot312/bin/python" ]; then
    PYTHON312="${HOME}/anaconda3/envs/tecplot312/bin/python"
elif [ -f "/usr/bin/python3.12" ]; then
    PYTHON312="/usr/bin/python3.12"
elif [ -f "/bin/python3.12" ]; then
    PYTHON312="/bin/python3.12"
fi

# Get current Python version
CURRENT_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)

# Decide which Python to use
if [ "$is_tecplot_cmd" = true ]; then
    # Tecplot command - check Python version
    if [[ "$CURRENT_VERSION" =~ ^3\.1[3-9] ]]; then
        # Python 3.13+, need to use 3.12
        if [ -n "$PYTHON312" ]; then
            exec "$PYTHON312" "/home/arunperiyal/.local/share/flexflow/main.py" "$@"
        else
            echo "[FlexFlow] WARNING: Python 3.12 not found for Tecplot operations!" >&2
            echo "[FlexFlow] Install with: conda create -n tecplot312 python=3.12 -y" >&2
            echo "[FlexFlow] Then: conda activate tecplot312 && pip install pytecplot" >&2
            echo "[FlexFlow] Attempting with current Python (may crash)..." >&2
            exec python3 "/home/arunperiyal/.local/share/flexflow/main.py" "$@"
        fi
    else
        # Python 3.12 or earlier, OK to use
        exec python3 "/home/arunperiyal/.local/share/flexflow/main.py" "$@"
    fi
else
    # Non-Tecplot command, use current Python
    exec python3 "/home/arunperiyal/.local/share/flexflow/main.py" "$@"
fi
