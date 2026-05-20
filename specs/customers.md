# Customers App

## Purpose

Manages the company's party master — buyers, clients, or anyone they invoice. Called "Parties" in the UI. Includes additional contacts, internal notes, balance tracking, and account statements.

## Models

### `Customer`

The core party record, scoped to a company.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → CompanyProfile | |
| `party_type` | CharField | BUSINESS / INDIVIDUAL / GOVERNMENT |
| `name` | CharField | Legal/trade name |
| `display_name` | CharField | Short name for lists/invoices |
| `gstin` | CharField(15) | Optional, validated format |
| `pan` | CharField(10) | Optional |
| `mobile_primary` | CharField | Required |
| `mobile_secondary` | CharField | Optional |
| `email` | EmailField | Optional |
| `website` | URLField | Optional |
| `billing_address_line1` | CharField | Required |
| `billing_address_line2` | CharField | Optional |
| `billing_city` | CharField | Required |
| `billing_state` | CharField | Required |
| `billing_state_code` | CharField(2) | Required, 2-digit GST code |
| `billing_pincode` | CharField | Required |
| `billing_country` | CharField | Default "India" |
| `credit_limit` | DecimalField | 0 = no limit |
| `payment_terms_days` | IntegerField | 0 = immediate |
| `opening_balance` | DecimalField | Positive = party owes company |
| `current_balance` | DecimalField | Updated by invoice service |
| `notes` | TextField | Internal notes field |
| `is_active` | BooleanField | Soft delete |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

**Unique together**: `(company, name)` — party names must be unique per company.

**Properties**:
- `is_over_credit_limit` → `bool`: True if `current_balance > credit_limit > 0`
- `full_billing_address` → `str`: formatted multi-line address string

### `CustomerContact`

Additional named contacts for a customer (e.g., different staff at the same company).

| Field | Type | Notes |
|---|---|---|
| `customer` | FK → Customer | |
| `name` | CharField | Required |
| `designation` | CharField | Optional |
| `mobile` | CharField | Optional |
| `email` | EmailField | Optional |
| `is_primary` | BooleanField | Only one should be primary |
| `created_at` | DateTimeField | Auto |

Ordered by `-is_primary` (primary contact always first).

### `CustomerNote`

Internal audit trail of notes added about a customer.

| Field | Type | Notes |
|---|---|---|
| `customer` | FK → Customer | |
| `note` | TextField | |
| `created_by` | FK → User | |
| `created_at` | DateTimeField | Auto |

Ordered by `-created_at` (newest first).

## UI Views (`views_ui.py`)

| View | URL | Description |
|---|---|---|
| `CustomerListView` | `/customers/` | Paginated list with search/filter |
| `CustomerCreateView` | `/customers/create/` | New party form |
| `CustomerUpdateView` | `/customers/<pk>/edit/` | Edit party |
| `CustomerDeleteView` | `/customers/<pk>/delete/` | Soft/hard delete |
| `CustomerDetailView` | `/customers/<pk>/` | Party detail with stats and recent invoices |
| `CustomerStatementView` | `/customers/<pk>/statement/` | Account statement (date range) |
| `ContactCreateView` | `/customers/<pk>/contacts/create/` | HTMX partial: add contact |
| `ContactDeleteView` | `/customers/<pk>/contacts/<cpk>/delete/` | HTMX partial: delete contact |
| `NoteCreateView` | `/customers/<pk>/notes/create/` | HTMX partial: add note |
| `NoteDeleteView` | `/customers/<pk>/notes/<npk>/delete/` | HTMX partial: delete note |

## URL Namespace: `customers_ui`

```
customers_ui:customer-list
customers_ui:customer-create
customers_ui:customer-detail
customers_ui:customer-edit
customers_ui:customer-delete
customers_ui:customer-statement
customers_ui:contact-create
customers_ui:contact-delete
customers_ui:note-create
customers_ui:note-delete
```

## Customer List Filters

The list view supports:
- Search by name, GSTIN, mobile
- Filter by `party_type` (Business / Individual / Government)
- Filter by `is_active`
- Filter by over credit limit

## Balance Tracking

`current_balance` is updated by the invoice service when invoices are issued or cancelled. It is not a computed field — it is stored and updated incrementally.

- Positive balance = customer owes the company (outstanding receivable)
- Negative balance = company owes the customer (credit note / advance scenario)
- `opening_balance` is set at creation time only (not editable after creation)

## Statement View

`CustomerStatementView` shows a date-filtered list of issued invoices for the party:
- Presets: this month, last month, this FY, last FY, custom
- Computed: opening balance at period start, closing balance at period end
- Printable format

## Contacts & Notes (HTMX Partials)

Contacts and notes on the customer detail page are managed via HTMX:
- Form POST → server returns updated partial HTML → HTMX swaps `#contacts-list` or `#notes-list`
- Alpine.js triggers via `htmx:afterSwap` events
- Setting `is_primary` on a new contact does NOT automatically unset others — handle this in the view

## Key Helpers

- `_current_fy_start()` → datetime for April 1 of current financial year
- `_default_statement_dates()` → dict with from/to defaults for statement view
- `_parse_decimal(val, default)` → safe decimal parsing for form inputs
- `_parse_non_negative_int(val, default)` → safe int parsing

## Notes for Agents

- Party name (`name`) is the legal name; `display_name` is the short name shown in lists and on invoice PDFs. If `display_name` is blank, fall back to `name`.
- `billing_state_code` is critical for GST calculation — it determines interstate vs intrastate tax on invoices.
- When creating a customer from the invoice form (quick-create modal), the endpoint is `invoices_ui:customer-quick-create` — it uses the same Customer model but returns JSON instead of HTML.
- The standalone party CRUD pages (`customers_ui:customer-create`, `customer-edit`) are full-featured and must remain untouched even if the invoice form adds inline creation.
