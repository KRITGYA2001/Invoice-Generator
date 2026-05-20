# BillMint — Project Overview

## What It Is

BillMint is a multi-tenant GST invoice generator built with Django. Each registered user gets one **Company** workspace. All data (customers, products, invoices) is scoped to that company.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Django REST Framework |
| Auth | Session-based (UI) + Token/JWT (API) |
| Frontend | Django templates, Alpine.js (reactivity), HTMX (partial updates) |
| Database | SQLite (dev) — swap to PostgreSQL for production |
| PDF | WeasyPrint (server-side PDF generation) |
| Email | Django email backend |
| IDs | UUID primary keys everywhere |

## Dual Endpoint Architecture

Every app exposes two parallel layers:

- **REST API** (`/api/<app>/`) — DRF serializers + viewsets, for external clients or mobile
- **HTML UI** (`/<app>/`) — Class-based views rendering Django templates with Alpine + HTMX

Both layers share the same models and services. Views are in separate files:
- `views.py` / `serializers.py` → API
- `views_ui.py` → HTML UI
- `urls.py` / `urls_ui.py` → respective URL confs

## App Structure

```
invoice_generator/   ← root URL conf + settings
accounts/            ← custom User model, auth flows
company/             ← CompanyProfile, BankDetail, InvoiceSettings, onboarding
customers/           ← Customer (party), contacts, notes, statements
products/            ← Product, category, UOM, stock movements
invoices/            ← Invoice, line items, PDF, email, GST calc
reports/             ← Aggregated GST/sales/inventory/outstanding reports
core/                ← Dashboard, OnboardingCheckMixin
```

## Multi-Tenancy Pattern

Every company-scoped model has a `company = ForeignKey(CompanyProfile)` field. All queryset filtering in views starts with `request.user.company_profile`. There is no cross-company data leakage by design.

## Key Patterns

### OnboardingCheckMixin
All UI views that need a company inherit `OnboardingCheckMixin`. If the user has no `CompanyProfile`, they are redirected to `/company/onboarding/`.

### Snapshotting (Invoices)
When an invoice is issued, customer and product data is copied into snapshot fields on the invoice and line items. This makes invoices immutable — future edits to a customer or product don't retroactively change issued invoices.

### GST Calculation
`invoices/services.py → GSTCalculator` handles all tax math:
- Intrastate: CGST + SGST (split equally)
- Interstate: IGST only
- Determination via company state code vs customer billing state code

### Invoice Numbering
`InvoiceNumberGenerator.generate()` uses a row-level DB lock on `InvoiceSettings.invoice_counter` to guarantee unique sequential numbers. Format: `PREFIX/FY/COUNTER` (e.g., `INV/25-26/0042`).

### Stock Movements
Every stock change (sale, purchase, adjustment) writes an immutable `StockMovement` record. The product's `current_stock` is the running total; movements are the audit log.

### Alpine + HTMX Integration
- HTMX handles server-driven partial HTML updates (search dropdowns, contact lists, note lists)
- Alpine.js manages client-side state (line item totals, tax calculation, modal open/close, form validation)
- They communicate via Alpine events: `$dispatch('event-name')` + `@event-name.window` listeners

## URL Namespaces

| App | Namespace |
|---|---|
| accounts UI | `accounts_ui` |
| company UI | `company_ui` |
| customers UI | `customers_ui` |
| products UI | `products_ui` |
| invoices UI | `invoices_ui` |
| reports UI | `reports_ui` |
| core UI | `core_ui` |
