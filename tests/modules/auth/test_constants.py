import importlib

from app.core import config
import app.modules.auth.constants as constants


def test_refresh_cookie_defaults_to_lax_when_invalid(monkeypatch):
    original_settings = config.settings
    temp_settings = config.Settings(
        REFRESH_TOKEN_SAMESITE="invalid", ENVIRONMENT=original_settings.ENVIRONMENT
    )
    monkeypatch.setattr(config, "settings", temp_settings)

    reloaded = importlib.reload(constants)

    assert reloaded.REFRESH_TOKEN_SAMESITE == "lax"
    assert reloaded.REFRESH_TOKEN_SECURE is (temp_settings.ENVIRONMENT != "local")

    config.settings = original_settings
    importlib.reload(constants)
