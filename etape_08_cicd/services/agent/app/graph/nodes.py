"""
Nœuds du graphe LangGraph
──────────────────────────
Chaque nœud est une fonction pure :
  - Reçoit l'état complet (AgentState)
  - Retourne un dict partiel avec les champs modifiés

Ordre d'exécution :
  transcribe → classify → [search_rag | generate_response] → synthesize

Étape 02 : chaque nœud est maintenant instrumenté avec des métriques Prometheus.
La mesure de chaque étape du pipeline permet de répondre à :
  - "Où passe le temps ?" (STT ? LLM ? RAG ? TTS ?)
  - "Quel composant dégrade la qualité de service ?"
  - "Faut-il changer de modèle Whisper ?" (→ étape 03)
"""

import json
import logging
import time

import httpx
from langchain_ollama import ChatOllama
from langchain.schema import HumanMessage, SystemMessage

from ..config import settings
from ..metrics import (
    llm_classify_latency_seconds,
    llm_classify_requests_total,
    llm_generate_latency_seconds,
    llm_generate_requests_total,
    rag_chunks_retrieved,
    rag_latency_seconds,
    rag_requests_total,
    stt_latency_seconds,
    stt_requests_total,
    tts_latency_seconds,
    tts_requests_total,
)
from ..rag.retriever import get_retriever
from .state import AgentState

logger = logging.getLogger(__name__)

# ── LLM partagé (instancié une seule fois) ────────────────────────────────────
llm = ChatOllama(
    model=settings.llm_model,
    base_url=settings.ollama_base_url,
    temperature=settings.llm_temperature,
)


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 1 : Transcription audio → texte
# ═════════════════════════════════════════════════════════════════════════════

def transcribe_audio(state: AgentState) -> dict:
    """
    Appelle le service STT (Whisper) pour transcrire l'audio en texte.
    Si text_input est déjà renseigné (appel texte direct), passe son tour.

    Métriques : stt_latency_seconds, stt_requests_total
    """
    if not state.get("audio_bytes"):
        # Entrée texte directe : rien à transcrire, on conserve text_input tel quel
        return {"text_input": state.get("text_input", "")}

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{settings.stt_service_url}/transcribe",
                files={"audio": ("audio.wav", state["audio_bytes"], "audio/wav")},
                params={"language": "fr"},
            )
            response.raise_for_status()
            data = response.json()

        latency = time.perf_counter() - t0
        stt_latency_seconds.observe(latency)
        stt_requests_total.labels(status="success").inc()

        transcript = data.get("transcript", "").strip()
        logger.info(f"STT [{latency:.2f}s] : '{transcript}'")
        return {"text_input": transcript}

    except Exception as exc:
        latency = time.perf_counter() - t0
        stt_latency_seconds.observe(latency)
        stt_requests_total.labels(status="error").inc()
        logger.error(f"STT erreur [{latency:.2f}s] : {exc}")
        return {"text_input": "", "error": f"Erreur de transcription : {exc}"}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 2 : Classification de l'intention + extraction des entités
# ═════════════════════════════════════════════════════════════════════════════

_CLASSIFY_SYSTEM = """Tu es un assistant pour un traiteur français.
Analyse la demande client et retourne UNIQUEMENT un objet JSON valide avec ces champs :

{
  "intent": "info" | "commande" | "autre",
  "topic": "menu" | "horaires" | "conges" | "general",
  "order_items": [{"produit": "nom exact", "quantite": N}]
}

Règles :
- intent="info"     → le client pose une question sur les menus, les prix, les horaires ou les congés
- intent="commande" → le client veut passer une commande (précise des produits et quantités)
- intent="autre"    → salutation, remerciement, question hors-sujet
- topic             → pertinent uniquement si intent="info"
- order_items       → liste vide [] si intent != "commande"
- quantite          → nombre entier, minimum 1

Réponds UNIQUEMENT avec le JSON. Aucun texte avant ou après."""


def classify_request(state: AgentState) -> dict:
    """
    Utilise le LLM pour classifier l'intention et extraire les articles commandés.
    Détermine aussi si la commande est simple ou complexe selon le seuil configuré.

    Métriques : llm_classify_latency_seconds, llm_classify_requests_total
    """
    text = state.get("text_input", "").strip()

    if not text:
        llm_classify_requests_total.labels(intent="autre").inc()
        return {"intent": "autre", "order_items": [], "query_topic": "general"}

    t0 = time.perf_counter()
    try:
        messages = [
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=text),
        ]
        response = llm.invoke(messages)

        latency = time.perf_counter() - t0
        llm_classify_latency_seconds.observe(latency)

        # Nettoyage du JSON (le LLM peut ajouter des backticks)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        intent_raw = data.get("intent", "autre")
        order_items = data.get("order_items") or []
        topic = data.get("topic") or "general"

        # Calcul du type de commande selon le seuil de complexité
        if intent_raw == "commande":
            total_units = sum(item.get("quantite", 1) for item in order_items)
            threshold = settings.order_complexity_threshold
            intent = "commande_complexe" if total_units > threshold else "commande_simple"
            logger.info(
                f"LLM classify [{latency:.2f}s] : {total_units} unités → "
                f"{'complexe' if total_units > threshold else 'simple'}"
            )
        else:
            intent = intent_raw

        llm_classify_requests_total.labels(intent=intent).inc()
        logger.info(f"LLM classify [{latency:.2f}s] : intent='{intent}' topic='{topic}'")
        return {"intent": intent, "order_items": order_items, "query_topic": topic}

    except (json.JSONDecodeError, Exception) as exc:
        latency = time.perf_counter() - t0
        llm_classify_latency_seconds.observe(latency)
        llm_classify_requests_total.labels(intent="autre").inc()
        logger.error(f"LLM classify erreur [{latency:.2f}s] : {exc}")
        return {"intent": "autre", "order_items": [], "query_topic": "general"}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 3 : Recherche RAG dans les fichiers de l'entreprise
# ═════════════════════════════════════════════════════════════════════════════

def search_rag(state: AgentState) -> dict:
    """
    Récupère les passages les plus pertinents dans les fichiers .txt
    (menus.txt, horaires.txt, conges.txt) via ChromaDB + sentence-transformers.

    Métriques : rag_latency_seconds, rag_requests_total, rag_chunks_retrieved
    Le "hit rate" (taux de succès RAG) est calculable dans Grafana :
      sum(rag_requests_total{result="hit"}) / sum(rag_requests_total)
    """
    t0 = time.perf_counter()
    try:
        retriever = get_retriever()
        docs = retriever.invoke(state["text_input"])

        latency = time.perf_counter() - t0
        rag_latency_seconds.observe(latency)
        rag_chunks_retrieved.observe(len(docs))

        if docs:
            rag_requests_total.labels(result="hit").inc()
        else:
            rag_requests_total.labels(result="miss").inc()

        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        logger.info(f"RAG [{latency:.2f}s] : {len(docs)} chunks")
        return {"rag_context": context}

    except Exception as exc:
        latency = time.perf_counter() - t0
        rag_latency_seconds.observe(latency)
        rag_requests_total.labels(result="miss").inc()
        logger.error(f"RAG erreur [{latency:.2f}s] : {exc}")
        return {"rag_context": ""}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 5 : Génération de la réponse textuelle
# ═════════════════════════════════════════════════════════════════════════════

_RESPONSE_SYSTEM = """Tu es l'assistant vocal du Traiteur Dupont, une entreprise française de restauration traiteur à Dijon.
Tu réponds en français, avec chaleur et professionnalisme.
Sois CONCIS : 1 à 3 phrases maximum, car ta réponse sera lue à voix haute.
N'utilise pas de listes à puces ni de markdown dans ta réponse."""


def generate_response(state: AgentState) -> dict:
    """
    Génère la réponse textuelle adaptée au contexte (info RAG ou confirmation commande).

    Métriques : llm_generate_latency_seconds, llm_generate_requests_total
    """
    intent = state.get("intent", "autre")
    context = state.get("rag_context", "")
    order_items = state.get("order_items", [])
    error = state.get("error")

    # ── Construction du prompt selon l'intention ───────────────────────────────
    if error:
        user_message = (
            f"Une erreur technique s'est produite lors du traitement de la demande. "
            f"Informe poliment le client et invite-le à rappeler ou envoyer un email."
        )

    elif intent in ("commande_simple", "commande_complexe"):
        items_str = ", ".join(
            f"{it['quantite']}× {it['produit']}" for it in order_items
        )
        user_message = (
            f"Le client souhaite commander : {items_str}. "
            f"Confirme que tu as bien noté les articles et demande-lui "
            f"son nom, son prénom et son numéro de téléphone pour finaliser la commande. "
            f"Sois chaleureux et concis (2 phrases maximum)."
        )

    elif intent == "info" and context:
        user_message = (
            f"Question du client : {state['text_input']}\n\n"
            f"Informations disponibles :\n{context}\n\n"
            f"Réponds à la question en te basant uniquement sur ces informations. "
            f"Si l'information n'est pas disponible, dis-le poliment."
        )

    else:
        user_message = state.get("text_input", "Bonjour")

    t0 = time.perf_counter()
    try:
        messages = [
            SystemMessage(content=_RESPONSE_SYSTEM),
            HumanMessage(content=user_message),
        ]
        response = llm.invoke(messages)

        latency = time.perf_counter() - t0
        llm_generate_latency_seconds.observe(latency)
        llm_generate_requests_total.labels(status="success").inc()

        logger.info(f"LLM generate [{latency:.2f}s] : '{response.content[:60]}...'")
        return {"response_text": response.content.strip()}

    except Exception as exc:
        latency = time.perf_counter() - t0
        llm_generate_latency_seconds.observe(latency)
        llm_generate_requests_total.labels(status="error").inc()
        logger.error(f"LLM generate erreur [{latency:.2f}s] : {exc}")
        raise


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 6 : Synthèse vocale (texte → audio WAV)
# ═════════════════════════════════════════════════════════════════════════════

def synthesize_speech(state: AgentState) -> dict:
    """
    Appelle le service TTS (piper-tts) pour convertir la réponse en audio.
    Ignoré si skip_tts=True.

    Métriques : tts_latency_seconds, tts_requests_total
    """
    if state.get("skip_tts"):
        tts_requests_total.labels(status="skipped").inc()
        return {}

    response_text = state.get("response_text", "")
    if not response_text:
        return {}

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{settings.tts_service_url}/synthesize",
                json={"text": response_text},
            )
            response.raise_for_status()

        latency = time.perf_counter() - t0
        tts_latency_seconds.observe(latency)
        tts_requests_total.labels(status="success").inc()

        logger.info(f"TTS [{latency:.2f}s] : {len(response.content)} bytes")
        return {"audio_response": response.content}

    except Exception as exc:
        latency = time.perf_counter() - t0
        tts_latency_seconds.observe(latency)
        tts_requests_total.labels(status="error").inc()
        logger.error(f"TTS erreur [{latency:.2f}s] : {exc}")
        return {}  # Pas critique : la réponse texte reste disponible


# ═════════════════════════════════════════════════════════════════════════════
# Fonction de routage conditionnel
# ═════════════════════════════════════════════════════════════════════════════

def route_after_classify(state: AgentState) -> str:
    """
    Détermine le prochain nœud après la classification :
    - "info"     → recherche RAG
    - "commande" → traitement de la commande
    - "autre"    → génération directe de la réponse
    """
    intent = state.get("intent", "autre")

    if intent == "info":
        return "search_rag"
    elif intent in ("commande_simple", "commande_complexe"):
        return "generate_response"
    else:
        return "generate_response"
