"""
Agent Vocal Traiteur Dupont — Étape 02
────────────────────────────────────────
Architecture :
  POST /api/voice  → audio  → STTProvider → LLMProvider → réponse JSON + audio TTS
  POST /api/text   → texte  → LLMProvider → réponse JSON + audio TTS optionnel
  POST /api/payment/simulate → simulation paiement CB
  GET  /api/orders            → liste des commandes (dashboard)
  GET  /api/status            → état des providers
  GET  /health                → healthcheck

Flux multi-tour (commande) :
  classify → awaiting_name → awaiting_phone → awaiting_payment → [awaiting_card] → complete

Conformité :
  - AI Act art.50 : l'agent annonce qu'il est une IA dès le premier message.
  - RGPD : aucune donnée personnelle dans les logs (filtre logging_config.py).
  - Menu injecté intégralement dans le prompt (pas de RAG — voir docs/DECISIONS.md).
"""

import asyncio
import base64
import json
import os
import random
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .factory import create_stt_provider, create_llm_provider
from .logging_config import setup_logging, get_logger, log_stt_event, log_llm_event, log_order_event, maybe_log_transcript
from .basket import from_order_items, to_order_items, compute_total, total_units, format_basket, add_item
from .excel_export import write_order

# ── Initialisation du logging ──────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── Chargement des prompts et du menu ─────────────────────────────────────────
_BASE = Path(__file__).parent
_PROMPTS = yaml.safe_load((_BASE / "prompts" / "system_prompt.yaml").read_text(encoding="utf-8"))
_MENU_DATA = yaml.safe_load((_BASE / "menu" / "menu.yaml").read_text(encoding="utf-8"))
MENU_TEXT: str = _MENU_DATA["text"]
MENU_CATALOG: dict[str, float] = _MENU_DATA["catalog"]
_PROMPT_META: dict = _PROMPTS.get("meta", {})


def _render(template: str, **kwargs) -> str:
    return template.format(**kwargs)


# ── Providers (instanciés au démarrage) ───────────────────────────────────────
_stt_provider = None
_llm_provider = None

_TTS_URL = os.getenv("TTS_SERVICE_URL", "http://tts:8002")
_ORDER_COMPLEXITY_THRESHOLD = int(os.getenv("ORDER_COMPLEXITY_THRESHOLD", "6"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _stt_provider, _llm_provider
    logger.info("agent_startup", stt_provider=os.getenv("STT_PROVIDER"), llm_provider=os.getenv("LLM_PROVIDER"))
    _stt_provider = create_stt_provider()
    _llm_provider = create_llm_provider()
    logger.info("providers_ready",
                stt=_stt_provider.provider_name,
                llm=_llm_provider.provider_name,
                llm_model=_llm_provider.model_name,
                prompt_version=_PROMPT_META.get("version", "unknown"),
                prompt_model_hint=_PROMPT_META.get("model_hint", ""))
    yield
    logger.info("agent_shutdown")


# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Traiteur Dupont – Agent Vocal IA",
    description="Agent vocal conforme RGPD / AI Act. Étape 02.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# UI — le répertoire est monté à / EN FIN DE FICHIER (après toutes les routes API)
# afin que les routes /api/* et /health prennent toujours la priorité.
_UI_DIR = Path(__file__).parent.parent / "ui"


# ── Gestion des sessions ───────────────────────────────────────────────────────

@dataclass
class OrderSession:
    session_id: str
    step: str  # awaiting_name | awaiting_phone | awaiting_payment | awaiting_card | complete
    basket: dict
    is_complex: bool
    total: float
    customer_lastname: str = ""
    customer_firstname: str = ""
    customer_phone: str = ""
    payment_method: Optional[str] = None
    order_id: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.now)


_sessions: dict[str, OrderSession] = {}
_SESSION_TTL = timedelta(minutes=30)

# Historique conversationnel léger pour les questions "info" (sans commande en cours).
# Permet au LLM d'interpréter les questions de suivi ("Et le rougail ?", "Pas d'autres ?").
# 6 entrées = 3 tours user+assistant conservés par session.
_info_contexts: dict[str, deque] = {}
_INFO_CTX_SIZE = 6


def _get_session(session_id: str) -> Optional[OrderSession]:
    session = _sessions.get(session_id)
    if session:
        if datetime.now() - session.last_activity < _SESSION_TTL:
            session.last_activity = datetime.now()
            return session
        del _sessions[session_id]
    return None


def _create_session(session_id: str, basket: dict, is_complex: bool, total: float) -> OrderSession:
    session = OrderSession(
        session_id=session_id, step="awaiting_name",
        basket=basket, is_complex=is_complex, total=total,
    )
    _sessions[session_id] = session
    return session


# ── Schémas ────────────────────────────────────────────────────────────────────

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
    order_step: Optional[str] = None
    order_total: Optional[float] = None
    order_id: Optional[str] = None


# ── Helpers TTS ────────────────────────────────────────────────────────────────

async def _call_tts(text: str, skip_tts: bool = False) -> Optional[bytes]:
    if skip_tts or not text.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{_TTS_URL}/synthesize", json={"text": text})
            r.raise_for_status()
            return r.content
    except Exception as exc:
        logger.warning("tts_unavailable", error=str(exc)[:100])
        return None


def _audio_b64(audio_bytes: Optional[bytes]) -> Optional[str]:
    return base64.b64encode(audio_bytes).decode() if audio_bytes else None


# ── LLM helpers ────────────────────────────────────────────────────────────────

async def _llm_classify(text: str) -> dict:
    """Classify intent and extract order items from user text."""
    t0 = time.perf_counter()
    prompt = _render(_PROMPTS["classify"], menu=MENU_TEXT)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    try:
        raw = await _llm_provider.chat(messages, max_tokens=256)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_llm_event(logger, _llm_provider.provider_name, _llm_provider.model_name, duration_ms, "classify")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return data
    except Exception as exc:
        logger.error("llm_classify_error", error=str(exc)[:200])
        return {"intent": "autre", "order_items": []}


async def _llm_respond(intent: str, text: str, order_items: list, history: list[dict] | None = None) -> str:
    """Generate a response text based on intent.

    history: turns précédents [{"role": "user", ...}, {"role": "assistant", ...}, ...]
             Passé uniquement pour intent="info" afin de gérer les questions de suivi.
    """
    t0 = time.perf_counter()
    if intent in ("commande_simple", "commande_complexe"):
        prompt = _render(_PROMPTS["respond_order"], menu=MENU_TEXT)
        items_str = ", ".join(f"{i['quantite']}× {i['produit']}" for i in order_items)
        user_msg = f"Le client souhaite commander : {items_str}. Confirme et demande nom, prénom, téléphone."
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}]
    elif intent == "info":
        prompt = _render(_PROMPTS["respond_info"], menu=MENU_TEXT)
        messages = [{"role": "system", "content": prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})
    else:
        prompt = _PROMPTS["respond_other"]
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": text}]

    try:
        response = await _llm_provider.chat(messages, max_tokens=512)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_llm_event(logger, _llm_provider.provider_name, _llm_provider.model_name, duration_ms, intent)
        return response
    except Exception as exc:
        logger.error("llm_respond_error", error=str(exc)[:200])
        raise


async def _extract_contact_info(text: str) -> dict[str, str]:
    messages = [
        {"role": "system", "content": _PROMPTS["extract_contact"]},
        {"role": "user", "content": text},
    ]
    try:
        raw = await _llm_provider.chat(messages, max_tokens=128)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"prenom": "", "nom": "", "telephone": ""}


def _detect_payment_method(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ["cb", "carte", "bancaire", "visa", "mastercard", "crédit", "credit"]):
        return "CB"
    if any(k in t for k in ["liquide", "espèces", "especes", "cash"]):
        return "liquide"
    return None


def _extract_phone(text: str) -> str:
    match = re.search(r'(?:\+33\s?|0)[1-9](?:[\s.\-]?\d{2}){4}', text)
    if match:
        return re.sub(r'[\s.\-]', '', match.group())
    return text.strip()


# ── Finalisation de commande ───────────────────────────────────────────────────

async def _finalize_order(session: OrderSession, payment_status: str) -> str:
    """Écrit la commande Excel et JSON. Retourne l'order_id."""
    from .orders_store import append_order

    order_id = str(uuid.uuid4())[:8].upper()
    items = to_order_items(session.basket)

    order_data = {
        "id": order_id,
        "nom": session.customer_lastname,
        "prenom": session.customer_firstname,
        "telephone": session.customer_phone,
        "items": items,
        "total": session.total,
        "is_complex": session.is_complex,
        "payment_method": session.payment_method or "Non renseigné",
        "payment_status": payment_status,
        "order_status": "Confirmée",
        "created_at": datetime.now().isoformat(),
    }

    append_order(order_data)

    await asyncio.to_thread(
        write_order,
        order_id=order_id,
        order_items=items,
        is_complex=session.is_complex,
        customer_lastname=session.customer_lastname,
        customer_firstname=session.customer_firstname,
        customer_phone=session.customer_phone,
        payment_method=session.payment_method or "Non renseigné",
        payment_status=payment_status,
        total=session.total,
    )

    log_order_event(logger, order_id, len(items), session.is_complex)
    return order_id


# ── Machine à états de collecte d'informations ────────────────────────────────

async def _handle_session_step(session: OrderSession, text: str, skip_tts: bool) -> AgentResponse:
    response_text = ""
    order_id_result = None

    if session.step == "awaiting_name":
        info = await _extract_contact_info(text)
        prenom = info.get("prenom", "").strip()
        nom = info.get("nom", "").strip()
        phone = info.get("telephone", "").strip()

        if prenom and nom:
            session.customer_firstname = prenom
            session.customer_lastname = nom
            if phone:
                session.customer_phone = phone
                session.step = "awaiting_payment"
                total_str = f"{session.total:.2f} €" if session.total > 0 else "un montant à confirmer"
                response_text = (f"Merci {prenom} ! Votre commande s'élève à {total_str}. "
                                 f"Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?")
            else:
                session.step = "awaiting_phone"
                response_text = f"Merci {prenom} {nom} ! Pourriez-vous me donner votre numéro de téléphone ?"
        else:
            response_text = "Pourriez-vous me donner votre nom, prénom et numéro de téléphone pour finaliser la commande ?"

    elif session.step == "awaiting_phone":
        session.customer_phone = _extract_phone(text)
        session.step = "awaiting_payment"
        total_str = f"{session.total:.2f} €" if session.total > 0 else "un montant à confirmer"
        response_text = (f"Votre commande s'élève à {total_str}. "
                         f"Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?")

    elif session.step == "awaiting_payment":
        method = _detect_payment_method(text)
        if method == "CB":
            session.payment_method = "CB"
            session.step = "awaiting_card"
            response_text = (f"Très bien ! Veuillez saisir vos informations de carte bancaire "
                             f"dans le formulaire pour régler {session.total:.2f} €.")
        elif method == "liquide":
            session.payment_method = "liquide"
            order_id_result = await _finalize_order(session, "Règlement sur place")
            session.order_id = order_id_result
            session.step = "complete"
            response_text = (f"Parfait ! Votre commande n°{order_id_result} est enregistrée. "
                             f"Montant à régler en liquide : {session.total:.2f} €. À bientôt !")
        else:
            response_text = "Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?"

    elif session.step == "awaiting_card":
        response_text = "Veuillez utiliser le formulaire pour saisir vos informations de carte bancaire."

    else:
        response_text = "Votre commande a déjà été enregistrée. N'hésitez pas à passer une nouvelle commande !"

    audio_bytes = await _call_tts(response_text, skip_tts)
    intent = "commande_complexe" if session.is_complex else "commande_simple"

    return AgentResponse(
        transcript=text, intent=intent,
        order_items=to_order_items(session.basket),
        response_text=response_text,
        audio_base64=_audio_b64(audio_bytes),
        session_id=session.session_id,
        order_step=session.step,
        order_total=session.total,
        order_id=order_id_result,
    )


# ── Traitement principal ───────────────────────────────────────────────────────

async def _process_request(
    text_input: str = "",
    audio_bytes: Optional[bytes] = None,
    session_id: Optional[str] = None,
    skip_tts: bool = False,
) -> AgentResponse:
    # ── Transcription STT ────────────────────────────────────────────────────
    if audio_bytes:
        t0 = time.perf_counter()
        text_input = await _stt_provider.transcribe(audio_bytes)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_stt_event(logger, _stt_provider.provider_name, duration_ms, "fr")
        maybe_log_transcript(logger, text_input)

    if not text_input.strip():
        return AgentResponse(
            transcript="", intent="autre", order_items=[],
            response_text="Je n'ai pas compris. Pouvez-vous répéter ?",
            session_id=session_id,
        )

    # ── Session active : collecte d'informations ─────────────────────────────
    if session_id:
        session = _get_session(session_id)
        if session and session.step not in ("complete",):
            # Classifier d'abord pour détecter infos ou ajouts d'articles
            try:
                data = await _llm_classify(text_input)
                intent_raw = data.get("intent", "autre")

                if intent_raw == "info":
                    history = list(_info_contexts.get(session_id, []))
                    response_text = await _llm_respond("info", text_input, [], history=history)
                    ctx = _info_contexts.setdefault(session_id, deque(maxlen=_INFO_CTX_SIZE))
                    ctx.append({"role": "user", "content": text_input})
                    ctx.append({"role": "assistant", "content": response_text})
                    reminder = {
                        "awaiting_name": "Pour finaliser votre commande, pourriez-vous me donner votre nom et prénom ?",
                        "awaiting_phone": "Pourriez-vous me donner votre numéro de téléphone pour finaliser votre commande ?",
                        "awaiting_payment": "Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?",
                    }.get(session.step, "")
                    combined = f"{response_text}\n\nEt pour votre commande en cours : {reminder}" if reminder else response_text
                    audio = await _call_tts(combined, skip_tts)
                    intent_label = "commande_complexe" if session.is_complex else "commande_simple"
                    return AgentResponse(
                        transcript=text_input, intent=intent_label,
                        order_items=to_order_items(session.basket),
                        response_text=combined,
                        audio_base64=_audio_b64(audio),
                        session_id=session.session_id,
                        order_step=session.step,
                        order_total=session.total,
                    )

                if intent_raw == "commande":
                    new_items = data.get("order_items") or []
                    if new_items:
                        new_basket = from_order_items(new_items)
                        for name, qty in new_basket.items():
                            session.basket = add_item(session.basket, name, qty)
                        session.total = compute_total(session.basket, MENU_CATALOG)
                        session.is_complex = total_units(session.basket) > _ORDER_COMPLEXITY_THRESHOLD
                    added_str = ", ".join(f"{i['quantite']}× {i['produit']}" for i in new_items)
                    reminder = {
                        "awaiting_name": "Pour finaliser, pourriez-vous me donner votre nom et prénom ?",
                        "awaiting_phone": "Pourriez-vous me donner votre numéro de téléphone ?",
                        "awaiting_payment": "Souhaitez-vous régler par carte bancaire (CB) ou en liquide ?",
                    }.get(session.step, "")
                    response_text = (
                        f"J'ai ajouté {added_str} à votre commande. "
                        f"Panier : {format_basket(session.basket)} — total estimé : {session.total:.2f} €. "
                        f"{reminder}"
                    )
                    audio = await _call_tts(response_text, skip_tts)
                    intent_label = "commande_complexe" if session.is_complex else "commande_simple"
                    return AgentResponse(
                        transcript=text_input, intent=intent_label,
                        order_items=to_order_items(session.basket),
                        response_text=response_text,
                        audio_base64=_audio_b64(audio),
                        session_id=session.session_id,
                        order_step=session.step,
                        order_total=session.total,
                    )
            except Exception as exc:
                logger.error("classify_error_in_session", error=str(exc)[:200])

            return await _handle_session_step(session, text_input, skip_tts)

    # ── Pas de session : classification + réponse ────────────────────────────
    try:
        data = await _llm_classify(text_input)
    except Exception as exc:
        logger.error("classify_error", error=str(exc)[:200])
        return AgentResponse(
            transcript=text_input, intent="", order_items=[],
            response_text="Je suis désolé, je rencontre une difficulté technique. Veuillez réessayer.",
            is_error=True, session_id=session_id,
        )

    intent_raw = data.get("intent", "autre")
    order_items = data.get("order_items") or []

    if intent_raw == "commande" and order_items:
        basket = from_order_items(order_items)
        total = compute_total(basket, MENU_CATALOG)
        is_complex = total_units(basket) > _ORDER_COMPLEXITY_THRESHOLD
        intent = "commande_complexe" if is_complex else "commande_simple"

        try:
            response_text = await _llm_respond(intent, text_input, order_items)
        except Exception as exc:
            logger.error("llm_respond_error", error=str(exc)[:200])
            response_text = f"J'ai bien noté votre commande : {format_basket(basket)}. Pourriez-vous me donner votre nom et prénom ?"

        sid = session_id or str(uuid.uuid4())[:12]
        _create_session(sid, basket, is_complex, total)

        audio = await _call_tts(response_text, skip_tts)
        return AgentResponse(
            transcript=text_input, intent=intent,
            order_items=to_order_items(basket),
            response_text=response_text,
            audio_base64=_audio_b64(audio),
            session_id=sid,
            order_step="awaiting_name",
            order_total=total,
        )

    intent = intent_raw if intent_raw in ("info", "autre") else "autre"
    history = list(_info_contexts.get(session_id, [])) if session_id and intent == "info" else None
    try:
        response_text = await _llm_respond(intent, text_input, [], history=history)
    except Exception as exc:
        logger.error("llm_respond_error", error=str(exc)[:200])
        response_text = "Je suis désolé, je rencontre une difficulté technique. Veuillez réessayer."

    if session_id and intent == "info":
        ctx = _info_contexts.setdefault(session_id, deque(maxlen=_INFO_CTX_SIZE))
        ctx.append({"role": "user", "content": text_input})
        ctx.append({"role": "assistant", "content": response_text})

    audio = await _call_tts(response_text, skip_tts)
    return AgentResponse(
        transcript=text_input, intent=intent,
        order_items=[],
        response_text=response_text,
        audio_base64=_audio_b64(audio),
        session_id=session_id,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Étape 1 du flux vocal : STT uniquement, renvoie la transcription brute."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")
    transcript = await _stt_provider.transcribe(audio_bytes)
    return {"transcript": transcript}


@app.post("/api/voice", response_model=AgentResponse)
async def process_voice(
    audio: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")
    return await _process_request(
        audio_bytes=audio_bytes,
        session_id=session_id or None,
        skip_tts=False,
    )


@app.post("/api/text", response_model=AgentResponse)
async def process_text(request: TextRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")
    return await _process_request(
        text_input=request.text,
        session_id=request.session_id or None,
        skip_tts=request.skip_tts,
    )


@app.post("/api/payment/simulate")
async def simulate_payment(request: PaymentSimulateRequest):
    """
    Simulation paiement CB.
    Cartes de test : 4242424242424242 → accepté, 4000000000000002 → refusé.
    RGPD : le numéro de carte n'est PAS loggé.
    """
    session = _get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable ou expirée")
    if session.step != "awaiting_card":
        raise HTTPException(status_code=400, detail="La session n'attend pas de paiement CB")

    card = re.sub(r'[\s\-]', '', request.card_number)
    if not card.isdigit() or len(card) != 16:
        raise HTTPException(status_code=400, detail="Numéro de carte invalide (16 chiffres)")

    if card == "4242424242424242":
        success = True
    elif card == "4000000000000002":
        success = False
    else:
        success = random.random() < 0.8

    logger.info("payment_simulation", success=success)

    if success:
        order_id = await _finalize_order(session, "Payé par CB")
        session.order_id = order_id
        session.step = "complete"
        return {
            "success": True, "message": "Paiement accepté",
            "order_id": order_id, "order_total": session.total,
            "customer_name": f"{session.customer_firstname} {session.customer_lastname}",
        }
    return {
        "success": False,
        "message": "Paiement refusé. Vous pouvez régler en liquide lors du retrait.",
    }


@app.post("/api/payment/accept-on-site")
async def accept_on_site(session_id: str):
    session = _get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable ou expirée")
    if session.step not in ("awaiting_card",):
        raise HTTPException(status_code=400, detail="Étape de session incorrecte")

    session.payment_method = session.payment_method or "CB (refusé) → liquide"
    order_id = await _finalize_order(session, "Paiement refusé → règlement sur place")
    session.order_id = order_id
    session.step = "complete"
    return {
        "success": True, "order_id": order_id,
        "message": f"Commande n°{order_id} enregistrée. Montant à régler sur place : {session.total:.2f} €.",
    }


@app.get("/api/orders")
async def list_orders():
    from .orders_store import get_all_orders
    return get_all_orders()


@app.get("/api/status")
async def get_status():
    checks: dict[str, Any] = {
        "stt": {"provider": _stt_provider.provider_name if _stt_provider else "none"},
        "llm": {
            "provider": _llm_provider.provider_name if _llm_provider else "none",
            "model": _llm_provider.model_name if _llm_provider else "none",
        },
    }
    tts_ok = False
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            r = await client.get(f"{_TTS_URL}/health")
            tts_ok = r.is_success
            checks["tts"] = {"status": "ok" if tts_ok else "error"}
        except Exception as exc:
            checks["tts"] = {"status": "error", "error": str(exc)[:100]}

    if _llm_provider and _llm_provider.provider_name == "local_ollama":
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        async with httpx.AsyncClient(timeout=3) as client:
            try:
                r = await client.get(f"{ollama_url}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                checks["ollama"] = {"status": "ok", "models": models}
            except Exception as exc:
                checks["ollama"] = {"status": "error", "error": str(exc)[:100]}

    return {"status": "ok", "checks": checks}


# ── UI statique ────────────────────────────────────────────────────────────────
# Monté EN DERNIER : les routes /api/*, /health déclarées au-dessus ont toujours
# la priorité. StaticFiles gère le reste : /, /index.html (chatbot), /traiteur.html
# (dashboard), /status.html, /style.css, /app.js, etc.
# html=True → sert automatiquement index.html pour les requêtes sur /
if _UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")
