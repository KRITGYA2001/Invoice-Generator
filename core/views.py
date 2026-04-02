from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views import View

from reports.services import DashboardService


class OnboardingCheckMixin:
	"""Ensure the user has a company profile before loading company-scoped pages."""

	@staticmethod
	def _onboarding_url() -> str:
		try:
			return reverse("company_ui:onboarding")
		except NoReverseMatch:
			return "/company/onboarding/"

	def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
		if not hasattr(request.user, "company_profile"):
			messages.warning(request, "Please complete company onboarding first.")
			return redirect(self._onboarding_url())
		return super().dispatch(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, OnboardingCheckMixin, View):
	"""Dashboard landing page for the session-authenticated UI."""

	login_url = "/accounts/login/"
	template_name = "core/dashboard.html"

	def get(self, request: HttpRequest) -> HttpResponse:
		company = request.user.company_profile
		current_fy = DashboardService.get_current_financial_year()
		overview = DashboardService.get_overview(company, financial_year=current_fy)
		trend = DashboardService.get_monthly_trend(company)
		context = {
			"company": company,
			"overview": overview,
			"trend": trend,
			"current_fy": current_fy,
			"trend_labels": json.dumps([month["month"] for month in trend["months"]]),
			"trend_revenue": json.dumps([float(month["revenue"]) for month in trend["months"]]),
			"trend_invoices": json.dumps([month["invoice_count"] for month in trend["months"]]),
			"trend_tax": json.dumps([float(month["tax_amount"]) for month in trend["months"]]),
			"low_stock_count": overview["products"]["low_stock"],
			"page_title": "Dashboard",
		}
		return render(request, self.template_name, context)
