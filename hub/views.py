import uuid
from functools import wraps

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SiteAuthError, authenticate_site_request
from .designer_auth import (
    DesignerAuthError,
    authenticate_designer,
    authenticate_designer_credentials,
    create_designer_session,
)
from .models import Designer, HubBrief
from .serializers import (
    BriefInSerializer,
    BriefOutSerializer,
    ClaimBriefInSerializer,
    DesignerBriefOutSerializer,
    DesignerLoginInSerializer,
)
from .services import emit_brief_event, process_bot_message

DESIGNER_SESSION_KEY = "designer_id"
DESIGNER_WORK_STATUS_CHOICES = [
    HubBrief.Status.ASSIGNED,
    HubBrief.Status.IN_PROGRESS,
    HubBrief.Status.NEEDS_CLARIFICATION,
    HubBrief.Status.DONE,
]


def _claim_brief_for_designer(*, designer, brief_id: str, eta: str):
    with transaction.atomic():
        brief = get_object_or_404(HubBrief.objects.select_for_update(), public_id=brief_id)
        if brief.status != HubBrief.Status.QUEUED:
            return None, {
                "detail": "Эту задачу уже взял другой дизайнер.",
                "status": brief.status,
                "designer_name": brief.designer.full_name if brief.designer else "",
            }
        brief.status = HubBrief.Status.ASSIGNED
        brief.designer = designer
        brief.eta = eta
        brief.save(update_fields=["status", "designer", "eta", "updated_at"])
        emit_brief_event(brief, event="taken_in_work")
        return brief, None


def _update_brief_work_state(
    *,
    brief: HubBrief,
    designer: Designer,
    status_value: str,
    designer_comment: str,
    final_model_url: str,
    final_screenshots_urls: str,
):
    if brief.designer_id != designer.id:
        return "Изменять заявку может только назначенный дизайнер."
    if status_value not in DESIGNER_WORK_STATUS_CHOICES:
        return "Выбран недопустимый статус."
    if status_value == HubBrief.Status.DONE:
        if not final_model_url:
            return "Для статуса 'Готово' укажите ссылку на финальный файл."
        if not final_screenshots_urls:
            return "Для статуса 'Готово' добавьте хотя бы одну ссылку на фото/скриншот."

    brief.status = status_value
    brief.designer_comment = designer_comment
    brief.final_model_url = final_model_url
    brief.final_screenshots_urls = final_screenshots_urls
    if status_value == HubBrief.Status.DONE:
        brief.done_at = timezone.now()
    brief.save(
        update_fields=[
            "status",
            "designer_comment",
            "final_model_url",
            "final_screenshots_urls",
            "done_at",
            "updated_at",
        ]
    )
    event_map = {
        HubBrief.Status.ASSIGNED: "assigned",
        HubBrief.Status.IN_PROGRESS: "in_progress",
        HubBrief.Status.NEEDS_CLARIFICATION: "needs_clarification",
        HubBrief.Status.DONE: "done",
    }
    emit_brief_event(brief, event=event_map[status_value], message=designer_comment)
    return None


def _require_designer_session(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        designer_id = request.session.get(DESIGNER_SESSION_KEY)
        if not designer_id:
            return redirect("designer-web-login")
        try:
            designer = Designer.objects.get(id=designer_id, is_active=True)
        except Designer.DoesNotExist:
            request.session.pop(DESIGNER_SESSION_KEY, None)
            return redirect("designer-web-login")
        request.designer = designer
        return view_func(request, *args, **kwargs)

    return _wrapped


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
            if "model_url" in data:
                brief.model_url = data["model_url"]
            if "description" in data:
                brief.description = data["description"]
            brief.agreed_price = data["agreed_price"]
            brief.designer_share_amount = data["designer_share_amount"]
            brief.site_share_amount = data["site_share_amount"]
            if "has_stl" in data:
                brief.has_stl = data["has_stl"]
            if "screenshots_count" in data:
                brief.screenshots_count = data["screenshots_count"]
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
        if "model_url" in data:
            brief.model_url = data["model_url"]
        if "description" in data:
            brief.description = data["description"]
        brief.agreed_price = data["agreed_price"]
        brief.designer_share_amount = data["designer_share_amount"]
        brief.site_share_amount = data["site_share_amount"]
        if "has_stl" in data:
            brief.has_stl = data["has_stl"]
        if "screenshots_count" in data:
            brief.screenshots_count = data["screenshots_count"]
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


class DesignerLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = DesignerLoginInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            designer, token = create_designer_session(login=data["login"], password=data["password"])
        except DesignerAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(
            {
                "token": token.key,
                "expires_at": token.expires_at.isoformat(),
                "designer": {"id": designer.id, "full_name": designer.full_name, "login": designer.web_login},
            },
            status=status.HTTP_200_OK,
        )


class DesignerBriefQueueView(APIView):
    def get(self, request):
        try:
            designer = authenticate_designer(request)
        except DesignerAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        briefs = (
            HubBrief.objects.select_related("designer", "site")
            .exclude(status=HubBrief.Status.DRAFT)
            .exclude(status=HubBrief.Status.CANCELLED)
            .order_by("-updated_at")
        )
        payload = DesignerBriefOutSerializer(briefs, many=True).data
        return Response(
            {
                "viewer": {"id": designer.id, "full_name": designer.full_name},
                "results": payload,
            },
            status=status.HTTP_200_OK,
        )


class DesignerBriefClaimView(APIView):
    def post(self, request, brief_id: str):
        try:
            designer = authenticate_designer(request)
        except DesignerAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = ClaimBriefInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        eta = serializer.validated_data["eta"]

        brief, error = _claim_brief_for_designer(designer=designer, brief_id=brief_id, eta=eta)
        if error:
            return Response(error, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "brief_id": brief.public_id,
                "status": brief.status,
                "designer_name": designer.full_name,
                "eta": brief.eta,
            },
            status=status.HTTP_200_OK,
        )


def designer_login_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        login = request.POST.get("login", "").strip()
        password = request.POST.get("password", "")
        try:
            designer = authenticate_designer_credentials(login=login, password=password)
        except DesignerAuthError as exc:
            messages.error(request, str(exc))
            return render(request, "hub/designer_login.html", {"login_value": login})
        request.session[DESIGNER_SESSION_KEY] = designer.id
        return redirect("designer-web-queue")

    return render(request, "hub/designer_login.html")


@_require_designer_session
def designer_logout(request: HttpRequest) -> HttpResponse:
    request.session.pop(DESIGNER_SESSION_KEY, None)
    return redirect("designer-web-login")


@_require_designer_session
def designer_queue_page(request: HttpRequest) -> HttpResponse:
    briefs = (
        HubBrief.objects.select_related("designer", "site")
        .exclude(status=HubBrief.Status.DRAFT)
        .exclude(status=HubBrief.Status.CANCELLED)
        .order_by("-updated_at")
    )
    context = {
        "designer": request.designer,
        "queued_briefs": [brief for brief in briefs if brief.status == HubBrief.Status.QUEUED],
        "taken_briefs": [brief for brief in briefs if brief.status != HubBrief.Status.QUEUED],
    }
    return render(request, "hub/designer_queue.html", context)


@_require_designer_session
def designer_brief_detail_page(request: HttpRequest, brief_id: str) -> HttpResponse:
    brief = get_object_or_404(HubBrief.objects.select_related("site", "designer"), public_id=brief_id)
    status_options = [
        (HubBrief.Status.ASSIGNED, "Назначена"),
        (HubBrief.Status.IN_PROGRESS, "В работе"),
        (HubBrief.Status.NEEDS_CLARIFICATION, "Нужно уточнение"),
        (HubBrief.Status.DONE, "Готово"),
    ]
    context = {
        "designer": request.designer,
        "brief": brief,
        "status_options": status_options,
    }
    return render(request, "hub/designer_brief_detail.html", context)


@_require_designer_session
def designer_brief_update_page(request: HttpRequest, brief_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("designer-web-brief-detail", brief_id=brief_id)
    brief = get_object_or_404(HubBrief, public_id=brief_id)
    error = _update_brief_work_state(
        brief=brief,
        designer=request.designer,
        status_value=request.POST.get("status", "").strip(),
        designer_comment=request.POST.get("designer_comment", "").strip(),
        final_model_url=request.POST.get("final_model_url", "").strip(),
        final_screenshots_urls=request.POST.get("final_screenshots_urls", "").strip(),
    )
    if error:
        messages.error(request, error)
    else:
        messages.success(request, "Заявка обновлена.")
    return redirect("designer-web-brief-detail", brief_id=brief_id)


@_require_designer_session
def designer_claim_page(request: HttpRequest, brief_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("designer-web-queue")
    eta = request.POST.get("eta", "").strip()
    if not eta:
        messages.error(request, "Укажите срок выполнения.")
        return redirect("designer-web-queue")
    brief, error = _claim_brief_for_designer(designer=request.designer, brief_id=brief_id, eta=eta)
    if error:
        messages.error(
            request,
            f"{error['detail']} Исполнитель: {error['designer_name'] or 'не указан'}.",
        )
    else:
        messages.success(request, f"Задача {brief.brief_number} назначена на вас.")
    return redirect("designer-web-queue")
