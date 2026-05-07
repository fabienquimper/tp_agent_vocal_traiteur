"""
Nœuds du graphe LangGraph
──────────────────────────
Chaque nœud est une fonction pure :
  - Reçoit l'état complet (AgentState)
  - Retourne un dict partiel avec les champs modifiés

Ordre d'exécution :
  transcribe → classify → [search_rag | process_order] → generate_response → synthesize
"""

import json
import logging

import httpx
from langchain.schema import HumanMessage, SystemMessage

from ..config import settings
from ..rag.retriever import get_retriever
from .state import AgentState

logger = logging.getLogger(__name__)


# ── LLM partagé (instancié une seule fois) ────────────────────────────────────

class _Resp:
    """Réponse minimaliste compatible avec l'interface LangChain (.content)."""
    content: str = ""


def _build_llm():
    """Crée le LLM selon LLM_PROVIDER : Ollama local, HuggingFace ou Groq."""

    if settings.llm_provider == "huggingface":
        from huggingface_hub import InferenceClient
        client = InferenceClient(model=settings.hf_llm_model, token=settings.hf_api_token or None)
        temperature = settings.llm_temperature

        class _HFChatLLM:
            def invoke(self, messages):
                hf_msgs = [
                    {"role": "system" if isinstance(m, SystemMessage) else "user", "content": m.content}
                    for m in messages if isinstance(m, (SystemMessage, HumanMessage))
                ]
                response = client.chat_completion(messages=hf_msgs, max_tokens=512, temperature=temperature)
                r = _Resp()
                r.content = response.choices[0].message.content
                return r

        logger.info(f"[LLM] Provider HuggingFace – modèle : {settings.hf_llm_model}")
        return _HFChatLLM()

    if settings.llm_provider == "groq":
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key or None)
        temperature = settings.llm_temperature

        class _GroqChatLLM:
            def invoke(self, messages):
                groq_msgs = [
                    {"role": "system" if isinstance(m, SystemMessage) else "user", "content": m.content}
                    for m in messages if isinstance(m, (SystemMessage, HumanMessage))
                ]
                response = client.chat.completions.create(
                    model=settings.groq_llm_model,
                    messages=groq_msgs,
                    max_tokens=512,
                    temperature=temperature,
                )
                r = _Resp()
                r.content = response.choices[0].message.content
                return r

        logger.info(f"[LLM] Provider Groq – modèle : {settings.groq_llm_model}")
        return _GroqChatLLM()

    # Provider local via Ollama (défaut)
    from langchain_ollama import ChatOllama
    logger.info(f"[LLM] Provider local (Ollama) – modèle : {settings.llm_model}")
    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
    )


llm = _build_llm()


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 1 : Transcription audio → texte
# ═════════════════════════════════════════════════════════════════════════════

def transcribe_audio(state: AgentState) -> dict:
    """
    Appelle le service STT (Whisper) pour transcrire l'audio en texte.
    Si text_input est déjà renseigné (appel texte direct), passe son tour.
    """
    if not state.get("audio_bytes"):
        # Entrée texte directe : rien à transcrire, on conserve text_input tel quel
        return {"text_input": state.get("text_input", "")}

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{settings.stt_service_url}/transcribe",
                files={"audio": ("audio.wav", state["audio_bytes"], "audio/wav")},
                params={"language": "fr"},
            )
            response.raise_for_status()
            data = response.json()

        transcript = data.get("transcript", "").strip()
        logger.info(f"Transcription : '{transcript}'")
        return {"text_input": transcript}

    except Exception as exc:
        logger.error(f"Erreur STT : {exc}")
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
    """
    text = state.get("text_input", "").strip()

    if not text:
        return {"intent": "autre", "order_items": [], "query_topic": "general"}

    try:
        messages = [
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=text),
        ]
        response = llm.invoke(messages)

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
                f"Commande : {total_units} unités → "
                f"{'complexe' if total_units > threshold else 'simple'} "
                f"(seuil={threshold})"
            )
        else:
            intent = intent_raw

        logger.info(f"Intent='{intent}' topic='{topic}' items={order_items}")
        return {"intent": intent, "order_items": order_items, "query_topic": topic}

    except (json.JSONDecodeError, Exception) as exc:
        logger.error(f"Erreur classification : {exc}")
        return {"intent": "autre", "order_items": [], "query_topic": "general"}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 3 : Recherche RAG dans les fichiers de l'entreprise
# ═════════════════════════════════════════════════════════════════════════════

def search_rag(state: AgentState) -> dict:
    """
    Récupère les passages les plus pertinents dans les fichiers .txt
    (menus.txt, horaires.txt, conges.txt) via ChromaDB + sentence-transformers.
    """
    try:
        retriever = get_retriever()
        docs = retriever.invoke(state["text_input"])
        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        logger.info(f"RAG : {len(docs)} chunks récupérés")
        return {"rag_context": context}
    except Exception as exc:
        logger.error(f"Erreur RAG : {exc}")
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
        # Salutation ou hors-sujet
        user_message = state.get("text_input", "Bonjour")

    messages = [
        SystemMessage(content=_RESPONSE_SYSTEM),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    logger.info(f"Réponse générée : '{response.content[:80]}...'")
    return {"response_text": response.content.strip()}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 6 : Synthèse vocale (texte → audio WAV)
# ═════════════════════════════════════════════════════════════════════════════

def synthesize_speech(state: AgentState) -> dict:
    """
    Appelle le service TTS (piper-tts) pour convertir la réponse en audio.
    Ignoré si skip_tts=True.
    """
    if state.get("skip_tts"):
        return {"audio_response": None}

    response_text = state.get("response_text", "")
    if not response_text:
        return {"audio_response": None}

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{settings.tts_service_url}/synthesize",
                json={"text": response_text},
            )
            response.raise_for_status()

        logger.info(f"Audio synthétisé : {len(response.content)} bytes")
        return {"audio_response": response.content}

    except Exception as exc:
        logger.error(f"Erreur TTS : {exc}")
        return {"audio_response": None}


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
