from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from invoices.models import Invoice, InvoiceLineItem
from invoices.services import AmountToWords


class InvoicePDFService:
    """Build invoice PDF bytes and send emails with attachments."""

    MAX_COPY_COUNT = 3

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
    def _copy_labels(num_copies, invoice: Invoice) -> list[str]:
        copy_count = num_copies or invoice.company.invoice_settings.number_of_copies or 1
        copy_count = max(1, min(int(copy_count), InvoicePDFService.MAX_COPY_COUNT))
        return [
            "Original for Recipient",
            "Duplicate for Transporter",
            "Triplicate for Supplier",
        ][:copy_count]

    @staticmethod
    def _format_amount(value: Any) -> str:
        if value in (None, ""):
            return "0.00"
        try:
            return f"{Decimal(str(value)):.2f}"
        except Exception:
            return str(value)

    @staticmethod
    def _text(value: Any) -> str:
        if value in (None, ""):
            return ""
        return escape(str(value)).replace("\n", "<br/>")

    @staticmethod
    def _generate_pdf_with_weasyprint(context: dict[str, Any], copy_labels: list[str]) -> bytes:
        try:
            from weasyprint import HTML
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "WeasyPrint is installed, but its native rendering libraries are not available in this environment."
            ) from exc

        fragments = []
        for index, copy_label in enumerate(copy_labels):
            copy_context = dict(context)
            copy_context["copy_label"] = copy_label.upper()
            copy_context["first_copy"] = index == 0
            fragments.append(render_to_string("invoices/pdf_invoice.html", copy_context))
        html = "<html><body>" + "".join(fragments) + "</body></html>"
        try:
            pdf_bytes = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
        except Exception as exc:
            raise RuntimeError(
                "WeasyPrint is installed, but its native rendering libraries are not available in this environment."
            ) from exc
        return pdf_bytes or b""

    @staticmethod
    def _generate_pdf_with_reportlab(context: dict[str, Any], copy_labels: list[str]) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        invoice = context["invoice"]
        company = context["company"]
        bank = context["bank"]
        settings_obj = context["settings"]
        gst_breakdown = context["gst_breakdown"]

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=colors.HexColor("#1a3a5c"),
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#1a3a5c"),
            spaceAfter=2,
        )
        small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10)
        tiny_style = ParagraphStyle("Tiny", parent=styles["BodyText"], fontName="Helvetica", fontSize=7, leading=9)
        right_style = ParagraphStyle(
            "Right",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
        )
        centered_style = ParagraphStyle(
            "Centered",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        )

        def money(value: Any) -> str:
            return f"₹{InvoicePDFService._format_amount(value)}"

        def line_text(value: Any) -> str:
            return InvoicePDFService._text(value) or "&nbsp;"

        def make_story(copy_label: str, first_page: bool) -> list[Any]:
            story: list[Any] = []
            if not first_page:
                story.append(PageBreak())

            company_lines = [InvoicePDFService._text(company.company_name)]
            if company.unit_division:
                company_lines.append(InvoicePDFService._text(company.unit_division))
            address_bits = [company.address_line1, company.address_line2, company.city, company.state, company.pincode]
            address = "<br/>".join(filter(None, [InvoicePDFService._text(bit) for bit in address_bits]))
            company_lines.append(address)
            if company.pan:
                company_lines.append(f"PAN: {InvoicePDFService._text(company.pan)}")
            if company.gstin:
                company_lines.append(f"GSTIN: {InvoicePDFService._text(company.gstin)}")

            story.append(Paragraph("<br/>".join(filter(None, company_lines)), title_style))
            story.append(Spacer(1, 4))

            header_table = Table(
                [[Paragraph("TAX INVOICE", centered_style), Paragraph(InvoicePDFService._text(copy_label).upper(), centered_style)]],
                colWidths=[110 * mm, 70 * mm],
            )
            header_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1a3a5c")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            story.append(header_table)
            story.append(Spacer(1, 6))

            meta_table = Table(
                [[
                    Paragraph(
                        f"Invoice No.: <b>{line_text(invoice.invoice_number)}</b><br/>"
                        f"Dated: {line_text(invoice.invoice_date)}<br/>"
                        f"Place of Supply: {line_text(invoice.place_of_supply)} ({line_text(invoice.place_of_supply_code)})<br/>"
                        f"Reverse Charge: {'Y' if invoice.reverse_charge else 'N'}<br/>"
                        f"Transport: {line_text(invoice.transport_mode)}",
                        small_style,
                    ),
                    Paragraph(
                        f"Vehicle No.: {line_text(invoice.vehicle_number)}<br/>"
                        f"Station: {line_text(invoice.station)}<br/>"
                        f"E-Way Bill No.: {line_text(invoice.eway_bill_number)}<br/>"
                        f"P.O. Number: {line_text(invoice.po_number)}<br/>"
                        f"P.O. Date: {line_text(invoice.po_date)}",
                        small_style,
                    ),
                ]],
                colWidths=[95 * mm, 85 * mm],
            )
            meta_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(meta_table)
            story.append(Spacer(1, 6))

            customer_table = Table(
                [[
                    Paragraph(
                        f"<b>Billed to:</b><br/><b>{line_text(invoice.customer_name)}</b><br/>{line_text(invoice.customer_address)}<br/>Party Mobile No: {line_text(invoice.customer_mobile)}<br/>GSTIN / UIN: {line_text(invoice.customer_gstin)}",
                        small_style,
                    ),
                    Paragraph(
                        f"<b>Shipped to:</b><br/><b>{line_text(invoice.shipping_name or invoice.customer_name)}</b><br/>{line_text(invoice.shipping_address or invoice.customer_address)}<br/>Party Mobile No: {line_text(invoice.customer_mobile)}<br/>GSTIN / UIN: {line_text(invoice.customer_gstin)}",
                        small_style,
                    ),
                ]],
                colWidths=[95 * mm, 85 * mm],
            )
            customer_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(customer_table)
            story.append(Spacer(1, 6))

            line_rows: list[list[Any]] = [["S.N.", "Description of Goods", "HSN/SAC Code", "Qty.", "Unit", "Price", "Amount(₹)"]]
            for line_item in invoice.line_items.all():
                description_parts = [f"<b>{InvoicePDFService._text(line_item.product_name)}</b>"]
                if line_item.description:
                    description_parts.append(InvoicePDFService._text(line_item.description))
                line_rows.append(
                    [
                        Paragraph(str(line_item.sr_no), tiny_style),
                        Paragraph("<br/>".join(description_parts), tiny_style),
                        Paragraph(InvoicePDFService._text(line_item.hsn_code), tiny_style),
                        Paragraph(InvoicePDFService._format_amount(line_item.quantity), tiny_style),
                        Paragraph(InvoicePDFService._text(line_item.unit), tiny_style),
                        Paragraph(money(line_item.unit_price), tiny_style),
                        Paragraph(money(line_item.taxable_amount), tiny_style),
                    ]
                )

            first_item = invoice.line_items.first()
            if first_item:
                if not invoice.is_interstate:
                    line_rows.append(["", Paragraph(f"Add : CGST @ {InvoicePDFService._format_amount(first_item.cgst_rate)} %", right_style), "", "", "", "", Paragraph(money(invoice.total_cgst), right_style)])
                    line_rows.append(["", Paragraph(f"Add : SGST @ {InvoicePDFService._format_amount(first_item.sgst_rate)} %", right_style), "", "", "", "", Paragraph(money(invoice.total_sgst), right_style)])
                else:
                    line_rows.append(["", Paragraph(f"Add : IGST @ {InvoicePDFService._format_amount(first_item.igst_rate)} %", right_style), "", "", "", "", Paragraph(money(invoice.total_igst), right_style)])
                if invoice.total_cess > 0:
                    line_rows.append(["", Paragraph(f"Add : CESS @ {InvoicePDFService._format_amount(first_item.cess_rate)} %", right_style), "", "", "", "", Paragraph(money(invoice.total_cess), right_style)])
            if invoice.round_off != 0:
                line_rows.append(["", Paragraph("Round Off", right_style), "", "", "", "", Paragraph(money(invoice.round_off), right_style)])

            line_rows.append(["", Paragraph("<b>Grand Total ₹</b>", right_style), "", "", "", "", Paragraph(f"<b>{InvoicePDFService._format_amount(invoice.grand_total)}</b>", right_style)])
            line_table = Table(line_rows, colWidths=[12 * mm, 63 * mm, 24 * mm, 14 * mm, 14 * mm, 26 * mm, 28 * mm], repeatRows=1)
            line_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("ALIGN", (1, 1), (1, -1), "LEFT"),
                        ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#1a3a5c")),
                        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ]
                )
            )
            story.append(line_table)
            story.append(Spacer(1, 6))

            tax_rows = [["Tax Rate", "Taxable Amt.", "CGST Amt.", "SGST Amt.", "Total Tax"]] if not invoice.is_interstate else [["Tax Rate", "Taxable Amt.", "IGST Amt.", "Total Tax"]]
            for row in gst_breakdown:
                if not invoice.is_interstate:
                    tax_rows.append([
                        f"{InvoicePDFService._format_amount(row['gst_rate'])}%",
                        money(row["taxable_amount"]),
                        money(row["cgst_amount"]),
                        money(row["sgst_amount"]),
                        money(row["total_tax"]),
                    ])
                else:
                    tax_rows.append([
                        f"{InvoicePDFService._format_amount(row['gst_rate'])}%",
                        money(row["taxable_amount"]),
                        money(row["igst_amount"]),
                        money(row["total_tax"]),
                    ])
            tax_table = Table(tax_rows, repeatRows=1)
            tax_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ]
                )
            )
            story.append(tax_table)
            story.append(Spacer(1, 6))

            amount_text = invoice.amount_in_words or AmountToWords.convert(invoice.grand_total)
            story.append(Paragraph(InvoicePDFService._text(amount_text), small_style))

            if settings_obj.show_bank_details and bank:
                bank_line = (
                    f"<b>Bank Details:</b><br/>{line_text(bank.bank_name)}, {line_text(bank.branch_name)} A/c No. {line_text(bank.account_number)}, "
                    f"IFSC Code {line_text(bank.ifsc_code)}"
                )
                if bank.ad_code:
                    bank_line += f" AD Code {line_text(bank.ad_code)}"
                if bank.swift_code:
                    bank_line += f" SWIFT Code {line_text(bank.swift_code)}"
                if bank.upi_id:
                    bank_line += f"<br/>UPI: {line_text(bank.upi_id)}"
                story.append(Paragraph(bank_line, small_style))

            if invoice.terms_and_conditions:
                story.append(Spacer(1, 4))
                story.append(Paragraph("<b>Terms & Conditions</b>", section_style))
                for index, term in enumerate(InvoicePDFService._text(invoice.terms_and_conditions).splitlines(), start=1):
                    if term.strip():
                        story.append(Paragraph(f"{index}. {term}", tiny_style))

            if invoice.notes:
                story.append(Spacer(1, 4))
                story.append(Paragraph(f"<i>Note: {InvoicePDFService._text(invoice.notes)}</i>", tiny_style))

            story.append(Spacer(1, 8))
            signature_table = Table(
                [[
                    Paragraph("Receiver's Signature :", small_style),
                    Paragraph(
                        f"for {InvoicePDFService._text(company.company_name)}<br/><br/><br/>__________________________<br/>{InvoicePDFService._text(company.authorised_signatory)}",
                        small_style,
                    ),
                ]],
                colWidths=[85 * mm, 95 * mm],
            )
            signature_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(signature_table)

            return story

        story: list[Any] = []
        for index, copy_label in enumerate(copy_labels):
            story.extend(make_story(copy_label, index == 0))

        document.build(story)
        return buffer.getvalue()

    @staticmethod
    def generate_pdf(invoice: Invoice, num_copies=None) -> bytes:
        """Generate invoice PDF bytes, preferring WeasyPrint and falling back to ReportLab."""
        context = InvoicePDFService.build_context(invoice)
        copy_labels = InvoicePDFService._copy_labels(num_copies, invoice)
        try:
            pdf_bytes = InvoicePDFService._generate_pdf_with_weasyprint(context, copy_labels)
            if pdf_bytes:
                return pdf_bytes
        except RuntimeError:
            pass
        return InvoicePDFService._generate_pdf_with_reportlab(context, copy_labels)

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
