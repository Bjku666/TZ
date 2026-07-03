#!/bin/zsh

set -e

PROJECT_DIR="/Users/lulu/Desktop/touzi"
BACKEND_URL="http://127.0.0.1:8000"
BACKEND_PORT="8000"
FRONTEND_URL="http://127.0.0.1:5173"
BACKEND_REQUIRED_CONTRACT="trade-link-v5"
BACKEND_REQUIRED_ROUTES=(
  "/api/watchlist/scan-turnover-changes"
  "/api/watchlist/include-turnover-stock"
)

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/.tmp"

echo "强势回踩系统：本地 Python 后端 + React 前端"
echo "项目目录：$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "首次启动：正在创建 Python 本地运行环境..."
  /usr/bin/python3 -m venv .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn, pandas, plotly, openpyxl" >/dev/null 2>&1; then
  echo "正在安装或更新 Python 依赖..."
  .venv/bin/python -m pip install -r requirements.txt
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm。请先安装 Node.js，再重新运行本脚本。"
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "首次启动：正在安装前端依赖..."
  npm --prefix frontend install
fi

wait_for_url() {
  local url="$1"
  local name="$2"
  local tries=40
  local i=1
  while [[ $i -le $tries ]]; do
    if /usr/bin/curl --silent --fail "$url" >/dev/null 2>&1; then
      echo "$name 已就绪：$url"
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  echo "$name 启动超时，请查看 .tmp 日志。"
  return 1
}

backend_has_required_routes() {
  local schema_file="$PROJECT_DIR/.tmp/backend-openapi.json"
  local route
  if ! /usr/bin/curl --silent --fail "$BACKEND_URL/openapi.json" > "$schema_file" 2>/dev/null; then
    return 1
  fi
  for route in "${BACKEND_REQUIRED_ROUTES[@]}"; do
    if ! /usr/bin/grep -q "$route" "$schema_file"; then
      return 1
    fi
  done
  return 0
}

backend_has_required_contract() {
  local health_file="$PROJECT_DIR/.tmp/backend-health.json"
  if ! /usr/bin/curl --silent --fail "$BACKEND_URL/api/health" > "$health_file" 2>/dev/null; then
    return 1
  fi
  /usr/bin/grep -q "\"contract\"[[:space:]]*:[[:space:]]*\"${BACKEND_REQUIRED_CONTRACT}\"" "$health_file"
}

stop_project_backend() {
  local pids pid command_line
  pids=("${(@f)$(/usr/sbin/lsof -tiTCP:${BACKEND_PORT} -sTCP:LISTEN 2>/dev/null || true)}")
  if [[ ${#pids[@]} -eq 0 ]]; then
    return 0
  fi

  for pid in "${pids[@]}"; do
    command_line="$(/bin/ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" == *"uvicorn backend.main:app"* || "$command_line" == *"backend.main:app"* ]]; then
      echo "正在停止旧 Python 后端进程：$pid"
      /bin/kill "$pid" 2>/dev/null || true
    else
      echo "警告：端口 ${BACKEND_PORT} 被非本项目进程占用：$command_line"
    fi
  done
  sleep 1
}

start_backend() {
  echo "正在启动 Python FastAPI 后端..."
  PYTHONPATH="$PROJECT_DIR" nohup .venv/bin/uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    > "$PROJECT_DIR/.tmp/backend.log" 2>&1 &
}

if /usr/bin/curl --silent --fail "$BACKEND_URL/api/health" >/dev/null 2>&1; then
  if backend_has_required_contract && backend_has_required_routes; then
    echo "Python 后端已在运行且接口完整：$BACKEND_URL"
  else
    echo "Python 后端已在运行，但版本或接口不是最新，正在重启..."
    stop_project_backend
    start_backend
  fi
else
  start_backend
fi

wait_for_url "$BACKEND_URL/api/health" "Python 后端"

if /usr/bin/curl --silent --fail "$FRONTEND_URL" >/dev/null 2>&1; then
  echo "React 前端已在运行：$FRONTEND_URL"
else
  echo "正在启动 React/Vite 前端..."
  nohup npm --prefix frontend run dev \
    > "$PROJECT_DIR/.tmp/frontend.log" 2>&1 &
fi

wait_for_url "$FRONTEND_URL" "React 前端"

echo ""
echo "系统已启动。"
echo "前端地址：$FRONTEND_URL"
echo "后端健康检查：$BACKEND_URL/api/health"
echo "后端日志：$PROJECT_DIR/.tmp/backend.log"
echo "前端日志：$PROJECT_DIR/.tmp/frontend.log"
echo ""
echo "旧 Streamlit 入口仍保留在 app.py；如需旧版，可手动运行："
echo ".venv/bin/streamlit run app.py --server.port 8501"

/usr/bin/open "$FRONTEND_URL"

echo ""
echo "可以关闭此窗口，后端和前端会在后台继续运行。"
echo "如需停止，可在终端执行：pkill -f 'uvicorn backend.main:app'；pkill -f 'vite --host 127.0.0.1 --port 5173'"
