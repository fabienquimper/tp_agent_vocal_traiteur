# Étape 10 — Observabilité avancée : Traces distribuées avec OpenTelemetry

> **Prérequis :** avoir complété l'étape 02 (métriques Prometheus).
>
> **Concepts clés :**
> - *"Les métriques disent QUOI, les traces disent POURQUOI."*
> - OpenTelemetry (OTel) : standard CNCF pour l'instrumentation (traces, métriques, logs)
> - Trace : voyage complet d'une requête à travers les services
> - Span : opération individuelle dans une trace (avec début, fin, attributs)
> - Propagation de contexte (W3C TraceContext) : `traceparent` header entre services
> - Jaeger : backend open-source pour stocker et visualiser les traces

---

## Problème posé

Avec les métriques Prometheus de l'étape 02, on sait :

```
conversation_duration_seconds{channel="text", status="success"} P95 = 3.2s
```

Mais impossible de répondre à :
- *Quelle opération prend 3.2s ? STT ? LLM ? RAG ?*
- *Cette requête précise — à 14h23:05 — a-t-elle eu une erreur ?*
- *La lenteur vient-elle de Ollama ou de ChromaDB ?*

Les métriques sont des **agrégats dans le temps** — elles perdent la dimension causale.

---

## Solution : Traces distribuées

```
Métriques (Prometheus) :         Traces (Jaeger) :
  conversation_duration P95=3s     request abc123 :
                                     POST /api/text           (3.2s)
  → "en moyenne c'est lent"          └── langgraph.invoke     (2.9s)
                                           └── HTTP POST ollama  (2.7s) ← GOULOT
                                           └── rag.similarity_search (0.05s)
```

Les traces montrent **UNE requête spécifique**, avec la **causalité** entre opérations.

---

## Ce qu'on ajoute dans cette étape

### Nouvelles dépendances (`services/agent/requirements.txt`)

```
opentelemetry-api==1.24.0
opentelemetry-sdk==1.24.0
opentelemetry-exporter-otlp-proto-grpc==1.24.0   → envoie les spans à Jaeger
opentelemetry-instrumentation-fastapi==0.45b0      → spans HTTP entrants (auto)
opentelemetry-instrumentation-httpx==0.45b0        → spans HTTP sortants (auto)
```

### Nouveau module (`services/agent/app/telemetry.py`)

Configure le TracerProvider global. Appelé une seule fois dans le lifespan FastAPI.

### Nouveau service (`docker-compose.yml`)

```yaml
jaeger:
  image: jaegertracing/all-in-one:1.57
  ports:
    - "16686:16686"   # UI Jaeger
    - "4317:4317"     # OTLP gRPC receiver
```

### Modifications code

| Fichier | Modification |
|---|---|
| `app/main.py` | `setup_telemetry(app)` dans lifespan + span `langgraph.invoke` |
| `app/rag/retriever.py` | Span `rag.similarity_search` avec attributs métier |

---

## Démarrage rapide

```bash
# Démarrer la stack (Jaeger inclus)
make up

# Ouvrir Jaeger UI
make traces-ui
# → http://localhost:16686

# Envoyer des requêtes test + guide d'exploration
make traces-demo
```

---

## Architecture de la télémétrie

```
┌─────────────────── Agent FastAPI ─────────────────────┐
│                                                        │
│  1. FastAPIInstrumentor (auto)                         │
│     → span "POST /api/text" à chaque requête HTTP      │
│                                                        │
│  2. HTTPXClientInstrumentor (auto)                     │
│     → span "HTTP POST http://ollama:11434/api/chat"    │
│     → span "HTTP POST http://stt:8001/transcribe"      │
│     → propagation W3C traceparent header               │
│                                                        │
│  3. Spans manuels                                      │
│     → langgraph.invoke (avec attribut llm.model)       │
│     → rag.similarity_search (avec rag.query, rag.hits) │
│     → session.handle_step (avec session.step)          │
│                                                        │
│  BatchSpanProcessor (non-bloquant, ~1s de délai)       │
│       ↓ OTLP gRPC                                      │
└───────┼────────────────────────────────────────────────┘
        │
        ▼ :4317
   ┌──────────┐    UI     ┌───────────────────┐
   │  Jaeger  │──────────▶│ http://localhost   │
   │ all-in-1 │  :16686   │      :16686        │
   └──────────┘           └───────────────────┘
```

---

## Les spans générés pour une requête vocale

```
POST /api/voice                         ← span auto (FastAPIInstrumentor)
  └── langgraph.invoke                  ← span manuel (main.py)
        ├── HTTP POST stt:8001/...      ← span auto (HTTPXClientInstrumentor)
        │     → transcription audio
        └── HTTP POST ollama:11434/...  ← span auto (HTTPXClientInstrumentor)
              → LLM classify + generate

  └── rag.similarity_search             ← span manuel (retriever.py)
        Attributs :
          rag.query    = "horaires samedi"
          rag.k        = 3
          rag.hits     = 3
          rag.collection = "traiteur_1705312800"
```

---

## Auto-instrumentation vs instrumentation manuelle

```python
# ── Auto-instrumentation : zéro code métier ──────────────────────────────
# FastAPIInstrumentor instrumente TOUTES les routes HTTP automatiquement
FastAPIInstrumentor.instrument_app(app)

# HTTPXClientInstrumentor instrumente TOUS les httpx.AsyncClient automatiquement
HTTPXClientInstrumentor().instrument()

# ── Instrumentation manuelle : attributs métier ──────────────────────────
# Quand on veut des attributs spécifiques au domaine (pas juste HTTP)
tracer = get_tracer()
with tracer.start_as_current_span("rag.similarity_search") as span:
    span.set_attribute("rag.query", query[:100])   # contexte métier
    span.set_attribute("rag.k", k)
    results = vectorstore.similarity_search_with_score(query, k=k)
    span.set_attribute("rag.hits", len(results))
    return results
```

**Règle** : auto-instrumentation pour l'infrastructure (HTTP, DB, etc.),
manuelle pour la logique métier (RAG, LLM, workflow).

---

## Propagation de contexte (W3C TraceContext)

```
Agent                          STT Service
  │                               │
  │  HTTPXClientInstrumentor      │
  │  ajoute le header :           │
  │  traceparent: 00-{trace_id}-{span_id}-01
  │──────────────────────────────▶│
  │                               │
  │  Si STT était aussi           │  Si STT était instrumenté OTel :
  │  instrumenté OTel...          │  → il lirait le traceparent
  │                               │  → créerait un child span
  │                               │  → même trace_id → trace unifiée
```

Dans ce TP, seul l'agent est instrumenté. Mais le `traceparent` est envoyé
— si on instrumente STT et TTS, leurs spans rejoindraient la même trace.

---

## Explorer dans Jaeger

```bash
# 1. Ouvrir l'UI
open http://localhost:16686

# 2. Service : traiteur-agent
# 3. Operation : POST /api/text  (ou /api/voice, ou rag.similarity_search)
# 4. Cliquer "Find Traces"
# 5. Cliquer sur une trace → Waterfall view

# Dans la waterfall view :
#   Chaque ligne = un span
#   Largeur = durée relative
#   Couleur rouge = erreur
#   Cliquer sur un span → voir ses attributs
```

**Questions pédagogiques à explorer :**
- Quelle opération prend le plus de temps dans `/api/text` ?
- Quelle est la latence typique de `rag.similarity_search` ?
- Est-ce que la latence LLM (httpx → Ollama) est stable ou variable ?
- Comparer P50 vs P99 (Jaeger → Compare → …)

---

## Corrélation Métriques ↔ Traces

Depuis Grafana (http://localhost:3001) :
```
Explore → datasource: Jaeger → service: traiteur-agent
→ Affiche les traces directement dans Grafana
→ On peut créer des panels corrélant métriques Prometheus + traces Jaeger
```

Depuis Prometheus (métriques) vers Jaeger (trace) :
```
On voit un pic de latence dans Grafana à 14h23
→ Aller dans Jaeger, filtrer les traces entre 14h22 et 14h24
→ Trouver la trace lente → voir quel span est responsable
```

---

## Désactiver le tracing (si besoin)

```bash
# Pour désactiver sans toucher au code :
echo "OTEL_TRACES_ENABLED=false" >> .env
make up  # ou docker-compose restart agent

# Pour réactiver :
# Supprimer la ligne OTEL_TRACES_ENABLED=false du .env
make up
```

Quand `OTEL_TRACES_ENABLED=false`, le TracerProvider est un **NoopTracer** :
les spans sont créés mais immédiatement ignorés (zéro overhead).

---

## Commandes utiles

```bash
# ── OpenTelemetry + Jaeger ────────────────────────────────────────────────────
make up           # démarre la stack + Jaeger
make traces-ui    # ouvre http://localhost:16686
make traces-demo  # requêtes test + guide d'exploration

# ── Stack complète ────────────────────────────────────────────────────────────
make up           # docker-compose (développement local)
make k8s-up       # kubernetes kind (avec jaeger.yaml inclus)

# ── Tests (hérite des étapes précédentes) ─────────────────────────────────────
make test-unit    # tests purs Python (< 30s)
make test-smoke   # health + métriques + RAG search
make test-rag     # quality gate RAG
```

---

## Ce que prépare cette étape

```
Étape 11 → Canary Release : déploiement progressif avec contrôle de risque
  Problème : rolling update (étape 07) déploie sur tous les pods en même temps.
             Si le nouveau code a un bug subtil, 100% des utilisateurs sont impactés.
  Solution : envoyer 10% du trafic vers la nouvelle version (canary),
             surveiller les métriques + traces, promouvoir ou rollback.
  Concepts : traffic splitting, Flagger, progressive delivery.
```
