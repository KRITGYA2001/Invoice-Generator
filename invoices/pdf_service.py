from __future__ import annotations

import base64
import os
import re
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright


class InvoicePDFService:
    """
    Generates invoice PDFs using Playwright (headless Chromium).
    Playwright renders HTML using a real Chrome engine so all
    modern CSS (Flexbox, Grid, custom fonts, etc.) works perfectly.

    PRODUCTION NOTE:
    Playwright requires Chromium browser binaries.
    On production server (Ubuntu/Debian) run:

      pip install playwright
      playwright install chromium
      playwright install-deps chromium

    On Docker: add to Dockerfile:
      RUN pip install playwright
      RUN playwright install chromium
      RUN playwright install-deps chromium

    Playwright PDF generation is synchronous and
    blocks the Django thread for 2-5 seconds.
    For high-traffic production use, consider:
      - Running PDF generation in Celery task
      - Using django-q or similar task queue
      - Returning a job ID and polling for result

    For now (single-user or low traffic):
    synchronous generation is fine.
    """

    COPY_LABELS = {
        1: ["Original for Recipient"],
        2: [
            "Original for Recipient",
            "Duplicate for Transporter",
        ],
        3: [
            "Original for Recipient",
            "Duplicate for Transporter",
            "Triplicate for Supplier",
        ],
    }

    @staticmethod
    def get_gst_breakdown(invoice) -> list[dict]:
        """
        Groups line items by gst_rate.
        Returns list of dicts sorted by gst_rate ascending.
        """
        from collections import defaultdict

        breakdown = defaultdict(
            lambda: {
                "gst_rate": Decimal("0"),
                "taxable_amount": Decimal("0"),
                "cgst_rate": Decimal("0"),
                "cgst_amount": Decimal("0"),
                "sgst_rate": Decimal("0"),
                "sgst_amount": Decimal("0"),
                "igst_rate": Decimal("0"),
                "igst_amount": Decimal("0"),
                "cess_amount": Decimal("0"),
                "total_tax": Decimal("0"),
            }
        )

        for item in invoice.line_items.all():
            rate = item.gst_rate
            breakdown[rate]["gst_rate"] = rate
            breakdown[rate]["taxable_amount"] += item.taxable_amount
            breakdown[rate]["cgst_rate"] = item.cgst_rate
            breakdown[rate]["cgst_amount"] += item.cgst_amount
            breakdown[rate]["sgst_rate"] = item.sgst_rate
            breakdown[rate]["sgst_amount"] += item.sgst_amount
            breakdown[rate]["igst_rate"] = item.igst_rate
            breakdown[rate]["igst_amount"] += item.igst_amount
            breakdown[rate]["cess_amount"] += item.cess_amount
            breakdown[rate]["total_tax"] += item.total_tax

        return sorted(breakdown.values(), key=lambda row: row["gst_rate"])

    @staticmethod
    def file_to_data_uri(file_field) -> str:
        """
        Converts a Django ImageField/FileField to a
        base64 data URI that Playwright can render
        without needing a running HTTP server.
        """
        if not file_field:
            return ""

        try:
            file_path = file_field.path
            if not os.path.exists(file_path):
                return ""

            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".svg": "image/svg+xml",
            }
            mime_type = mime_map.get(ext, "image/png")

            with open(file_path, "rb") as file_obj:
                data = base64.b64encode(file_obj.read()).decode()

            return f"data:{mime_type};base64,{data}"
        except Exception:
            return ""

    @staticmethod
    def build_context(invoice) -> dict:
        """
        Builds the full template context for the invoice.
        Fetches company, bank, settings, gst_breakdown.
        """
        company = invoice.company
        try:
            inv_settings = company.invoice_settings
        except Exception:
            inv_settings = None

        bank = company.bank_details.filter(is_primary=True, is_active=True).first()
        gst_breakdown = InvoicePDFService.get_gst_breakdown(invoice)
        line_items_qs = list(invoice.line_items.all().order_by("sr_no"))

        # Total quantity across all line items (for Grand Total row display)
        total_qty = sum(item.quantity for item in line_items_qs)
        units = [item.unit for item in line_items_qs if item.unit]
        predominant_unit = max(set(units), key=units.count) if units else "Pcs."
        total_qty_display = f"{total_qty:,.3f}".rstrip("0").rstrip(".") + f" {predominant_unit}"

        # Blank filler rows so the table fills the A4 page
        min_rows = 3
        filler_count = max(0, min_rows - len(line_items_qs))

        first_item = line_items_qs[0] if line_items_qs else None

        return {
            "invoice": invoice,
            "company": company,
            "bank": bank,
            "settings": inv_settings,
            "gst_breakdown": gst_breakdown,
            "line_items": line_items_qs,
            "first_item": first_item,
            "filler_rows": range(filler_count),
            "total_qty_display": total_qty_display,
            "company_logo_uri": InvoicePDFService.file_to_data_uri(company.logo),
            "company_signature_uri": InvoicePDFService.file_to_data_uri(company.signature_image),
            "bank_qr_uri": InvoicePDFService.file_to_data_uri(bank.qr_code_image if bank else None),
        }

    @staticmethod
    def render_invoice_html(invoice, num_copies: Optional[int] = None) -> str:
        """
        Renders the invoice HTML template for all copies.
        Returns complete HTML string ready for Playwright.
        """
        context = InvoicePDFService.build_context(invoice)

        if num_copies is None:
            settings_obj = context.get("settings")
            num_copies = getattr(settings_obj, "number_of_copies", 1) if settings_obj else 1

        num_copies = max(1, min(3, int(num_copies)))
        copy_labels = InvoicePDFService.COPY_LABELS.get(num_copies, InvoicePDFService.COPY_LABELS[1])

        copies_html = []
        for index, label in enumerate(copy_labels):
            context["copy_label"] = label
            context["is_first_copy"] = index == 0
            html = render_to_string("invoices/pdf_invoice.html", context)
            copies_html.append(html)

        if len(copies_html) == 1:
            return copies_html[0]

        return InvoicePDFService._combine_html_copies(copies_html)

    @staticmethod
    def _combine_html_copies(html_list: list[str]) -> str:
        """
        Combines multiple rendered HTML invoice copies
        into a single HTML document.
        """

        def extract_body(html: str) -> str:
            match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else html

        def extract_head(html: str) -> str:
            match = re.search(r"<head[^>]*>(.*?)</head>", html, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else ""

        head = extract_head(html_list[0])
        bodies = [extract_body(html) for html in html_list]

        page_break_css = """
        <style>
          .invoice-copy + .invoice-copy {
            page-break-before: always;
          }
        </style>
        """

        combined_body = "\n".join(f'<div class="invoice-copy">{body}</div>' for body in bodies)

        return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
{head}
{page_break_css}
</head>
<body>
{combined_body}
</body>
</html>"""

    @staticmethod
    def generate_pdf(invoice, num_copies: Optional[int] = None) -> bytes:
        """
        Generates PDF bytes using Playwright headless Chromium.
        """
        html_content = InvoicePDFService.render_invoice_html(invoice, num_copies)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            try:
                page = browser.new_page()
                page.set_content(
                    html_content,
                    wait_until="networkidle",
                    timeout=30000,
                )
                page.evaluate("""
                    () => document.fonts.ready
                """)
                return page.pdf(
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "5mm",
                        "right": "6mm",
                        "bottom": "5mm",
                        "left": "6mm",
                    },
                    prefer_css_page_size=False,
                )
            finally:
                browser.close()

    @staticmethod
    def get_pdf_filename(invoice) -> str:
        """
        Returns sanitized PDF filename.
        Format: Invoice_SSI_25-26_0001_CustomerName.pdf
        """
        inv_no = re.sub(r"[/\\]", "_", invoice.invoice_number)
        customer = re.sub(r"[^A-Za-z0-9_]", "_", invoice.customer_name[:30]).strip("_")
        return f"Invoice_{inv_no}_{customer}.pdf"

    @staticmethod
    def send_invoice_email(invoice, recipient_email: Optional[str] = None) -> bool:
        """
        Generates PDF and sends it as email attachment.
        """
        recipient = recipient_email or invoice.customer_email
        if not recipient:
            raise ValueError(
                "No email address available for this invoice. "
                "Please provide a recipient email."
            )

        pdf_bytes = InvoicePDFService.generate_pdf(invoice)
        filename = InvoicePDFService.get_pdf_filename(invoice)

        company = invoice.company
        try:
            bank = company.bank_details.filter(is_primary=True, is_active=True).first()
        except Exception:
            bank = None

        email_html = render_to_string(
            "invoices/email_invoice.html",
            {
                "invoice": invoice,
                "company": company,
                "bank": bank,
            },
        )

        subject = f"Invoice {invoice.invoice_number} from {company.company_name}"
        email = EmailMessage(
            subject=subject,
            body=email_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.content_subtype = "html"
        email.attach(filename, pdf_bytes, "application/pdf")
        email.send(fail_silently=False)
        return True
