"""
Point d'entrée FastAPI – Agent Vocal Traiteur
──────────────────────────────────────────────
Expose deux modes d'interaction :
  POST /api/voice  → entrée audio (WAV/MP3) → réponse JSON + audio base64
  POST /api/text   → entrée texte           → réponse JSON (+ audio optionnel)
  POST /api/reload-documents → re-indexe les fichiers data/
  GET  /health     → état de santé du service
"""

import base64
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .graph.workflow import get_graph
from .graph.state import AgentState
from .rag.retriever import initialize_vectorstore, get_retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ── Initialisation au démarrage ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base vectorielle et compile le graphe au démarrage."""
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


# ── Application FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Traiteur Dupont – Agent Vocal IA",
    description="Agent conversationnel vocal basé sur LangGraph + Ollama (Mistral)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # À restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schémas de requête/réponse ────────────────────────────────────────────────

class TextRequest(BaseModel):
    text: str
    skip_tts: bool = False  # True = mode texte pur (sans synthèse vocale)


class AgentResponse(BaseModel):
    transcript: str          # Texte de la question (original ou transcrit)
    intent: str              # Intent détecté
    order_items: list        # Articles commandés (vide si intent != commande)
    response_text: str       # Réponse textuelle de l'agent
    audio_base64: Optional[str] = None  # Audio WAV encodé en base64 (si TTS activé)
    is_error: bool = False   # True si la réponse est un message d'erreur technique


# ── Détection des erreurs Ollama ──────────────────────────────────────────────

def _is_ollama_unavailable(exc: Exception) -> bool:
    """Détecte si l'exception est due à Ollama inaccessible (parcourt toute la chaîne)."""
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
    """Retourne une réponse lisible en cas d'erreur interne."""
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
        transcript=transcript,
        intent="",
        order_items=[],
        response_text=message,
        audio_base64=None,
        is_error=True,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _state_to_response(result: AgentState) -> AgentResponse:
    audio_b64 = None
    if result.get("audio_response"):
        audio_b64 = base64.b64encode(result["audio_response"]).decode("utf-8")

    return AgentResponse(
        transcript=result.get("text_input", ""),
        intent=result.get("intent", ""),
        order_items=result.get("order_items", []),
        response_text=result.get("response_text", ""),
        audio_base64=audio_b64,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}


@app.post("/api/voice", response_model=AgentResponse)
async def process_voice(
    audio: UploadFile = File(..., description="Fichier audio (WAV, MP3, OGG…)"),
):
    """
    Traite une entrée vocale :
      1. Transcription via le service STT (Whisper)
      2. Exécution du graphe LangGraph
      3. Synthèse vocale de la réponse
    Retourne la transcription, l'intent, et la réponse texte + audio base64.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    graph = get_graph()
    initial_state = _build_initial_state(audio_bytes=audio_bytes)

    try:
        result = graph.invoke(initial_state)
        return _state_to_response(result)
    except Exception as exc:
        logger.error(f"Erreur traitement vocal : {exc}", exc_info=True)
        return _friendly_error_response(initial_state.get("text_input", ""), exc)


@app.post("/api/text", response_model=AgentResponse)
async def process_text(request: TextRequest):
    """
    Traite une entrée textuelle :
      1. Exécution du graphe LangGraph (sans transcription)
      2. Optionnellement, synthèse vocale de la réponse
    Retourne l'intent, la réponse texte, et optionnellement l'audio base64.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    graph = get_graph()
    initial_state = _build_initial_state(
        text_input=request.text,
        skip_tts=request.skip_tts,
    )

    try:
        result = graph.invoke(initial_state)
        return _state_to_response(result)
    except Exception as exc:
        logger.error(f"Erreur traitement texte : {exc}", exc_info=True)
        return _friendly_error_response(request.text, exc)


@app.get("/api/status")
async def get_status():
    """Vérifie l'état de tous les services (Ollama, STT, TTS, RAG)."""
    from .config import settings as cfg

    results: dict = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Ollama
        try:
            r = await client.get(f"{cfg.ollama_base_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            results["ollama"] = {"status": "ok", "models": models}
        except Exception as exc:
            results["ollama"] = {"status": "error", "error": str(exc)}

        # STT
        try:
            r = await client.get(f"{cfg.stt_service_url}/health")
            results["stt"] = {"status": "ok" if r.is_success else "error"}
        except Exception as exc:
            results["stt"] = {"status": "error", "error": str(exc)}

        # TTS
        try:
            r = await client.get(f"{cfg.tts_service_url}/health")
            results["tts"] = {"status": "ok" if r.is_success else "error"}
        except Exception as exc:
            results["tts"] = {"status": "error", "error": str(exc)}

    # RAG chunk count
    try:
        count = get_retriever().vectorstore._collection.count()
        results["rag"] = {"status": "ok", "chunks": count}
    except Exception as exc:
        results["rag"] = {"status": "error", "error": str(exc)}

    overall = "ok" if all(v["status"] == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}


@app.post("/api/reload-documents")
async def reload_documents():
    """
    Force la re-indexation de tous les fichiers du dossier data/.
    Utile après ajout ou modification d'un fichier .txt.
    """
    try:
        from .rag import retriever as retriever_module
        retriever_module._retriever = None
        retriever_module._vectorstore = None
        initialize_vectorstore(force_reload=True)
        count = get_retriever().vectorstore._collection.count()
        return {"status": "ok", "message": f"Documents re-indexés ({count} chunks)"}
    except Exception as exc:
        logger.error(f"Erreur reload documents : {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
