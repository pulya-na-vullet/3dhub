import uuid

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SiteAuthError, authenticate_site_request
from .models import HubBrief
from .serializers import BriefInSerializer, BriefOutSerializer
from .services import process_bot_message


class BriefListCreateView(APIView):
    def post(self, request):
        try:
            site = authenticate_site_request(request)
        except SiteAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = BriefInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        brief = HubBrief.objects.filter(site=site, local_brief_id=data["local_brief_id"]).first()
        if brief is None:
            brief = HubBrief.objects.create(
                public_id=str(uuid.uuid4()),
                site=site,
                local_brief_id=data["local_brief_id"],
                brief_number=data["brief_number"],
                client_ref=data["client_ref"],
                model_url=data.get("model_url", ""),
                description=data.get("description", ""),
                agreed_price=data["agreed_price"],
                designer_share_amount=data["designer_share_amount"],
                site_share_amount=data["site_share_amount"],
                has_stl=data.get("has_stl", False),
                screenshots_count=data.get("screenshots_count", 0),
                status=HubBrief.Status.QUEUED,
            )
        else:
            brief.brief_number = data["brief_number"]
            brief.client_ref = data["client_ref"]
            brief.model_url = data.get("model_url", "")
            brief.description = data.get("description", "")
            brief.agreed_price = data["agreed_price"]
            brief.designer_share_amount = data["designer_share_amount"]
            brief.site_share_amount = data["site_share_amount"]
            brief.has_stl = data.get("has_stl", False)
            brief.screenshots_count = data.get("screenshots_count", 0)
            brief.status = HubBrief.Status.QUEUED
            brief.save()
        return Response(
            {"brief_id": brief.public_id, "id": brief.public_id, "status": brief.status},
            status=status.HTTP_200_OK,
        )


class BriefDetailView(APIView):
    def get(self, request, brief_id: str):
        try:
            site = authenticate_site_request(request)
        except SiteAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        brief = get_object_or_404(HubBrief, public_id=brief_id, site=site)
        return Response(BriefOutSerializer(brief).data)

    def post(self, request, brief_id: str):
        try:
            site = authenticate_site_request(request)
        except SiteAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        brief = get_object_or_404(HubBrief, public_id=brief_id, site=site)
        serializer = BriefInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        brief.local_brief_id = data["local_brief_id"]
        brief.brief_number = data["brief_number"]
        brief.client_ref = data["client_ref"]
        brief.model_url = data.get("model_url", "")
        brief.description = data.get("description", "")
        brief.agreed_price = data["agreed_price"]
        brief.designer_share_amount = data["designer_share_amount"]
        brief.site_share_amount = data["site_share_amount"]
        brief.has_stl = data.get("has_stl", False)
        brief.screenshots_count = data.get("screenshots_count", 0)
        if brief.status == HubBrief.Status.NEEDS_CLARIFICATION:
            brief.status = HubBrief.Status.CLARIFICATION_PROVIDED
        brief.save()
        return Response(BriefOutSerializer(brief).data, status=status.HTTP_200_OK)


class BriefMessageView(APIView):
    def post(self, request, brief_id: str):
        try:
            site = authenticate_site_request(request)
        except SiteAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        brief = get_object_or_404(HubBrief, public_id=brief_id, site=site)
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"detail": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        brief.last_message = text
        brief.status = HubBrief.Status.CLARIFICATION_PROVIDED
        brief.save(update_fields=["last_message", "status", "updated_at"])
        return Response({"status": "accepted"}, status=status.HTTP_200_OK)


class MaxWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user_id = str(request.data.get("user_id", "")).strip()
        text = str(request.data.get("text", "")).strip()
        if not user_id or not text:
            return Response(
                {"detail": "user_id and text are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reply = process_bot_message(max_user_id=user_id, text=text)
        return Response({"reply": reply.text}, status=status.HTTP_200_OK)
