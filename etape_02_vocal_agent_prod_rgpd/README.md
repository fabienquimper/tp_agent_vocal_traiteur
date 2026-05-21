# Étape 02 – Agent Vocal Traiteur (Production / RGPD)

Agent vocal pour la prise de commandes chez un traiteur.  
Architecture orientée **release applicative** : code + prompts + config modèles + menu versionnés.

---

## Démarrage rapide

```bash
git clone <repo>
cp etape_02_vocal_agent_prod_rgpd/.env.example etape_02_vocal_agent_prod_rgpd/.env
# Éditer .env avec votre GROQ_API_KEY
docker compose up
```

Ouvrir http://localhost:8000

**Mode 100 % local (Ollama) :**

```bash
./scripts/setup_ollama_local.sh   # installe Ollama + pull le modèle
# Éditer .env : LLM_PROVIDER=local_ollama, STT_PROVIDER=local_ollama
docker compose up
```

---

## Providers supportés

| Modèle | Providers |
|--------|-----------|
| STT    | `groq`, `local_ollama` (faster-whisper), `local_lms` |
| LLM    | `groq`, `mistral`, `local_ollama`, `local_lms` |

Configurer via `.env` :

```env
STT_PROVIDER=groq
LLM_PROVIDER=local_ollama
LLM_MODEL=qwen2.5:7b
```

---

## Tests

```bash
# Tests unitaires (< 30 s, sans réseau)
pytest -m "not slow"

# Tests de prompts (nécessite promptfoo installé)
promptfoo eval --config tests/promptfoo.yaml

# Tests de conversation complets (appels LLM réels)
pytest -m slow
```

---

## Structure

```
src/
├── app.py              # FastAPI, endpoints, machine à états commande
├── factory.py          # Instanciation des providers selon .env
├── basket.py           # Logique panier (fonctions pures)
├── excel_export.py     # Export commandes Excel
├── logging_config.py   # Logging structuré RGPD
├── orders_store.py     # Stockage JSON des commandes
├── providers/          # Implémentations STT et LLM
├── prompts/            # Prompts versionnés (YAML)
└── menu/               # Menu et catalogue prix (YAML)
docs/
├── AIPD.md             # Analyse d'Impact relative à la Protection des Données
├── ARCHITECTURE.md     # Schéma des composants
└── DECISIONS.md        # Choix architecturaux (ADR-style)
```

---

## Conformité RGPD / AI Act

- **AI Act art. 50** : l'agent annonce qu'il est une IA à chaque ouverture de session.
- **Logs** : aucune donnée personnelle loggée (filtre regex dans `logging_config.py`).
- **Mode 100 % local** : `STT_PROVIDER=local_ollama + LLM_PROVIDER=local_ollama` → aucune donnée ne quitte la machine.
- Voir `docs/AIPD.md` pour l'analyse complète.
