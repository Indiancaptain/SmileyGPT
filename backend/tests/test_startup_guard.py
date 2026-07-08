import pytest

from app.core.config import settings
from app.main import lifespan, app


async def test_startup_fails_with_default_secret_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        async with lifespan(app):
            pass


async def test_startup_succeeds_with_real_secret_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "a-real-randomly-generated-secret")

    async with lifespan(app):
        pass  # should not raise


async def test_startup_succeeds_with_default_secret_in_development(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")

    async with lifespan(app):
        pass  # should not raise — default secret is fine for local dev
