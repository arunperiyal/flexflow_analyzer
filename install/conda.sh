#!/bin/bash
# FlexFlow Conda Environment Management
# Functions for checking and managing conda environments

# Source dependencies
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ui.sh"

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

remove_conda_env() {
    print_step "Removing conda environment"

    if ask_yes_no "Do you want to remove the conda environment '$CONDA_ENV_NAME'?"; then
        # Try to find and source conda
        if command -v conda &> /dev/null; then
            :
        elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
        elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
        fi

        if conda env list | grep -q "^$CONDA_ENV_NAME "; then
            conda env remove -n "$CONDA_ENV_NAME" -y
            print_success "Removed conda environment: $CONDA_ENV_NAME"
        else
            print_info "Conda environment '$CONDA_ENV_NAME' not found"
        fi
    else
        print_info "Keeping conda environment: $CONDA_ENV_NAME"
    fi
}
