from app.core.config import settings

# Refresh token cookie metadata for auth routes.
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

_samesite = settings.REFRESH_TOKEN_SAMESITE.lower()
if _samesite not in {"lax", "strict", "none"}:
    _samesite = "lax"
REFRESH_TOKEN_SAMESITE = _samesite

# If SameSite=None, cookie spec requires Secure; also require Secure outside local.
REFRESH_TOKEN_SECURE = settings.ENVIRONMENT != "local" or _samesite == "none"
