"""
Logging RGPD-compliant — Traiteur Dupont Étape 02

Règles :
- Logger les ÉVÉNEMENTS structurels (requête reçue, modèle appelé, latence, code retour).
- Ne JAMAIS logger le contenu des conversations, noms, téléphones, ou numéros de carte.
- Les transcriptions STT ne sont loggées qu'en mode DEBUG_LOCAL=true (désactivé par défaut).
- Un filtre regex scrub les patterns sensibles résiduels par sécurité.

Catégories de données masquées (RGPD art. 9 pour les catégories spéciales) :
  [CC]      → numéros de carte bancaire
  [PHONE]   → numéros de téléphone français
  [EMAIL]   → adresses e-mail
  [HEALTH]  → données de santé et régimes alimentaires religieux
              (allergi*, intoléran*, halal, casher, diabèt*, coeliaqu*, etc.)
"""

import logging
import os
import re
import sys

import structlog

_DEBUG_LOCAL = os.getenv("DEBUG_LOCAL", "false").lower() == "true"

# ── Catégorie 1 : données d'identification ────────────────────────────────────
_PATTERNS_PII = [
    (re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'), "[CC]"),
    (re.compile(r'(?:\+33\s?|0)[1-9](?:[\s.\-]?\d{2}){4}'), "[PHONE]"),
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'), "[EMAIL]"),
]

# ── Catégorie 2 : données sensibles RGPD art. 9 ───────────────────────────────
# Santé (allergi*, intoléran*, pathologies courantes) + convictions religieuses
# (régimes halal/casher) → catégories spéciales interdites de traitement sans
# consentement explicite. On masque leur apparition éventuelle dans les logs.
_PATTERNS_SPECIAL = [
    (re.compile(
        r'\b(allergi\w*|intoléran\w*|intoleran\w*|coeliaqu\w*|celiaqu\w*'
        r'|diab[eèé]t\w*|asthmat\w*|cardiaque\w*'
        r'|halal|haram|casher|kosher|cacher'
        r'|v[eé]g[eé]tali\w*)\b',
        re.IGNORECASE,
    ), "[HEALTH]"),
]


def _scrub(value: str) -> str:
    for pattern, label in _PATTERNS_PII + _PATTERNS_SPECIAL:
        value = pattern.sub(label, value)
    return value


class _ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _scrub(str(record.msg))
        if record.args:
            # Ne convertir en str que les arguments textuels — les entiers/floats
            # (ex: code HTTP 200 formaté avec %d par httpx) doivent rester numériques.
            record.args = tuple(
                _scrub(a) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def setup_logging() -> None:
    log_level = logging.DEBUG if _DEBUG_LOCAL else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Appliquer le filtre scrub sur le logging stdlib aussi (pour les libs tierces)
    root = logging.getLogger()
    root.setLevel(log_level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(_ScrubFilter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.addFilter(_ScrubFilter())


def get_logger(name: str):
    return structlog.get_logger(name)


def log_stt_event(logger, provider: str, duration_ms: int, language: str) -> None:
    logger.info("stt_done", provider=provider, duration_ms=duration_ms, language=language)


def log_llm_event(logger, provider: str, model: str, duration_ms: int, intent: str) -> None:
    logger.info("llm_done", provider=provider, model=model, duration_ms=duration_ms, intent=intent)


def log_order_event(logger, order_id: str, item_count: int, is_complex: bool) -> None:
    logger.info("order_created", order_id=order_id, item_count=item_count, is_complex=is_complex)


def maybe_log_transcript(logger, transcript: str) -> None:
    if _DEBUG_LOCAL:
        logger.debug("stt_transcript_debug_only", transcript=transcript[:200])
