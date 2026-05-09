"""
RAG – Chargement, indexation et récupération de documents
──────────────────────────────────────────────────────────
Pipeline :
  1. Chargement structuré des fichiers .txt depuis data/
     - Les sections (--- PLATS ---, --- HORAIRES ---) deviennent des préfixes
     - Chaque item (séparé par une ligne vide) devient un chunk distinct
     - Exemple : "[PLATS]\nRougail saucisse des îles et son riz saffrané: 13€"
  2. Calcul des embeddings (sentence-transformers, multilingue)
  3. Stockage dans ChromaDB (persistant sur disque)
  4. Récupération par similarité sémantique à la requête

Le vectorstore est créé au premier démarrage puis rechargé depuis le disque
lors des démarrages suivants (évite de ré-indexer à chaque redémarrage).
"""

import logging
import re
import shutil
from pathlib import Path

from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from ..config import settings

logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────
_vectorstore: Chroma | None = None
_retriever = None

_SECTION_RE = re.compile(r'^---\s*(.+?)\s*---\s*$')
_SEPARATOR_RE = re.compile(r'^=+\s*$')


def _load_structured_documents(data_path: str) -> list[Document]:
    """
    Découpage hiérarchique des fichiers .txt.

    Pour chaque fichier, on exploite les marqueurs de section (--- SECTION ---)
    comme préfixes de contexte, et on crée un chunk par item (délimité par une
    ligne vide). Cela évite de mélanger des items sans rapport dans le même
    vecteur et améliore significativement la précision de la recherche.
    """
    documents: list[Document] = []

    for txt_file in sorted(Path(data_path).glob("**/*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        source = str(txt_file)
        current_section: str | None = None
        current_lines: list[str] = []
        count_before = len(documents)

        def flush() -> None:
            content = "\n".join(current_lines).strip()
            if content and current_section:
                documents.append(Document(
                    page_content=content,
                    metadata={"source": source, "section": current_section},
                ))
            current_lines.clear()

        for line in text.splitlines():
            stripped = line.strip()
            if _SEPARATOR_RE.match(stripped):
                continue
            m = _SECTION_RE.match(stripped)
            if m:
                flush()
                current_section = m.group(1).strip()
                continue
            if not stripped:
                flush()
                continue
            if current_section is None:
                # Titre du fichier (avant la première section) — ignoré
                continue
            current_lines.append(line)

        flush()
        logger.info(f"{txt_file.name} → {len(documents) - count_before} chunks")

    return documents


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Instancie le modèle d'embeddings (sentence-transformers, CPU)."""
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def initialize_vectorstore(force_reload: bool = False) -> Chroma:
    """
    Charge ou crée la base vectorielle ChromaDB.

    - force_reload=False : charge la base existante si elle existe
    - force_reload=True  : re-indexe tous les documents (utile après ajout de fichiers)
    """
    global _vectorstore, _retriever

    chroma_path = settings.chroma_dir
    data_path = settings.data_dir
    embeddings = _get_embeddings()

    # ── Chargement depuis le disque si déjà indexé ────────────────────────────
    if not force_reload and Path(chroma_path).exists():
        logger.info("Chargement du vectorstore existant depuis le disque...")
        _vectorstore = Chroma(
            persist_directory=chroma_path,
            embedding_function=embeddings,
        )
        count = _vectorstore._collection.count()
        logger.info(f"Vectorstore chargé : {count} chunks")
        _retriever = None  # Force la recréation du retriever
        return _vectorstore

    # ── Vidage de l'ancienne collection pour éviter les doublons ─────────────
    if Path(chroma_path).exists():
        try:
            old = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
            old.delete_collection()
            logger.info("Collection ChromaDB vidée")
        except Exception as exc:
            logger.warning(f"Impossible de vider la collection ({exc}) — suppression du dossier")
            shutil.rmtree(chroma_path, ignore_errors=True)

    # ── Indexation depuis les fichiers sources ────────────────────────────────
    logger.info(f"Indexation des documents depuis {data_path}...")

    chunks = _load_structured_documents(data_path)
    logger.info(f"{len(chunks)} chunks créés au total")

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=chroma_path,
    )
    logger.info("Vectorstore créé et persisté sur disque")
    _retriever = None  # Force la recréation du retriever

    # ── Génération du catalogue des prix depuis menus.txt ─────────────────────
    # Import différé pour éviter les imports circulaires au chargement des modules
    try:
        from ..orders.catalog_generator import generate_catalog_from_menu
        from ..orders.catalog import reload_catalog
        generate_catalog_from_menu()
        reload_catalog()
    except Exception as exc:
        logger.warning(f"Génération catalog.json échouée (non bloquant) : {exc}")

    return _vectorstore


def get_retriever():
    """Retourne le retriever (singleton). Initialise si nécessaire."""
    global _retriever, _vectorstore

    if _retriever is None:
        if _vectorstore is None:
            initialize_vectorstore()
        _retriever = _vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.rag_top_k},
        )

    return _retriever
