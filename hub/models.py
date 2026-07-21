from django.db import models


class SiteNode(models.Model):
    site_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    callback_base_url = models.URLField(blank=True)
    site_token = models.CharField(max_length=255)
    site_secret = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.site_id})"


class Designer(models.Model):
    max_user_id = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=255)
    sbp_phone = models.CharField(max_length=32)
    experience_text = models.TextField()
    portfolio_url = models.URLField()
    web_login = models.CharField(max_length=64, unique=True, blank=True)
    web_password_hash = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    avg_rating = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    ratings_count = models.PositiveIntegerField(default=0)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.full_name


class HubAdminUser(models.Model):
    """Portal administrator (role policy), separate from Django staff/superuser."""

    full_name = models.CharField(max_length=255)
    web_login = models.CharField(max_length=64, unique=True)
    web_password_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    can_manage_users = models.BooleanField(default=True)
    can_manage_briefs = models.BooleanField(default=True)
    can_view_ratings = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.web_login})"


class HubBrief(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        QUEUED = "queued", "В очереди"
        ASSIGNED = "assigned", "Назначена"
        IN_PROGRESS = "in_progress", "В работе"
        NEEDS_CLARIFICATION = "needs_clarification", "Нужно уточнение"
        CLARIFICATION_PROVIDED = "clarification_provided", "Уточнение получено"
        DONE = "done", "Готово"
        CANCELLED = "cancelled", "Отменено"

    public_id = models.CharField(max_length=64, unique=True)
    site = models.ForeignKey(SiteNode, on_delete=models.PROTECT, related_name="briefs")
    local_brief_id = models.PositiveIntegerField()
    brief_number = models.CharField(max_length=64)
    client_ref = models.CharField(max_length=128)
    model_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2)
    designer_share_amount = models.DecimalField(max_digits=12, decimal_places=2)
    site_share_amount = models.DecimalField(max_digits=12, decimal_places=2)
    has_stl = models.BooleanField(default=False)
    source_stl_file = models.FileField(upload_to="hub/source-stl/", blank=True)
    stl_sync_error = models.CharField(max_length=255, blank=True)
    screenshots_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    designer = models.ForeignKey(
        Designer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_briefs",
    )
    eta = models.CharField(max_length=128, blank=True)
    last_message = models.TextField(blank=True)
    designer_comment = models.TextField(blank=True)
    final_model_url = models.URLField(blank=True)
    final_model_file = models.FileField(upload_to="hub/final-models/", blank=True)
    final_screenshots_urls = models.TextField(blank=True)
    final_screenshots_archive = models.FileField(upload_to="hub/final-screenshots/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "local_brief_id"], name="uniq_brief_per_site_local_id"
            )
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.get_status_display()})"


class DesignerRating(models.Model):
    """Rating of a designer for a completed brief, sent by CRM manager."""

    event_id = models.CharField(max_length=64, unique=True)
    brief = models.ForeignKey(HubBrief, on_delete=models.CASCADE, related_name="ratings")
    designer = models.ForeignKey(Designer, on_delete=models.CASCADE, related_name="ratings")
    site = models.ForeignKey(SiteNode, on_delete=models.PROTECT, related_name="ratings")
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    rated_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(score__gte=1, score__lte=5), name="rating_score_1_5"),
        ]

    def __str__(self) -> str:
        return f"{self.designer} = {self.score}/5 ({self.brief.public_id})"


class HubBriefEvent(models.Model):
    event_id = models.CharField(max_length=64, unique=True)
    brief = models.ForeignKey(HubBrief, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=64)
    payload_json = models.JSONField(default=dict)
    delivered_ok = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class BotConversationState(models.Model):
    class State(models.TextChoices):
        WAITING_FULL_NAME = "waiting_full_name", "Ожидание ФИО"
        WAITING_SBP_PHONE = "waiting_sbp_phone", "Ожидание телефона СБП"
        WAITING_EXPERIENCE = "waiting_experience", "Ожидание опыта"
        WAITING_PORTFOLIO = "waiting_portfolio", "Ожидание портфолио"

    max_user_id = models.CharField(max_length=64, unique=True)
    state = models.CharField(max_length=64, choices=State.choices)
    full_name = models.CharField(max_length=255, blank=True)
    sbp_phone = models.CharField(max_length=32, blank=True)
    experience_text = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DesignerSessionToken(models.Model):
    key = models.CharField(max_length=64, unique=True)
    designer = models.ForeignKey(Designer, on_delete=models.CASCADE, related_name="session_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
