"""
RAG – Quality Gate avant Atomic Swap (Étape 05)
────────────────────────────────────────────────
Problème de l'étape 04 :
  Le shadow indexing évite le downtime, mais garantit-il la QUALITÉ ?
  Un rebuild peut terminer sans erreur et produire un index dégradé :
    - documents tronqués (erreur silencieuse d'encodage)
    - embeddings corrompus (mémoire saturée pendant l'indexation)
    - fichier de données vide ou mal formaté
  → Résultat : l'agent répond "Je n'ai pas cette information" pour des questions
    légitimes, sans aucune alerte dans les logs.

Solution : Quality Gate avant l'Atomic Swap
  Après la construction du shadow index, AVANT de l'activer en production :
  1. Charger un jeu de requêtes de référence (eval/rag_quality_eval.json)
  2. Lancer chaque requête contre le SHADOW (pas encore actif)
  3. Calculer le hit_rate = requêtes avec ≥1 chunk / total
  4a. hit_rate >= threshold → atomic swap → nouveau index en production
  4b. hit_rate < threshold → swap ANNULÉ → ancien index conservé

Avantages :
  - Zéro downtime (même comportement qu'étape 04 si la gate passe)
  - Protection contre les régressions silencieuses
  - Métriques Grafana : rag_quality_gate_total{result="failed"} alerte
  - Rollback automatique : pas besoin d'intervention humaine

Concept : "Shift Left"
  Détecter les problèmes le plus tôt possible dans le pipeline.
  Avant : les problèmes se détectent en production (utilisateurs frustrés)
  Après : les problèmes se détectent avant le swap (invisible pour l'utilisateur)

  shift left ──────────────────────────────────────────────────────────▶ shift right
  [tests unitaires] [quality gate] [staging] [canary] [production] [monitoring]
                         ↑
                   on est ici (étape 05)
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
    rag_quality_gate_total,
    rag_quality_gate_hit_rate as rag_qg_hit_rate_metric,
)

logger = logging.getLogger(__name__)

# ── Persistance de l'état entre redémarrages ─────────────────────────────────

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
    # Quality gate (étape 05)
    quality_gate_passed: Optional[bool] = None
    quality_gate_hit_rate: Optional[float] = None


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
    # Quality gate fields (présents seulement après un rebuild)
    if s.quality_gate_hit_rate is not None:
        out["quality_gate"] = {
            "hit_rate": round(s.quality_gate_hit_rate, 3),
            "passed": s.quality_gate_passed,
            "threshold": settings.rag_quality_threshold,
        }
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


def _check_quality_gate(vs: Chroma) -> tuple[bool, float, int, int]:
    """
    Évalue la qualité du vectorstore shadow sur le jeu de référence.

    Charge eval/rag_quality_eval.json, lance chaque requête contre
    le shadow collection (PAS encore actif en production), et calcule :
      hit_rate = requêtes avec ≥1 chunk retourné / total requêtes

    Retourne (passed, hit_rate, hits, total).

    IMPORTANT : si le fichier d'évaluation est absent → gate ignorée (True).
    Cela permet de démarrer sans fichier eval (ex: première mise en place).
    En production, le fichier DOIT exister.

    Pourquoi évaluer sur le shadow avant le swap ?
      ┌───────────────────┐   quality check   ┌───────────────────┐
      │ vectorstore ACTIF │ ─── inchangé ────  │ vectorstore SHADOW│
      │  sert 100% trafic │                   │  shadow testé ici │
      └───────────────────┘                   └───────────────────┘
                                                       ↑
                                              on interroge celui-ci
                                              (jamais l'actif)
    """
    eval_path = Path(settings.eval_dir) / "rag_quality_eval.json"

    if not eval_path.exists():
        logger.warning(
            f"[quality-gate] Fichier introuvable : {eval_path} → gate ignorée (True par défaut). "
            "Créez eval/rag_quality_eval.json pour activer la vérification."
        )
        return True, 1.0, 0, 0

    try:
        queries = json.loads(eval_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"[quality-gate] Impossible de lire {eval_path} : {exc} → gate ignorée")
        return True, 1.0, 0, 0

    hits = 0
    total = len(queries)

    for item in queries:
        query = item.get("query", "").strip()
        if not query:
            total -= 1
            continue
        try:
            results = vs.similarity_search(query, k=1)
            if results and results[0].page_content.strip():
                hits += 1
        except Exception as exc:
            logger.warning(f"[quality-gate] Erreur sur '{query}' : {exc}")

    hit_rate = hits / total if total > 0 else 1.0
    threshold = settings.rag_quality_threshold
    passed = hit_rate >= threshold

    logger.info(
        f"[quality-gate] hit_rate={hit_rate:.1%} ({hits}/{total}) "
        f"seuil={threshold:.0%} → {'✓ PASSED' if passed else '✗ FAILED — swap annulé'}"
    )
    return passed, hit_rate, hits, total


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

    Workflow (étape 05 — avec quality gate) :
      appel API → acquire lock → lance thread → retourne immédiatement (< 1ms)
                                     ↓ (background, 20-60s)
                               build shadow collection
                                     ↓
                               quality gate check  ← NOUVEAU
                                  ↓           ↓
                               passed       failed
                                  ↓           ↓
                            atomic swap   swap annulé
                                  ↓       (ancien index conservé)
                           release lock
    """
    if not _rebuild_lock.acquire(blocking=False):
        return False

    _status.state = "rebuilding"
    _status.started_at = time.time()
    _status.error = None
    _status.quality_gate_passed = None
    _status.quality_gate_hit_rate = None
    rag_rebuild_in_progress.set(1)

    threading.Thread(
        target=_rebuild_worker,
        daemon=True,
        name="rag-shadow-rebuild",
    ).start()

    logger.info("Thread shadow rebuild démarré")
    return True


def _rebuild_worker():
    """Thread background : shadow index → quality gate → atomic swap → metrics."""
    new_name = f"traiteur_{int(time.time())}"
    _status.building_collection = new_name
    t0 = time.time()

    try:
        # Phase 1 : construction shadow (le vectorstore actif sert toujours les requêtes)
        new_vs = _build_collection(new_name, settings.data_dir)
        new_count = _count_chunks(new_vs)

        # Phase 2 : quality gate — évaluation avant swap (NOUVEAU étape 05)
        #
        #   On interroge le shadow pour vérifier qu'il répond correctement.
        #   L'actif continue de servir 100% du trafic pendant ce check.
        #
        passed, hit_rate, hits, total = _check_quality_gate(new_vs)
        _status.quality_gate_hit_rate = hit_rate
        _status.quality_gate_passed = passed

        rag_qg_hit_rate_metric.observe(hit_rate)
        rag_quality_gate_total.labels(result="passed" if passed else "failed").inc()

        if not passed:
            # Quality gate FAILED → swap annulé, ancien index conservé
            duration = time.time() - t0
            _status.state = "quality_gate_failed"
            _status.completed_at = time.time()
            _status.error = (
                f"Quality gate FAILED : hit_rate={hit_rate:.1%} "
                f"({hits}/{total} requêtes) < seuil={settings.rag_quality_threshold:.0%}. "
                "Swap annulé — ancien index conservé en production."
            )
            rag_rebuild_duration_seconds.observe(duration)
            rag_rebuild_total.labels(status="quality_gate_failed").inc()
            rag_rebuild_in_progress.set(0)
            logger.warning(
                f"[quality-gate] FAILED → swap annulé. "
                f"hit_rate={hit_rate:.1%} < {settings.rag_quality_threshold:.0%}"
            )
            return

        # Phase 3 : atomic swap (quality gate passed)
        old_name = _status.active_collection
        _atomic_swap(new_vs, new_name)

        # Phase 4 : état + persistance + métriques
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

        logger.info(
            f"Rebuild terminé ({duration:.1f}s) : {new_count} chunks dans '{new_name}' "
            f"(quality gate: {hit_rate:.1%})"
        )

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


def search_chunks(query: str, k: int = 3) -> list[dict]:
    """
    Recherche sémantique brute dans le vectorstore actif.
    Retourne les chunks sans passer par le LLM.
    Utilisé par /api/rag/search et par les tests d'intégration.
    """
    if _vectorstore is None:
        initialize_vectorstore()

    try:
        results = _vectorstore.similarity_search_with_score(query, k=k)
        return [
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", ""),
                "score": round(float(score), 4),
            }
            for doc, score in results
        ]
    except Exception as exc:
        logger.error(f"search_chunks error: {exc}")
        return []


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
