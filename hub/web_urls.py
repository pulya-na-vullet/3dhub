from django.urls import path
from django.views.generic.base import RedirectView

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
    path("designer/briefs/<str:brief_id>", designer_brief_detail_page, name="designer-web-brief-detail"),
    path(
        "designer/briefs/<str:brief_id>/update",
        designer_brief_update_page,
        name="designer-web-brief-update",
    ),
]
