#!/bin/bash
# FlexFlow Common Functions Library
# Reusable functions for all FlexFlow SLURM scripts

# ============================================================================
# COLOR CODES FOR OUTPUT
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

# Initialize log file
init_logging() {
    if [ "${ENABLE_LOGGING}" = "1" ]; then
        mkdir -p "${LOG_DIR}"
        LOG_FILE="${LOG_DIR}/$(basename $0 .sh)_$(date +%Y%m%d_%H%M%S).log"
        touch "${LOG_FILE}"
    fi
}

# Log message with timestamp
log() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] $*"
    echo -e "${msg}"
    if [ "${ENABLE_LOGGING}" = "1" ] && [ -n "${LOG_FILE}" ]; then
        echo "${msg}" >> "${LOG_FILE}"
    fi
}

# Log info message (cyan)
log_info() {
    log "${CYAN}[INFO]${NC} $*"
}

# Log success message (green)
log_success() {
    log "${GREEN}[✓]${NC} $*"
}

# Log warning message (yellow)
log_warning() {
    log "${YELLOW}[!]${NC} $*"
}

# Log error message (red)
log_error() {
    log "${RED}[✗]${NC} $*"
}

# ============================================================================
# SLURM INFORMATION
# ============================================================================

print_job_info() {
    log_info "=========================================="
    log_info "FlexFlow Job Started"
    log_info "Script: $(basename $0)"
    log_info "Job ID: ${SLURM_JOB_ID:-local}"
    log_info "Job Name: ${SLURM_JOB_NAME:-N/A}"
    log_info "Node(s): ${SLURM_NODELIST:-localhost}"
    log_info "Tasks: ${SLURM_NTASKS:-N/A}"
    log_info "CPUs per Task: ${SLURM_CPUS_PER_TASK:-N/A}"
    log_info "Start Time: $(date)"
    log_info "Working Directory: $(pwd)"
    log_info "=========================================="
}

print_job_summary() {
    log_info "=========================================="
    log_info "Job Completed"
    log_info "End Time: $(date)"
    log_info "Duration: $SECONDS seconds"
    log_info "=========================================="
}

# ============================================================================
# DIRECTORY MANAGEMENT
# ============================================================================

# Create required output directories
create_output_dirs() {
    log_info "Creating output directories..."
    mkdir -p "${OTHD_DIR}" "${OISD_DIR}" "${RCV_DIR}" "${PLT_DIR}" "${OUTDIR}"
    log_success "Output directories created"
}

# ============================================================================
# FILE MANAGEMENT
# ============================================================================

# Count files in directory (robust method)
count_files() {
    local dir="$1"
    local pattern="${2:-*}"
    
    if [ ! -d "${dir}" ]; then
        echo "0"
        return
    fi
    
    shopt -s nullglob
    local files=("${dir}"/${pattern})
    echo "${#files[@]}"
    shopt -u nullglob
}

# Save output files with sequential numbering
save_output_files() {
    local problem="$1"
    local outdir="$2"
    
    log_info "Checking for output files to save..."
    
    if [ ! -f "${outdir}/${problem}.othd" ]; then
        log_warning "No output files found to save"
        return 0
    fi
    
    # Create directories if needed
    mkdir -p "${OTHD_DIR}" "${OISD_DIR}" "${RCV_DIR}"
    
    # Get next file number
    local file_count=$(count_files "${OTHD_DIR}" "*.othd")
    ((file_count++))
    
    log_info "Saving output files as #${file_count}..."
    
    # Move output files
    if [ -f "${outdir}/${problem}.othd" ]; then
        mv "${outdir}/${problem}.othd" "${OTHD_DIR}/${problem}${file_count}.othd"
        log_success "Saved ${problem}${file_count}.othd"
    fi
    
    if [ -f "${outdir}/${problem}.oisd" ]; then
        mv "${outdir}/${problem}.oisd" "${OISD_DIR}/${problem}${file_count}.oisd"
        log_success "Saved ${problem}${file_count}.oisd"
    fi
    
    if [ -f "${problem}.rcv" ]; then
        cp "${problem}.rcv" "${RCV_DIR}/${problem}${file_count}.rcv"
        log_success "Saved ${problem}${file_count}.rcv"
    fi
}

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

# Check if file exists
check_file() {
    local file="$1"
    local desc="${2:-File}"
    
    if [ ! -f "${file}" ]; then
        log_error "${desc} not found: ${file}"
        return 1
    fi
    return 0
}

# Check if executable exists and is executable
check_executable() {
    local exe="$1"
    local desc="${2:-Executable}"
    
    if [ ! -x "${exe}" ]; then
        log_error "${desc} not found or not executable: ${exe}"
        log_error "Please check your config.sh file"
        return 1
    fi
    log_success "${desc} found: ${exe}"
    return 0
}

# Check if command is available
check_command() {
    local cmd="$1"
    local desc="${2:-Command}"
    
    if ! command -v "${cmd}" &> /dev/null; then
        log_error "${desc} not found: ${cmd}"
        return 1
    fi
    return 0
}

# Validate environment before running
validate_environment() {
    local errors=0
    
    log_info "Validating environment..."
    
    # Check required commands
    for cmd in awk sed grep; do
        if ! check_command "${cmd}" "${cmd}"; then
            ((errors++))
        fi
    done
    
    # Check SLURM variables (warning only)
    if [ -z "${SLURM_NTASKS:-}" ]; then
        log_warning "Not running under SLURM scheduler"
    fi
    
    if [ ${errors} -gt 0 ]; then
        log_error "Environment validation failed with ${errors} error(s)"
        return 1
    fi
    
    log_success "Environment validation passed"
    return 0
}

# ============================================================================
# MODULE LOADING
# ============================================================================

# Load module with fallback
load_module_safe() {
    local module_name="$1"
    local fallback="${2:-}"
    
    log_info "Loading module: ${module_name}..."
    
    # Check if module command exists
    if ! command -v module &> /dev/null; then
        log_warning "Module command not available"
        return 0
    fi
    
    # Try to load primary module
    if module is-avail "${module_name}" 2>/dev/null; then
        module load "${module_name}"
        log_success "Loaded module: ${module_name}"
        return 0
    fi
    
    # Try fallback if provided
    if [ -n "${fallback}" ]; then
        log_warning "Module ${module_name} not available, trying ${fallback}..."
        if module is-avail "${fallback}" 2>/dev/null; then
            module load "${fallback}"
            log_success "Loaded fallback module: ${fallback}"
            return 0
        fi
    fi
    
    log_error "Module not found: ${module_name}"
    return 1
}

# ============================================================================
# EXECUTION HELPERS
# ============================================================================

# Run command with logging and error checking
run_cmd() {
    local desc="$1"
    shift
    
    log_info "Running: ${desc}"
    log_info "Command: $*"
    
    if "$@"; then
        log_success "${desc} completed"
        return 0
    else
        local exit_code=$?
        log_error "${desc} failed with exit code ${exit_code}"
        return ${exit_code}
    fi
}

# Set OpenMP threads
set_omp_threads() {
    local threads="${SLURM_CPUS_PER_TASK:-1}"
    export OMP_NUM_THREADS=${threads}
    log_info "Set OMP_NUM_THREADS=${threads}"
}

# ============================================================================
# CLEANUP
# ============================================================================

# Cleanup function (can be customized per script)
cleanup() {
    log_info "Performing cleanup..."
    # Add cleanup commands as needed
}

# Register cleanup on exit
register_cleanup() {
    trap cleanup EXIT
}

# ============================================================================
# ERROR HANDLING
# ============================================================================

# Error handler
error_handler() {
    local line_no=$1
    log_error "Script failed at line ${line_no}"
    log_error "Check ${LOG_FILE} for details"
    exit 1
}

# Set error handling
set_error_handling() {
    set -e  # Exit on error
    set -u  # Exit on undefined variable
    set -o pipefail  # Catch errors in pipes
    trap 'error_handler ${LINENO}' ERR
}
