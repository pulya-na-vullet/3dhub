from functools import wraps
from secrets import token_hex

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Designer, DesignerRating, HubAdminUser, HubBrief
from .portal_admin import (
    ADMIN_SESSION_KEY,
    PortalAdminAuthError,
    authenticate_portal_admin,
    create_designer_account,
)


def _require_portal_admin(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        admin_id = request.session.get(ADMIN_SESSION_KEY)
        if not admin_id:
            return redirect("portal-admin-login")
        try:
            admin_user = HubAdminUser.objects.get(id=admin_id, is_active=True)
        except HubAdminUser.DoesNotExist:
            request.session.pop(ADMIN_SESSION_KEY, None)
            return redirect("portal-admin-login")
        request.portal_admin = admin_user
        return view_func(request, *args, **kwargs)

    return _wrapped


def portal_admin_login(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        login = request.POST.get("login", "").strip()
        password = request.POST.get("password", "")
        try:
            admin_user = authenticate_portal_admin(login=login, password=password)
        except PortalAdminAuthError as exc:
            messages.error(request, str(exc))
            return render(request, "hub/portal_admin_login.html", {"login_value": login})
        request.session[ADMIN_SESSION_KEY] = admin_user.id
        return redirect("portal-admin-dashboard")
    return render(request, "hub/portal_admin_login.html")


@_require_portal_admin
def portal_admin_logout(request: HttpRequest) -> HttpResponse:
    request.session.pop(ADMIN_SESSION_KEY, None)
    return redirect("portal-admin-login")


@_require_portal_admin
def portal_admin_dashboard(request: HttpRequest) -> HttpResponse:
    designers = Designer.objects.annotate(done_count=Count("assigned_briefs")).order_by(
        "-avg_rating", "-ratings_count", "full_name"
    )
    recent_ratings = DesignerRating.objects.select_related("designer", "brief", "site").order_by("-created_at")[:20]
    return render(
        request,
        "hub/portal_admin_dashboard.html",
        {
            "portal_admin": request.portal_admin,
            "designers": designers,
            "recent_ratings": recent_ratings,
            "briefs_count": HubBrief.objects.count(),
            "active_designers": Designer.objects.filter(is_active=True).count(),
        },
    )


@_require_portal_admin
def portal_admin_designers(request: HttpRequest) -> HttpResponse:
    if not request.portal_admin.can_manage_users:
        messages.error(request, "Недостаточно прав для управления пользователями.")
        return redirect("portal-admin-dashboard")
    designers = Designer.objects.order_by("-registered_at")
    return render(
        request,
        "hub/portal_admin_designers.html",
        {"portal_admin": request.portal_admin, "designers": designers},
    )


@_require_portal_admin
def portal_admin_designer_create(request: HttpRequest) -> HttpResponse:
    if not request.portal_admin.can_manage_users:
        messages.error(request, "Недостаточно прав для выдачи УЗ.")
        return redirect("portal-admin-dashboard")
    if request.method != "POST":
        return redirect("portal-admin-designers")

    full_name = request.POST.get("full_name", "").strip()
    web_login = request.POST.get("web_login", "").strip()
    password = request.POST.get("password", "").strip() or token_hex(4)
    sbp_phone = request.POST.get("sbp_phone", "").strip()
    try:
        designer = create_designer_account(
            full_name=full_name,
            web_login=web_login,
            password=password,
            sbp_phone=sbp_phone,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("portal-admin-designers")

    messages.success(
        request,
        f"УЗ выдана: логин={designer.web_login}, пароль={password}",
    )
    return redirect("portal-admin-designers")


@_require_portal_admin
def portal_admin_designer_toggle(request: HttpRequest, designer_id: int) -> HttpResponse:
    if not request.portal_admin.can_manage_users:
        messages.error(request, "Недостаточно прав.")
        return redirect("portal-admin-dashboard")
    if request.method != "POST":
        return redirect("portal-admin-designers")
    designer = get_object_or_404(Designer, id=designer_id)
    designer.is_active = not designer.is_active
    designer.save(update_fields=["is_active"])
    state = "активирован" if designer.is_active else "деактивирован"
    messages.success(request, f"Дизайнер {designer.full_name} {state}.")
    return redirect("portal-admin-designers")


@_require_portal_admin
def portal_admin_designer_reset_password(request: HttpRequest, designer_id: int) -> HttpResponse:
    if not request.portal_admin.can_manage_users:
        messages.error(request, "Недостаточно прав.")
        return redirect("portal-admin-dashboard")
    if request.method != "POST":
        return redirect("portal-admin-designers")
    designer = get_object_or_404(Designer, id=designer_id)
    password = request.POST.get("password", "").strip() or token_hex(4)
    designer.web_password_hash = make_password(password)
    designer.save(update_fields=["web_password_hash"])
    messages.success(request, f"Новый пароль для {designer.web_login}: {password}")
    return redirect("portal-admin-designers")


@_require_portal_admin
def portal_admin_designer_delete(request: HttpRequest, designer_id: int) -> HttpResponse:
    if not request.portal_admin.can_manage_users:
        messages.error(request, "Недостаточно прав.")
        return redirect("portal-admin-dashboard")
    if request.method != "POST":
        return redirect("portal-admin-designers")
    designer = get_object_or_404(Designer, id=designer_id)
    name = designer.full_name
    designer.delete()
    messages.success(request, f"Пользователь {name} удалён.")
    return redirect("portal-admin-designers")


@_require_portal_admin
def portal_admin_briefs(request: HttpRequest) -> HttpResponse:
    if not request.portal_admin.can_manage_briefs:
        messages.error(request, "Недостаточно прав для управления заказами.")
        return redirect("portal-admin-dashboard")
    briefs = HubBrief.objects.select_related("site", "designer").order_by("-updated_at")[:200]
    return render(
        request,
        "hub/portal_admin_briefs.html",
        {"portal_admin": request.portal_admin, "briefs": briefs},
    )


@_require_portal_admin
def portal_admin_brief_delete(request: HttpRequest, brief_id: str) -> HttpResponse:
    if not request.portal_admin.can_manage_briefs:
        messages.error(request, "Недостаточно прав.")
        return redirect("portal-admin-dashboard")
    if request.method != "POST":
        return redirect("portal-admin-briefs")
    brief = get_object_or_404(HubBrief, public_id=brief_id)
    number = brief.brief_number
    brief.delete()
    messages.success(request, f"Заказ {number} удалён.")
    return redirect("portal-admin-briefs")
