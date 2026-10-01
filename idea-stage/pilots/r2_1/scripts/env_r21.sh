# Pilot R2-1 runtime (a script, not a new environment): the cluster's module CPython 3.12.1 running the existing
# shared vldb27 site-packages.
module load cuda/13.1.0 >/dev/null 2>&1 || true
module load python/3.12.1 >/dev/null 2>&1
export VLDB27=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
export PYTHONPATH=$VLDB27/venv/lib/python3.12/site-packages
python() { python3 "$@"; }
export -f python
export HF_HOME=$VLDB27/hf
export HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-0}
export VLLM_USE_FLASHINFER_SAMPLER=0
export TOKENIZERS_PARALLELISM=false
export PYTHONHASHSEED=0  # stable Python hashing (OBSERVE v3 client-side key)
