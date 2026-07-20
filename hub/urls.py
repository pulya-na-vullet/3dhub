from django.urls import path

from .views import (
    BriefDetailView,
    BriefListCreateView,
    BriefMessageView,
    DesignerBriefClaimView,
    DesignerBriefQueueView,
    DesignerLoginView,
    MaxWebhookView,
)

urlpatterns = [
    path("briefs", BriefListCreateView.as_view(), name="brief-create"),
    path("briefs/<str:brief_id>", BriefDetailView.as_view(), name="brief-detail"),
    path("briefs/<str:brief_id>/messages", BriefMessageView.as_view(), name="brief-message"),
    path("max/webhook", MaxWebhookView.as_view(), name="max-webhook"),
    path("designer/auth/login", DesignerLoginView.as_view(), name="designer-login"),
    path("designer/briefs", DesignerBriefQueueView.as_view(), name="designer-briefs"),
    path("designer/briefs/<str:brief_id>/claim", DesignerBriefClaimView.as_view(), name="designer-claim"),
]
