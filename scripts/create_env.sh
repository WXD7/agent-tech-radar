#!/bin/zsh
set -e

PROJECT_DIR="${0:A:h:h}"

if [[ -n "${CONDA_BIN:-}" && -x "$CONDA_BIN" ]]; then
  :
elif command -v conda >/dev/null 2>&1; then
  CONDA_BIN="$(command -v conda)"
elif [[ -x "$HOME/anaconda3/bin/conda" ]]; then
  CONDA_BIN="$HOME/anaconda3/bin/conda"
elif [[ -x "$HOME/miniconda3/bin/conda" ]]; then
  CONDA_BIN="$HOME/miniconda3/bin/conda"
elif [[ -x "$HOME/miniforge3/bin/conda" ]]; then
  CONDA_BIN="$HOME/miniforge3/bin/conda"
else
  echo "未找到 Conda。请先安装 Anaconda、Miniconda 或 Miniforge，或设置 CONDA_BIN。"
  exit 1
fi

"$CONDA_BIN" create \
  -n agent-radar \
  -c conda-forge \
  --override-channels \
  python=3.12 \
  pip \
  -y

"$CONDA_BIN" run -n agent-radar python -m pip install -r "$PROJECT_DIR/requirements.lock.txt"

echo "agent-radar 环境已经准备好。"
