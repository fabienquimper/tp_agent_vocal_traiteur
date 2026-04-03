"""
Point d'entrée FastAPI – Agent Vocal Traiteur
──────────────────────────────────────────────
Endpoints :
  POST /api/voice            → audio  → réponse JSON + audio base64
  POST /api/text             → texte  → réponse JSON (+ audio optionnel)
  POST /api/payment/simulate → simule un paiement CB
  GET  /api/orders           → liste des commandes (dashboard traiteur)
  GET  /health               → état de santé
  GET  /metrics              → métriques Prometheus

  — Hot RAG Reload (étape 04) ——————————————————————————
  POST /api/rag/rebuild      → démarre un rebuild shadow (non-bloquant, < 1ms)
  GET  /api/rag/status       → état du rebuild (idle/rebuilding/done/error)
  POST /api/rag/rollback     → revient à la collection précédente

  — Compatibilité étape 03 ——————————————————————————————
  POST /api/reload-documents → alias vers /api/rag/rebuild (non-bloquant maintenant)

Flux multi-tour pour les commandes :
  1. Classify (LangGraph) → intent = commande → session créée
  2. Session "awaiting_name"    → agent demande nom + prénom
  3. Session "awaiting_phone"   → agent demande téléphone (si absent de l'étape 2)
  4. Session "awaiting_payment" → agent demande CB ou liquide
  5a. CB    → session "awaiting_card" → frontend affiche formulaire
            → POST /api/payment/simulate → succès ou échec
            → échec → propose règlement sur place
  5b. Liquide → commande finalisée directement
  6. Écriture Excel + JSON → order_id retourné
"""

import asyncio
import base64
import json
import logging
import random
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from langchain.schema import HumanMessage, SystemMessage
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from .graph.workflow import get_graph
from .graph.state import AgentState
from .metrics import (
    conversation_duration_seconds,
    conversations_total,
    orders_total,
    payments_total,
    sessions_active,
)
from .rag.retriever import (
    initialize_vectorstore,
    get_retriever,
    rebuild_in_background,
    rollback_vectorstore,
    get_status as get_rag_status,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ── Initialisation ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialisation du vectorstore RAG...")
    try:
        initialize_vectorstore()
        logger.info("Vectorstore prêt.")
    except Exception as exc:
        logger.error(f"Erreur initialisation vectorstore : {exc}")

    logger.info("Compilation du graphe LangGraph...")
    get_graph()
    logger.info("Graphe prêt. Agent démarré.")
    yield


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Traiteur Dupont – Agent Vocal IA",
    description="Agent conversationnel vocal basé sur LangGraph + Ollama (Mistral)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Gestion des sessions de commande ─────────────────────────────────────────
#
# Une session est créée dès qu'une intention "commande" est détectée.
# Elle stocke les articles et les infos client collectées au fil de la conversation.

@dataclass
class OrderSession:
    session_id: str
    step: str          # awaiting_name | awaiting_phone | awaiting_payment | awaiting_card | complete
    order_items: list
    is_complex: bool
    total: float
    customer_lastname: str = ""
    customer_firstname: str = ""
    customer_phone: str = ""
    payment_method: Optional[str] = None   # "CB" | "liquide"
    order_id: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.now)


_sessions: dict[str, OrderSession] = {}
_SESSION_TTL = timedelta(minutes=30)


def _get_session(session_id: str) -> Optional[OrderSession]:
    session = _sessions.get(session_id)
    if session:
        if datetime.now() - session.last_activity < _SESSION_TTL:
            session.last_activity = datetime.now()
            return session
        del _sessions[session_id]
        sessions_active.dec()
    return None


def _create_session(session_id: str, order_items: list, is_complex: bool, total: float) -> OrderSession:
    session = OrderSession(
        session_id=session_id,
        step="awaiting_name",
        order_items=order_items,
        is_complex=is_complex,
        total=total,
    )
    _sessions[session_id] = session
    sessions_active.inc()
    return session


def _clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
        sessions_active.dec()


# ── Schémas ───────────────────────────────────────────────────────────────────

class TextRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    skip_tts: bool = False


class PaymentSimulateRequest(BaseModel):
    session_id: str
    card_number: str
    expiry: str = ""
    cvv: str = ""


class AgentResponse(BaseModel):
    transcript: str
    intent: str
    order_items: list
    response_text: str
    audio_base64: Optional[str] = None
    is_error: bool = False
    session_id: Optional[str] = None
    order_step: Optional[str] = None   # étape de collecte en cours
    order_total: Optional[float] = None
    order_id: Optional[str] = None


# ── Helpers TTS ───────────────────────────────────────────────────────────────

async def _call_tts(text: str, skip_tts: bool = False) -> Optional[bytes]:
    if skip_tts or not text:
        return None
    from .config import settings
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{settings.tts_service_url}/synthesize",
                json={"text": text},
            )
            r.raise_for_status()
            return r.content
    except Exception as exc:
        logger.warning(f"TTS indisponible : {exc}")
        return None


def _audio_b64(audio_bytes: Optional[bytes]) -> Optional[str]:
    return base64.b64encode(audio_bytes).decode() if audio_bytes else None


# ── Extraction d'informations via LLM ────────────────────────────────────────

_EXTRACT_SYSTEM = """Extrait les informations suivantes du texte et retourne UNIQUEMENT un JSON valide :
{
  "prenom": "...",
  "nom": "...",
  "telephone": "..."
}
Si une information est absente du texte, utilise "". Réponds UNIQUEMENT avec le JSON."""


async def _extract_contact_info(text: str) -> dict[str, str]:
    """Extrait nom, prénom, téléphone depuis un texte libre via le LLM."""
    from .graph.nodes import llm
    try:
        response = await asyncio.to_thread(
            llm.invoke,
            [SystemMessage(content=_EXTRACT_SYSTEM), HumanMessage(content=text)],
        )
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as exc:
        logger.warning(f"Extraction contact info échouée : {exc}")
        return {"prenom": "", "nom": "", "telephone": ""}


def _detect_payment_method(text: str) -> Optional[str]:
    """Détecte CB ou liquide dans une réponse libre."""
    t = text.lower()
    if any(k in t for k in ["cb", "carte", "bancaire", "visa", "mastercard", "crédit", "credit"]):
        return "CB"
    if any(k in t for k in ["liquide", "espèces", "especes", "cash"]):
        return "liquide"
    return None


def _extract_phone(text: str) -> str:
    """Extrait un numéro de téléphone français depuis un texte."""
    match = re.search(r'(?:\+33\s?|0)[1-9](?:[\s.\-]?\d{2}){4}', text)
    if match:
        return re.sub(r'[\s.\-]', '', match.group())
    return text.strip()


# ── Finalisation d'une commande ───────────────────────────────────────────────

async def _finalize_order(session: OrderSession, payment_status: str) -> str:
    """Écrit la commande dans Excel + JSON. Retourne l'order_id."""
    from .orders.writer import write_order
    from .orders.store import append_order

    order_data = {
        "nom": session.customer_lastname,
        "prenom": session.customer_firstname,
        "telephone": session.customer_phone,
        "items": session.order_items,
        "total": session.total,
        "is_complex": session.is_complex,
        "payment_method": session.payment_method or "Non renseigné",
        "payment_status": payment_status,
        "order_status": "Confirmée",
    }

    order_id = append_order(order_data)

    await asyncio.to_thread(
        write_order,
        order_items=session.order_items,
        is_complex=session.is_complex,
        customer_lastname=session.customer_lastname,
        customer_firstname=session.customer_firstname,
        customer_phone=session.customer_phone,
        payment_method=session.payment_method or "Non renseigné",
        payment_status=payment_status,
        total=session.total,
        order_id=order_id,
    )

    # Métrique business : commande créée
    order_type = "complexe" if session.is_complex else "simple"
    orders_total.labels(type=order_type).inc()

    logger.info(f"Commande finalisée : {order_id} ({session.customer_firstname} {session.customer_lastname})")
    return order_id


# ── Gestion des tours de collecte d'informations ──────────────────────────────

async def _handle_session_step(
    session: OrderSession,
    text: str,
    skip_tts: bool,
) -> AgentResponse:
    """
    Traite un tour de conversation dans le contexte d'une commande en cours.
    Fait avancer la machine à états et génère la réponse appropriée.
    """
    response_text = ""
    order_id_result = None

    if session.step == "awaiting_name":
        info = await _extract_contact_info(text)
        prenom = info.get("prenom", "").strip()
        nom    = info.get("nom", "").strip()
        phone  = info.get("telephone", "").strip()

        if prenom and nom:
            session.customer_firstname = prenom
            session.customer_lastname  = nom
            if phone:
                session.customer_phone = phone
                session.step = "awaiting_payment"
                total_str = f"{session.total:.2f} €" if session.total > 0 else "un montant à confirmer"
                response_text = (
                    f"Merci {prenom} ! Votre commande s'élève à {total_str}. "
                    f"Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?"
                )
            else:
                session.step = "awaiting_phone"
                response_text = (
                    f"Merci {prenom} {nom} ! Pourriez-vous me donner votre numéro de téléphone ?"
                )
        else:
            response_text = (
                "Pourriez-vous me donner votre nom, prénom et numéro de téléphone "
                "pour finaliser la commande ?"
            )

    elif session.step == "awaiting_phone":
        session.customer_phone = _extract_phone(text)
        session.step = "awaiting_payment"
        total_str = f"{session.total:.2f} €" if session.total > 0 else "un montant à confirmer par notre équipe"
        response_text = (
            f"Votre commande s'élève à {total_str}. "
            f"Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?"
        )

    elif session.step == "awaiting_payment":
        method = _detect_payment_method(text)
        if method == "CB":
            session.payment_method = "CB"
            session.step = "awaiting_card"
            total_str = f"{session.total:.2f} €" if session.total > 0 else "le montant à confirmer"
            response_text = (
                f"Très bien ! Veuillez saisir vos informations de carte bancaire "
                f"dans le formulaire pour régler {total_str}."
            )
        elif method == "liquide":
            session.payment_method = "liquide"
            order_id_result = await _finalize_order(session, "Règlement sur place")
            session.order_id = order_id_result
            session.step = "complete"
            _clear_session(session.session_id)
            payments_total.labels(method="liquide", status="on_site").inc()
            response_text = (
                f"Parfait ! Votre commande n°{order_id_result} a bien été enregistrée. "
                f"Montant à régler en liquide lors du retrait : {session.total:.2f} €. "
                f"À bientôt chez Traiteur Dupont !"
            )
        else:
            response_text = (
                "Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?"
            )

    elif session.step == "awaiting_card":
        response_text = (
            "Veuillez utiliser le formulaire ci-dessous pour saisir "
            "vos informations de carte bancaire."
        )

    else:
        response_text = (
            "Votre commande a déjà été enregistrée. "
            "N'hésitez pas à passer une nouvelle commande !"
        )

    audio_bytes = await _call_tts(response_text, skip_tts)
    intent = "commande_complexe" if session.is_complex else "commande_simple"

    return AgentResponse(
        transcript=text,
        intent=intent,
        order_items=session.order_items,
        response_text=response_text,
        audio_base64=_audio_b64(audio_bytes),
        session_id=session.session_id,
        order_step=session.step,
        order_total=session.total,
        order_id=order_id_result,
    )


# ── Détection erreurs Ollama ──────────────────────────────────────────────────

def _is_ollama_unavailable(exc: Exception) -> bool:
    checked = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in checked:
        checked.add(id(current))
        if isinstance(current, (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError)):
            return True
        msg = f"{type(current).__name__} {current}".lower()
        if any(kw in msg for kw in ("connection refused", "connecterror", "connectionrefused")):
            return True
        current = current.__cause__ or current.__context__
    return False


def _friendly_error_response(transcript: str, exc: Exception) -> AgentResponse:
    if _is_ollama_unavailable(exc):
        message = (
            "Je suis désolé, le service de traitement IA (Ollama/Mistral) est actuellement "
            "indisponible. Vérifiez que tous les services sont démarrés (`make up`) et que "
            "le modèle Mistral est téléchargé (`make init-ollama`)."
        )
    else:
        message = (
            "Je suis désolé, une erreur technique s'est produite. "
            "Veuillez réessayer dans quelques instants ou contacter directement notre boutique."
        )
    return AgentResponse(
        transcript=transcript, intent="", order_items=[],
        response_text=message, is_error=True,
    )


# ── Helpers graph ─────────────────────────────────────────────────────────────

def _build_initial_state(
    audio_bytes: Optional[bytes] = None,
    text_input: str = "",
    skip_tts: bool = False,
) -> AgentState:
    return AgentState(
        audio_bytes=audio_bytes,
        text_input=text_input,
        intent="",
        order_items=[],
        query_topic="general",
        rag_context="",
        response_text="",
        audio_response=None,
        skip_tts=skip_tts,
        error=None,
    )


def _state_to_response(result: AgentState, session_id: Optional[str] = None) -> AgentResponse:
    audio_b64 = _audio_b64(result.get("audio_response"))
    return AgentResponse(
        transcript=result.get("text_input", ""),
        intent=result.get("intent", ""),
        order_items=result.get("order_items", []),
        response_text=result.get("response_text", ""),
        audio_base64=audio_b64,
        session_id=session_id,
        order_step=None,
        order_total=None,
    )


# ── Traitement commun (audio ou texte) ────────────────────────────────────────

async def _process_request(
    text_input: str = "",
    audio_bytes: Optional[bytes] = None,
    session_id: Optional[str] = None,
    skip_tts: bool = False,
    channel: str = "text",
) -> AgentResponse:
    """
    Point d'entrée commun pour les requêtes texte et voix.
    Gère la machine à états des sessions de commande.
    Mesure la durée totale bout-en-bout.
    """
    from .orders.catalog import compute_total

    t0 = time.perf_counter()

    # ── Session active : on continue la collecte d'infos ─────────────────────
    if session_id:
        session = _get_session(session_id)
        if session and session.step not in ("complete",):
            result = await _handle_session_step(session, text_input, skip_tts)
            duration = time.perf_counter() - t0
            conversation_duration_seconds.observe(duration)
            conversations_total.labels(channel=channel, status="success").inc()
            return result

    # ── Pas de session active : on passe par le graphe ───────────────────────
    graph = get_graph()
    initial_state = _build_initial_state(
        audio_bytes=audio_bytes,
        text_input=text_input,
        skip_tts=skip_tts,
    )

    try:
        result = await asyncio.to_thread(graph.invoke, initial_state)
    except Exception as exc:
        duration = time.perf_counter() - t0
        conversation_duration_seconds.observe(duration)
        conversations_total.labels(channel=channel, status="error").inc()
        logger.error(f"Erreur graphe : {exc}", exc_info=True)
        return _friendly_error_response(text_input, exc)

    intent = result.get("intent", "")
    order_items = result.get("order_items", [])

    # ── Commande détectée → on crée une session de collecte ──────────────────
    if intent in ("commande_simple", "commande_complexe") and order_items:
        sid = session_id or str(uuid.uuid4())[:12]
        total = compute_total(order_items)
        is_complex = intent == "commande_complexe"
        _create_session(sid, order_items, is_complex, total)

        response_text = result.get("response_text", "")
        audio_bytes_resp = result.get("audio_response")
        if not skip_tts and not audio_bytes_resp:
            audio_bytes_resp = await _call_tts(response_text, skip_tts)

        duration = time.perf_counter() - t0
        conversation_duration_seconds.observe(duration)
        conversations_total.labels(channel=channel, status="success").inc()

        return AgentResponse(
            transcript=result.get("text_input", ""),
            intent=intent,
            order_items=order_items,
            response_text=response_text,
            audio_base64=_audio_b64(audio_bytes_resp),
            session_id=sid,
            order_step="awaiting_name",
            order_total=total,
        )

    duration = time.perf_counter() - t0
    conversation_duration_seconds.observe(duration)
    conversations_total.labels(channel=channel, status="success").inc()
    return _state_to_response(result, session_id)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}


@app.get(
    "/metrics",
    response_class=Response,
    summary="Métriques Prometheus",
    description=(
        "Endpoint scrappé par Prometheus toutes les 15 secondes. "
        "Expose les métriques du pipeline vocal (STT, LLM, RAG, TTS) "
        "et les métriques business (commandes, paiements, sessions)."
    ),
    tags=["Observabilité"],
)
def prometheus_metrics():
    """
    Retourne les métriques au format Prometheus text-based exposition format.

    Ce format est un standard open source (CNCF). Toutes les métriques définies
    dans metrics.py sont automatiquement incluses ici.

    Exemple de sortie :
      # HELP stt_latency_seconds Temps de transcription Whisper en secondes
      # TYPE stt_latency_seconds histogram
      stt_latency_seconds_bucket{le="0.1"} 0.0
      stt_latency_seconds_bucket{le="0.25"} 2.0
      ...
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/api/transcribe")
async def transcribe_audio_only(
    audio: UploadFile = File(..., description="Fichier audio (WAV, MP3, OGG…)"),
):
    """
    Transcrit uniquement l'audio en texte via le service STT.
    Utilisé par le frontend pour afficher la transcription avant
    de soumettre la requête complète à l'agent.
    """
    from .config import settings
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{settings.stt_service_url}/transcribe",
                files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                params={"language": "fr"},
            )
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        logger.error(f"Transcription error : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/voice", response_model=AgentResponse)
async def process_voice(
    audio: UploadFile = File(..., description="Fichier audio (WAV, MP3, OGG…)"),
    session_id: str = Form(default=""),
):
    """Traite une entrée vocale (transcription + graphe ou session)."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    # Si session active, on récupère le texte transcrit d'abord
    session = _get_session(session_id) if session_id else None
    if session and session.step not in ("complete",):
        from .config import settings
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{settings.stt_service_url}/transcribe",
                    files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                    params={"language": "fr"},
                )
                r.raise_for_status()
                transcript = r.json().get("transcript", "").strip()
        except Exception as exc:
            logger.error(f"STT error : {exc}")
            raise HTTPException(status_code=500, detail="Erreur de transcription")
        return await _handle_session_step(session, transcript, skip_tts=False)

    return await _process_request(
        audio_bytes=audio_bytes,
        session_id=session_id or None,
        channel="voice",
    )


@app.post("/api/text", response_model=AgentResponse)
async def process_text(request: TextRequest):
    """Traite une entrée textuelle."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")
    return await _process_request(
        text_input=request.text,
        session_id=request.session_id or None,
        skip_tts=request.skip_tts,
        channel="text",
    )


@app.post("/api/payment/simulate")
async def simulate_payment(request: PaymentSimulateRequest):
    """
    Simule un paiement CB.
    Cartes de test :
      4242 4242 4242 4242 → toujours accepté
      4000 0000 0000 0002 → toujours refusé
      Autre carte valide  → 80 % de chance d'acceptation
    """
    session = _get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable ou expirée")
    if session.step != "awaiting_card":
        raise HTTPException(status_code=400, detail="La session n'attend pas de paiement CB")

    card = re.sub(r'[\s\-]', '', request.card_number)

    if not card.isdigit() or len(card) != 16:
        raise HTTPException(status_code=400, detail="Numéro de carte invalide (16 chiffres attendus)")

    if card == "4242424242424242":
        success = True
    elif card == "4000000000000002":
        success = False
    else:
        success = random.random() < 0.8

    if success:
        order_id = await _finalize_order(session, "Payé par CB")
        session.order_id = order_id
        session.step = "complete"
        _clear_session(session.session_id)
        payments_total.labels(method="CB", status="accepted").inc()
        return {
            "success": True,
            "message": "Paiement accepté",
            "order_id": order_id,
            "order_total": session.total,
            "customer_name": f"{session.customer_firstname} {session.customer_lastname}",
        }
    else:
        payments_total.labels(method="CB", status="refused").inc()
        return {
            "success": False,
            "message": (
                "Paiement refusé. Vous pouvez régler en liquide lors du retrait de votre commande."
            ),
        }


@app.post("/api/payment/accept-on-site")
async def accept_on_site(session_id: str):
    """Finalise la commande avec règlement sur place (après refus CB)."""
    session = _get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable ou expirée")
    if session.step not in ("awaiting_card",):
        raise HTTPException(status_code=400, detail="Étape de session incorrecte")

    session.payment_method = session.payment_method or "CB (refusé) → liquide"
    order_id = await _finalize_order(session, "Paiement refusé → règlement sur place")
    session.order_id = order_id
    session.step = "complete"
    _clear_session(session.session_id)
    payments_total.labels(method="CB", status="on_site").inc()

    return {
        "success": True,
        "order_id": order_id,
        "message": (
            f"Commande n°{order_id} enregistrée. "
            f"Montant à régler sur place : {session.total:.2f} €."
        ),
    }


@app.get("/api/orders")
async def list_orders():
    """Retourne toutes les commandes confirmées (pour le tableau de bord traiteur)."""
    from .orders.store import get_all_orders
    return get_all_orders()


@app.get("/api/status")
async def get_status():
    from .config import settings as cfg

    results: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{cfg.ollama_base_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            results["ollama"] = {"status": "ok", "models": models}
        except Exception as exc:
            results["ollama"] = {"status": "error", "error": str(exc)}

        try:
            r = await client.get(f"{cfg.stt_service_url}/health")
            results["stt"] = {"status": "ok" if r.is_success else "error"}
        except Exception as exc:
            results["stt"] = {"status": "error", "error": str(exc)}

        try:
            r = await client.get(f"{cfg.tts_service_url}/health")
            results["tts"] = {"status": "ok" if r.is_success else "error"}
        except Exception as exc:
            results["tts"] = {"status": "error", "error": str(exc)}

    try:
        count = get_retriever().vectorstore._collection.count()
        results["rag"] = {"status": "ok", "chunks": count}
    except Exception as exc:
        results["rag"] = {"status": "error", "error": str(exc)}

    overall = "ok" if all(v["status"] == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}


@app.post(
    "/api/rag/rebuild",
    summary="Démarre un rebuild RAG sans downtime",
    description=(
        "Lance la reconstruction de l'index RAG en tâche de fond (shadow indexing). "
        "Retourne immédiatement (< 1ms). Le vectorstore actif continue de servir "
        "les requêtes pendant le rebuild. L'atomic swap a lieu quand le nouveau "
        "index est prêt. Suivre l'avancement via GET /api/rag/status."
    ),
    tags=["RAG Hot Reload"],
)
async def rag_rebuild():
    """
    Démarre un rebuild shadow non-bloquant.

    Séquence :
      1. POST /api/rag/rebuild → retourne en < 1ms
      2. GET  /api/rag/status  → {"state": "rebuilding", "elapsed_s": 12.4}
      3. GET  /api/rag/status  → {"state": "done", "chunks_active": 87, "duration_s": 34.2}
    """
    started = rebuild_in_background()
    if not started:
        status = get_rag_status()
        return {
            "status": "already_running",
            "message": "Un rebuild est déjà en cours.",
            "rag": status,
        }
    return {
        "status": "started",
        "message": (
            "Rebuild shadow démarré en arrière-plan. "
            "L'agent continue de répondre normalement. "
            "Suivez l'avancement via GET /api/rag/status."
        ),
    }


@app.get(
    "/api/rag/status",
    summary="État du rebuild RAG",
    tags=["RAG Hot Reload"],
)
async def rag_status():
    """
    Retourne l'état courant du RAG.

    state = "idle"       → aucun rebuild en cours, RAG opérationnel
    state = "rebuilding" → rebuild en cours (+ elapsed_s)
    state = "done"       → dernier rebuild réussi (+ duration_s, rollback_available)
    state = "error"      → dernier rebuild a échoué (+ error message)
    """
    return get_rag_status()


@app.post(
    "/api/rag/rollback",
    summary="Revient à la collection RAG précédente",
    description=(
        "Effectue un atomic swap inverse : remet en service la collection "
        "qui était active avant le dernier rebuild. "
        "Disponible seulement si rollback_available=true dans /api/rag/status."
    ),
    tags=["RAG Hot Reload"],
)
async def rag_rollback():
    """
    Rollback atomique vers la collection précédente.

    Utile si le nouveau index dégrade la qualité des réponses.
    Même mécanique que le swap forward : instantané, zéro downtime.
    """
    success = rollback_vectorstore()
    if not success:
        raise HTTPException(
            status_code=409,
            detail=(
                "Rollback impossible : pas de collection précédente disponible. "
                "Effectuez d'abord un /api/rag/rebuild."
            ),
        )
    status = get_rag_status()
    return {
        "status": "ok",
        "message": f"Rollback effectué → collection '{status['active_collection']}'",
        "rag": status,
    }


@app.post("/api/reload-documents", tags=["RAG Hot Reload"])
async def reload_documents():
    """
    Alias non-bloquant vers /api/rag/rebuild (compatibilité étapes précédentes).

    CHANGEMENT vs étape 03 :
      Avant : bloquait 30s+, RAG indisponible pendant le rebuild
      Maintenant : retourne immédiatement, rebuild en background
    """
    return await rag_rebuild()
