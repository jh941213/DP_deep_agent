#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
START_FRONTEND="${START_FRONTEND:-1}"
FRONTEND_PID=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

cat <<EOF
${BLUE}
  ██████╗ ██████╗  █████╗  ██████╗ ███████╗███╗   ███╗████████╗
  ██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ███║╚══██╔══╝
  ██║  ██║██████╔╝███████║██║  ███╗█████╗  ██╔██╗ ███║   ██║   
  ██║  ██║██╔═══╝ ██╔══██║██║   ██║██╔══╝  ██║╚██╗███║   ██║   
  ██████╔╝██║     ██║  ██║╚██████╔╝███████╗██║ ╚█████║   ██║   
  ╚═════╝ ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚════╝   ╚═╝   
${NC}
                   ${CYAN}${BOLD}DIRECT PURCHASE AGENT${NC}
                 ${BOLD}Code by @jh941213 | v1.0.0${NC}

EOF

echo ""
echo -e "${YELLOW}🧹 캐시 정리 시작...${NC}"

cleanup_targets=(
  "$ROOT_DIR/shopping_agent/.cache"
  "$ROOT_DIR/__pycache__"
  "$ROOT_DIR/frontend/.next"
  "$ROOT_DIR/frontend/node_modules/.cache"
)

for target in "${cleanup_targets[@]}"; do
  if [ -e "$target" ]; then
    rm -rf "$target"
    echo -e "  ${RED}- 삭제됨:${NC} $target"
  else
    echo -e "  ${GREEN}- 없음:${NC}   $target"
  fi
done

echo ""
echo -e "${GREEN}✅ 캐시 정리 완료${NC}"
echo ""

if ! command -v uv >/dev/null 2>&1; then
  echo -e "${RED}❌ uv가 설치되어 있지 않습니다. 먼저 uv를 설치해주세요.${NC}"
  echo "   https://docs.astral.sh/uv/"
  exit 1
fi

cleanup() {
  if [ -n "$FRONTEND_PID" ]; then
    kill -15 "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  echo -e "\n${YELLOW}👋 서버가 종료되었습니다.${NC}"
}

trap cleanup EXIT INT TERM

echo -e "${BLUE}🔌 포트 확인: $BACKEND_PORT${NC}"
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -nP -tiTCP:"$BACKEND_PORT" -sTCP:LISTEN || true)"
  if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}⚠️  포트 $BACKEND_PORT 사용 중인 프로세스 종료: $PIDS${NC}"
    kill -15 $PIDS || true
    sleep 1
  fi
fi

echo -e "${BOLD}🐍 uv 가상환경 준비...${NC}"
cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/uv.lock" ]; then
  uv sync > /dev/null 2>&1
else
  uv venv .venv
  uv pip install -e .
fi

echo ""
if [ "$START_FRONTEND" != "0" ] && [ -d "$ROOT_DIR/frontend" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  npm이 없어 프론트 서버를 시작할 수 없습니다.${NC}"
  else
    echo -e "${BLUE}🧩 프론트 포트 확인: $FRONTEND_PORT${NC}"
    if command -v lsof >/dev/null 2>&1; then
      FRONT_PIDS="$(lsof -nP -tiTCP:"$FRONTEND_PORT" -sTCP:LISTEN || true)"
      if [ -n "$FRONT_PIDS" ]; then
        echo -e "${YELLOW}⚠️  포트 $FRONTEND_PORT 사용 중인 프로세스 종료: $FRONT_PIDS${NC}"
        kill -15 $FRONT_PIDS || true
        sleep 1
      fi
    fi

    echo -e "${GREEN}🌐 프론트 서버 실행 (포트 $FRONTEND_PORT)${NC}"
    (cd "$ROOT_DIR/frontend" && NEXT_DISABLE_TURBOPACK=1 PORT="$FRONTEND_PORT" npm run dev -- -p "$FRONTEND_PORT") &
    FRONTEND_PID=$!
  fi
fi

echo ""
echo -e "${CYAN}🚀 에이전트 서버 실행 (포트 $BACKEND_PORT)${NC}"
echo -e "${BOLD}   (종료하려면 Ctrl+C)${NC}"
uv run uvicorn shopping_agent.api.app:app --host 0.0.0.0 --port "$BACKEND_PORT"
