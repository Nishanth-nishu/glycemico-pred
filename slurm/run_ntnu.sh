#!/bin/bash
#SBATCH --job-name=earspectro_ntnu
#SBATCH --output=/scratch/nishanth.r/glycemico-pred/logs/earspectro_ntnu_%j.log
#SBATCH --error=/scratch/nishanth.r/glycemico-pred/logs/earspectro_ntnu_%j.log
#SBATCH --partition=plafnet2
#SBATCH --account=plafnet2
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --nodelist=gnode118

# ============================================================================
# Job: EarSpectro suite on real in-vitro NIR glucose spectra (NTNU)
#
#   Data: Fuglerud et al., doi:10.18710/NSHFAK (CC0). Put CalibrationData.txt and
#         ValidationData.txt in data/ntnu_raw/ first.
#   Three wavelength grids: nir (1100-2350 nm, 2 nm), dense (1000-1700 nm, 5 nm),
#   ear5 (the 5 EarSpectro LEDs, 20 nm bands).
#   No calibration stage: the samples are not time series.
#
# Submit:  sbatch slurm/run_ntnu.sh
# ============================================================================

echo "Job ID: $SLURM_JOB_ID | Node: $SLURM_NODELIST | Start: $(date)"
PROJ=/scratch/nishanth.r/glycemico-pred
cd "$PROJ"
mkdir -p logs
source venv/bin/activate
set -euo pipefail

RUN="python experiments/run.py"
N_JOBS=${SLURM_CPUS_PER_TASK:-8}

for GRID in ear5 dense nir; do
    DATA=data/ntnu_$GRID.csv
    OUT=outputs/ntnu_$GRID
    COMMON="--data $DATA --out $OUT --n_jobs $N_JOBS"
    echo "===== $GRID ====="
    $RUN import_ntnu --raw data/ntnu_raw --grid $GRID --output $DATA
    $RUN qc          $COMMON
    $RUN scenarios   $COMMON --prep snv
    $RUN matrix      $COMMON --scenario subject
    $RUN wavelengths $COMMON --prep raw
    $RUN selection   $COMMON --prep raw
    $RUN explain     $COMMON --prep raw
    $RUN report      $COMMON
done

echo "JOB COMPLETED | $(date)"
