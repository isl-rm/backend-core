from app.core.config import settings

# Token cookie metadata for auth routes.
ACCESS_TOKEN_COOKIE_NAME = "access_token"
ACCESS_TOKEN_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

_samesite = settings.REFRESH_TOKEN_SAMESITE.lower()
if _samesite not in {"lax", "strict", "none"}:
    _samesite = "lax"

ACCESS_TOKEN_SAMESITE = _samesite
REFRESH_TOKEN_SAMESITE = _samesite

# If SameSite=None, cookie spec requires Secure; also require Secure outside local.
ACCESS_TOKEN_SECURE = settings.ENVIRONMENT != "local" or _samesite == "none"
REFRESH_TOKEN_SECURE = settings.ENVIRONMENT != "local" or _samesite == "none"
