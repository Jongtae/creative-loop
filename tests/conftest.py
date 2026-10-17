"""Keep tests independent of the user's .env and prevent accidental paid calls."""
import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch):
    for name in ('APP_TOKEN', 'OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_IMAGE_MODEL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('ALLOW_EXTERNAL_AI', '0')
    monkeypatch.setenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver,::1')
    monkeypatch.setenv('MAX_PROVIDER_CALLS_PER_DAY', '20')
