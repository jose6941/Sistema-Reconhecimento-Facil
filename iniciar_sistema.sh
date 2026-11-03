#!/usr/bin/env bash
# ==============================================================================
# Inicialização unificada (Linux / macOS) - Sistema de Reconhecimento Facial
# Equivalente ao iniciar_sistema.bat. Uso:  ./iniciar_sistema.sh
#
# O que faz:
#   1. Cria .env (backend e frontend) a partir dos .env.example, se faltarem
#   2. Cria o ambiente virtual Python (venv/) e instala o requirements.txt
#   3. Instala as dependências do frontend (npm install)
#   4. Sobe o backend Flask e o painel Next.js; Ctrl+C encerra os dois
# ==============================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

erro() { echo "[ERRO] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }

# --- Pré-requisitos ---------------------------------------------------------
command -v python3 >/dev/null 2>&1 || erro "python3 não encontrado (necessário Python 3.10+)."
command -v node    >/dev/null 2>&1 || erro "node não encontrado (necessário Node.js 20+)."
command -v npm     >/dev/null 2>&1 || erro "npm não encontrado."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || erro "Python 3.10 ou superior é necessário (encontrado: $(python3 --version 2>&1))."
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' \
  || erro "Node.js 20 ou superior é necessário (encontrado: $(node --version 2>&1))."

# --- Arquivos .env ----------------------------------------------------------
for pasta in "." "frontend"; do
  if [ ! -f "$pasta/.env" ]; then
    cp "$pasta/.env.example" "$pasta/.env"
    info "Criado $pasta/.env a partir do .env.example (revise os valores se necessário)."
  fi
done

# Carrega o .env do backend (também fornece FRONTEND_PORT e FLASK_PORT ao script)
set -a
# shellcheck disable=SC1091
. ./.env
set +a
FLASK_PORT="${FLASK_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# --- Backend: venv + dependências ------------------------------------------
if [ ! -d venv ]; then
  info "Criando ambiente virtual Python em ./venv ..."
  python3 -m venv venv
fi
PY="$RAIZ/venv/bin/python"
MARCADOR="venv/.requirements_instalado"
if [ ! -f "$MARCADOR" ] || [ requirements.txt -nt "$MARCADOR" ]; then
  info "Instalando dependências Python (pode demorar na primeira vez) ..."
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
  touch "$MARCADOR"
fi

# --- Frontend: dependências -------------------------------------------------
if [ ! -d frontend/node_modules ]; then
  info "Instalando dependências do frontend (npm install) ..."
  (cd frontend && npm install)
fi

# --- Encerramento limpo -----------------------------------------------------
PIDS=()

matar_arvore() {
  local pid="$1" filho
  for filho in $(pgrep -P "$pid" 2>/dev/null || true); do
    matar_arvore "$filho"
  done
  kill "$pid" 2>/dev/null || true
}

encerrar() {
  local codigo=$?
  trap - INT TERM EXIT
  echo
  info "Encerrando serviços ..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && matar_arvore "$pid"
  done
  wait 2>/dev/null || true
  exit "$codigo"
}
trap encerrar INT TERM EXIT

# --- Inicialização ----------------------------------------------------------
info "[1/2] Iniciando backend Flask na porta $FLASK_PORT ..."
PYTHONUNBUFFERED=1 "$PY" servidor_reconhecimento.py &
PIDS+=("$!")

info "[2/2] Iniciando painel Next.js na porta $FRONTEND_PORT ..."
(cd frontend && PORT="$FRONTEND_PORT" exec npm run dev) &
PIDS+=("$!")

echo
echo "===================================================================="
echo " Sistema inicializado. Pressione Ctrl+C para encerrar."
echo " - Backend API:  http://localhost:$FLASK_PORT"
echo " - Painel Web:   http://localhost:$FRONTEND_PORT"
echo " - Documentação: http://localhost:$FRONTEND_PORT/documentacao"
echo "===================================================================="

# Se qualquer um dos serviços cair, derruba o outro e informa
wait -n 2>/dev/null || wait
erro "Um dos serviços foi encerrado inesperadamente."
