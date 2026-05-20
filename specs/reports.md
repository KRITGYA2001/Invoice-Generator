# Reports App

## Purpose

Aggregated read-only reports. No models — all data is computed from Invoice, InvoiceLineItem, Customer, Product, and StockMovement records. Three report categories: GST compliance, Sales analytics, Inventory, and Outstanding receivables.

## No Models

The reports app has no `models.py`. It only queries existing data from other apps.

## Date Range Resolution

All report views use `resolve_date_range(request)` helper:

**Presets**:
- `this_month` — current calendar month
- `last_month` — previous calendar month
- `this_fy` — April 1 of current FY to today
- `last_fy` — full previous financial year
- `last_30` — last 30 days
- `last_90` — last 90 days
- `this_quarter` — current quarter (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar)
- `ytd` — Jan 1 to today
- `custom` — user-supplied `date_from` / `date_to` params

Returns a dict with `preset`, `date_from`, `date_to` for use in querysets and template context.

## GST Reports

### `GSTReportView` — `/reports/gst/`

Summary of GST collected in the selected date range for issued invoices:
- Total taxable value
- Total CGST, SGST, IGST, Cess collected
- Breakdown by GST rate slab
- Interstate vs intrastate split

### `GSTGSTR1View` — `/reports/gst/gstr1/`

GSTR-1 formatted report for filing:
- B2B invoices (customer has GSTIN)
- B2C invoices (no GSTIN)
- Filtered to ISSUED status only
- Grouped by customer GSTIN for B2B

### `GSTHSNView` — `/reports/gst/hsn/`

HSN-wise summary as required for GSTR-1:
- Groups line items by HSN/SAC code
- Shows: HSN, total quantity, taxable value, integrated tax, central tax, state tax, cess
- Useful for HSN summary table in GSTR-1

## Sales Reports

### `SalesReportView` — `/reports/sales/`

Overview of sales performance:
- Total invoices (count), total revenue, total tax collected
- Comparison to previous period (growth %)
- Month-by-month trend (for chart)

### `SalesByCustomerView` — `/reports/sales/customers/`

Revenue breakdown per customer:
- Customer name, invoice count, total business
- Sorted by total business descending
- Filterable by date range

### `SalesByProductView` — `/reports/sales/products/`

Revenue breakdown per product/line item:
- Product name, quantity sold, revenue
- Sorted by revenue descending

### `DailySalesView` — `/reports/sales/daily/`

Day-by-day sales log:
- Each day: invoice count + revenue
- Useful for spotting slow/busy periods

## Inventory Reports

### `InventoryReportView` — `/reports/inventory/`

Current stock snapshot across all active products:
- Product name, SKU, category, current stock, min stock
- Low stock flag
- Stock value (current_stock × purchase_price)

### `StockMovementView` — `/reports/inventory/movement/`

Filtered stock movement log:
- Filter by product, movement type, date range
- Shows: date, product, type, quantity, stock before/after, reference, created by

### `LowStockReportView` — `/reports/inventory/low-stock/`

All products where `current_stock <= min_stock`:
- Product name, current stock, min stock, shortfall
- Excludes services (`is_service=True`) and inactive products

## Outstanding Reports

### `OutstandingReportView` — `/reports/outstanding/`

Customers with positive `current_balance`:
- Customer name, balance, credit limit, over-limit flag
- Sorted by balance descending
- Total outstanding sum

### `AgeingReportView` — `/reports/outstanding/ageing/`

Receivables aged by invoice due date:
- Buckets: 0–30 days, 31–60 days, 61–90 days, 90+ days overdue
- Per-customer row showing amount in each bucket
- Grand total row

## URL Namespace: `reports_ui`

```
reports_ui:gst-report
reports_ui:gst-gstr1
reports_ui:gst-hsn
reports_ui:sales-report
reports_ui:sales-by-customer
reports_ui:sales-by-product
reports_ui:sales-daily
reports_ui:inventory-report
reports_ui:stock-movement
reports_ui:low-stock
reports_ui:outstanding-report
reports_ui:outstanding-ageing
```

## Notes for Agents

- All reports filter to ISSUED invoices only (not DRAFT or CANCELLED), unless the report explicitly includes cancelled (e.g., for reconciliation purposes).
- Reports are scoped to `request.user.company_profile` — no cross-company data.
- Reports have no write operations — they are all GET-only views.
- For GST reports, the date range applies to `invoice_date`, not `issued_at` or `created_at`.
- The ageing report uses `due_date` for bucketing. Invoices with no `due_date` should appear in the oldest bucket or be listed separately.
- `resolve_date_range()` is a shared utility — import from `reports/views_ui.py` if needed elsewhere.
