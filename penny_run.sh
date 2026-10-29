#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J penny_talent
#SBATCH -n 10
#SBATCH --gres=gpu:1
#SBATCH --mem-per-cpu=3G
#SBATCH --time=1-00:00:00
#SBATCH --nodelist=gnode114
#SBATCH --output=/home2/nishanth.r/pen_sm/logs/penny_%j.log
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=nishanth0962333@gmail.com
#
# Penny-stock talent pipeline on gnode114 with local Ollama extraction.
#
#   sbatch penny_run.sh                                   # pilot: 2 tickers
#   PENNY_MODE=full sbatch penny_run.sh                   # all 100 companies
#   PENNY_TICKERS="PDSB india:NHCFOODS" sbatch penny_run.sh
#   PENNY_MODEL=llama3.1:8b PENNY_MODE=full sbatch penny_run.sh
#   PENNY_NUM_CTX=32768 sbatch penny_run.sh                # on a 24 GB card
#
# plafnet2 (gnode113-118) is out of GPU-minutes until ~1 Nov 2026; until then run on the
# general partition with the plafnet account:
#   sbatch -A plafnet -p u22 --qos=normal --nodelist= --gres=gpu:1 -n 10 penny_run.sh
#
# Repo source : /home2/nishanth.r/pen_sm/penny-stocks-investing  (git checkout, edit here)
# Work dir    : /scratch/nishanth.r/penny                        (venv, data/, caches; node-local)
# Results     : /home2/nishanth.r/pen_sm/penny_results/<jobid>/  (exports copied back every run)

set -o pipefail
SRC=/home2/nishanth.r/pen_sm/penny-stocks-investing
PROJ=/scratch/nishanth.r/penny
RESULTS=/home2/nishanth.r/pen_sm/penny_results/$SLURM_JOB_ID
MODE=${PENNY_MODE:-pilot}
TICKERS=${PENNY_TICKERS:-"PDSB india:NHCFOODS"}
MODEL=${PENNY_MODEL:-llama3.1:8b}
PY312=/software/apps/u22/python/3.12.15/bin/python3.12
export LD_LIBRARY_PATH=/software/apps/u22/python/3.12.15/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}   # python3.12 needs its libpython
NUM_CTX=${PENNY_NUM_CTX:-16384}   # 32768 in the repo default; 16k keeps llama3.1:8b inside an 11 GB card

echo "=========================================="
echo "PENNY TALENT | job $SLURM_JOB_ID on $SLURM_NODELIST | mode=$MODE model=$MODEL"
echo "start: $(date -u '+%F %T') UTC / $(TZ=Asia/Kolkata date '+%T') IST"
echo "=========================================="
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

# ── 1. stage repo into scratch (keep data/ and .venv between runs: caches live there)
mkdir -p "$PROJ" "$RESULTS"
rsync -a --delete --exclude .venv --exclude data --exclude .env --exclude 'dashboard/index.html' "$SRC/" "$PROJ/"
cd "$PROJ" || exit 1
[ -f .env ] || cp .env.example .env
sed -i "s/^\(  ollama_num_ctx:\) *[0-9]*/\1 $NUM_CTX/" config/sources.yaml
grep -n 'ollama_num_ctx' config/sources.yaml

# ── 2. python 3.12 venv (repo needs >=3.11; node default is 3.10)
if [ -x "$PY312" ]; then PY=$PY312; else PY=$(command -v python3.12 || command -v python3.11 || command -v python3); fi
echo "base python: $PY ($($PY --version 2>&1))"
if [ ! -x .venv/bin/python ]; then
    "$PY" -m venv .venv || exit 1
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e ".[dev]" || { echo "pip install failed"; exit 1; }
echo "venv python: $(.venv/bin/python --version)"

# ── 3. Ollama from node scratch
source /home2/nishanth.r/pen_sm/ollama_env.sh "$MODEL" || exit 1
trap ollama_sync_back EXIT
export TALENT_EXTRACTION_PROVIDER=ollama
export TALENT_OLLAMA_URL="http://$OLLAMA_HOST"
export TALENT_OLLAMA_MODEL="$MODEL"
export PYTHONPATH="$PROJ/src"
talent() { "$PROJ/.venv/bin/python" -m talent.cli "$@"; }

# ── 4. pipeline
stage() { echo; echo "────────── $1  ($(date -u +%T) UTC)"; }

stage "llm-check"
talent llm-check || exit 1

stage "universe build"
talent universe build || exit 1
talent universe show --limit 10

if [ "$MODE" = "full" ]; then
    stage "run-all (all selected companies)"
    talent run-all
else
    stage "run-all pilot: $TICKERS"
    ARGS=(); for t in $TICKERS; do ARGS+=(--ticker "$t"); done
    talent run-all "${ARGS[@]}"
    for t in $TICKERS; do
        stage "score --explain $t"; talent score "$t" --explain
        stage "people show $t";     talent people show "$t"
    done
fi

stage "status + export"
talent status
talent export

# ── 5. copy results home
cp -r data/export "$RESULTS/" 2>/dev/null
cp dashboard/index.html "$RESULTS/dashboard.html" 2>/dev/null
cp data/talent.db "$RESULTS/" 2>/dev/null
du -sh "$RESULTS"; ls -la "$RESULTS"
echo "=========================================="
echo "DONE $(date -u '+%F %T') UTC / $(TZ=Asia/Kolkata date '+%T') IST  → $RESULTS"
echo "=========================================="
