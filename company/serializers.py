from __future__ import annotations

import re
from typing import Any

from PIL import Image
from django.db import transaction
from rest_framework import serializers

from company.models import BankDetail, CompanyProfile, InvoiceSettings


MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _validate_image_file(uploaded_file: Any) -> Any:
    if uploaded_file is None:
        return uploaded_file

    if getattr(uploaded_file, "size", 0) > MAX_IMAGE_SIZE_BYTES:
        raise serializers.ValidationError("Image size must not exceed 2MB")

    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise serializers.ValidationError("Only jpeg, png, and webp images are allowed")

    try:
        image = Image.open(uploaded_file)
        image.verify()
    except Exception as exc:
        raise serializers.ValidationError("Uploaded file is not a valid image") from exc
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    return uploaded_file


def _absolute_file_url(serializer: serializers.Serializer, file_field: Any) -> str | None:
    if not file_field:
        return None

    request = serializer.context.get("request")
    file_url = file_field.url
    if request is not None:
        return request.build_absolute_uri(file_url)
    return file_url


class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        """Meta options for CompanyProfileSerializer."""

        model = CompanyProfile
        fields = (
            "id",
            "user",
            "company_name",
            "trade_name",
            "unit_division",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "state_code",
            "pincode",
            "country",
            "pan",
            "gstin",
            "udyam_number",
            "mobile_primary",
            "mobile_secondary",
            "email",
            "website",
            "logo",
            "logo_text",
            "signature_image",
            "authorised_signatory",
            "is_msme",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate_state_code(self, value: str) -> str:
        if not re.fullmatch(r"\d{2}", value):
            raise serializers.ValidationError("State code must be exactly 2 digits")
        return value

    def validate_pan(self, value: str) -> str:
        if value and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]{1}", value):
            raise serializers.ValidationError("Enter a valid PAN")
        return value

    def validate_gstin(self, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}", value):
            raise serializers.ValidationError("Enter a valid GSTIN")
        return value

    def validate_logo(self, value: Any) -> Any:
        return _validate_image_file(value)

    def validate_signature_image(self, value: Any) -> Any:
        return _validate_image_file(value)

    def create(self, validated_data: dict[str, Any]) -> CompanyProfile:
        request = self.context["request"]
        return CompanyProfile.objects.create(user=request.user, **validated_data)

    def to_representation(self, instance: CompanyProfile) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["logo"] = _absolute_file_url(self, instance.logo)
        data["signature_image"] = _absolute_file_url(self, instance.signature_image)
        return data


class BankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetail
        fields = (
            "id",
            "company",
            "bank_name",
            "branch_name",
            "account_number",
            "ifsc_code",
            "account_type",
            "swift_code",
            "ad_code",
            "upi_id",
            "qr_code_image",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "created_at", "updated_at")

    def validate_ifsc_code(self, value: str) -> str:
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value):
            raise serializers.ValidationError("Enter a valid IFSC code")
        return value

    def validate_account_number(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("Account number must contain digits only")
        if not 9 <= len(value) <= 18:
            raise serializers.ValidationError("Account number must be between 9 and 18 digits")
        return value

    def validate_qr_code_image(self, value: Any) -> Any:
        return _validate_image_file(value)

    def create(self, validated_data: dict[str, Any]) -> BankDetail:
        company = validated_data.pop("company")
        bank_details_manager = getattr(company, "bank_details")
        if not bank_details_manager.exists():
            validated_data["is_primary"] = True
        return BankDetail.objects.create(company=company, **validated_data)

    def to_representation(self, instance: BankDetail) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["qr_code_image"] = _absolute_file_url(self, instance.qr_code_image)
        return data


class InvoiceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        """Meta options for InvoiceSettingsSerializer."""

        model = InvoiceSettings
        fields = (
            "id",
            "company",
            "invoice_prefix",
            "financial_year",
            "invoice_counter",
            "counter_reset_yearly",
            "default_due_days",
            "default_transport",
            "default_place_of_supply",
            "reverse_charge_applicable",
            "einvoicing_enabled",
            "ewaybill_enabled",
            "invoice_terms",
            "invoice_notes",
            "show_bank_details",
            "show_signature",
            "number_of_copies",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "invoice_counter", "created_at", "updated_at")

    def validate_financial_year(self, value: str) -> str:
        if not re.fullmatch(r"\d{2}-\d{2}", value):
            raise serializers.ValidationError("Financial year must be in the format YY-YY")
        return value


class CompanyOnboardingSerializer(serializers.Serializer):
    company_profile = CompanyProfileSerializer()
    bank_detail = BankDetailSerializer(required=False, allow_null=True)
    invoice_settings = InvoiceSettingsSerializer(required=False, allow_null=True)

    def create(self, validated_data: dict[str, Any]) -> CompanyProfile:
        request = self.context["request"]
        profile_data = validated_data.pop("company_profile")
        bank_detail_data = validated_data.pop("bank_detail", None)
        invoice_settings_data = validated_data.pop("invoice_settings", None)

        with transaction.atomic():
            company_profile = CompanyProfile.objects.create(user=request.user, **profile_data)

            if invoice_settings_data:
                invoice_settings, _ = InvoiceSettings.objects.get_or_create(company=company_profile)
                for attribute, value in invoice_settings_data.items():
                    setattr(invoice_settings, attribute, value)
                invoice_settings.save()

            if bank_detail_data:
                bank_details_manager = getattr(company_profile, "bank_details")
                if not bank_details_manager.exists():
                    bank_detail_data["is_primary"] = True
                BankDetail.objects.create(company=company_profile, **bank_detail_data)

        return company_profile
