from datetime import timedelta
from secrets import token_urlsafe

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from .models import Designer, DesignerSessionToken


class DesignerAuthError(Exception):
    """Raised when designer auth fails."""


def authenticate_designer_credentials(login: str, password: str) -> Designer:
    try:
        designer = Designer.objects.get(web_login=login, is_active=True)
    except Designer.DoesNotExist as exc:
        raise DesignerAuthError("Неверный логин или пароль.") from exc

    if not check_password(password, designer.web_password_hash):
        raise DesignerAuthError("Неверный логин или пароль.")

    return designer


def create_designer_session(login: str, password: str) -> tuple[Designer, DesignerSessionToken]:
    designer = authenticate_designer_credentials(login=login, password=password)

    token = DesignerSessionToken.objects.create(
        key=token_urlsafe(32),
        designer=designer,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return designer, token


def authenticate_designer(request) -> Designer:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise DesignerAuthError("Требуется Bearer токен.")
    token_key = auth_header.replace("Bearer ", "", 1).strip()
    now = timezone.now()
    try:
        token = DesignerSessionToken.objects.select_related("designer").get(
            key=token_key,
            is_revoked=False,
            expires_at__gt=now,
        )
    except DesignerSessionToken.DoesNotExist as exc:
        raise DesignerAuthError("Сессия недействительна или истекла.") from exc
    if not token.designer.is_active:
        raise DesignerAuthError("Пользователь деактивирован.")
    return token.designer
