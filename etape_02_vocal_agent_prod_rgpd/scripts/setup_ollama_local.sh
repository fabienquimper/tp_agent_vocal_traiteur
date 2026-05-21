#!/usr/bin/env bash
# setup_ollama_local.sh — Installe Ollama sur l'hôte et télécharge les modèles du projet.
# À exécuter UNE FOIS avant docker compose up en mode local_ollama.
set -euo pipefail

LLM_MODEL="${LLM_MODEL:-qwen2.5:7b}"
OLLAMA_URL="http://localhost:11434"

echo "=== Setup Ollama local — Traiteur Dupont Étape 02 ==="

# ── 1. Installation d'Ollama si absent ────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  echo "[1/3] Ollama absent — installation..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  macOS : télécharger Ollama depuis https://ollama.com/download"
    echo "  Ou via Homebrew : brew install ollama"
    exit 1
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "  Windows : télécharger Ollama depuis https://ollama.com/download"
    exit 1
  fi
else
  echo "[1/3] Ollama déjà installé : $(ollama --version)"
fi

# ── 2. Démarrage du service Ollama ────────────────────────────────────────────
echo "[2/3] Vérification que le service Ollama est actif..."
if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
  echo "  Démarrage d'Ollama en arrière-plan..."
  ollama serve &
  sleep 5
  for i in {1..12}; do
    if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
      echo "  Ollama prêt."
      break
    fi
    echo "  Attente Ollama... ($i/12)"
    sleep 5
  done
fi

# ── 3. Téléchargement du modèle LLM ──────────────────────────────────────────
echo "[3/3] Pull du modèle LLM : ${LLM_MODEL}"
ollama pull "${LLM_MODEL}"

# ── Vérification finale ───────────────────────────────────────────────────────
echo ""
echo "=== Vérification ==="
echo "Modèles disponibles :"
ollama list

echo ""
echo "Test de génération rapide..."
if ollama run "${LLM_MODEL}" "Réponds uniquement : OK" --nowordwrap 2>&1 | grep -q "OK"; then
  echo "Modèle ${LLM_MODEL} : OK"
else
  echo "ATTENTION : le modèle n'a pas répondu 'OK'. Vérifiez qu'il est bien téléchargé."
fi

echo ""
echo "=== Setup terminé ==="
echo "Vous pouvez maintenant lancer : docker compose up"
echo "Configurez dans .env : LLM_PROVIDER=local_ollama et LLM_MODEL=${LLM_MODEL}"
