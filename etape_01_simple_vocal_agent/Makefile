# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help build up down logs init-ollama reload-docs test clean dev up-hf build-hf up-groq build-groq build-groq-nocache

AGENT_URL = http://localhost:8000

# Détection GPU : nvidia-container-cli doit charger les libs avec succès
HAS_GPU := $(shell nvidia-container-cli info > /dev/null 2>&1 && echo "yes" || echo "no")
ifeq ($(HAS_GPU),yes)
  GPU_FLAGS = -f docker-compose.yml -f docker-compose.gpu.yml
  GPU_MSG   = GPU NVIDIA detecte
else
  GPU_FLAGS =
  GPU_MSG   = mode CPU
endif

COMPOSE    = docker compose $(GPU_FLAGS)
COMPOSE_HF = docker compose -f docker-compose.yml -f docker-compose.hf.yml

## help : Affiche cette aide
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## ─── Construction ────────────────────────────────────────────────────────────

## build : Construit toutes les images Docker
build:
	$(COMPOSE) build

## build-nocache : Reconstruit sans cache (utile après mise à jour des deps)
build-nocache:
	$(COMPOSE) build --no-cache

## ─── Cycle de vie ────────────────────────────────────────────────────────────

## up : Démarre tous les services
up:
	@echo "Mode :$(GPU_MSG)"
	$(COMPOSE) up -d
	@echo ""
	@echo "✓ Services démarrés"
	@echo "  UI       → http://localhost:3000"
	@echo "  Agent    → http://localhost:8000"
	@echo "  STT      → http://localhost:8001"
	@echo "  TTS      → http://localhost:8002"
	@echo "  Ollama   → http://localhost:11434"
	@echo ""
	@echo "Prochaine étape : make init-ollama"

## down : Arrête tous les services
down:
	$(COMPOSE) down

## restart : Redémarre tous les services
restart:
	$(COMPOSE) restart

## logs : Affiche les logs en temps réel
logs:
	$(COMPOSE) logs -f

## logs-agent : Logs de l'agent uniquement
logs-agent:
	$(COMPOSE) logs -f agent

## ─── Initialisation ──────────────────────────────────────────────────────────

## init-ollama : Télécharge le modèle LLM Mistral dans Ollama (skip si déjà présent)
init-ollama:
	@if docker exec traiteur_ollama ollama list 2>/dev/null | grep -q "mistral"; then \
		echo "✓ Modèle Mistral déjà présent, skip"; \
	else \
		echo "Téléchargement du modèle Mistral (peut prendre plusieurs minutes)..."; \
		docker exec traiteur_ollama ollama pull mistral; \
		echo "✓ Modèle Mistral prêt"; \
	fi

## init-all : Build + up + init-ollama (démarrage complet depuis zéro)
init-all: build up
	@echo "Attente du démarrage d'Ollama..."
	@sleep 15
	$(MAKE) init-ollama
	@echo ""
	@echo "✓ Installation complète – Ouvrez http://localhost:3000"

## ─── Documents & RAG ─────────────────────────────────────────────────────────

## reload-docs : Re-indexe les fichiers du dossier data/ dans ChromaDB
reload-docs:
	@curl -s -X POST $(AGENT_URL)/api/reload-documents | python3 -m json.tool

## ─── Tests ───────────────────────────────────────────────────────────────────

## test : Lance un test conversationnel rapide (smoke test)
test:
	@echo "=== Test : Question sur les horaires ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== Test : Commande simple (≤6 unités) ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Je voudrais commander 2 quiches lorraines et 1 tarte aux pommes", "skip_tts": true}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== Test : Commande complexe (>6 unités) ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Je voudrais 4 plateaux de charcuterie et 5 quiches lorraines", "skip_tts": true}' \
		| python3 -m json.tool

## test-health : Vérifie l'état de santé de tous les services
test-health:
	@echo "=== Santé des services ==="
	@echo -n "Ollama  : " && curl -sf http://localhost:11434/api/tags > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "STT     : " && curl -sf http://localhost:8001/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "TTS     : " && curl -sf http://localhost:8002/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Agent   : " && curl -sf http://localhost:8000/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "UI      : " && curl -sf http://localhost:3000 > /dev/null && echo "✓ OK" || echo "✗ KO"

## ─── Nettoyage ───────────────────────────────────────────────────────────────

## clean : Arrête les services et supprime les volumes (ATTENTION : supprime ChromaDB)
clean:
	$(COMPOSE) down -v
	@echo "✓ Conteneurs et volumes supprimés"

## clean-orders : Supprime les fichiers Excel de commandes
clean-orders:
	rm -f orders/*.xlsx
	@echo "✓ Fichiers de commandes supprimés"

## ─── Mode HuggingFace (APIs distantes) ──────────────────────────────────────

## build-hf : Construit les images pour le mode HuggingFace
build-hf:
	$(COMPOSE_HF) build stt tts agent ui

## up-hf : Démarre les services en mode HuggingFace (sans Ollama local)
## Usage : make up-hf HF_API_TOKEN=hf_xxxxxxxxxxxx  (ou via .env)
up-hf:
	$(eval _HF_TOKEN := $(or $(HF_API_TOKEN),$(HF_HUB_TOKEN),$(shell grep -E '^HF_(API_TOKEN|HUB_TOKEN)=' .env 2>/dev/null | head -1 | cut -d= -f2-)))
	@if [ -z "$(_HF_TOKEN)" ]; then \
		echo "ERREUR : token HuggingFace introuvable."; \
		echo "  Option 1 : make up-hf HF_API_TOKEN=hf_xxxxxxxxxxxx"; \
		echo "  Option 2 : ajouter HF_API_TOKEN=hf_xxx dans votre fichier .env"; \
		echo "Token gratuit : https://huggingface.co/settings/tokens"; \
		exit 1; \
	fi
	@echo "Mode HuggingFace (APIs distantes)"
	HF_API_TOKEN=$(_HF_TOKEN) HF_HUB_TOKEN=$(_HF_TOKEN) $(COMPOSE_HF) up -d stt tts agent ui
	@echo ""
	@echo "Services demarres (sans Ollama local) :"
	@echo "  UI    → http://localhost:3000"
	@echo "  Agent → http://localhost:8000"
	@echo "  STT   → http://localhost:8001  (whisper-large-v3 via HF)"
	@echo "  TTS   → http://localhost:8002  (facebook/mms-tts-fra via HF)"
	@echo ""
	@echo "Note : premier appel peut prendre ~30 s (chargement modele HF)"

## ─── Mode Groq (LLM + STT gratuits via API Groq) ────────────────────────────
COMPOSE_GROQ = docker compose -f docker-compose.yml -f docker-compose.groq.yml

## build-groq : Construit les images pour le mode Groq
build-groq:
	$(COMPOSE_GROQ) build stt agent

## build-groq-nocache : Reconstruit UNIQUEMENT l'agent sans cache (Groq mode)
## Utile après modification du code Python sans toucher aux deps ni au modèle Whisper
## Plus léger que build-nocache : ne re-télécharge pas Whisper (~1 GB), ne plante pas WSL
build-groq-nocache:
	$(COMPOSE_GROQ) build --no-cache agent

## up-groq : Démarre les services en mode Groq (sans Ollama local)
## Usage : make up-groq GROQ_API_KEY=gsk_xxxxxxxxxxxx  (ou via .env)
up-groq:
	$(eval _GROQ_KEY := $(or $(GROQ_API_KEY),$(shell grep -E '^GROQ_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2-)))
	@if [ -z "$(_GROQ_KEY)" ]; then \
		echo "ERREUR : token Groq introuvable."; \
		echo "  Option 1 : make up-groq GROQ_API_KEY=gsk_xxxxxxxxxxxx"; \
		echo "  Option 2 : ajouter GROQ_API_KEY=gsk_xxx dans votre fichier .env"; \
		echo "Token gratuit : https://console.groq.com/keys"; \
		exit 1; \
	fi
	@echo "Mode Groq (LLM llama-3.1-8b + STT whisper-large-v3-turbo)"
	GROQ_API_KEY=$(_GROQ_KEY) $(COMPOSE_GROQ) up -d stt tts agent ui
	@echo ""
	@echo "Services demarres (sans Ollama local) :"
	@echo "  UI    → http://localhost:3000"
	@echo "  Agent → http://localhost:8000"
	@echo "  STT   → http://localhost:8001  (whisper-large-v3-turbo via Groq)"
	@echo "  TTS   → http://localhost:8002  (piper local)"
	@echo ""
	@echo "Note : Groq est tres rapide (~1-3 s). Audio et texte passes par Groq."

## ─── Développement ───────────────────────────────────────────────────────────

## dev : Lance l'agent en mode développement avec hot-reload (hors Docker)
dev:
	@echo "Démarrage en mode développement..."
	@echo "Assurez-vous qu'Ollama, STT et TTS tournent dans Docker :"
	@echo "  $(COMPOSE) up -d ollama stt tts"
	cd services/agent && \
		OLLAMA_BASE_URL=http://localhost:11434 \
		STT_SERVICE_URL=http://localhost:8001 \
		TTS_SERVICE_URL=http://localhost:8002 \
		DATA_DIR=../../data \
		ORDERS_DIR=../../orders \
		CHROMA_DIR=./chroma_dev \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
