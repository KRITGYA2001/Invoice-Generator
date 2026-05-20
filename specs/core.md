# Core App

## Purpose

Provides the dashboard (main landing page after login) and the `OnboardingCheckMixin` guard used by all other apps. Has no models and no API layer.

## No Models

The core app has no `models.py`. It's purely view and utility logic.

## `OnboardingCheckMixin`

A mixin for class-based views that ensures the user has a completed company profile before accessing any company-scoped page.

```python
class OnboardingCheckMixin:
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'company_profile'):
            return redirect('company_ui:onboarding')
        return super().dispatch(request, *args, **kwargs)
```

**Used by**: `DashboardView` and every view in customers, products, invoices, and reports that inherits from it (directly or through a base class).

**If missing**: Any view that accesses `request.user.company_profile` without this guard will raise `RelatedObjectDoesNotExist` for newly registered users who haven't finished onboarding.

## `DashboardView`

Main landing page at `/`. Requires login + completed onboarding.

**Data fetched** (via `DashboardService`):
- Overview stats: total revenue (this month / this FY), invoice count, outstanding balance
- Monthly trend for the last 12 months: labels, revenue, invoice count, total tax
- Low stock product count (products where `current_stock <= min_stock`)
- Current company profile
- Financial year label (e.g., "2025–26")

**Template context**:
- `overview` — dict with summary numbers
- `trend_labels` — JSON-encoded list of month labels
- `trend_revenue` — JSON-encoded list of revenue values
- `trend_invoice_count` — JSON-encoded list of invoice counts
- `trend_tax` — JSON-encoded list of tax amounts
- `low_stock_count` — integer
- `company` — CompanyProfile instance
- `financial_year` — string

The trend data is embedded as JSON in the template and consumed by a Chart.js or similar charting library via a `<script>` block.

## URL Namespace: `core_ui`

```
core_ui:dashboard   →   /
```

## URL Configuration (`invoice_generator/urls.py`)

The root URL conf includes all app URL confs:

| Path | Included URLconf | Namespace |
|---|---|---|
| `/` | `core.urls_ui` | `core_ui` |
| `/accounts/` | `accounts.urls_ui` | `accounts_ui` |
| `/company/` | `company.urls_ui` | `company_ui` |
| `/products/` | `products.urls_ui` | `products_ui` |
| `/customers/` | `customers.urls_ui` | `customers_ui` |
| `/invoices/` | `invoices.urls_ui` | `invoices_ui` |
| `/reports/` | `reports.urls_ui` | `reports_ui` |
| `/api/auth/` | `accounts.urls` | `accounts_api` |
| `/api/company/` | `company.urls` | `company_api` |
| `/api/products/` | `products.urls` | `products_api` |
| `/api/customers/` | `customers.urls` | `customers_api` |
| `/api/invoices/` | `invoices.urls` | `invoices_api` |
| `/api/reports/` | `reports.urls` | `reports_api` |
| `/admin/` | Django admin | |
| `/media/` | Media file serving (DEBUG only) | |

## Notes for Agents

- `OnboardingCheckMixin` must come before `LoginRequiredMixin` in MRO (method resolution order) — place it first in the class definition: `class MyView(LoginRequiredMixin, OnboardingCheckMixin, View)`.
- The dashboard is the redirect target after login. If you add a new post-login redirect, update the `LOGIN_REDIRECT_URL` setting or the `LoginView.get_success_url()` method.
- `DashboardService` lives in `core/services.py` — it queries `Invoice` and `Product` models directly. Keep this service lean; heavy aggregations should live in the reports app.
