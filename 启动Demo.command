#!/bin/zsh
set -e

PROJECT_DIR="${0:A:h}"
LOCAL_URL="http://127.0.0.1:8765"

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
  echo "未找到 Conda。请先运行 scripts/create_env.sh 或设置 CONDA_BIN。"
  read -k 1 "?按任意键关闭…"
  exit 1
fi

cd "$PROJECT_DIR"

if curl -fsS "$LOCAL_URL/health" >/dev/null 2>&1; then
  open "$LOCAL_URL"
  exit 0
fi

"$CONDA_BIN" run --no-capture-output -n agent-radar uvicorn app.main:app --host 127.0.0.1 --port 8765 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM

for attempt in {1..20}; do
  if curl -fsS "$LOCAL_URL/health" >/dev/null 2>&1; then
    open "$LOCAL_URL"
    wait "$SERVER_PID"
    exit 0
  fi
  sleep 0.25
done

echo "Demo 启动失败，请保留这个窗口并把错误信息发给 Codex。"
wait "$SERVER_PID"
