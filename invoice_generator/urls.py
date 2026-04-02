"""
URL configuration for invoice_generator project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/company/", include("company.urls")),
    path("api/products/", include("products.urls")),
    path("api/customers/", include("customers.urls")),
    path("api/invoices/", include("invoices.urls")),
    path("api/reports/", include("reports.urls")),
    path("", include("core.urls", namespace="core")),
    path("accounts/", include("accounts.urls_ui", namespace="accounts_ui")),
    path("company/", include("company.urls_ui", namespace="company_ui")),
    path("products/", include("products.urls_ui", namespace="products_ui")),
    path("customers/", include("customers.urls_ui", namespace="customers_ui")),
    path("invoices/", include("invoices.urls_ui", namespace="invoices_ui")),
    path("reports/", include("reports.urls_ui", namespace="reports_ui")),
]
