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

# ── 2. Configuration OLLAMA_HOST (accès depuis Docker) ───────────────────────
# Par défaut Ollama écoute sur 127.0.0.1 → inaccessible depuis les conteneurs Docker.
# On force 0.0.0.0 pour que host.docker.internal fonctionne.
echo "[2/4] Configuration OLLAMA_HOST=0.0.0.0..."
if snap list ollama &>/dev/null 2>&1; then
  # Installation snap : configurer via snap set
  sudo snap set ollama host=0.0.0.0
  echo "  Snap Ollama : OLLAMA_HOST=0.0.0.0 configuré."
else
  # Installation classique : variable d'environnement (persiste dans la session)
  export OLLAMA_HOST=0.0.0.0
  echo "  OLLAMA_HOST=0.0.0.0 (session courante)."
  echo "  Pour le rendre permanent, ajoutez dans ~/.bashrc ou ~/.zshrc :"
  echo '    export OLLAMA_HOST=0.0.0.0'
fi

# ── 3. Démarrage du service Ollama ────────────────────────────────────────────
echo "[3/4] Vérification que le service Ollama est actif..."
if ! curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
  echo "  Démarrage d'Ollama en arrière-plan..."
  if snap list ollama &>/dev/null 2>&1; then
    sudo snap restart ollama
  else
    OLLAMA_HOST=0.0.0.0 ollama serve &
  fi
  sleep 5
  for i in {1..12}; do
    if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
      echo "  Ollama prêt."
      break
    fi
    echo "  Attente Ollama... ($i/12)"
    sleep 5
  done
else
  # Ollama tourne déjà — vérifier qu'il écoute sur 0.0.0.0
  if ss -tlnp sport = :11434 2>/dev/null | grep -q "127.0.0.1"; then
    echo "  Ollama tourne sur 127.0.0.1 seulement — redémarrage nécessaire."
    if snap list ollama &>/dev/null 2>&1; then
      sudo snap restart ollama && sleep 3
    else
      pkill -f "ollama serve" 2>/dev/null || true
      OLLAMA_HOST=0.0.0.0 ollama serve &
      sleep 5
    fi
  fi
fi

# ── 3. Téléchargement du modèle LLM ──────────────────────────────────────────
echo "[4/4] Pull du modèle LLM : ${LLM_MODEL}"
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
