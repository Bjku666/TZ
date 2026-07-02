#!/bin/zsh

set -e

PROJECT_DIR="/Users/lulu/Desktop/touzi"
cd "$PROJECT_DIR"

if /usr/bin/curl --silent --fail http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
  /usr/bin/open http://localhost:8501
  echo "强势回踩系统已经在运行，已打开浏览器。"
  exit 0
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "首次启动：正在创建本地运行环境..."
  /usr/bin/python3 -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, pandas, plotly, openpyxl" >/dev/null 2>&1; then
  echo "首次启动：正在安装所需组件，请稍候..."
  .venv/bin/python -m pip install -r requirements.txt
fi

echo "正在启动强势回踩系统..."
echo "浏览器打开后即可使用。保持此窗口开启；按 Control+C 停止系统。"
export PYTHONPATH="$PROJECT_DIR"
exec .venv/bin/streamlit run app.py \
  --server.port 8501 \
  --server.headless false \
  --server.runOnSave false \
  --server.fileWatcherType none
