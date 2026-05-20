# Products App

## Purpose

Manages the company's product/service catalog. Products are used as line items in invoices. Supports inventory tracking with an immutable stock movement log, categories, units of measurement, and bulk CSV upload.

## Models

### `ProductCategory`

Simple label for grouping products.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → CompanyProfile | |
| `name` | CharField | |
| `description` | TextField | Optional |
| `created_at` | DateTimeField | Auto |

**Unique together**: `(company, name)`

### `UnitOfMeasurement`

Units attached to products (e.g., Pieces, kg, metres, box).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → CompanyProfile | |
| `name` | CharField | Full name (e.g., "Kilogram") |
| `short_name` | CharField | Used on invoices (e.g., "kg") |
| `created_at` | DateTimeField | Auto |

**Unique together**: `(company, short_name)`

### `Product`

The invoiceable item or service.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → CompanyProfile | |
| `category` | FK → ProductCategory | Optional |
| `name` | CharField | |
| `sku` | CharField | Optional stock-keeping unit |
| `description` | TextField | Optional |
| `hsn_sac_code` | CharField | 4–8 digit HSN (goods) or SAC (services) |
| `unit` | FK → UnitOfMeasurement | Optional |
| `selling_price` | DecimalField | Default selling price |
| `purchase_price` | DecimalField | Optional, for margin tracking |
| `gst_rate` | DecimalField | GST % (0, 5, 12, 18, 28) |
| `cess_rate` | DecimalField | Cess % (default 0) |
| `is_service` | BooleanField | Services don't track stock |
| `track_inventory` | BooleanField | Whether to decrement stock on invoice |
| `opening_stock` | DecimalField | Set at creation |
| `current_stock` | DecimalField | Running total, updated by StockMovement |
| `min_stock` | DecimalField | Low stock threshold |
| `max_stock` | DecimalField | Optional max level |
| `image` | ImageField | Optional product image |
| `is_active` | BooleanField | Soft delete |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

**Properties**:
- `is_low_stock` → `bool`: `current_stock <= min_stock`
- `stock_value` → `Decimal`: `current_stock * purchase_price`
- `gst_amount` → `Decimal`: `selling_price * gst_rate / 100`

### `StockMovement`

Immutable audit log of every stock change. Never delete or edit records here.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `product` | FK → Product | |
| `movement_type` | CharField | IN / OUT / ADJUST / OPENING / RETURN |
| `quantity` | DecimalField | Positive or negative depending on type |
| `stock_before` | DecimalField | Stock level before this movement |
| `stock_after` | DecimalField | Stock level after (= before + quantity) |
| `reference_type` | CharField | e.g., "invoice", "adjustment" |
| `reference_id` | CharField | UUID of the related invoice/adjustment |
| `notes` | TextField | Optional memo |
| `created_by` | FK → User | |
| `created_at` | DateTimeField | Auto |

**Movement types**:
- `OPENING` — initial stock at product creation
- `IN` — stock received (purchase/return)
- `OUT` — stock consumed (invoice sale)
- `ADJUST` — manual correction
- `RETURN` — sales return

## UI Views (`views_ui.py`)

| View | URL | Description |
|---|---|---|
| `ProductListView` | `/products/` | Filterable, sortable list |
| `ProductCreateView` | `/products/create/` | New product form |
| `ProductDetailView` | `/products/<pk>/` | Product stats + movement history |
| `ProductUpdateView` | `/products/<pk>/edit/` | Edit product |
| `ProductDeleteView` | `/products/<pk>/delete/` | Soft delete |
| `StockAdjustView` | `/products/<pk>/stock/` | Manual stock adjustment form |
| `StockHistoryView` | `/products/<pk>/stock/history/` | Full movement log |
| `ProductCategoryListView` | `/products/categories/` | List + manage categories |
| `ProductCategoryCreateView` | `/products/categories/create/` | Add category |
| `ProductCategoryDeleteView` | `/products/categories/<pk>/delete/` | Delete category |
| `BulkUploadView` | `/products/bulk-upload/` | CSV import |
| `CSVTemplateDownloadView` | `/products/bulk-upload/template/` | Download CSV template |

## URL Namespace: `products_ui`

```
products_ui:product-list
products_ui:product-create
products_ui:product-detail
products_ui:product-edit
products_ui:product-delete
products_ui:stock-adjust
products_ui:stock-history
products_ui:category-list
products_ui:category-create
products_ui:category-delete
products_ui:bulk-upload
products_ui:csv-template
```

## Product List Filters

- Search: name, SKU, HSN code
- Filter: category, GST rate, active status, service/goods
- Low stock indicator
- Sorting: name, selling price, current stock

## Stock Service Pattern

All stock changes should go through the service layer (not direct model updates):

1. Create a `StockMovement` record with correct `stock_before`/`stock_after`
2. Update `product.current_stock`
3. Both steps in a database transaction

When an invoice is issued, the invoice service calls the stock service to decrement stock for each `track_inventory=True` product in the line items.

## Invoice Search Endpoints

Two read-only search endpoints are exposed under the `invoices_ui` namespace (not `products_ui`) for use in the invoice form:

- `invoices_ui:product-search` → returns partial HTML for HTMX search dropdown
- `invoices_ui:product-search-json` → returns JSON for Alpine.js auto-fill

Both filter to active products of the current company.

## Bulk CSV Upload

`BulkUploadView` accepts a CSV file matching the template from `CSVTemplateDownloadView`. Each row creates or updates a product (matched by SKU if present). Validation errors are returned row-by-row.

## Key Helpers

- `_validate_image(file)` → validates image MIME + max 2MB
- `_product_base_context(company)` → returns dict with all categories, units, and GST rate choices for form rendering

## Notes for Agents

- `is_service=True` products skip inventory tracking regardless of `track_inventory`.
- `current_stock` is a stored field, not computed — always update it through `StockMovement` to keep the audit log consistent.
- The `hsn_sac_code` is printed on GST invoice PDFs and GSTR-1 reports — it must be 4–8 digits.
- `gst_rate` on the product is just the default. The invoice line item stores its own rate (copied at invoice creation time), so changing a product's GST rate doesn't affect existing invoices.
