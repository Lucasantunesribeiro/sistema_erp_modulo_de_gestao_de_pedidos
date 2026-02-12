"""Auth0 JWT Authentication backend for Django REST Framework.

Uses PyJWT with RS256 asymmetric verification.  JWKS keys are fetched
from the Auth0 tenant and cached in-memory (default 300 s) via
``PyJWKClient`` — no network call on every request.

Security decisions
------------------
* **Fail Closed** — any decode / validation error returns 401.
* ``algorithms`` is hard-coded to the configured value (default RS256).
  Never derived from the incoming token (prevents algorithm-confusion
  attacks like CVE-2024-33663).
* Audience **and** issuer are always validated.
"""

import jwt as pyjwt
import structlog
from decouple import config
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Auth0 settings (read once at module level)
# ---------------------------------------------------------------------------
AUTH0_DOMAIN = config("AUTH0_DOMAIN", default="")
AUTH0_AUDIENCE = config("AUTH0_AUDIENCE", default="")
AUTH0_ALGORITHM = config("AUTH0_ALGORITHM", default="RS256")

_ISSUER = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else ""
_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else ""

# JWKS client with built-in cache (300 s lifespan)
_jwks_client: PyJWKClient | None = None

if _JWKS_URL:
    _jwks_client = PyJWKClient(
        _JWKS_URL,
        cache_jwk_set=True,
        lifespan=300,
    )

_AUTH0_ENABLED = bool(_jwks_client and AUTH0_AUDIENCE and _ISSUER)


class Auth0User:
    """Lightweight user object for requests authenticated via Auth0.

    Auth0 is the source of truth — we do **not** require a local Django
    ``User`` row.  Views can read ``request.user.sub`` / ``.permissions``
    to make authorisation decisions.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.sub: str = payload.get("sub", "")
        self.permissions: list[str] = payload.get("permissions", [])

    # DRF checks
    is_authenticated = True
    is_active = True

    def __str__(self) -> str:  # pragma: no cover
        return self.sub


class Auth0JSONWebTokenAuthentication(BaseAuthentication):
    """DRF authentication class that validates Auth0 JWT Bearer tokens."""

    keyword = "Bearer"

    # ------------------------------------------------------------------
    # Public API (DRF contract)
    # ------------------------------------------------------------------

    def authenticate(self, request):
        """Return ``(Auth0User, token)`` or ``None`` (no credentials)."""
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None  # no credentials — let other backends try

        token = self._extract_token(header)

        # Allow other JWT backends (e.g. SimpleJWT) if Auth0 is not configured
        # or if the token issuer does not match the Auth0 tenant.
        if not _AUTH0_ENABLED:
            return None
        if not self._token_has_auth0_issuer(token):
            return None

        payload = self._decode_token(token)
        user = Auth0User(payload)
        logger.info(
            "jwt_authenticated",
            sub=user.sub,
        )
        return (user, token)

    def authenticate_header(self, request):
        """Value for the ``WWW-Authenticate`` response header on 401."""
        return f'{self.keyword} realm="api"'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_token(header: str) -> str:
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Invalid Authorization header format.")
        return parts[1]

    @staticmethod
    def _token_has_auth0_issuer(token: str) -> bool:
        try:
            payload = pyjwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except PyJWTError:
            return False
        return payload.get("iss") == _ISSUER

    @staticmethod
    def _decode_token(token: str) -> dict:
        if not _jwks_client:
            raise AuthenticationFailed(
                "Auth0 is not configured (AUTH0_DOMAIN missing)."
            )
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=[AUTH0_ALGORITHM],
                audience=AUTH0_AUDIENCE,
                issuer=_ISSUER,
            )
        except PyJWTError as exc:
            logger.warning("jwt_validation_failed", error=str(exc))
            raise AuthenticationFailed(f"Token validation failed: {exc}") from exc
        return payload
