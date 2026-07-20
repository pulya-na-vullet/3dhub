from rest_framework import serializers

from .models import HubBrief


class BriefInSerializer(serializers.Serializer):
    local_brief_id = serializers.IntegerField(min_value=1)
    brief_number = serializers.CharField(max_length=64)
    client_ref = serializers.CharField(max_length=128)
    model_url = serializers.URLField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    agreed_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    designer_share_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    site_share_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    has_stl = serializers.BooleanField(required=False)
    screenshots_count = serializers.IntegerField(required=False, min_value=0)


class BriefOutSerializer(serializers.ModelSerializer):
    brief_id = serializers.CharField(source="public_id")

    class Meta:
        model = HubBrief
        fields = [
            "brief_id",
            "local_brief_id",
            "brief_number",
            "client_ref",
            "model_url",
            "description",
            "agreed_price",
            "designer_share_amount",
            "site_share_amount",
            "has_stl",
            "source_stl_file",
            "stl_sync_error",
            "screenshots_count",
            "status",
            "eta",
            "last_message",
            "designer_comment",
            "final_model_url",
            "final_screenshots_urls",
        ]


class BriefCreateOutSerializer(serializers.Serializer):
    brief_id = serializers.CharField()
    id = serializers.CharField()
    status = serializers.ChoiceField(choices=[HubBrief.Status.QUEUED, HubBrief.Status.CLARIFICATION_PROVIDED])


class DesignerLoginInSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128)


class DesignerBriefOutSerializer(serializers.ModelSerializer):
    brief_id = serializers.CharField(source="public_id")
    site_name = serializers.CharField(source="site.name")
    designer_name = serializers.CharField(source="designer.full_name", allow_null=True)

    class Meta:
        model = HubBrief
        fields = [
            "brief_id",
            "brief_number",
            "site_name",
            "description",
            "agreed_price",
            "designer_share_amount",
            "status",
            "designer_name",
            "eta",
            "model_url",
            "has_stl",
            "source_stl_file",
            "stl_sync_error",
            "screenshots_count",
            "final_model_url",
            "final_screenshots_urls",
            "designer_comment",
            "updated_at",
        ]


class ClaimBriefInSerializer(serializers.Serializer):
    eta = serializers.CharField(max_length=128)
