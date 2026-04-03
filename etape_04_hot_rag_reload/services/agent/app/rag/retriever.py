"""
RAG – Hot Reload sans downtime (Étape 04)
──────────────────────────────────────────
Problème de l'étape 03 :
  L'endpoint /api/reload-documents BLOQUE pendant 30s+.
  Pendant ce temps, toutes les requêtes RAG échouent ou retournent l'ancien index.
  → Inacceptable en production.

Solution : Shadow Indexing + Atomic Pointer Swap
  1. Le vectorstore actif continue de servir les requêtes (zéro interruption)
  2. En parallèle (thread background), on construit un nouveau vectorstore
     dans une collection ChromaDB séparée → "shadow"
  3. Quand le shadow est prêt : on échange atomiquement le pointeur Python
     _vectorstore = new_vs  ← une seule instruction = atomique avec le GIL CPython
  4. L'ancien vectorstore reste disponible en mémoire pour rollback

Garanties :
  - Les requêtes en cours sur l'ancien index se terminent normalement
  - Aucune requête ne voit un état intermédiaire (partiellement indexé)
  - En cas d'erreur du rebuild, l'ancien index reste actif

Concept clé — GIL (Global Interpreter Lock) :
  En CPython, l'affectation d'une variable Python est atomique grâce au GIL.
  Un seul thread peut exécuter du bytecode Python à la fois.
  _vectorstore = new_vs  → opcode STORE_GLOBAL = 1 instruction = atomique.
  Aucun autre thread ne peut lire _vectorstore pendant cette instruction.

Analogie production :
  - Elasticsearch : reindex + alias swap
  - Kubernetes : rolling update (nouveau pod prêt avant suppression de l'ancien)
  - Redis : RENAME (atomic key swap)
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from ..config import settings
from ..metrics import (
    rag_active_chunks,
    rag_rebuild_duration_seconds,
    rag_rebuild_in_progress,
    rag_rebuild_total,
)

logger = logging.getLogger(__name__)

# ── Persistance de l'état entre redémarrages ─────────────────────────────────
# On stocke le nom de la collection active dans rag_metadata.json.
# Ainsi, même après un restart, on charge la bonne collection.

_META_FILENAME = "rag_metadata.json"


def _meta_path() -> Path:
    return Path(settings.chroma_dir) / _META_FILENAME


def _load_meta() -> dict:
    p = _meta_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"active": f"traiteur_{int(time.time())}", "prev": None}


def _save_meta(meta: dict):
    _meta_path().parent.mkdir(parents=True, exist_ok=True)
    _meta_path().write_text(json.dumps(meta, indent=2))


# ── État global ───────────────────────────────────────────────────────────────

_vectorstore: Optional[Chroma] = None        # collection active (sert les requêtes)
_prev_vectorstore: Optional[Chroma] = None   # collection précédente (rollback)
_retriever = None
_rebuild_lock = threading.Lock()             # un seul rebuild à la fois


class _RebuildStatus:
    """Données d'état — modifiées uniquement depuis le thread rebuild ou l'init."""
    state: str = "idle"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    active_collection: str = ""
    building_collection: str = ""
    previous_collection: str = ""
    chunks_active: int = 0
    error: Optional[str] = None
    rollback_available: bool = False


_status = _RebuildStatus()


def get_status() -> dict:
    """Retourne l'état du RAG pour l'endpoint /api/rag/status."""
    s = _status
    out: dict = {
        "state": s.state,
        "active_collection": s.active_collection,
        "chunks_active": s.chunks_active,
        "rollback_available": s.rollback_available,
    }
    if s.started_at:
        out["started_at"] = s.started_at
        if s.state == "rebuilding":
            out["elapsed_s"] = round(time.time() - s.started_at, 1)
    if s.completed_at and s.started_at:
        out["completed_at"] = s.completed_at
        out["duration_s"] = round(s.completed_at - s.started_at, 1)
    if s.previous_collection:
        out["previous_collection"] = s.previous_collection
    if s.error:
        out["error"] = s.error
    return out


# ── Helpers internes ──────────────────────────────────────────────────────────

def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _count_chunks(vs: Chroma) -> int:
    try:
        return vs._collection.count()
    except Exception:
        return 0


def _build_collection(collection_name: str, data_path: str) -> Chroma:
    """
    Construit une collection ChromaDB depuis les fichiers .txt.
    Peut prendre 20-60s selon le volume — appelée dans un thread background.
    """
    logger.info(f"[shadow] Indexation → '{collection_name}'...")

    loader = DirectoryLoader(
        data_path,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
    )
    documents = loader.load()
    logger.info(f"[shadow]   {len(documents)} fichiers chargés")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    logger.info(f"[shadow]   {len(chunks)} chunks créés")

    vs = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        persist_directory=settings.chroma_dir,
        collection_name=collection_name,
    )
    logger.info(f"[shadow]   Collection prête ({len(chunks)} chunks)")
    return vs


def _atomic_swap(new_vs: Chroma, new_name: str):
    """
    Échange atomiquement le pointeur vers le vectorstore actif.

    POURQUOI C'EST ATOMIQUE :
      L'affectation `_vectorstore = new_vs` est compilée en un seul opcode
      Python (STORE_GLOBAL). Le GIL garantit qu'aucun autre thread ne peut
      s'intercaler entre deux opcodes. Résultat :
        - Thread A (requête) : lit soit l'ancien, soit le nouveau → jamais les deux
        - Thread B (rebuild) : effectue le swap en 1 opération

    CE QUI SE PASSE PENDANT LE SWAP (< 1µs) :
        requêtes en cours → finissent sur l'ancien vectorstore (toujours en mémoire)
        nouvelles requêtes → partent sur le nouveau vectorstore immédiatement
    """
    global _vectorstore, _prev_vectorstore, _retriever

    old_vs = _vectorstore

    # ══════════════════════════════════════
    _prev_vectorstore = old_vs   # rollback
    _vectorstore = new_vs        # ← SWAP ATOMIQUE
    _retriever = None
    # ══════════════════════════════════════

    logger.info(f"Atomic swap : '{_status.active_collection}' → '{new_name}'")


# ── API publique ──────────────────────────────────────────────────────────────

def initialize_vectorstore(force_reload: bool = False) -> Chroma:
    """Chargement initial synchrone (au démarrage de l'agent)."""
    global _vectorstore, _retriever

    meta = _load_meta()
    collection_name = meta["active"]
    chroma_path = settings.chroma_dir

    # Charger depuis le disque si déjà indexé
    if not force_reload and Path(chroma_path).exists():
        try:
            vs = Chroma(
                persist_directory=chroma_path,
                embedding_function=_get_embeddings(),
                collection_name=collection_name,
            )
            count = _count_chunks(vs)
            if count > 0:
                _vectorstore = vs
                _retriever = None
                _status.active_collection = collection_name
                _status.chunks_active = count
                _status.previous_collection = meta.get("prev") or ""
                rag_active_chunks.set(count)
                logger.info(f"Vectorstore chargé : {count} chunks ('{collection_name}')")
                return _vectorstore
        except Exception as exc:
            logger.warning(f"Chargement impossible : {exc} → réindexation")

    # Première indexation (synchrone)
    logger.info("Indexation initiale (synchrone, peut prendre ~30s)...")
    _vectorstore = _build_collection(collection_name, settings.data_dir)
    count = _count_chunks(_vectorstore)
    _status.active_collection = collection_name
    _status.chunks_active = count
    _retriever = None
    _save_meta({"active": collection_name, "prev": None})
    rag_active_chunks.set(count)
    return _vectorstore


def rebuild_in_background() -> bool:
    """
    Démarre un rebuild shadow en tâche de fond. Non-bloquant.

    Retourne True si le rebuild a démarré.
    Retourne False si un rebuild est déjà en cours.

    Workflow :
      appel API → acquire lock → lance thread → retourne immédiatement (< 1ms)
                                     ↓ (background, 20-60s)
                               build shadow collection
                                     ↓
                               atomic swap
                                     ↓
                               release lock + mise à jour métriques
    """
    if not _rebuild_lock.acquire(blocking=False):
        return False  # rebuild déjà en cours

    _status.state = "rebuilding"
    _status.started_at = time.time()
    _status.error = None
    rag_rebuild_in_progress.set(1)

    threading.Thread(
        target=_rebuild_worker,
        daemon=True,
        name="rag-shadow-rebuild",
    ).start()

    logger.info("Thread shadow rebuild démarré")
    return True


def _rebuild_worker():
    """Thread background : shadow index → atomic swap → metrics."""
    new_name = f"traiteur_{int(time.time())}"
    _status.building_collection = new_name
    t0 = time.time()

    try:
        # Phase 1 : construction shadow (le vectorstore actif sert toujours les requêtes)
        new_vs = _build_collection(new_name, settings.data_dir)
        new_count = _count_chunks(new_vs)

        # Phase 2 : atomic swap
        old_name = _status.active_collection
        _atomic_swap(new_vs, new_name)

        # Phase 3 : état + persistance + métriques
        duration = time.time() - t0
        _status.state = "done"
        _status.completed_at = time.time()
        _status.previous_collection = old_name
        _status.active_collection = new_name
        _status.chunks_active = new_count
        _status.rollback_available = True

        _save_meta({"active": new_name, "prev": old_name})

        rag_rebuild_duration_seconds.observe(duration)
        rag_rebuild_total.labels(status="success").inc()
        rag_active_chunks.set(new_count)
        rag_rebuild_in_progress.set(0)

        logger.info(f"Rebuild terminé ({duration:.1f}s) : {new_count} chunks dans '{new_name}'")

    except Exception as exc:
        duration = time.time() - t0
        _status.state = "error"
        _status.error = str(exc)
        _status.building_collection = ""

        rag_rebuild_duration_seconds.observe(duration)
        rag_rebuild_total.labels(status="error").inc()
        rag_rebuild_in_progress.set(0)

        logger.error(f"Rebuild erreur ({duration:.1f}s) : {exc}", exc_info=True)

    finally:
        _rebuild_lock.release()


def rollback_vectorstore() -> bool:
    """
    Revient à la collection précédente. Utilise le même atomic swap.
    Disponible seulement si un rebuild a été effectué et rollback_available=True.
    """
    global _vectorstore, _prev_vectorstore, _retriever

    if not _prev_vectorstore or not _status.rollback_available:
        return False

    prev_name = _status.previous_collection
    curr_name = _status.active_collection

    # ══════════════════════════════════════
    _vectorstore = _prev_vectorstore   # ← ROLLBACK ATOMIQUE
    _prev_vectorstore = None
    _retriever = None
    # ══════════════════════════════════════

    new_count = _count_chunks(_vectorstore)

    _status.active_collection = prev_name
    _status.previous_collection = curr_name
    _status.rollback_available = False
    _status.state = "idle"
    _status.chunks_active = new_count

    _save_meta({"active": prev_name, "prev": None})

    rag_active_chunks.set(new_count)
    rag_rebuild_total.labels(status="rollback").inc()

    logger.info(f"Rollback : '{curr_name}' → '{prev_name}' ({new_count} chunks)")
    return True


def get_retriever():
    """Retourne le retriever actif. Thread-safe grâce au GIL."""
    global _retriever

    if _vectorstore is None:
        initialize_vectorstore()

    if _retriever is None:
        _retriever = _vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.rag_top_k},
        )

    return _retriever
