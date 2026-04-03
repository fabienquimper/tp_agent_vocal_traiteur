"""
Configuration centralisée
─────────────────────────
Toutes les valeurs configurables passent par des variables d'environnement
(avec valeurs par défaut pour le développement local).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Services externes ──────────────────────────────────────────────────────
    ollama_base_url: str = "http://ollama:11434"
    stt_service_url: str = "http://stt:8001"
    tts_service_url: str = "http://tts:8002"

    # ── Modèle LLM ─────────────────────────────────────────────────────────────
    llm_model: str = "mistral"
    llm_temperature: float = 0.1  # Faible pour des réponses déterministes

    # ── Logique métier ─────────────────────────────────────────────────────────
    # Au-delà de ce seuil (total d'unités), la commande est "complexe"
    order_complexity_threshold: int = 6

    # ── Chemins des données ────────────────────────────────────────────────────
    data_dir: str = "/app/data"
    orders_dir: str = "/app/orders"
    chroma_dir: str = "/app/chroma"

    # ── RAG ────────────────────────────────────────────────────────────────────
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 3          # Nombre de chunks récupérés
    chunk_size: int = 500
    chunk_overlap: int = 50

    # ── Quality Gate (étape 05) ────────────────────────────────────────────────
    # Taux de hit minimum pour valider un rebuild shadow.
    # Si hit_rate < rag_quality_threshold → swap ANNULÉ, ancien index conservé.
    # hit_rate = (requêtes avec ≥1 chunk retourné) / total requêtes d'évaluation
    rag_quality_threshold: float = 0.8  # 80% minimum

    # Répertoire du jeu d'évaluation (rag_quality_eval.json)
    eval_dir: str = "/app/eval"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
