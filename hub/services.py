import uuid
from dataclasses import dataclass
from secrets import token_hex

import json
import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlparse
from pathlib import Path

from .models import BotConversationState, Designer, HubBrief, HubBriefEvent


@dataclass
class BotReply:
    text: str


def emit_brief_event(brief: HubBrief, event: str, message: str = "") -> None:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event": event,
        "local_brief_id": brief.local_brief_id,
        "brief_id": brief.public_id,
        "designer_name": brief.designer.full_name if brief.designer else "",
        "designer_id": brief.designer.max_user_id if brief.designer else "",
        "eta": brief.eta,
        "message": message,
    }
    event_log = HubBriefEvent.objects.create(
        event_id=payload["event_id"],
        brief=brief,
        event=event,
        payload_json=payload,
        delivered_ok=False,
    )
    callback = (brief.site.callback_base_url or "").rstrip("/")
    if not callback:
        return
    webhook_url = f"{callback}/hooks/hub/briefs"
    timestamp = str(int(timezone.now().timestamp()))
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature_payload = f"{timestamp}\n{body}".encode("utf-8")
    try:
        import hashlib
        import hmac

        signature = hmac.new(
            key=brief.site.site_secret.encode("utf-8"),
            msg=signature_payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        response = requests.post(
            webhook_url,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {brief.site.site_token}",
                "X-Site-Id": brief.site.site_id,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
            },
            timeout=3,
        )
        if 200 <= response.status_code < 300:
            event_log.delivered_ok = True
            event_log.save(update_fields=["delivered_ok"])
    except requests.RequestException:
        # Keep event in outbox log; delivery can be retried manually/by worker later.
        return


def sync_source_stl_file_for_brief(brief: HubBrief) -> None:
    if not brief.has_stl:
        if brief.source_stl_file:
            brief.source_stl_file.delete(save=False)
            brief.source_stl_file = ""
            brief.stl_sync_error = ""
            brief.save(update_fields=["source_stl_file", "stl_sync_error", "updated_at"])
        return

    if not brief.model_url:
        brief.stl_sync_error = "STL отмечен, но ссылка на файл не передана из CRM."
        brief.save(update_fields=["stl_sync_error", "updated_at"])
        return

    try:
        response = requests.get(brief.model_url, timeout=8)
        response.raise_for_status()
    except requests.RequestException:
        brief.stl_sync_error = "Не удалось скачать STL по ссылке из CRM."
        brief.save(update_fields=["stl_sync_error", "updated_at"])
        return

    file_bytes = response.content or b""
    max_bytes = int(getattr(settings, "HUB_MAX_STL_SIZE_BYTES", 25 * 1024 * 1024))
    if not file_bytes:
        brief.stl_sync_error = "CRM вернула пустой STL-файл."
        brief.save(update_fields=["stl_sync_error", "updated_at"])
        return
    if len(file_bytes) > max_bytes:
        brief.stl_sync_error = "Размер STL превышает лимит HUB."
        brief.save(update_fields=["stl_sync_error", "updated_at"])
        return

    parsed = urlparse(brief.model_url)
    suffix = Path(parsed.path).suffix.lower() or ".stl"
    filename = f"{brief.public_id}-source{suffix}"
    brief.source_stl_file.save(filename, ContentFile(file_bytes), save=False)
    brief.stl_sync_error = ""
    brief.save(update_fields=["source_stl_file", "stl_sync_error", "updated_at"])


def _handle_registration(max_user_id: str, text: str) -> BotReply | None:
    if text == "Регистрация: Дизайнер":
        BotConversationState.objects.update_or_create(
            max_user_id=max_user_id,
            defaults={"state": BotConversationState.State.WAITING_FULL_NAME},
        )
        return BotReply("Введите ФИО.")

    try:
        state = BotConversationState.objects.get(max_user_id=max_user_id)
    except BotConversationState.DoesNotExist:
        return None

    if state.state == BotConversationState.State.WAITING_FULL_NAME:
        state.full_name = text
        state.state = BotConversationState.State.WAITING_SBP_PHONE
        state.save(update_fields=["full_name", "state", "updated_at"])
        return BotReply("Укажите телефон СБП.")

    if state.state == BotConversationState.State.WAITING_SBP_PHONE:
        state.sbp_phone = text
        state.state = BotConversationState.State.WAITING_EXPERIENCE
        state.save(update_fields=["sbp_phone", "state", "updated_at"])
        return BotReply("Опишите ваш опыт в 3D-моделировании.")

    if state.state == BotConversationState.State.WAITING_EXPERIENCE:
        state.experience_text = text
        state.state = BotConversationState.State.WAITING_PORTFOLIO
        state.save(update_fields=["experience_text", "state", "updated_at"])
        return BotReply("Пришлите ссылку на портфолио.")

    if state.state == BotConversationState.State.WAITING_PORTFOLIO:
        web_login = max_user_id
        plain_password = token_hex(4)
        Designer.objects.update_or_create(
            max_user_id=max_user_id,
            defaults={
                "full_name": state.full_name,
                "sbp_phone": state.sbp_phone,
                "experience_text": state.experience_text,
                "portfolio_url": text,
                "web_login": web_login,
                "web_password_hash": make_password(plain_password),
                "is_active": True,
            },
        )
        state.delete()
        return BotReply(
            "Регистрация завершена.\n"
            f"Веб-логин: {web_login}\n"
            f"Веб-пароль: {plain_password}\n"
            "Войдите в портал и откройте очередь задач."
        )

    return BotReply("Неизвестное состояние регистрации. Начните заново: Регистрация: Дизайнер")


def _format_brief_line(brief: HubBrief) -> str:
    return (
        f"{brief.public_id}: {brief.brief_number}, "
        f"цена {brief.agreed_price}, STL={'да' if brief.has_stl else 'нет'}, "
        f"скриншотов={brief.screenshots_count}"
    )


def process_bot_message(max_user_id: str, text: str) -> BotReply:
    text = text.strip()
    registration_reply = _handle_registration(max_user_id=max_user_id, text=text)
    if registration_reply:
        return registration_reply

    try:
        designer = Designer.objects.get(max_user_id=max_user_id, is_active=True)
    except Designer.DoesNotExist:
        return BotReply("Сначала зарегистрируйтесь: Регистрация: Дизайнер")

    if text == "Очередь":
        queued = HubBrief.objects.filter(status=HubBrief.Status.QUEUED).order_by("created_at")[:20]
        if not queued:
            return BotReply("Сейчас нет доступных задач.")
        lines = ["Доступные задачи:"] + [_format_brief_line(brief) for brief in queued]
        return BotReply("\n".join(lines))

    if text.startswith("Беру "):
        payload = text.split(maxsplit=2)
        if len(payload) < 3:
            return BotReply("Формат: Беру <brief_id> <срок>")
        brief_id = payload[1]
        eta = payload[2]
        with transaction.atomic():
            try:
                brief = HubBrief.objects.select_for_update().get(public_id=brief_id)
            except HubBrief.DoesNotExist:
                return BotReply("Задача не найдена.")
            if brief.status != HubBrief.Status.QUEUED:
                return BotReply("Задача уже занята или недоступна.")
            brief.status = HubBrief.Status.ASSIGNED
            brief.designer = designer
            brief.eta = eta
            brief.save(update_fields=["status", "designer", "eta", "updated_at"])
            emit_brief_event(brief, event="taken_in_work")
        return BotReply(f"Задача {brief_id} назначена на вас.")

    if text.startswith("Уточнение "):
        payload = text.split(maxsplit=2)
        if len(payload) < 3:
            return BotReply("Формат: Уточнение <brief_id> <текст>")
        brief_id = payload[1]
        message = payload[2]
        with transaction.atomic():
            try:
                brief = HubBrief.objects.select_for_update().get(public_id=brief_id, designer=designer)
            except HubBrief.DoesNotExist:
                return BotReply("Задача не найдена или не назначена вам.")
            brief.status = HubBrief.Status.NEEDS_CLARIFICATION
            brief.last_message = message
            brief.save(update_fields=["status", "last_message", "updated_at"])
            emit_brief_event(brief, event="needs_clarification", message=message)
        return BotReply("Уточнение отправлено менеджеру.")

    if text.startswith("Готово "):
        payload = text.split(maxsplit=1)
        if len(payload) < 2:
            return BotReply("Формат: Готово <brief_id>")
        brief_id = payload[1]
        with transaction.atomic():
            try:
                brief = HubBrief.objects.select_for_update().get(public_id=brief_id, designer=designer)
            except HubBrief.DoesNotExist:
                return BotReply("Задача не найдена или не назначена вам.")
            brief.status = HubBrief.Status.DONE
            brief.done_at = timezone.now()
            brief.save(update_fields=["status", "done_at", "updated_at"])
            emit_brief_event(brief, event="done")
        return BotReply(f"Задача {brief_id} отмечена как готовая.")

    return BotReply("Команды: Очередь | Беру <brief_id> <срок> | Уточнение <brief_id> <текст> | Готово <brief_id>")
