from prescriptions.services import generate_invoice_number


def get_or_create_encounter_invoice(encounter):
    """Return the open invoice for an encounter, creating one if needed."""
    from billing.models import Invoice

    invoice = Invoice.objects.filter(encounter=encounter).exclude(status=Invoice.Status.VOID).first()
    if not invoice:
        invoice = Invoice.objects.create(
            patient=encounter.patient,
            encounter=encounter,
            invoice_number=generate_invoice_number(),
            status=Invoice.Status.DRAFT,
        )
    return invoice


def add_invoice_item(encounter, description, unit_price, quantity=1, service=None):
    invoice = get_or_create_encounter_invoice(encounter)
    from billing.models import InvoiceItem
    item = InvoiceItem.objects.create(
        invoice=invoice,
        service=service,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        total=unit_price * quantity,
    )
    invoice.recalculate()
    return item


def record_payment(invoice, amount, mode, reference, cashier, notes=""):
    from billing.models import Payment
    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        mode=mode,
        reference=reference,
        cashier=cashier,
        notes=notes,
    )
    invoice.amount_paid = sum(p.amount for p in invoice.payments.all())
    invoice.recalculate()
    return payment
