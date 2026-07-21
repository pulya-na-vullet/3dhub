from django.urls import path
from django.views.generic.base import RedirectView

from .portal_admin_views import (
    portal_admin_brief_delete,
    portal_admin_briefs,
    portal_admin_dashboard,
    portal_admin_designer_create,
    portal_admin_designer_delete,
    portal_admin_designer_reset_password,
    portal_admin_designer_toggle,
    portal_admin_designers,
    portal_admin_login,
    portal_admin_logout,
)
from .views import (
    designer_brief_detail_page,
    designer_brief_update_page,
    designer_claim_page,
    designer_login_page,
    designer_logout,
    designer_queue_page,
)

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="designer-web-login", permanent=False)),
    path("designer/login", designer_login_page, name="designer-web-login"),
    path("designer/logout", designer_logout, name="designer-web-logout"),
    path("designer/queue", designer_queue_page, name="designer-web-queue"),
    path("designer/briefs/<str:brief_id>/claim", designer_claim_page, name="designer-web-claim"),
    path(
        "designer/briefs/<str:brief_id>/update",
        designer_brief_update_page,
        name="designer-web-brief-update",
    ),
    path("designer/briefs/<str:brief_id>", designer_brief_detail_page, name="designer-web-brief-detail"),
    path("portal-admin/login", portal_admin_login, name="portal-admin-login"),
    path("portal-admin/logout", portal_admin_logout, name="portal-admin-logout"),
    path("portal-admin/", portal_admin_dashboard, name="portal-admin-dashboard"),
    path("portal-admin/designers", portal_admin_designers, name="portal-admin-designers"),
    path(
        "portal-admin/designers/create",
        portal_admin_designer_create,
        name="portal-admin-designer-create",
    ),
    path(
        "portal-admin/designers/<int:designer_id>/toggle",
        portal_admin_designer_toggle,
        name="portal-admin-designer-toggle",
    ),
    path(
        "portal-admin/designers/<int:designer_id>/reset-password",
        portal_admin_designer_reset_password,
        name="portal-admin-designer-reset",
    ),
    path(
        "portal-admin/designers/<int:designer_id>/delete",
        portal_admin_designer_delete,
        name="portal-admin-designer-delete",
    ),
    path("portal-admin/briefs", portal_admin_briefs, name="portal-admin-briefs"),
    path(
        "portal-admin/briefs/<str:brief_id>/delete",
        portal_admin_brief_delete,
        name="portal-admin-brief-delete",
    ),
]
