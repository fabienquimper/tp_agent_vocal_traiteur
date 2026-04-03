"""
OpenTelemetry — Configuration des traces distribuées
─────────────────────────────────────────────────────
Étape 10 : Observabilité avancée

POURQUOI LES TRACES ?
─────────────────────
Métriques (étape 02) = Vue agrégée
  → "La latence P95 est à 2s depuis 10 min"
  → NE DIT PAS : quel service est lent ? quelle requête précise ?

Logs = Vue fragmentée
  → "STT: 1.2s", "RAG: 0.3s", "LLM: 1.8s" — dans des fichiers séparés
  → Difficile de relier les logs d'une même requête entre services

Traces = Vue bout-en-bout d'UNE requête
  → request_id=abc123 → stt(1.2s) → rag(0.3s) → llm(1.8s) → tts(0.4s)
  → On voit exactement où le temps est passé, dans quel service

ARCHITECTURE OPENTELEMETRY
──────────────────────────

  Agent FastAPI                    Jaeger (backend)
  ┌──────────────────────┐         ┌─────────────────┐
  │  Tracer Provider     │         │  OTLP Collector │
  │  ┌──────────────┐    │  OTLP   │  ┌───────────┐  │
  │  │BatchSpan     │────┼────────▶│  │  Storage  │  │
  │  │Processor     │    │  gRPC   │  │  (memory) │  │
  │  └──────────────┘    │  :4317  │  └───────────┘  │
  │                      │         │  ┌───────────┐  │
  │  Auto-instrumentation:│         │  │  Query UI │  │
  │  - FastAPI routes    │         │  │  :16686   │  │
  │  - httpx (STT,TTS,  │         │  └───────────┘  │
  │    Ollama)           │         └─────────────────┘
  └──────────────────────┘

PROPAGATION DE CONTEXTE (W3C TraceContext)
──────────────────────────────────────────
  Agent fait un httpx.post("http://stt:8001/transcribe")
      → HTTPXClientInstrumentor() ajoute automatiquement :
        Header: traceparent: 00-{trace_id}-{span_id}-01
      → Si STT était aussi instrumenté OTel, il créerait un child span
        avec le même trace_id → trace bout-en-bout multi-service

FALLBACK GRACIEUX
─────────────────
  Si Jaeger est indisponible :
    - Le BatchSpanProcessor log une erreur de connexion
    - L'agent CONTINUE à fonctionner normalement
    - Les spans sont perdus (pas de crash, pas de retry bloquant)
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

# Exporter OTLP configuré (non None) → Jaeger actif
_initialized = False


def setup_telemetry(app=None) -> None:
    """
    Configure le TracerProvider global + auto-instrumentation.

    À appeler UNE seule fois, pendant le lifespan de l'app FastAPI.
    Après cet appel, `trace.get_tracer(__name__)` retourne un tracer actif.

    Variables d'environnement :
      OTEL_EXPORTER_OTLP_ENDPOINT  → URL du collecteur OTLP (défaut: http://jaeger:4317)
      OTEL_SERVICE_NAME            → nom du service dans Jaeger (défaut: traiteur-agent)
      OTEL_TRACES_ENABLED          → "false" pour désactiver (utile en tests unitaires)
    """
    global _initialized

    if _initialized:
        return

    # Respecter le flag de désactivation (pratique pour tests unitaires)
    if os.getenv("OTEL_TRACES_ENABLED", "true").lower() == "false":
        logger.info("[otel] Traces désactivées (OTEL_TRACES_ENABLED=false)")
        _initialized = True
        return

    # ── Ressource : métadonnées du service ──────────────────────────────────
    # Ces attributs apparaissent dans CHAQUE span → identifient la source
    resource = Resource.create({
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "traiteur-agent"),
        SERVICE_VERSION: "2.0.0",
        "deployment.environment": os.getenv("APP_ENV", "production"),
        "service.instance.id": os.getenv("HOSTNAME", "local"),
    })

    # ── TracerProvider ───────────────────────────────────────────────────────
    provider = TracerProvider(resource=resource)

    # ── Exporter OTLP → Jaeger ───────────────────────────────────────────────
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,   # pas de TLS en local (kind/docker-compose)
        )
        # BatchSpanProcessor : regroupe les spans et les envoie par batch
        # → non-bloquant, ne ralentit pas les requêtes HTTP
        provider.add_span_processor(
            BatchSpanProcessor(
                otlp_exporter,
                max_queue_size=512,
                max_export_batch_size=64,
                schedule_delay_millis=1000,   # exporte toutes les 1s
            )
        )
        logger.info(f"[otel] OTLP exporter configuré → {otlp_endpoint}")
    except Exception as exc:
        logger.warning(f"[otel] OTLP exporter non disponible ({exc}) → spans ignorés")
        # Fallback Console (utile pour le debug local sans Jaeger)
        if os.getenv("OTEL_CONSOLE_FALLBACK", "false").lower() == "true":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("[otel] Fallback : spans affichés dans la console")

    # ── Enregistrement du provider global ────────────────────────────────────
    trace.set_tracer_provider(provider)
    _initialized = True

    # ── Auto-instrumentation FastAPI ─────────────────────────────────────────
    # Crée automatiquement un span pour chaque requête HTTP entrante :
    #   GET /health, POST /api/text, etc.
    # Attributs ajoutés : http.method, http.url, http.status_code, http.route
    if app is not None:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/metrics",   # pas de spans pour les probes K8s
        )
        logger.info("[otel] FastAPI auto-instrumentation activée")

    # ── Auto-instrumentation httpx ────────────────────────────────────────────
    # Crée automatiquement un span pour chaque appel httpx sortant :
    #   httpx.post("http://stt:8001/transcribe") → span "HTTP POST"
    #   httpx.post("http://ollama:11434/api/chat") → span "HTTP POST"
    # + propagation du W3C traceparent header → trace bout-en-bout multi-service
    HTTPXClientInstrumentor().instrument()
    logger.info("[otel] httpx auto-instrumentation activée (STT, TTS, Ollama)")

    logger.info(
        f"[otel] Télémétrie prête. Service: {resource.attributes.get(SERVICE_NAME)} "
        f"| Env: {resource.attributes.get('deployment.environment')}"
    )


def get_tracer(name: str = "traiteur-agent"):
    """Retourne le tracer actif (raccourci)."""
    return trace.get_tracer(name)
