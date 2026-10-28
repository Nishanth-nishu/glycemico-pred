#!/bin/bash
# Regenerate the synthetic datasets used in README "Findings". Run from the repo root
# with the venv active; each dataset then goes through the suite with
#   DATA=data/<name>.csv OUT=outputs/<name> sbatch slurm/run_all.sh
set -euo pipefail
RUN="python experiments/run.py generate"
$RUN --grid ear5  --output data/synthetic_ear5.csv                                    # 5 LEDs, default (10x) glucose
$RUN --grid dense --output data/synthetic_dense.csv                                   # 1000-1700 nm, same physiology
$RUN --grid ear5  --output data/control_ear5.csv --glucose_gain 1e-4 --confound 0     # positive control
$RUN --grid dense --output data/physical_dense.csv --glucose_gain physical            # literature glucose strength
