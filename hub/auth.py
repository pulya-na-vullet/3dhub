import hashlib
import hmac
import time

from .models import SiteNode


class SiteAuthError(Exception):
    """Raised when a SITE request fails signature validation."""


def _extract_bearer_token(header_value: str) -> str:
    prefix = "Bearer "
    if not header_value.startswith(prefix):
        raise SiteAuthError("Authorization header must be Bearer token.")
    return header_value[len(prefix):].strip()


def authenticate_site_request(request) -> SiteNode:
    auth_header = request.headers.get("Authorization", "")
    site_id = request.headers.get("X-Site-Id", "").strip()
    timestamp_raw = request.headers.get("X-Timestamp", "").strip()
    signature = request.headers.get("X-Signature", "").strip().lower()

    if not all([auth_header, site_id, timestamp_raw, signature]):
        raise SiteAuthError("Missing auth headers.")

    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise SiteAuthError("Invalid timestamp.") from exc

    now = int(time.time())
    if abs(now - timestamp) > 300:
        raise SiteAuthError("Timestamp skew too large.")

    token = _extract_bearer_token(auth_header)
    try:
        site = SiteNode.objects.get(site_id=site_id, is_active=True)
    except SiteNode.DoesNotExist as exc:
        raise SiteAuthError("Unknown or inactive site.") from exc

    if token != site.site_token:
        raise SiteAuthError("Invalid token.")

    raw_body = request.body.decode("utf-8")
    signed_payload = f"{timestamp}\n{raw_body}".encode("utf-8")
    expected_signature = hmac.new(
        key=site.site_secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise SiteAuthError("Signature mismatch.")

    return site
