"""
Configuration centralisée
─────────────────────────
Toutes les valeurs configurables passent par des variables d'environnement
(avec valeurs par défaut pour le développement local).
"""

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Services externes ──────────────────────────────────────────────────────
    ollama_base_url: str = "http://ollama:11434"
    stt_service_url: str = "http://stt:8001"
    tts_service_url: str = "http://tts:8002"

    # ── Modèle LLM ─────────────────────────────────────────────────────────────
    llm_provider: str = "local"        # "local" (Ollama) | "huggingface" | "groq"
    llm_model: str = "mistral"         # Utilisé uniquement si llm_provider=local
    llm_temperature: float = 0.1       # Faible pour des réponses déterministes

    # ── HuggingFace (si llm_provider="huggingface") ────────────────────────────
    # Accepte HF_API_TOKEN, HF_HUB_TOKEN ou HF_TOKEN indifféremment
    hf_api_token: str = Field(
        default="",
        validation_alias=AliasChoices("hf_api_token", "HF_API_TOKEN", "HF_HUB_TOKEN", "HF_TOKEN"),
    )
    hf_llm_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # ── Groq (si llm_provider="groq") ──────────────────────────────────────────
    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("groq_api_key", "GROQ_API_KEY"),
    )
    groq_llm_model: str = "llama-3.1-8b-instant"

    # ── Logique métier ─────────────────────────────────────────────────────────
    # Au-delà de ce seuil (total d'unités), la commande est "complexe"
    order_complexity_threshold: int = 6

    # ── Chemins des données ────────────────────────────────────────────────────
    data_dir: str = "/app/data"
    orders_dir: str = "/app/orders"
    chroma_dir: str = "/app/chroma"

    # ── RAG ────────────────────────────────────────────────────────────────────
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 5          # Nombre de chunks récupérés
    chunk_size: int = 500
    chunk_overlap: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
