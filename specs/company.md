# Company App

## Purpose

Manages the user's business identity: company profile, bank accounts, and invoice configuration. Every new user must complete the onboarding wizard before accessing the app.

## Models

### `CompanyProfile`

One-to-one with `User`. The root tenant record — every other model's `company` FK points here.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOne → User | |
| `name` | CharField | Legal/trade name |
| `display_name` | CharField | Short name for UI |
| `gstin` | CharField(15) | Validated format |
| `pan` | CharField(10) | |
| `mobile` | CharField | |
| `email` | EmailField | |
| `address_line1/2` | CharField | |
| `city`, `state`, `pincode` | CharField | |
| `state_code` | CharField(2) | 2-digit GST state code |
| `country` | CharField | Default "India" |
| `logo` | ImageField | Shown on PDF/invoices |
| `signature` | ImageField | Shown on PDF |
| `website` | URLField | |

`state_code` is validated to be exactly 2 digits. This code is compared against the customer's `billing_state_code` to determine interstate vs intrastate tax.

### `BankDetail`

Multiple bank accounts per company. The primary active one is shown on invoice PDFs.

| Field | Type | Notes |
|---|---|---|
| `company` | FK → CompanyProfile | |
| `bank_name` | CharField | |
| `account_number` | CharField | |
| `account_type` | CharField | SAVINGS or CURRENT |
| `ifsc_code` | CharField | |
| `swift_code` | CharField | Optional, for international |
| `upi_id` | CharField | |
| `qr_code` | ImageField | Payment QR |
| `is_primary` | BooleanField | |
| `is_active` | BooleanField | |

Ordered by `-is_primary` so the primary account always appears first.

### `InvoiceSettings`

One-to-one with `CompanyProfile`. Controls invoice numbering and defaults.

| Field | Type | Notes |
|---|---|---|
| `company` | OneToOne → CompanyProfile | |
| `invoice_prefix` | CharField | e.g., "INV" |
| `invoice_counter` | IntegerField | Incremented atomically per invoice |
| `financial_year` | CharField | e.g., "25-26" |
| `default_due_days` | IntegerField | Due date = invoice date + this |
| `default_transport` | CharField | Pre-filled transport field |
| `place_of_supply` | CharField | Default POS for invoices |
| `enable_reverse_charge` | BooleanField | Show RC field on invoices |
| `enable_einvoice` | BooleanField | IRN generation |
| `enable_ewaybill` | BooleanField | E-way bill fields |
| `show_bank_details` | BooleanField | Print bank on PDF |
| `show_signature` | BooleanField | Print signature on PDF |
| `default_terms` | TextField | Pre-filled terms & conditions |
| `default_notes` | TextField | Pre-filled invoice notes |

## Onboarding Wizard (3 Steps)

All new users are redirected here after registration. `OnboardingView` handles all 3 steps via `?step=N` query param.

**Step 1 — Company Details**
- Business name, GSTIN, PAN, address, state/state code, contact info
- Logo upload (max 2MB, image only)

**Step 2 — Bank Details**
- Bank name, account number, type, IFSC, UPI, QR code (max 5MB)
- Optional — user can skip

**Step 3 — Invoice Settings**
- Invoice prefix, counter start, financial year
- Due days, place of supply, default terms/notes
- Feature toggles (reverse charge, e-invoice, e-waybill)
- Show bank/signature on PDF

Completing step 3 marks onboarding as done. User is redirected to `/` (dashboard).

## UI Views (`views_ui.py`)

| View | URL | Description |
|---|---|---|
| `OnboardingView` | `/company/onboarding/?step=1|2|3` | 3-step setup wizard |
| `CompanyProfileView` | `/company/profile/` | Edit company profile post-onboarding |
| `BankDetailListView` | `/company/bank-details/` | List all bank accounts |
| `BankDetailCreateView` | `/company/bank-details/create/` | Add bank account |
| `BankDetailUpdateView` | `/company/bank-details/<pk>/edit/` | Edit bank account |
| `BankDetailDeleteView` | `/company/bank-details/<pk>/delete/` | Delete bank account |
| `SetPrimaryBankView` | `/company/bank-details/<pk>/set-primary/` | Set as primary bank |
| `InvoiceSettingsView` | `/company/invoice-settings/` | Edit invoice settings |

## URL Namespace: `company_ui`

```
company_ui:onboarding
company_ui:profile
company_ui:bank-list
company_ui:bank-create
company_ui:bank-edit
company_ui:bank-delete
company_ui:bank-set-primary
company_ui:invoice-settings
```

## Key Helpers

- `_validate_logo_file(file)` → validates image MIME + max 2MB
- `_validate_qr_file(file)` → validates image MIME + max 5MB
- `_onboarding_complete(company)` → checks if InvoiceSettings exists

## Notes for Agents

- `request.user.company_profile` is the standard accessor. If it raises `RelatedObjectDoesNotExist`, the user hasn't onboarded.
- `InvoiceSettings.invoice_counter` is incremented atomically in `InvoiceNumberGenerator.generate()` using `select_for_update()` — never increment it manually.
- When comparing state codes for GST (interstate/intrastate), use `company.state_code` vs `customer.billing_state_code`.
