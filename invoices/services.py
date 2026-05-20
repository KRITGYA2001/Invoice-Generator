from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from company.models import InvoiceSettings
from customers.models import Customer
from customers.services import CustomerService
from products.models import Product, StockMovement
from products.services import StockService


TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def quantize_money(value: Decimal) -> Decimal:
    """Round monetary values to 2 decimal places."""
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class GSTCalculator:
    """GST and invoice total calculator."""

    @staticmethod
    def calculate_line_item(
        unit_price: Decimal,
        quantity: Decimal,
        gst_rate: Decimal,
        cess_rate: Decimal,
        discount_percent: Decimal,
        is_interstate: bool,
    ) -> dict[str, Decimal]:
        """Calculate all tax components for a line item."""
        gross_amount = unit_price * quantity
        discount_amount = quantize_money(gross_amount * (discount_percent / Decimal("100")))
        taxable_amount = quantize_money(gross_amount - discount_amount)
        if is_interstate:
            cgst_rate = ZERO
            sgst_rate = ZERO
            igst_rate = gst_rate
        else:
            cgst_rate = quantize_money(gst_rate / Decimal("2"))
            sgst_rate = quantize_money(gst_rate / Decimal("2"))
            igst_rate = ZERO

        cgst_amount = quantize_money(taxable_amount * cgst_rate / Decimal("100"))
        sgst_amount = quantize_money(taxable_amount * sgst_rate / Decimal("100"))
        igst_amount = quantize_money(taxable_amount * igst_rate / Decimal("100"))
        cess_amount = quantize_money(taxable_amount * cess_rate / Decimal("100"))
        total_tax = quantize_money(cgst_amount + sgst_amount + igst_amount + cess_amount)
        line_total = quantize_money(taxable_amount + total_tax)
        return {
            "discount_amount": discount_amount,
            "taxable_amount": taxable_amount,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
            "igst_amount": igst_amount,
            "cess_amount": cess_amount,
            "total_tax": total_tax,
            "line_total": line_total,
        }

    @staticmethod
    def calculate_invoice_totals(line_items_data: list[dict[str, Decimal]], apply_round_off: bool = True) -> dict[str, Decimal]:
        """Aggregate invoice totals from line item calculations."""
        subtotal = quantize_money(sum((item["taxable_amount"] for item in line_items_data), ZERO))
        total_cgst = quantize_money(sum((item["cgst_amount"] for item in line_items_data), ZERO))
        total_sgst = quantize_money(sum((item["sgst_amount"] for item in line_items_data), ZERO))
        total_igst = quantize_money(sum((item["igst_amount"] for item in line_items_data), ZERO))
        total_cess = quantize_money(sum((item["cess_amount"] for item in line_items_data), ZERO))
        total_tax = quantize_money(total_cgst + total_sgst + total_igst + total_cess)
        pre_round_total = subtotal + total_tax
        if apply_round_off:
            round_off = quantize_money(round(pre_round_total) - pre_round_total)
        else:
            round_off = ZERO
        grand_total = quantize_money(pre_round_total + round_off)
        return {
            "subtotal": subtotal,
            "total_cgst": total_cgst,
            "total_sgst": total_sgst,
            "total_igst": total_igst,
            "total_cess": total_cess,
            "total_tax": total_tax,
            "round_off": round_off,
            "grand_total": grand_total,
        }


class InvoiceNumberGenerator:
    """Generate invoice numbers using company invoice settings."""

    @staticmethod
    def generate(company) -> str:
        """Generate the next invoice number under a row lock."""
        with transaction.atomic():
            settings = InvoiceSettings.objects.select_for_update().get(company=company)
            number = f"{settings.invoice_prefix}/{settings.financial_year}/{settings.invoice_counter:04d}"
            settings.invoice_counter += 1
            settings.save(update_fields=["invoice_counter", "updated_at"])
            return number


class AmountToWords:
    """Convert numeric amounts into Indian English words."""

    ONES = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]
    TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    @classmethod
    def _two_digit_words(cls, number: int) -> str:
        if number < 20:
            return cls.ONES[number]
        tens = cls.TENS[number // 10]
        ones = cls.ONES[number % 10]
        return f"{tens} {ones}".strip()

    @classmethod
    def _three_digit_words(cls, number: int) -> str:
        hundred = number // 100
        rest = number % 100
        parts = []
        if hundred:
            parts.append(f"{cls.ONES[hundred]} Hundred")
        if rest:
            parts.append(cls._two_digit_words(rest))
        return " and ".join(parts) if hundred and rest else " ".join(parts)

    @classmethod
    def _integer_to_words(cls, number: int) -> str:
        if number == 0:
            return "Zero"
        parts = []
        crore = number // 10000000
        number %= 10000000
        lakh = number // 100000
        number %= 100000
        thousand = number // 1000
        number %= 1000
        hundred_part = number
        if crore:
            parts.append(f"{cls._two_digit_words(crore)} Crore")
        if lakh:
            parts.append(f"{cls._two_digit_words(lakh)} Lakh")
        if thousand:
            parts.append(f"{cls._two_digit_words(thousand)} Thousand")
        if hundred_part:
            parts.append(cls._three_digit_words(hundred_part))
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def convert(amount: Decimal) -> str:
        """Convert a Decimal amount to Indian English words."""
        amount = quantize_money(amount)
        integer_part = int(amount)
        paise_part = int((amount - Decimal(integer_part)) * 100)
        words = AmountToWords._integer_to_words(integer_part)
        if paise_part:
            paise_words = AmountToWords._two_digit_words(paise_part)
            return f"Rupees {words} and Paise {paise_words} Only"
        return f"Rupees {words} Only"


class InvoiceService:
    """High-level invoice lifecycle operations."""

    @staticmethod
    def _resolve_product(company, product_ref):
        """Resolve a product reference into a company-scoped Product instance."""
        if not product_ref:
            return None
        try:
            return Product.objects.get(id=product_ref, company=company)
        except Product.DoesNotExist as exc:
            raise ValueError("One or more line items reference an invalid product") from exc

    @staticmethod
    def _build_line_item(invoice, company, item_data: dict[str, Any], sr_no: int):
        """Build an unsaved invoice line item from validated input."""
        from invoices.models import InvoiceLineItem

        product = InvoiceService._resolve_product(company, item_data.get("product"))
        product_name = item_data.get("product_name") or (product.name if product else "")
        hsn_code = item_data.get("hsn_code") or (product.hsn_code if product else "")
        description = item_data.get("description", product.description if product else "")
        quantity = item_data["quantity"]
        unit_price = item_data["unit_price"]
        discount_percent = item_data.get("discount_percent", Decimal("0"))
        gst_rate = item_data["gst_rate"]
        cess_rate = item_data.get("cess_rate", Decimal("0"))
        line_calc = GSTCalculator.calculate_line_item(
            unit_price=unit_price,
            quantity=quantity,
            gst_rate=gst_rate,
            cess_rate=cess_rate,
            discount_percent=discount_percent,
            is_interstate=invoice.is_interstate,
        )
        return InvoiceLineItem(
            invoice=invoice,
            product=product,
            sr_no=sr_no,
            product_name=product_name,
            hsn_code=hsn_code,
            description=description,
            quantity=quantity,
            unit=item_data["unit"],
            unit_price=unit_price,
            discount_percent=discount_percent,
            discount_amount=line_calc["discount_amount"],
            taxable_amount=line_calc["taxable_amount"],
            gst_rate=gst_rate,
            cgst_rate=line_calc["cgst_rate"],
            sgst_rate=line_calc["sgst_rate"],
            igst_rate=line_calc["igst_rate"],
            cess_rate=cess_rate,
            cgst_amount=line_calc["cgst_amount"],
            sgst_amount=line_calc["sgst_amount"],
            igst_amount=line_calc["igst_amount"],
            cess_amount=line_calc["cess_amount"],
            total_tax=line_calc["total_tax"],
            line_total=line_calc["line_total"],
        ), line_calc

    @staticmethod
    def _snapshot_customer(invoice, customer: Customer | None) -> None:
        """Copy customer billing details onto the invoice record."""
        if not customer:
            return
        invoice.customer_name = customer.display_name or customer.name
        invoice.customer_address = customer.full_billing_address
        invoice.customer_gstin = customer.gstin
        invoice.customer_state = customer.billing_state
        invoice.customer_state_code = customer.billing_state_code
        invoice.customer_mobile = customer.mobile_primary
        invoice.customer_email = customer.email

    @staticmethod
    def _snapshot_manual_customer(invoice, invoice_data: dict[str, Any]) -> None:
        """Copy manual customer fields onto the invoice record."""
        invoice.customer_name = invoice_data.get("customer_name", "")
        invoice.customer_address = invoice_data.get("customer_address", "")
        invoice.customer_gstin = invoice_data.get("customer_gstin", "")
        invoice.customer_state = invoice_data.get("customer_state", "")
        invoice.customer_state_code = invoice_data.get("customer_state_code", "")
        invoice.customer_mobile = invoice_data.get("customer_mobile", "")
        invoice.customer_email = invoice_data.get("customer_email", "")

    @staticmethod
    def _snapshot_shipping(invoice, customer: Customer | None, invoice_data: dict[str, Any]) -> None:
        """Resolve and snapshot the shipping address onto the invoice record.

        If shipping_same_as_billing is True, shipping fields are copied from the
        already-snapshotted billing data. Otherwise the caller-supplied shipping
        fields are used directly.
        """
        same = invoice_data.get("shipping_same_as_billing", True)
        invoice.shipping_same_as_billing = same

        if same:
            # Mirror the billing snapshot already set by _snapshot_customer / _snapshot_manual_customer
            if customer:
                invoice.shipping_name = customer.display_name or customer.name
                invoice.shipping_address_line1 = customer.billing_address_line1
                invoice.shipping_address_line2 = customer.billing_address_line2
                invoice.shipping_city = customer.billing_city
                invoice.shipping_state = customer.billing_state
                invoice.shipping_state_code = customer.billing_state_code
                invoice.shipping_pincode = customer.billing_pincode
                invoice.shipping_country = customer.billing_country
            else:
                invoice.shipping_name = invoice.customer_name
                invoice.shipping_address_line1 = invoice_data.get("customer_address", "")
                invoice.shipping_address_line2 = ""
                invoice.shipping_city = ""
                invoice.shipping_state = invoice.customer_state
                invoice.shipping_state_code = invoice.customer_state_code
                invoice.shipping_pincode = ""
                invoice.shipping_country = ""
        else:
            invoice.shipping_name = invoice_data.get("shipping_name", "") or invoice.customer_name
            invoice.shipping_address_line1 = invoice_data.get("shipping_address_line1", "")
            invoice.shipping_address_line2 = invoice_data.get("shipping_address_line2", "")
            invoice.shipping_city = invoice_data.get("shipping_city", "")
            invoice.shipping_state = invoice_data.get("shipping_state", "")
            invoice.shipping_state_code = invoice_data.get("shipping_state_code", "")
            invoice.shipping_pincode = invoice_data.get("shipping_pincode", "")
            invoice.shipping_country = invoice_data.get("shipping_country", "")

    @staticmethod
    def _snapshot_bank(invoice, company) -> None:
        """Copy primary bank details onto the invoice record."""
        primary_bank = company.bank_details.filter(is_primary=True, is_active=True).first()
        if not primary_bank:
            return
        invoice.bank_name = primary_bank.bank_name
        invoice.bank_account_number = primary_bank.account_number
        invoice.bank_ifsc = primary_bank.ifsc_code
        invoice.bank_branch = primary_bank.branch_name
        invoice.bank_upi_id = primary_bank.upi_id

    @staticmethod
    def create_invoice(company, customer, invoice_data, line_items_data, user):
        """Create a draft invoice with persisted line items and totals."""
        from invoices.models import Invoice, InvoiceLineItem

        with transaction.atomic():
            invoice_number = InvoiceNumberGenerator.generate(company)
            settings = company.invoice_settings
            invoice = Invoice(
                company=company,
                customer=customer,
                invoice_number=invoice_number,
                financial_year=settings.financial_year,
                status=Invoice.StatusChoices.DRAFT,
                created_by=user,
                updated_by=user,
                terms_and_conditions=invoice_data.get("terms_and_conditions", settings.invoice_terms),
                notes=invoice_data.get("notes", settings.invoice_notes),
                due_date=invoice_data.get("due_date") or None,
                invoice_date=invoice_data.get("invoice_date") or date.today(),
                place_of_supply=invoice_data.get("place_of_supply") or settings.default_place_of_supply or company.state,
                place_of_supply_code=invoice_data.get("place_of_supply_code") or company.state_code,
                reverse_charge=invoice_data.get("reverse_charge", settings.reverse_charge_applicable),
                transport_mode=invoice_data.get("transport_mode") or settings.default_transport,
                vehicle_number=invoice_data.get("vehicle_number", ""),
                station=invoice_data.get("station", ""),
                eway_bill_number=invoice_data.get("eway_bill_number", ""),
                po_number=invoice_data.get("po_number", ""),
                po_date=invoice_data.get("po_date") or None,
            )
            if customer:
                InvoiceService._snapshot_customer(invoice, customer)
            else:
                InvoiceService._snapshot_manual_customer(invoice, invoice_data)
            InvoiceService._snapshot_shipping(invoice, customer, invoice_data)
            InvoiceService._snapshot_bank(invoice, company)
            invoice.is_interstate = bool(
                customer and invoice.place_of_supply_code and customer.billing_state_code and invoice.place_of_supply_code != customer.billing_state_code
            )
            invoice.save()

            calculated_items = []
            invoice_items = []
            for index, item_data in enumerate(line_items_data, start=1):
                line_item, line_calc = InvoiceService._build_line_item(invoice, company, item_data, index)
                calculated_items.append(line_calc)
                invoice_items.append(line_item)
            InvoiceLineItem.objects.bulk_create(invoice_items)
            InvoiceService.recalculate_invoice(invoice)
            return Invoice.objects.select_related("customer", "company").prefetch_related("line_items").get(pk=invoice.pk)

    @staticmethod
    def recalculate_invoice(invoice):
        """Recalculate and persist draft invoice totals."""
        from invoices.models import InvoiceLineItem

        line_items = list(invoice.line_items.all().order_by("sr_no"))
        if not line_items:
            invoice.subtotal = ZERO
            invoice.total_cgst = ZERO
            invoice.total_sgst = ZERO
            invoice.total_igst = ZERO
            invoice.total_cess = ZERO
            invoice.total_tax = ZERO
            invoice.round_off = ZERO
            invoice.grand_total = ZERO
            invoice.amount_in_words = AmountToWords.convert(ZERO)
            invoice.save(update_fields=[
                "subtotal",
                "total_cgst",
                "total_sgst",
                "total_igst",
                "total_cess",
                "total_tax",
                "round_off",
                "grand_total",
                "amount_in_words",
                "updated_at",
            ])
            return invoice

        line_totals = []
        for line_item in line_items:
            line_calc = GSTCalculator.calculate_line_item(
                unit_price=line_item.unit_price,
                quantity=line_item.quantity,
                gst_rate=line_item.gst_rate,
                cess_rate=line_item.cess_rate,
                discount_percent=line_item.discount_percent,
                is_interstate=invoice.is_interstate,
            )
            for field, value in line_calc.items():
                setattr(line_item, field, value)
            line_item.save()
            line_totals.append(line_calc)

        totals = GSTCalculator.calculate_invoice_totals(line_totals, apply_round_off=True)
        invoice.subtotal = totals["subtotal"]
        invoice.total_cgst = totals["total_cgst"]
        invoice.total_sgst = totals["total_sgst"]
        invoice.total_igst = totals["total_igst"]
        invoice.total_cess = totals["total_cess"]
        invoice.total_tax = totals["total_tax"]
        invoice.round_off = totals["round_off"]
        invoice.grand_total = totals["grand_total"]
        invoice.amount_in_words = AmountToWords.convert(invoice.grand_total)
        invoice.save(update_fields=[
            "subtotal",
            "total_cgst",
            "total_sgst",
            "total_igst",
            "total_cess",
            "total_tax",
            "round_off",
            "grand_total",
            "amount_in_words",
            "updated_at",
        ])
        return invoice

    @staticmethod
    def issue_invoice(invoice, user):
        """Issue a draft invoice, deducting stock and updating customer balance."""
        if invoice.status != invoice.StatusChoices.DRAFT:
            raise ValueError("Cannot issue an invoice that is not in draft status")
        with transaction.atomic():
            invoice = invoice.__class__.objects.select_for_update().get(pk=invoice.pk)
            if invoice.status != invoice.StatusChoices.DRAFT:
                raise ValueError("Cannot issue an invoice that is not in draft status")
            for line_item in invoice.line_items.select_related("product").all():
                if line_item.product and line_item.product.track_inventory:
                    StockService.deduct_stock(
                        line_item.product,
                        line_item.quantity,
                        reference_type="invoice",
                        reference_id=invoice.id,
                        notes=f"Invoice {invoice.invoice_number}",
                        created_by=user,
                    )
            if invoice.customer:
                CustomerService.update_balance(invoice.customer, invoice.grand_total, "add")
            invoice.status = invoice.StatusChoices.ISSUED
            invoice.issued_at = timezone.now()
            invoice.updated_by = user
            invoice.save(update_fields=["status", "issued_at", "updated_by", "updated_at"])
            return invoice

    @staticmethod
    def cancel_invoice(invoice, reason, user):
        """Cancel an issued invoice and reverse stock and balance effects."""
        if invoice.status != invoice.StatusChoices.ISSUED:
            raise ValueError("Only issued invoices can be cancelled")
        with transaction.atomic():
            invoice = invoice.__class__.objects.select_for_update().get(pk=invoice.pk)
            if invoice.status != invoice.StatusChoices.ISSUED:
                raise ValueError("Only issued invoices can be cancelled")
            for line_item in invoice.line_items.select_related("product").all():
                if line_item.product and line_item.product.track_inventory:
                    StockService.add_stock(
                        line_item.product,
                        line_item.quantity,
                        reference_type="invoice_cancel",
                        reference_id=invoice.id,
                        notes=f"Cancellation of {invoice.invoice_number}",
                        movement_type="RETURN",
                        created_by=user,
                    )
            if invoice.customer:
                CustomerService.update_balance(invoice.customer, invoice.grand_total, "subtract")
            invoice.status = invoice.StatusChoices.CANCELLED
            invoice.cancelled_at = timezone.now()
            invoice.cancellation_reason = reason
            invoice.updated_by = user
            invoice.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_by", "updated_at"])
            return invoice
