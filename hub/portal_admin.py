from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Avg, Count

from .models import Designer, DesignerRating, HubAdminUser, HubBrief


class PortalAdminAuthError(Exception):
    """Raised when portal admin auth fails."""


ADMIN_SESSION_KEY = "hub_admin_id"


def authenticate_portal_admin(login: str, password: str) -> HubAdminUser:
    try:
        admin_user = HubAdminUser.objects.get(web_login=login, is_active=True)
    except HubAdminUser.DoesNotExist as exc:
        raise PortalAdminAuthError("Неверный логин или пароль.") from exc
    if not check_password(password, admin_user.web_password_hash):
        raise PortalAdminAuthError("Неверный логин или пароль.")
    return admin_user


def create_designer_account(
    *,
    full_name: str,
    web_login: str,
    password: str,
    sbp_phone: str = "",
    experience_text: str = "",
    portfolio_url: str = "https://example.com",
    max_user_id: str = "",
) -> Designer:
    login = web_login.strip()
    if not login:
        raise ValueError("Логин обязателен.")
    if Designer.objects.filter(web_login=login).exists():
        raise ValueError("Дизайнер с таким логином уже существует.")
    uid = (max_user_id or f"manual-{login}").strip()
    if Designer.objects.filter(max_user_id=uid).exists():
        raise ValueError("Дизайнер с таким max_user_id уже существует.")
    return Designer.objects.create(
        max_user_id=uid,
        full_name=full_name.strip() or login,
        sbp_phone=sbp_phone.strip() or "—",
        experience_text=experience_text.strip() or "Создан администратором",
        portfolio_url=portfolio_url.strip() or "https://example.com",
        web_login=login,
        web_password_hash=make_password(password),
        is_active=True,
    )


def recalculate_designer_rating(designer: Designer) -> None:
    stats = designer.ratings.aggregate(avg=Avg("score"), cnt=Count("id"))
    avg = stats["avg"] or 0
    designer.avg_rating = Decimal(str(avg)).quantize(Decimal("0.01"))
    designer.ratings_count = int(stats["cnt"] or 0)
    designer.save(update_fields=["avg_rating", "ratings_count"])


def upsert_designer_rating(
    *,
    site,
    brief: HubBrief,
    event_id: str,
    score: int,
    comment: str = "",
    rated_by: str = "",
    designer: Designer | None = None,
) -> tuple[DesignerRating, bool]:
    if not 1 <= int(score) <= 5:
        raise ValueError("score must be in range 1..5")
    existing = DesignerRating.objects.filter(event_id=event_id).first()
    if existing:
        return existing, False

    target_designer = designer or brief.designer
    if target_designer is None:
        raise ValueError("Нельзя поставить рейтинг: у заявки нет назначенного дизайнера.")

    rating = DesignerRating.objects.create(
        event_id=event_id,
        brief=brief,
        designer=target_designer,
        site=site,
        score=int(score),
        comment=comment.strip(),
        rated_by=rated_by.strip(),
    )
    recalculate_designer_rating(target_designer)
    return rating, True
