"""
Métriques Prometheus — Agent Vocal Traiteur
────────────────────────────────────────────
Ce module centralise TOUTES les métriques exposées par l'agent.

Pipeline instrumenté :
  Audio → [STT] → texte → [LLM classify] → intent
       → [RAG] → contexte → [LLM generate] → réponse → [TTS] → audio

Métriques business :
  sessions actives · commandes créées · paiements

Pourquoi Prometheus ?
  Prometheus est le standard de facto du monitoring en production.
  Il scrape (tire) les métriques depuis /metrics à intervalle régulier.
  Grafana interroge Prometheus pour afficher les dashboards.

Types de métriques utilisés ici :
  - Counter   : valeur qui ne fait qu'augmenter (nb de requêtes, erreurs)
  - Histogram : distribution statistique (latences P50/P95/P99)
  - Gauge     : valeur instantanée qui peut monter/descendre (sessions actives)
"""

from prometheus_client import Counter, Gauge, Histogram

# ── STT (Speech-to-Text / Whisper) ───────────────────────────────────────────
# Mesure les performances de la transcription vocale.
# Pourquoi important : le STT est souvent le premier goulot d'étranglement
# dans un pipeline vocal. On veut détecter si le modèle Whisper est trop lent.

stt_requests_total = Counter(
    "stt_requests_total",
    "Nombre total de requêtes STT (transcription audio→texte)",
    ["status"],  # "success" | "error"
)
stt_latency_seconds = Histogram(
    "stt_latency_seconds",
    "Temps de transcription Whisper en secondes",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

# ── LLM – Classification de l'intention ──────────────────────────────────────
# Mesure combien de temps le LLM met à comprendre l'intention du client.
# Pourquoi important : la classification est appelée à CHAQUE tour de
# conversation (même pour une simple question). Si elle est lente, tout l'est.

llm_classify_requests_total = Counter(
    "llm_classify_requests_total",
    "Nombre total de classifications d'intention par le LLM",
    ["intent"],  # "info" | "commande_simple" | "commande_complexe" | "autre"
)
llm_classify_latency_seconds = Histogram(
    "llm_classify_latency_seconds",
    "Temps de classification LLM (intent extraction) en secondes",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0],
)

# ── RAG (Retrieval-Augmented Generation) ─────────────────────────────────────
# Mesure les performances de la recherche sémantique dans ChromaDB.
# Pourquoi important : un RAG lent peut compenser les économies de tokens.
# Un hit rate faible indique que les documents ne sont pas bien indexés.

rag_requests_total = Counter(
    "rag_requests_total",
    "Nombre total de requêtes RAG dans ChromaDB",
    ["result"],  # "hit" (≥1 chunk) | "miss" (0 chunk)
)
rag_latency_seconds = Histogram(
    "rag_latency_seconds",
    "Temps de recherche ChromaDB (embedding + similarity search) en secondes",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)
rag_chunks_retrieved = Histogram(
    "rag_chunks_retrieved",
    "Nombre de chunks retournés par requête RAG",
    buckets=[0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
)

# ── LLM – Génération de la réponse ───────────────────────────────────────────
# C'est généralement l'étape la plus longue : le LLM doit produire
# plusieurs tokens pour formuler une réponse conversationnelle complète.

llm_generate_requests_total = Counter(
    "llm_generate_requests_total",
    "Nombre total de générations de réponse LLM",
    ["status"],  # "success" | "error"
)
llm_generate_latency_seconds = Histogram(
    "llm_generate_latency_seconds",
    "Temps de génération de la réponse textuelle par le LLM (secondes)",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0],
)

# ── TTS (Text-to-Speech / Piper) ─────────────────────────────────────────────
# Mesure la synthèse vocale. Piper est rapide sur CPU, mais la latence
# dépend de la longueur du texte à synthétiser.

tts_requests_total = Counter(
    "tts_requests_total",
    "Nombre total de requêtes TTS (synthèse texte→audio)",
    ["status"],  # "success" | "error" | "skipped"
)
tts_latency_seconds = Histogram(
    "tts_latency_seconds",
    "Temps de synthèse vocale Piper en secondes",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

# ── Conversation (bout-en-bout) ───────────────────────────────────────────────
# La métrique la plus importante du point de vue utilisateur :
# combien de temps s'écoule entre "l'utilisateur parle" et "l'agent répond" ?
# SLA cible : P95 < 10 secondes pour une conversation vocale fluide.

conversation_duration_seconds = Histogram(
    "conversation_duration_seconds",
    "Durée totale d'un tour de conversation (audio→réponse audio) en secondes",
    buckets=[1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0],
)
conversations_total = Counter(
    "conversations_total",
    "Nombre total de tours de conversation traités",
    ["channel", "status"],  # channel: "voice"|"text", status: "success"|"error"
)

# ── Sessions ──────────────────────────────────────────────────────────────────
# Gauge : peut monter (nouvelle commande) ou descendre (commande finalisée).
# Utile pour détecter des sessions bloquées ou des fuites mémoire.

sessions_active = Gauge(
    "sessions_active",
    "Nombre de sessions de commande actives en ce moment",
)

# ── Business ──────────────────────────────────────────────────────────────────
# Métriques métier : combien de commandes, comment sont-elles payées ?
# Ces métriques ont de la valeur au-delà de l'IT (direction, commercial).

orders_total = Counter(
    "orders_total",
    "Nombre de commandes finalisées",
    ["type"],  # "simple" | "complexe"
)
payments_total = Counter(
    "payments_total",
    "Nombre de tentatives de paiement",
    ["method", "status"],  # method: "CB"|"liquide", status: "accepted"|"refused"|"on_site"
)

# ── RAG Rebuild (Hot Reload — étape 04) ───────────────────────────────────────
# Ces métriques permettent de suivre les opérations de rebuild RAG dans Grafana.
# Elles répondent aux questions :
#   - "Y a-t-il un rebuild en cours ?" (rag_rebuild_in_progress)
#   - "Combien de temps dure un rebuild ?" (rag_rebuild_duration_seconds)
#   - "Combien de documents sont indexés maintenant ?" (rag_active_chunks)
#   - "Est-ce que les rebuilds réussissent ?" (rag_rebuild_total)

rag_rebuild_in_progress = Gauge(
    "rag_rebuild_in_progress",
    "1 si un rebuild shadow est en cours, 0 sinon",
)
rag_rebuild_total = Counter(
    "rag_rebuild_total",
    "Nombre total d'opérations de rebuild RAG",
    ["status"],  # "success" | "error" | "rollback"
)
rag_rebuild_duration_seconds = Histogram(
    "rag_rebuild_duration_seconds",
    "Durée du rebuild RAG (shadow indexing + atomic swap) en secondes",
    buckets=[5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0],
)
rag_active_chunks = Gauge(
    "rag_active_chunks",
    "Nombre de chunks dans la collection RAG active",
)
