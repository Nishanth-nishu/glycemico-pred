#!/bin/bash
# Source this INSIDE a SLURM job (srun shell or sbatch) to get Ollama running
# from node-local /scratch, staged from the persistent copy in /home2.
#
#   source /home2/nishanth.r/pen_sm/ollama_env.sh [model]
#
# Persistent copy (survives scratch purges, visible on every node):
#   /home2/nishanth.r/ollama_persist/{bin,lib,models}
# Node-local working copy (fast disk, purged ~7-10 days, per node):
#   /scratch/nishanth.r/ollama
# Models pulled during the job are synced back to /home2 by ollama_sync_back.

PERSIST=/home2/nishanth.r/ollama_persist
SCR=/scratch/nishanth.r/ollama
MODEL="${1:-${OLLAMA_MODEL:-llama3.2:3b}}"

if [ -z "$SLURM_JOB_ID" ]; then
    echo "ollama_env.sh: not inside a SLURM job (no GPU here). Use srun/sbatch first." >&2
    return 1 2>/dev/null || exit 1
fi

echo "[ollama_env] node=$(hostname) job=$SLURM_JOB_ID gpus=${CUDA_VISIBLE_DEVICES:-none}"
mkdir -p "$SCR"
echo "[ollama_env] staging $PERSIST -> $SCR"
rsync -a "$PERSIST/" "$SCR/"

export PATH="$SCR/bin:$PATH"
export OLLAMA_MODELS="$SCR/models"
# Unique loopback port per job so two jobs on one node never collide.
export OLLAMA_HOST="127.0.0.1:$((20000 + SLURM_JOB_ID % 10000))"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-24h}"

ollama serve > "$SCR/serve_${SLURM_JOB_ID}.log" 2>&1 &
export OLLAMA_PID=$!
for i in $(seq 1 60); do
    curl -s "http://$OLLAMA_HOST/" >/dev/null 2>&1 && break
    sleep 1
done
echo "[ollama_env] serve pid=$OLLAMA_PID host=$OLLAMA_HOST"

if ! ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$MODEL"; then
    echo "[ollama_env] pulling $MODEL (compute nodes have internet)"
    ollama pull "$MODEL"
fi
ollama list

ollama_sync_back() {
    echo "[ollama_env] syncing models back to $PERSIST/models"
    rsync -a "$SCR/models/" "$PERSIST/models/"
    kill "$OLLAMA_PID" 2>/dev/null
}
export -f ollama_sync_back
