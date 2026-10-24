#!/bin/bash
#SBATCH --job-name=earspectro
#SBATCH --output=/scratch/nishanth.r/glycemico-pred/logs/earspectro_%j.log
#SBATCH --error=/scratch/nishanth.r/glycemico-pred/logs/earspectro_%j.log
#SBATCH --partition=plafnet2
#SBATCH --account=plafnet2
# No GPU: the venv has CPU torch and these models are small. For GPU, install CUDA torch and add --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00
#SBATCH --nodelist=gnode118

# ============================================================================
# Job: EarSpectro full experiment suite
#
#   Stage 1  data        synthetic ear-NIR set (skipped if present / real data given)
#   Stage 2  qc          quality control vs injected artifacts
#   Stage 3  scenarios   random vs subject vs session splits         (H5)
#   Stage 4  matrix      representation x preprocessing x model      (H1, H3, H4)
#   Stage 5  wavelengths subset study with nested selection          (H2)
#   Stage 6  selection   feature-selection methods                   (sec. 17)
#   Stage 7  calibration 0/1/2/3/5-point calibration                 (H6)
#   Stage 8  explain     wavelength importance stability             (sec. 27)
#   Stage 9  report      outputs/REPORT.md
#
# Submit:  sbatch slurm/run_all.sh                 (synthetic data)
#          DATA=data/real.csv sbatch slurm/run_all.sh
# ============================================================================

echo "=========================================="
echo "EarSpectro  |  Experiment suite"
echo "=========================================="
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $SLURM_NODELIST"
echo "Start    : $(date)"
echo "=========================================="

PROJ=/scratch/nishanth.r/glycemico-pred
cd "$PROJ"
mkdir -p logs
source venv/bin/activate
set -euo pipefail

echo "Python : $(which python)"
python -c 'import torch; print(f"PyTorch {torch.__version__}, CUDA {torch.cuda.is_available()}")'
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader || true
echo ""

# ── Configuration ──────────────────────────────────────────────────────────
DATA=${DATA:-data/synthetic_ear5.csv}
OUT=${OUT:-outputs}
N_JOBS=${SLURM_CPUS_PER_TASK:-8}
RUN="python experiments/run.py"

# ── Stage 1: Data ──────────────────────────────────────────────────────────
if [ ! -f "$DATA" ]; then
    echo "STAGE 1: generating synthetic data -> $DATA"
    $RUN generate --output "$DATA" --grid ear5 --subjects 40 --sessions 2
else
    echo "STAGE 1: $DATA present — skipping."
fi

COMMON="--data $DATA --out $OUT --n_jobs $N_JOBS"

echo "STAGE 2: QC";            $RUN qc          $COMMON
echo "STAGE 3: scenarios";     $RUN scenarios   $COMMON --prep snv
echo "STAGE 4: matrix";        $RUN matrix      $COMMON --scenario subject
echo "STAGE 5: wavelengths";   $RUN wavelengths $COMMON --prep raw
echo "STAGE 6: selection";     $RUN selection   $COMMON --prep raw
echo "STAGE 7: calibration";   $RUN calibration $COMMON --prep snv
echo "STAGE 8: explain";       $RUN explain     $COMMON --prep raw
echo "STAGE 9: report";        $RUN report      $COMMON

echo "=========================================="
echo "JOB COMPLETED  |  $(date)"
echo "=========================================="
