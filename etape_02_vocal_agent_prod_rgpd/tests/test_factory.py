"""Tests de la factory des providers."""

import os
import sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCreateSTTProvider:
    def test_groq_provider_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("STT_PROVIDER", "groq")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        from src.factory import create_stt_provider
        with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
            create_stt_provider()

    def test_groq_provider_instantiates_with_key(self, monkeypatch):
        monkeypatch.setenv("STT_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_fake")
        monkeypatch.setenv("STT_MODEL", "whisper-large-v3-turbo")
        from src.factory import create_stt_provider
        from src.providers.base import STTProvider
        provider = create_stt_provider()
        assert isinstance(provider, STTProvider)
        assert provider.provider_name == "groq"

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("STT_PROVIDER", "unknown_provider")
        from src.factory import create_stt_provider
        with pytest.raises(ValueError, match="STT_PROVIDER inconnu"):
            create_stt_provider()


class TestCreateLLMProvider:
    def test_groq_provider_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        from src.factory import create_llm_provider
        with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
            create_llm_provider()

    def test_groq_provider_instantiates(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_fake")
        monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")
        from src.factory import create_llm_provider
        from src.providers.base import LLMProvider
        provider = create_llm_provider()
        assert isinstance(provider, LLMProvider)
        assert provider.provider_name == "groq"
        assert provider.model_name == "llama-3.1-8b-instant"

    def test_mistral_provider_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mistral")
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from src.factory import create_llm_provider
        with pytest.raises(EnvironmentError, match="MISTRAL_API_KEY"):
            create_llm_provider()

    def test_local_ollama_provider_instantiates(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "local_ollama")
        monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from src.factory import create_llm_provider
        from src.providers.base import LLMProvider
        provider = create_llm_provider()
        assert isinstance(provider, LLMProvider)
        assert provider.provider_name == "local_ollama"
        assert provider.model_name == "qwen2.5:7b"

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
        from src.factory import create_llm_provider
        with pytest.raises(ValueError, match="LLM_PROVIDER inconnu"):
            create_llm_provider()

    def test_default_model_groq(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        from src.factory import create_llm_provider
        provider = create_llm_provider()
        assert provider.model_name == "llama-3.1-8b-instant"
