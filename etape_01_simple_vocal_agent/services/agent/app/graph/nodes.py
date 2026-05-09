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
from langchain.schema import Document, HumanMessage, SystemMessage

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

# Mots déclenchant un mode "liste complète" → retourner tous les chunks de la section
_LIST_TRIGGERS = {"plats", "entrées", "entrees", "desserts", "formules", "menu", "carte"}
_SECTION_KEYWORDS = {
    "plats":    "PLATS",
    "entrées":  "ENTRÉES",
    "entrees":  "ENTRÉES",
    "desserts": "DESSERTS",
    "formules": "FORMULES",
    "menu":     None,   # None = toutes les sections menu (pas horaires/congés)
    "carte":    None,
}
_MENU_SECTIONS = {"PLATS", "ENTRÉES", "DESSERTS", "FORMULES ÉVÉNEMENTIELLES", "INFORMATIONS IMPORTANTES"}


def search_rag(state: AgentState) -> dict:
    """
    Récupère les passages les plus pertinents via ChromaDB + sentence-transformers.

    Deux enrichissements par rapport à la recherche sémantique pure :
    - Mode "liste généreuse" : si la requête demande une catégorie entière (plats,
      entrées, desserts, menu…), tous les chunks de cette section sont retournés.
    - Fallback mots-clés : si des termes spécifiques (noms de plats rares, termes
      régionaux) sont absents des résultats sémantiques, un scan keyword les ajoute.
    """
    try:
        retriever = get_retriever()
        query = state["text_input"]
        query_lower = query.lower()
        docs = retriever.invoke(query)

        # ── Mode liste généreuse ──────────────────────────────────────────────
        triggered_section: str | None = "NOT_TRIGGERED"
        for trigger, section in _SECTION_KEYWORDS.items():
            if trigger in query_lower:
                triggered_section = section   # None = toutes sections menu
                break

        if triggered_section != "NOT_TRIGGERED":
            try:
                all_data = retriever.vectorstore._collection.get()
                existing_texts = {d.page_content for d in docs}
                for text, meta in zip(all_data["documents"], all_data["metadatas"] or [{}] * len(all_data["documents"])):
                    if text in existing_texts:
                        continue
                    chunk_section = (meta or {}).get("section", "")
                    if triggered_section is None:
                        # Toutes sections du menu (exclut horaires et congés)
                        if chunk_section in _MENU_SECTIONS:
                            docs.append(Document(page_content=text, metadata=meta or {}))
                            existing_texts.add(text)
                    elif triggered_section in chunk_section:
                        docs.append(Document(page_content=text, metadata=meta or {}))
                        existing_texts.add(text)
                logger.info(f"RAG liste généreuse : section={triggered_section or 'menu complet'}")
            except Exception as list_exc:
                logger.warning(f"RAG liste généreuse échoué : {list_exc}")

        # ── Fallback mots-clés ────────────────────────────────────────────────
        # Mots significatifs (>3 chars) absents des résultats : scan direct
        # strip_punct évite "saucisse?" != "saucisse" lors de la comparaison
        query_words = {w.lower().strip("?!.,;:\"'()") for w in query.split()
                       if len(w.strip("?!.,;:\"'()")) > 3}
        existing_text = " ".join(d.page_content.lower() for d in docs)
        missing_words = [w for w in query_words if w not in existing_text]

        if missing_words:
            try:
                all_data = retriever.vectorstore._collection.get()
                existing_texts = {d.page_content for d in docs}
                for text, meta in zip(all_data["documents"], all_data["metadatas"] or [{}] * len(all_data["documents"])):
                    if text in existing_texts:
                        continue
                    if any(w in text.lower() for w in missing_words):
                        docs.append(Document(page_content=text, metadata=meta or {}))
                        existing_texts.add(text)
                logger.info(f"RAG keyword fallback : mots manquants={missing_words}")
            except Exception as kw_exc:
                logger.warning(f"RAG keyword fallback échoué : {kw_exc}")

        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        logger.info(f"RAG : {len(docs)} chunks récupérés au total")
        return {"rag_context": context}
    except Exception as exc:
        logger.error(f"Erreur RAG : {exc}")
        return {"rag_context": ""}


# ═════════════════════════════════════════════════════════════════════════════
# Nœud 5 : Génération de la réponse textuelle
# ═════════════════════════════════════════════════════════════════════════════

_RESPONSE_SYSTEM = """Tu es l'assistant vocal du Traiteur Dupont, une entreprise française de restauration traiteur à Dijon.
Tu réponds en français, avec chaleur et professionnalisme.
N'utilise pas de listes à puces ni de markdown dans ta réponse.
Si le client demande une liste complète (tous les plats, toutes les entrées, tout le menu…), \
cite TOUS les articles disponibles dans le contexte avec leur prix — sois généreux et exhaustif.
Sinon, sois concis : 1 à 3 phrases maximum, car ta réponse sera lue à voix haute."""


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
            f"RÈGLE ABSOLUE : cite uniquement des produits, prix ou informations "
            f"EXPLICITEMENT présents dans le contexte ci-dessus. "
            f"Si un plat ou produit spécifique mentionné par le client n'apparaît pas dans ce contexte, "
            f"réponds : 'Ce produit ne figure pas à notre carte actuelle.' "
            f"Si c'est une question générale (horaires, livraison, allergènes…) sans réponse dans le contexte, "
            f"dis : 'Je n'ai pas cette information, n'hésitez pas à nous appeler.' "
            f"N'invente aucun produit, prix ou détail."
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
