# Architecture — Agent Vocal Traiteur Dupont (Étape 02)

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│  Docker Compose (2 services)                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────┐              │
│  │  agent (port 8000)                           │              │
│  │                                              │              │
│  │   FastAPI                                    │              │
│  │   ├── /api/voice  (STT → LLM → TTS)         │              │
│  │   ├── /api/text   (LLM → TTS)               │              │
│  │   ├── /api/payment/simulate                  │              │
│  │   ├── /api/orders                            │              │
│  │   └── /static (UI)                           │              │
│  │                                              │              │
│  │   Providers (via factory.py)                 │              │
│  │   ├── STTProvider ──────► Groq API           │              │
│  │   │                  └──► faster-whisper     │              │
│  │   │                        (dans conteneur)  │              │
│  │   └── LLMProvider ──────► Groq API           │              │
│  │                       ├──► Mistral API        │              │
│  │                       └──► Ollama (hôte) ────┼──► :11434   │
│  │                                              │              │
│  │   Modules métier                             │              │
│  │   ├── basket.py (panier, calcul total)       │              │
│  │   ├── excel_export.py                        │              │
│  │   ├── orders_store.py                        │              │
│  │   └── logging_config.py (RGPD)              │              │
│  │                                              │              │
│  │   Données versionnées                        │              │
│  │   ├── src/menu/menu.yaml                     │              │
│  │   └── src/prompts/system_prompt.yaml         │              │
│  └──────────────────────────────────────────────┘              │
│                          │ HTTP :8002                           │
│  ┌───────────────────────▼──────────────────────┐              │
│  │  tts (port 8002)                             │              │
│  │  piper-tts — voix française hors-ligne       │              │
│  └──────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
         │ volume ./orders
         ▼
    commandes_simples.xlsx
    commandes_complexes.xlsx
    orders.json
```

## Flux de traitement d'une commande vocale

```
Utilisateur
    │ audio
    ▼
POST /api/voice
    │
    ├── STTProvider.transcribe(audio) → texte
    │
    ├── _llm_classify(texte) → {intent, order_items}
    │
    ├── [intent=commande] → créer session OrderSession
    │                     → _llm_respond() → texte confirmation
    │
    ├── Tours suivants (session active) :
    │     ├── awaiting_name  → _extract_contact_info()
    │     ├── awaiting_phone → extraction regex
    │     ├── awaiting_payment → détection CB/liquide
    │     └── awaiting_card → frontend formulaire
    │
    ├── _finalize_order() → write_order() + append_order()
    │
    └── _call_tts(texte) → audio WAV
```

## Choix des providers

| Besoin | Provider recommandé | Alternative locale |
|--------|--------------------|--------------------|
| STT rapide | `groq` (whisper-large-v3-turbo) | `local_ollama` (faster-whisper base) |
| LLM rapide | `groq` (llama-3.1-8b-instant) | `local_ollama` (qwen2.5:7b) |
| 100 % local | `local_ollama` STT + LLM | — |
| Souveraineté EU | `mistral` (La Plateforme, EU) | `local_ollama` |

## Séparation des responsabilités

| Module | Rôle | Dépendances |
|--------|------|-------------|
| `app.py` | Orchestration, sessions, endpoints | factory, basket, excel_export, orders_store |
| `factory.py` | Instanciation providers selon .env | providers/ |
| `providers/` | Implémentations STT/LLM | SDK providers |
| `basket.py` | Logique panier (fonctions pures) | aucune |
| `excel_export.py` | Export Excel | openpyxl |
| `orders_store.py` | Persistance JSON | stdlib |
| `logging_config.py` | Logging structuré RGPD | structlog |
| `menu/menu.yaml` | Menu et catalogue prix | — |
| `prompts/system_prompt.yaml` | Prompts versionnés | — |
