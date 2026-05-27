#!/usr/bin/env bash
# setup_ollama_wsl.sh — Configure Ollama pour WSL2 (Windows Subsystem for Linux)
#
# Deux stratégies selon votre situation :
#   Mode A (défaut) : Ollama tourne sur WINDOWS, WSL l'atteint via la gateway.
#                     → Recommandé si Ollama est déjà installé sur Windows.
#   Mode B          : Ollama s'installe directement dans WSL2.
#                     → Nécessite CUDA for WSL2 pour le GPU.
#
# Usage :
#   bash scripts/setup_ollama_wsl.sh           # Mode A (Windows Ollama)
#   bash scripts/setup_ollama_wsl.sh --wsl     # Mode B (Ollama dans WSL)
set -euo pipefail

LLM_MODEL="${LLM_MODEL:-qwen2.5:7b}"
MODE="windows"
[[ "${1:-}" == "--wsl" ]] && MODE="wsl"

echo "=== Setup Ollama WSL2 — Traiteur Dupont Étape 02 ==="
echo "Mode : ${MODE}"

# ── Vérification WSL ──────────────────────────────────────────────────────────
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo "ATTENTION : ce script est conçu pour WSL2. Exécutez-le depuis un terminal WSL."
  echo "Pour Linux natif, utilisez : bash scripts/setup_ollama_local.sh"
  exit 1
fi

# ── MODE A : Ollama sur Windows ───────────────────────────────────────────────
if [[ "$MODE" == "windows" ]]; then
  echo ""
  echo "[Mode A] Utilisation d'Ollama installé sur Windows."
  echo "  → Ollama doit être lancé sur Windows (ollama serve ou l'appli Ollama)."
  echo ""

  # Détecter l'IP de la gateway Windows (= hôte Windows vu depuis WSL2)
  WINDOWS_IP=$(ip route show default 2>/dev/null | awk '/default/ {print $3}' | head -1)
  if [[ -z "$WINDOWS_IP" ]]; then
    echo "Impossible de détecter l'IP Windows. Valeur par défaut : host.docker.internal"
    WINDOWS_IP="host.docker.internal"
  fi

  OLLAMA_URL="http://${WINDOWS_IP}:11434"
  echo "[1/3] IP Windows détectée : ${WINDOWS_IP}"
  echo "      URL Ollama : ${OLLAMA_URL}"

  # Vérifier qu'Ollama répond sur Windows
  echo "[2/3] Test de connexion à Ollama Windows..."
  if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    echo ""
    echo "  ERREUR : Ollama ne répond pas sur ${OLLAMA_URL}"
    echo "  → Vérifiez qu'Ollama est bien lancé sur Windows."
    echo "  → Si Ollama écoute sur 127.0.0.1 seulement, ajoutez dans Windows :"
    echo "      Variable d'environnement : OLLAMA_HOST=0.0.0.0"
    echo "      Puis redémarrez Ollama."
    exit 1
  fi
  echo "  Ollama Windows accessible."

  # Pull du modèle via Ollama Windows
  echo "[3/3] Pull du modèle '${LLM_MODEL}' sur Ollama Windows..."
  curl -s "${OLLAMA_URL}/api/pull" -d "{\"name\": \"${LLM_MODEL}\"}" | grep -E '"status"' | tail -1

  echo ""
  echo "=== Configuration .env recommandée ==="
  echo "LLM_PROVIDER=local_ollama"
  echo "LLM_MODEL=${LLM_MODEL}"
  echo "OLLAMA_BASE_URL=http://${WINDOWS_IP}:11434"
  echo ""
  echo "Dans docker-compose.yml, extra_hosts est déjà configuré pour host.docker.internal."
  echo "Si l'IP change, relancez ce script pour obtenir la nouvelle IP."

# ── MODE B : Ollama dans WSL2 ─────────────────────────────────────────────────
else
  echo ""
  echo "[Mode B] Installation d'Ollama directement dans WSL2."
  OLLAMA_URL="http://localhost:11434"

  # Installation
  if ! command -v ollama &>/dev/null; then
    echo "[1/3] Installation d'Ollama dans WSL2..."
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "[1/3] Ollama déjà installé : $(ollama --version)"
  fi

  # Démarrage
  echo "[2/3] Démarrage d'Ollama..."
  if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    ollama serve > /tmp/ollama.log 2>&1 &
    echo "  Attente du démarrage..."
    for i in {1..12}; do
      sleep 5
      if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        echo "  Ollama prêt."
        break
      fi
      echo "  ($i/12)..."
    done
  fi

  # Pull modèle
  echo "[3/3] Pull du modèle '${LLM_MODEL}'..."
  ollama pull "${LLM_MODEL}"

  echo ""
  echo "=== Configuration .env recommandée ==="
  echo "LLM_PROVIDER=local_ollama"
  echo "LLM_MODEL=${LLM_MODEL}"
  echo "OLLAMA_BASE_URL=http://host.docker.internal:11434"
  echo ""
  echo "NOTE GPU : pour utiliser le GPU depuis WSL2, CUDA for WSL2 doit être installé."
  echo "  → https://developer.nvidia.com/cuda/wsl"
fi

echo ""
echo "=== Setup terminé. Lancez ensuite : docker compose up ==="
