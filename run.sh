#!/usr/bin/env bash
#
# Opposition Scouting Dashboard — one-command local startup.
#
#   ./run.sh          start Postgres, the API and the dashboard
#   ./run.sh setup    first-time data build (download → ingest → derive → ML)
#   ./run.sh stop     stop everything this script started
#   ./run.sh status    show what is running and whether data is loaded
#
# Safe to re-run: it frees its own ports, reuses the running database, and
# skips install steps that are already done.

set -euo pipefail
cd "$(dirname "$0")"

API_PORT=${API_PORT:-8000}
WEB_PORT=${WEB_PORT:-5173}
LOG_DIR=".run-logs"
DB_CONTAINER="football-sequence-search-db-1"
VERIFY_MATCH_ID=3857254   # Argentina v Saudi Arabia — used by `pipeline verify`

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
info() { printf '  %s\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }
die()  { printf '\033[31m  x %s\033[0m\n' "$1" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed. $2"
}

check_prereqs() {
  require docker "Install Docker Desktop: https://docker.com/products/docker-desktop"
  require uv     "Install with: brew install uv"
  require node   "Install with: brew install node"
  docker info >/dev/null 2>&1 || die "Docker is installed but not running — start Docker Desktop."
}

# Kill whatever listens on a port. `uv run` and `npm run dev` both spawn
# grandchildren that survive their parent being signalled, so killing by PID
# alone leaves the port held — always sweep by port.
kill_port() {
  local port=$1 pids
  pids=$(lsof -ti ":$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -ti ":$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  fi
  return 0
}

# Pre-flight version: explains itself before taking someone else's port.
# The compose `app` service also publishes 8000 and silently shadows the local
# API with stale image code, so stop that container rather than kill its port.
free_port() {
  local port=$1
  if [ "$port" = "$API_PORT" ] &&
     docker compose ps --status running --services 2>/dev/null | grep -qx app; then
    warn "the compose 'app' container holds port $port — stopping it"
    docker compose stop app >/dev/null 2>&1 || true
  fi
  if [ -n "$(lsof -ti ":$port" 2>/dev/null || true)" ]; then
    warn "port $port was in use — freeing it"
  fi
  kill_port "$port"
}

start_db() {
  docker compose up -d db >/dev/null
  printf '  waiting for Postgres'
  local i
  for i in $(seq 1 60); do
    if docker exec "$DB_CONTAINER" pg_isready -U scout -d scouting >/dev/null 2>&1; then
      printf ' ready\n'; return 0
    fi
    printf '.'; sleep 1
  done
  printf '\n'; die "Postgres did not become ready in 60s. Check: docker compose logs db"
}

# Row counts that tell us how far through the data build we are.
count() {
  docker exec "$DB_CONTAINER" psql -U scout -d scouting -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

data_state() {
  local matches threat
  matches=$(count "SELECT count(*) FROM matches" || echo 0)
  threat=$(count "SELECT count(*) FROM zone_threat" || echo 0)
  if [ "${matches:-0}" = "0" ] || [ -z "${matches:-}" ]; then echo "empty"
  elif [ "${threat:-0}" = "0" ]; then echo "partial"
  else echo "ready"; fi
}

wait_for_http() {
  local url=$1 name=$2 i
  for i in $(seq 1 45); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  die "$name did not respond at $url — see $LOG_DIR/"
}

cmd_setup() {
  bold "Building the dataset (first run takes a while)"
  check_prereqs
  start_db
  info "syncing Python workspace"
  uv sync --all-packages
  info "downloading StatsBomb open data (~1.1 GB — several minutes)"
  uv run python -m pipeline download
  info "creating schema"
  uv run python -m pipeline init-db
  info "ingesting matches (115 matches, ~420k events)"
  uv run python -m pipeline ingest
  info "verifying ingest against the raw JSON"
  uv run python -m pipeline verify --match-id "$VERIFY_MATCH_ID"
  info "deriving metrics (sequences, pass networks, set pieces)"
  uv run python -m pipeline derive --skip-xt
  info "training the xT model"
  uv run python -m ml.train
  info "crediting actions with xT"
  uv run python -m ml.xt_apply
  info "clustering build-up patterns"
  uv run python -m ml.cluster
  bold "Data build complete — now run: ./run.sh"
}

cmd_up() {
  bold "Starting Opposition Scouting Dashboard"
  check_prereqs
  mkdir -p "$LOG_DIR"
  start_db

  case "$(data_state)" in
    empty)
      die "The database is empty. Build the dataset first:  ./run.sh setup" ;;
    partial)
      warn "Matches are loaded but derived metrics are missing."
      die  "Finish the build with:  ./run.sh setup" ;;
  esac
  info "database ready ($(count 'SELECT count(*) FROM matches') matches)"

  if [ ! -d .venv ]; then
    info "syncing Python workspace"
    uv sync --all-packages
  fi
  if [ ! -d frontend/node_modules ]; then
    info "installing frontend dependencies"
    (cd frontend && npm install)
  fi

  free_port "$API_PORT"
  free_port "$WEB_PORT"

  uv run uvicorn backend.main:app --port "$API_PORT" >"$LOG_DIR/api.log" 2>&1 &
  API_PID=$!
  (cd frontend && npm run dev -- --port "$WEB_PORT" >"../$LOG_DIR/web.log" 2>&1) &
  WEB_PID=$!

  cleanup() {
    trap '' INT TERM        # ignore repeat Ctrl-C while we shut down
    printf '\n'
    info "shutting down"
    kill "$API_PID" "$WEB_PID" 2>/dev/null || true
    kill_port "$API_PORT"   # sweeps the grandchildren the signal misses
    kill_port "$WEB_PORT"
    info "Postgres left running (stop it with: ./run.sh stop)"
    exit 0
  }
  trap cleanup INT TERM

  wait_for_http "http://localhost:$API_PORT/api/health" "API"
  wait_for_http "http://localhost:$WEB_PORT" "dashboard"

  printf '\n'
  bold "Ready"
  info "Dashboard  http://localhost:$WEB_PORT"
  info "API        http://localhost:$API_PORT/api/health"
  if curl -fsS "http://localhost:$API_PORT/api/health" | grep -q '"ask_enabled":true'; then
    info "Ask tab    enabled (ANTHROPIC_API_KEY found)"
  else
    info "Ask tab    off — optional, see .env.example to enable"
  fi
  info "Logs       $LOG_DIR/api.log, $LOG_DIR/web.log"
  printf '\n  Press Ctrl-C to stop.\n'
  wait
}

cmd_stop() {
  bold "Stopping"
  free_port "$API_PORT"
  free_port "$WEB_PORT"
  docker compose stop db >/dev/null 2>&1 || true
  info "stopped"
}

cmd_status() {
  bold "Status"
  if docker info >/dev/null 2>&1; then
    if docker exec "$DB_CONTAINER" pg_isready -U scout -d scouting >/dev/null 2>&1; then
      info "database   up — data $(data_state), $(count 'SELECT count(*) FROM matches') matches"
    else
      info "database   down"
    fi
  else
    info "docker     not running"
  fi
  curl -fsS -o /dev/null "http://localhost:$API_PORT/api/health" 2>/dev/null \
    && info "API        up on $API_PORT" || info "API        down"
  curl -fsS -o /dev/null "http://localhost:$WEB_PORT" 2>/dev/null \
    && info "dashboard  up on $WEB_PORT" || info "dashboard  down"
}

case "${1:-up}" in
  up)     cmd_up ;;
  setup)  cmd_setup ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  *) die "unknown command '${1}'. Use: up | setup | stop | status" ;;
esac
