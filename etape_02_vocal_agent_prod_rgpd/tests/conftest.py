import pytest


# Supprime l'avertissement pytest-asyncio sur le loop scope
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: tests nécessitant des appels LLM réels (réseau requis)"
    )
