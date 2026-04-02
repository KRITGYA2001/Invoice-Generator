from __future__ import annotations

from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from company.models import BankDetail, CompanyProfile, InvoiceSettings
from company.permissions import HasCompanyProfile
from company.serializers import (
    BankDetailSerializer,
    CompanyOnboardingSerializer,
    CompanyProfileSerializer,
    InvoiceSettingsSerializer,
)


def success_response(message: str, data: Any, status_code: int) -> Response:
    return Response({"success": True, "message": message, "data": data}, status=status_code)


def error_response(message: str, errors: Any = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    if errors is None:
        errors = {}
    return Response({"success": False, "message": message, "errors": errors}, status=status_code)


def get_company_profile(user) -> CompanyProfile | None:
    try:
        return user.company_profile
    except CompanyProfile.DoesNotExist:
        return None


def company_overview(company_profile: CompanyProfile | None) -> dict[str, Any]:
    if not company_profile:
        return {
            "profile": None,
            "bank_details": [],
            "invoice_settings": None,
            "onboarding_complete": False,
        }

    bank_details = getattr(company_profile, "bank_details").all()
    try:
        invoice_settings = company_profile.invoice_settings
    except InvoiceSettings.DoesNotExist:
        invoice_settings = InvoiceSettings.objects.create(company=company_profile)
    if invoice_settings is None:
        invoice_settings = InvoiceSettings.objects.create(company=company_profile)

    return {
        "profile": CompanyProfileSerializer(company_profile, context={"request": None}).data,
        "bank_details": BankDetailSerializer(bank_details, many=True, context={"request": None}).data,
        "invoice_settings": InvoiceSettingsSerializer(invoice_settings, context={"request": None}).data,
        "onboarding_complete": bool(company_profile and bank_details.exists() and invoice_settings),
    }


class CompanyOnboardingView(GenericAPIView):
    serializer_class = CompanyOnboardingSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if get_company_profile(request.user):
            return error_response("Company profile already exists. Use update endpoint.", status_code=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            company_profile = serializer.save()

        data = company_overview(company_profile)
        return success_response("Company onboarded successfully", data, status.HTTP_201_CREATED)


class CompanyProfileView(GenericAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_company(self, request: Request) -> CompanyProfile | None:
        return get_company_profile(request.user)

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company_profile = self.get_company(request)
        if company_profile is None:
            return error_response("Company profile not found. Please complete onboarding.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(company_profile, context={"request": request})
        return success_response("Company profile fetched", serializer.data, status.HTTP_200_OK)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update_company(request, partial=False)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update_company(request, partial=True)

    def _update_company(self, request: Request, partial: bool) -> Response:
        company_profile = self.get_company(request)
        if company_profile is None:
            return error_response("Company profile not found. Please complete onboarding.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(company_profile, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Company profile updated", serializer.data, status.HTTP_200_OK)


class BankDetailListCreateView(GenericAPIView):
    serializer_class = BankDetailSerializer
    permission_classes = [IsAuthenticated, HasCompanyProfile]

    def get_company(self, request: Request) -> CompanyProfile:
        return request.user.company_profile

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = self.get_company(request)
        serializer = self.get_serializer(company.bank_details.all(), many=True, context={"request": request})
        return success_response("Bank details fetched", serializer.data, status.HTTP_200_OK)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = self.get_company(request)
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        bank_detail = serializer.save(company=company)
        return success_response("Bank detail created", self.get_serializer(bank_detail, context={"request": request}).data, status.HTTP_201_CREATED)


class BankDetailDetailView(GenericAPIView):
    serializer_class = BankDetailSerializer
    permission_classes = [IsAuthenticated, HasCompanyProfile]

    def get_company(self, request: Request) -> CompanyProfile:
        return request.user.company_profile

    def get_object(self, request: Request, pk: str) -> BankDetail:
        company = self.get_company(request)
        return get_object_or_404(BankDetail, pk=pk, company=company)

    def get(self, request: Request, pk: str, *args: Any, **kwargs: Any) -> Response:
        bank_detail = self.get_object(request, pk)
        serializer = self.get_serializer(bank_detail, context={"request": request})
        return success_response("Bank detail fetched", serializer.data, status.HTTP_200_OK)

    def put(self, request: Request, pk: str, *args: Any, **kwargs: Any) -> Response:
        return self._update(request, pk, partial=False)

    def patch(self, request: Request, pk: str, *args: Any, **kwargs: Any) -> Response:
        return self._update(request, pk, partial=True)

    def _update(self, request: Request, pk: str, partial: bool) -> Response:
        bank_detail = self.get_object(request, pk)
        serializer = self.get_serializer(bank_detail, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Bank detail updated", serializer.data, status.HTTP_200_OK)

    def delete(self, request: Request, pk: str, *args: Any, **kwargs: Any) -> Response:
        bank_detail = self.get_object(request, pk)
        company = self.get_company(request)
        bank_details = company.bank_details.all()

        if bank_details.count() == 1:
            return error_response("Cannot delete the only bank account", status_code=status.HTTP_400_BAD_REQUEST)

        was_primary = bank_detail.is_primary
        bank_detail.delete()

        if was_primary:
            replacement = company.bank_details.order_by("-is_primary", "bank_name").first()
            if replacement is not None:
                replacement.is_primary = True
                replacement.save(update_fields=["is_primary", "updated_at"])

        return success_response("Bank detail deleted", {}, status.HTTP_200_OK)


class SetPrimaryBankView(GenericAPIView):
    permission_classes = [IsAuthenticated, HasCompanyProfile]

    def post(self, request: Request, pk: str, *args: Any, **kwargs: Any) -> Response:
        company = request.user.company_profile
        bank_detail = get_object_or_404(BankDetail, pk=pk, company=company)

        with transaction.atomic():
            company.bank_details.exclude(pk=bank_detail.pk).update(is_primary=False)
            bank_detail.is_primary = True
            bank_detail.save(update_fields=["is_primary", "updated_at"])

        return success_response("Primary bank account updated", {}, status.HTTP_200_OK)


class InvoiceSettingsView(GenericAPIView):
    serializer_class = InvoiceSettingsSerializer
    permission_classes = [IsAuthenticated, HasCompanyProfile]

    def get_company(self, request: Request) -> CompanyProfile:
        return request.user.company_profile

    def get_settings(self, company: CompanyProfile) -> InvoiceSettings:
        settings_object, _ = InvoiceSettings.objects.get_or_create(company=company)
        return settings_object

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        settings_object = self.get_settings(self.get_company(request))
        serializer = self.get_serializer(settings_object, context={"request": request})
        return success_response("Invoice settings fetched", serializer.data, status.HTTP_200_OK)

    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request, partial=False)

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._update(request, partial=True)

    def _update(self, request: Request, partial: bool) -> Response:
        company = self.get_company(request)
        settings_object = self.get_settings(company)
        serializer = self.get_serializer(settings_object, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Invoice settings updated", serializer.data, status.HTTP_200_OK)


class CompanyCompleteProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company_profile = get_company_profile(request.user)
        data = company_overview(company_profile)
        return success_response("Company profile fetched", data, status.HTTP_200_OK)
