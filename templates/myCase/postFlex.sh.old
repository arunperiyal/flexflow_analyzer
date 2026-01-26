#!/bin/bash
#SBATCH -J myCase_post
#SBATCH -p shared            # name of the partition: available options "standard, standard-low, gpu, hm"
#SBATCH -n 4                      # no of processes or tasks
#SBATCH --cpus-per-task=4          # no of threads per process or task
#SBATCH -t 24:00:00                # walltime in HH:MM:SS, Max value 72:00:00
#list of modules you want to use, for example

module load compiler/openmpi/4.0.2 

PROBLEM=riser
OUTFREQ=50
LAST_TIME=4000
OUTDIR="RUN_1/"

# Extract plt files from the out files
exe="/home/ritwikna/modalFlexFlow/bin/simPlt"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
$exe -n $SLURM_NTASKS -pb ${PROBLEM} -outFreq ${OUTFREQ} -last ${LAST_TIME}

# Convert the plt files from ASCII to binary
exe="/home/ritwikna/modalFlexFlow/bin/simPlt2Bin"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
$exe -n $SLURM_NTASKS -w ${OUTDIR} -f ${OURFREQ} -p ${PROBLEM} -l ${LAST_TIME}
