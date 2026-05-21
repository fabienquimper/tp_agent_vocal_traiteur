#!/usr/bin/env bash
# cleanup_ollama_local.sh — Supprime les modèles du projet d'Ollama.
# Usage : ./scripts/cleanup_ollama_local.sh [--remove-ollama]
set -euo pipefail

LLM_MODEL="${LLM_MODEL:-qwen2.5:7b}"
REMOVE_OLLAMA=false

for arg in "$@"; do
  [[ "$arg" == "--remove-ollama" ]] && REMOVE_OLLAMA=true
done

echo "=== Cleanup Ollama local — Traiteur Dupont Étape 02 ==="

if ! command -v ollama &>/dev/null; then
  echo "Ollama non installé — rien à nettoyer."
  exit 0
fi

echo "Suppression du modèle : ${LLM_MODEL}"
ollama rm "${LLM_MODEL}" 2>/dev/null && echo "  Supprimé." || echo "  Modèle introuvable (déjà supprimé ?)."

if $REMOVE_OLLAMA; then
  echo "Désinstallation d'Ollama..."
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo systemctl stop ollama 2>/dev/null || true
    sudo rm -f /usr/local/bin/ollama
    sudo rm -rf /usr/share/ollama
    echo "Ollama désinstallé."
  else
    echo "Désinstallation manuelle requise sur macOS/Windows."
  fi
fi

echo "=== Cleanup terminé ==="
