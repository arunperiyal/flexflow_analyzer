#!/bin/bash
# Fast FlexFlow wrapper - uses source directly for 7x faster startup
# Startup time: ~0.4s vs ~2.8s for standalone

FLEXFLOW_DIR="/media/arunperiyal/Works/projects/flexflow_manager"
CONDA_ENV="tecplot312"

# Activate conda environment quietly
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null
conda activate $CONDA_ENV 2>/dev/null

# Run FlexFlow from source
exec python "$FLEXFLOW_DIR/main.py" "$@"
