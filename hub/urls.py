from django.urls import path

from .views import BriefDetailView, BriefListCreateView, BriefMessageView, MaxWebhookView

urlpatterns = [
    path("briefs", BriefListCreateView.as_view(), name="brief-create"),
    path("briefs/<str:brief_id>", BriefDetailView.as_view(), name="brief-detail"),
    path("briefs/<str:brief_id>/messages", BriefMessageView.as_view(), name="brief-message"),
    path("max/webhook", MaxWebhookView.as_view(), name="max-webhook"),
]
