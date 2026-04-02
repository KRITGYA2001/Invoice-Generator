from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from invoices.models import Invoice, InvoiceLineItem
from invoices.services import AmountToWords


class InvoicePDFService:
    """Build invoice PDF HTML, render bytes, and send emails with attachments."""

    @staticmethod
    def get_gst_breakdown(invoice: Invoice) -> list[dict[str, Any]]:
        """Group line items by GST rate and aggregate their totals."""
        groups: dict[str, dict[str, Any]] = {}
        for line_item in InvoiceLineItem.objects.filter(invoice=invoice):
            key = str(line_item.gst_rate)
            if key not in groups:
                groups[key] = {
                    "gst_rate": line_item.gst_rate,
                    "taxable_amount": Decimal("0.00"),
                    "cgst_rate": line_item.cgst_rate,
                    "cgst_amount": Decimal("0.00"),
                    "sgst_rate": line_item.sgst_rate,
                    "sgst_amount": Decimal("0.00"),
                    "igst_rate": line_item.igst_rate,
                    "igst_amount": Decimal("0.00"),
                    "cess_amount": Decimal("0.00"),
                    "total_tax": Decimal("0.00"),
                }
            bucket = groups[key]
            bucket["taxable_amount"] += line_item.taxable_amount
            bucket["cgst_amount"] += line_item.cgst_amount
            bucket["sgst_amount"] += line_item.sgst_amount
            bucket["igst_amount"] += line_item.igst_amount
            bucket["cess_amount"] += line_item.cess_amount
            bucket["total_tax"] += line_item.total_tax
        return [groups[key] for key in sorted(groups.keys(), key=lambda value: Decimal(value))]

    @staticmethod
    def build_context(invoice: Invoice) -> dict[str, Any]:
        """Build template context for an invoice PDF."""
        company = invoice.company
        bank = company.bank_details.filter(is_primary=True, is_active=True).first()
        settings_obj = company.invoice_settings
        gst_breakdown = InvoicePDFService.get_gst_breakdown(invoice)

        def as_file_uri(image_field):
            if not image_field:
                return None
            return Path(image_field.path).resolve().as_uri()

        return {
            "invoice": invoice,
            "company": company,
            "bank": bank,
            "gst_breakdown": gst_breakdown,
            "settings": settings_obj,
            "company_logo_src": as_file_uri(company.logo),
            "company_signature_src": as_file_uri(company.signature_image),
            "bank_qr_src": as_file_uri(bank.qr_code_image) if bank else None,
        }

    @staticmethod
    def generate_pdf(invoice: Invoice, num_copies=None) -> bytes:
        """Generate invoice PDF bytes using WeasyPrint."""
        try:
            from weasyprint import HTML
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "WeasyPrint is installed, but its native rendering libraries are not available in this environment."
            ) from exc

        context = InvoicePDFService.build_context(invoice)
        copy_count = num_copies or invoice.company.invoice_settings.number_of_copies or 1
        copy_count = max(1, min(int(copy_count), 3))
        copy_labels = [
            "Original for Recipient",
            "Duplicate for Transporter",
            "Triplicate for Supplier",
        ][:copy_count]
        fragments = []
        for index, copy_label in enumerate(copy_labels):
            copy_context = dict(context)
            copy_context["copy_label"] = copy_label.upper()
            copy_context["first_copy"] = index == 0
            fragments.append(render_to_string("invoices/pdf_invoice.html", copy_context))
        html = "<html><body>" + "".join(fragments) + "</body></html>"
        pdf_bytes = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
        return pdf_bytes or b""

    @staticmethod
    def get_pdf_filename(invoice: Invoice) -> str:
        """Build a safe PDF filename for an invoice."""
        customer_name = (invoice.customer_name or "customer").replace("/", "_").replace(" ", "_")
        invoice_number = invoice.invoice_number.replace("/", "_").replace(" ", "_")
        return f"Invoice_{invoice_number}_{customer_name}.pdf"

    @staticmethod
    def send_invoice_email(invoice: Invoice, recipient_email=None) -> bool:
        """Send an invoice PDF to the party or override email address."""
        recipient = recipient_email or invoice.customer_email
        if not recipient:
            raise ValueError("No recipient email available")

        pdf_bytes = InvoicePDFService.generate_pdf(invoice)
        email_context = {
            "invoice": invoice,
            "company": invoice.company,
            "bank": invoice.company.bank_details.filter(is_primary=True, is_active=True).first(),
            "settings": invoice.company.invoice_settings,
        }
        body = render_to_string("invoices/email_invoice.html", email_context)
        message = EmailMessage(
            subject=f"Invoice {invoice.invoice_number} from {invoice.company.company_name}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.content_subtype = "html"
        message.attach(InvoicePDFService.get_pdf_filename(invoice), pdf_bytes, "application/pdf")
        message.send(fail_silently=False)
        return True
