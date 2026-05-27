"""
Factory — lit les variables d'env et instancie le bon provider.
Un seul endroit dans la codebase où le choix de provider est fait.
"""

import os
from .providers.base import STTProvider, LLMProvider
from .logging_config import get_logger

logger = get_logger(__name__)

_MASK_VISIBLE = 4


def _mask(value: str) -> str:
    if not value:
        return "(non défini)"
    if len(value) <= _MASK_VISIBLE * 2:
        return "*" * len(value)
    return f"{value[:_MASK_VISIBLE]}...{value[-_MASK_VISIBLE:]}"


def create_stt_provider() -> STTProvider:
    provider = os.getenv("STT_PROVIDER", "groq").lower()
    model = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY est requis pour STT_PROVIDER=groq")
        from .providers.stt_groq import GroqSTTProvider
        logger.info("stt_provider_init", provider="groq", model=model, api_key=_mask(api_key))
        return GroqSTTProvider(api_key=api_key, model=model)

    if provider == "local_ollama":
        # WHISPER_MODEL = taille faster-whisper (tiny/base/small/medium/large-v2/large-v3)
        # STT_MODEL est réservé aux providers cloud (groq, lms)
        whisper_model = os.getenv("WHISPER_MODEL", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        from .providers.stt_local_ollama import LocalOllamaSTTProvider
        logger.info("stt_provider_init", provider="local_ollama", model=whisper_model, device=device)
        return LocalOllamaSTTProvider(model_size=whisper_model, device=device)

    if provider == "local_lms":
        base_url = os.getenv("LMS_BASE_URL", "http://host.docker.internal:1234")
        from .providers.stt_local_lms import LocalLMSSTTProvider
        logger.info("stt_provider_init", provider="local_lms", base_url=base_url)
        return LocalLMSSTTProvider(base_url=base_url, model=model)

    raise ValueError(f"STT_PROVIDER inconnu : '{provider}'. Valeurs valides : groq, local_ollama, local_lms")


def create_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "local_ollama").lower()
    model = os.getenv("LLM_MODEL", "")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY est requis pour LLM_PROVIDER=groq")
        _model = model or "llama-3.1-8b-instant"
        from .providers.llm_groq import GroqLLMProvider
        logger.info("llm_provider_init", provider="groq", model=_model, api_key=_mask(api_key))
        return GroqLLMProvider(api_key=api_key, model=_model, temperature=temperature)

    if provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY", "")
        if not api_key:
            raise EnvironmentError("MISTRAL_API_KEY est requis pour LLM_PROVIDER=mistral")
        _model = model or "mistral-small-latest"
        from .providers.llm_mistral import MistralLLMProvider
        logger.info("llm_provider_init", provider="mistral", model=_model, api_key=_mask(api_key))
        return MistralLLMProvider(api_key=api_key, model=_model, temperature=temperature)

    if provider == "local_ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        _model = model or "qwen2.5:7b"
        from .providers.llm_local_ollama import LocalOllamaLLMProvider
        logger.info("llm_provider_init", provider="local_ollama", model=_model, base_url=base_url)
        return LocalOllamaLLMProvider(base_url=base_url, model=_model, temperature=temperature)

    if provider == "local_lms":
        base_url = os.getenv("LMS_BASE_URL", "http://host.docker.internal:1234")
        _model = model or "local-model"
        from .providers.llm_local_lms import LocalLMSLLMProvider
        logger.info("llm_provider_init", provider="local_lms", model=_model, base_url=base_url)
        return LocalLMSLLMProvider(base_url=base_url, model=_model, temperature=temperature)

    raise ValueError(f"LLM_PROVIDER inconnu : '{provider}'. Valeurs valides : groq, mistral, local_ollama, local_lms")
