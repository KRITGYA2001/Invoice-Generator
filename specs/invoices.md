# Invoices App

## Purpose

The core of BillMint. Manages the full invoice lifecycle: draft → issue → (cancel). Includes PDF generation, email delivery, party/product search for the create/edit form, and inline party creation.

## Models

### `Invoice`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → CompanyProfile | |
| `invoice_number` | CharField | Auto-generated on issue |
| `invoice_date` | DateField | |
| `due_date` | DateField | Optional |
| `status` | CharField | DRAFT / ISSUED / CANCELLED |
| — **Customer snapshot** — | | Copied from Customer on issue |
| `customer` | FK → Customer | Nullable (for walk-in) |
| `customer_name` | CharField | Snapshot of name at issue time |
| `customer_gstin` | CharField | Snapshot |
| `customer_address` | TextField | Snapshot of full billing address |
| `customer_state` | CharField | Snapshot of billing state |
| `customer_state_code` | CharField | Snapshot of billing state code |
| `customer_mobile` | CharField | Snapshot |
| — **Shipping** — | | |
| `shipping_same_as_billing` | BooleanField | If True, shipping = billing |
| `shipping_name` | CharField | Recipient name at shipping address |
| `shipping_address_line1` | CharField | |
| `shipping_address_line2` | CharField | |
| `shipping_city` | CharField | |
| `shipping_state` | CharField | |
| `shipping_state_code` | CharField(2) | |
| `shipping_pincode` | CharField | |
| `shipping_country` | CharField | Default "India" |
| — **Totals** — | | |
| `subtotal` | DecimalField | Sum of line taxable amounts |
| `cgst_amount` | DecimalField | |
| `sgst_amount` | DecimalField | |
| `igst_amount` | DecimalField | |
| `cess_amount` | DecimalField | |
| `total_tax` | DecimalField | |
| `round_off` | DecimalField | |
| `grand_total` | DecimalField | |
| — **Tax flags** — | | |
| `is_interstate` | BooleanField | Drives IGST vs CGST+SGST |
| `reverse_charge` | BooleanField | |
| `place_of_supply` | CharField | |
| — **Transport** — | | |
| `transport_name` | CharField | |
| `vehicle_number` | CharField | |
| `lr_number` | CharField | |
| `eway_bill_number` | CharField | |
| — **Bank** — | | |
| `bank_detail` | FK → BankDetail | Snapshot for PDF |
| — **E-invoice** — | | |
| `irn` | CharField | IRN from NIC e-invoice API |
| `irn_generated_at` | DateTimeField | |
| — **Audit** — | | |
| `notes` | TextField | Internal notes |
| `terms` | TextField | Printed on invoice |
| `created_by` | FK → User | |
| `updated_by` | FK → User | |
| `issued_at` | DateTimeField | Timestamp when status → ISSUED |
| `cancelled_at` | DateTimeField | |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

**Unique together**: `(company, invoice_number)`

**Ordering**: `(-invoice_date, -created_at)`

### `InvoiceLineItem`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `invoice` | FK → Invoice | |
| `product` | FK → Product | Nullable (manual line) |
| `sr_no` | PositiveIntegerField | Display order |
| `product_name` | CharField | Snapshot or manual entry |
| `description` | TextField | |
| `hsn_sac_code` | CharField | |
| `quantity` | DecimalField | |
| `unit` | CharField | UOM short name |
| `unit_price` | DecimalField | Before discount |
| `discount_percent` | DecimalField | |
| `discount_amount` | DecimalField | |
| `taxable_amount` | DecimalField | After discount |
| `cgst_rate` | DecimalField | |
| `cgst_amount` | DecimalField | |
| `sgst_rate` | DecimalField | |
| `sgst_amount` | DecimalField | |
| `igst_rate` | DecimalField | |
| `igst_amount` | DecimalField | |
| `cess_rate` | DecimalField | |
| `cess_amount` | DecimalField | |
| `line_total` | DecimalField | taxable + all tax amounts |

**Ordering**: `sr_no`

## Invoice Statuses

```
DRAFT → ISSUED → CANCELLED
            ↑
     (cannot go back to DRAFT)
DRAFT can be deleted.
ISSUED and CANCELLED cannot be deleted.
```

- **DRAFT**: editable, no invoice number assigned, no stock decremented
- **ISSUED**: locked (read-only), invoice number assigned, stock decremented, customer balance updated
- **CANCELLED**: locked, stock movement reversed, customer balance reversed

## Services (`services.py`)

### `GSTCalculator`

Handles all tax arithmetic. No database access — pure calculation.

**`calculate_line_item(qty, unit_price, discount_percent, gst_rate, cess_rate, is_interstate)`**
- Returns dict: `{taxable_amount, cgst_rate, cgst_amount, sgst_rate, sgst_amount, igst_rate, igst_amount, cess_rate, cess_amount, line_total}`
- Interstate → IGST only; Intrastate → CGST + SGST (split equally)

**`calculate_invoice_totals(line_items, round_off=True)`**
- Aggregates from all line items
- Returns: `{subtotal, cgst_amount, sgst_amount, igst_amount, cess_amount, total_tax, round_off, grand_total}`

### `InvoiceNumberGenerator`

**`generate(company)`**
- Reads `InvoiceSettings` for prefix, counter, financial year
- Uses `select_for_update()` to prevent race conditions
- Increments counter atomically
- Returns formatted string: `PREFIX/FY/COUNTER` (e.g., `INV/25-26/0042`)

### `AmountToWords`

Converts `grand_total` to Indian English words for invoice PDF footer.

## Snapshotting Pattern

When an invoice transitions from DRAFT → ISSUED:
1. Customer fields are copied into `customer_name`, `customer_address`, etc.
2. Product names and HSN codes are copied into line item snapshot fields
3. `invoice_number` is generated and assigned
4. These snapshots are immutable — future edits to the customer/product don't change the invoice

This means issued invoices are self-contained documents. The `customer` FK stays for linking, but all printed fields come from snapshots.

## Shipping Address Pattern

Shipping address is stored per-invoice (not on the Customer model).

- `shipping_same_as_billing = True` → display billing address for shipping (no separate shipping fields needed)
- `shipping_same_as_billing = False` → use the structured `shipping_*` fields

On the invoice create/edit form:
- A "Same as Billing Address" toggle (Alpine.js `sameAsBilling` state) controls field visibility
- If toggled ON when submitting, the shipping fields are not sent / are ignored by the view

## UI Views (`views_ui.py`)

| View | URL | Description |
|---|---|---|
| `InvoiceListView` | `/invoices/` | Filterable list (status, date, customer) |
| `InvoiceCreateView` | `/invoices/create/` | Full invoice form with party + product search |
| `InvoiceDetailView` | `/invoices/<pk>/` | Read-only issued invoice view |
| `InvoiceUpdateView` | `/invoices/<pk>/edit/` | Edit DRAFT invoice |
| `InvoiceIssueView` | `/invoices/<pk>/issue/` | Issue (DRAFT → ISSUED) |
| `InvoiceCancelView` | `/invoices/<pk>/cancel/` | Cancel (ISSUED → CANCELLED) |
| `InvoiceDuplicateView` | `/invoices/<pk>/duplicate/` | Clone invoice as new DRAFT |
| `InvoicePDFView` | `/invoices/<pk>/pdf/` | Download PDF (WeasyPrint) |
| `InvoiceEmailView` | `/invoices/<pk>/send-email/` | Send invoice PDF via email |
| `CustomerSearchView` | `/invoices/customer-search/` | HTMX partial: party search results |
| `CustomerSearchJsonView` | `/invoices/customer-search-json/` | JSON party search for Alpine |
| `CustomerQuickCreateView` | `/invoices/customer-quick-create/` | JSON endpoint: inline party creation |
| `ProductSearchView` | `/invoices/product-search/` | HTMX partial: product search results |
| `ProductSearchJsonView` | `/invoices/product-search-json/` | JSON product search for Alpine |

## URL Namespace: `invoices_ui`

```
invoices_ui:invoice-list
invoices_ui:invoice-create
invoices_ui:invoice-detail
invoices_ui:invoice-edit
invoices_ui:invoice-issue
invoices_ui:invoice-cancel
invoices_ui:invoice-duplicate
invoices_ui:invoice-pdf
invoices_ui:invoice-email
invoices_ui:customer-search
invoices_ui:customer-search-json
invoices_ui:customer-quick-create
invoices_ui:product-search
invoices_ui:product-search-json
```

## Invoice Form Architecture (Alpine + HTMX)

The create/edit form (`invoice_form.html`) is built with a layered client-side architecture:

### `invoiceApp()` (main Alpine component on `<form>`)

The root Alpine data object. Controls:
- `showCreatePartyModal` — whether the inline party creation modal is open
- `creatingParty`, `createPartyErrors`, `createPartyForm` — modal state
- `customerStateCode`, `customerStateName` — selected party's state (drives interstate detection)
- `is_interstate` — computed from company state vs customer state code
- Line item array: add/remove rows, quantity/price changes
- Real-time total calculation (mirrors server-side `GSTCalculator` logic)

**Methods**:
- `selectCustomer(id, name, gstin, stateCode, stateName, mobile)` — populates Bill To section
- `updateInterstate()` — recomputes `is_interstate` based on state codes
- `openCreatePartyModal()` / `closeCreatePartyModal()` — modal lifecycle
- `extractModalGstinState()` — auto-fills state from GSTIN in the modal
- `submitCreateParty()` — async POST to `customer-quick-create`, calls `selectCustomer()` on success
- `addLineItem()` / `removeLineItem(idx)` / `recalcTotals()` — line item management

### Bill To Card (nested `x-data`)

Has its own Alpine scope but listens for `@customer-selected.window` dispatched by `invoiceApp()` via `selectCustomer()`. Displays:
1. Always-visible search input (HTMX-powered, calls `customer-search`)
2. "+ Add Party" button → dispatches `open-create-party-modal` to `invoiceApp()`
3. Selected party card (shown after selection, with Clear button)

### Customer Search Flow

```
User types in search input
  → HTMX GET /invoices/customer-search/?q=... (delay 300ms)
  → Server returns partial HTML (_customer_results.html)
  → User clicks a result
  → Result calls selectCustomer(...) on invoiceApp()
  → invoiceApp() dispatches customer-selected event
  → Bill To card shows selected party card
```

### Quick Create Party Flow

```
User clicks "+ Add Party"
  → Bill To card dispatches open-create-party-modal
  → invoiceApp() receives event, sets showCreatePartyModal = true
  → Modal renders (centered overlay, position:fixed)
  → User fills minimal form (name, mobile, address required)
  → submitCreateParty() POSTs to /invoices/customer-quick-create/
  → On success: selectCustomer() is called with returned data
  → Modal closes, party is selected
```

### Product Search Flow

```
User types in product search input on a line item
  → HTMX GET /invoices/product-search/?q=...
  → Server returns partial HTML
  → User clicks product
  → Product data (price, HSN, GST rate) auto-fills that line item
  → Alpine recalcTotals() updates all totals
```

## `CustomerQuickCreateView`

POST-only JSON endpoint at `/invoices/customer-quick-create/`.

**Required fields**: `name`, `mobile_primary`, `billing_address_line1`, `billing_city`, `billing_state`, `billing_state_code`, `billing_pincode`

**Optional**: `display_name`, `party_type`, `gstin`, `email`, `billing_address_line2`, `billing_country`

**Validation**:
- `name` unique per company
- GSTIN format (regex: `^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$`)
- `billing_state_code` exactly 2 digits

**Response on success**:
```json
{
  "success": true,
  "customer": {
    "id": "<uuid>",
    "name": "...",
    "display_name": "...",
    "gstin": "...",
    "billing_state": "...",
    "billing_state_code": "...",
    "mobile_primary": "..."
  }
}
```

**Response on error**:
```json
{ "success": false, "errors": { "name": "...", "gstin": "..." } }
```

## PDF Generation

`InvoicePDFView` uses WeasyPrint to render the invoice detail template as a downloadable PDF. The PDF template is a separate template file that includes:
- Company header (logo, name, address, GSTIN)
- Invoice metadata (number, date, due date)
- Bill To and Ship To sections (from snapshots)
- Line items table with GST columns
- Totals block (subtotal, tax breakdown, grand total, amount in words)
- Bank details (if `InvoiceSettings.show_bank_details`)
- Terms & conditions
- Signature (if `InvoiceSettings.show_signature`)

## Notes for Agents

- Never allow editing an ISSUED or CANCELLED invoice. Check `invoice.status == 'DRAFT'` before allowing edits.
- `invoice_number` is only assigned at issue time. DRAFT invoices have no invoice number.
- The interstate flag (`is_interstate`) is determined at save time by comparing `company.state_code` with `customer.billing_state_code` (or the snapshot `customer_state_code` for issued invoices).
- All monetary fields use `DecimalField` with 2 decimal places. Use `quantize_money()` from `services.py` for rounding, not Python's built-in `round()`.
- The `customer` FK on Invoice is nullable to support walk-in customers (no registered party). In that case, `customer_name` etc. are filled manually.
- `InvoiceSettings.show_bank_details` and `show_signature` control PDF rendering — check these flags, not just whether bank/signature data exists.
