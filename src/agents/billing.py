from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_framework import Agent, tool
from pydantic import BaseModel, Field


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


class InvoiceRecord(BaseModel):
    invoice_id: str
    customer_id: str
    amount: float
    currency: str = "USD"
    due_date: str | None = None
    description: str = ""
    status: str = "open"
    created_at: str = Field(default_factory=_timestamp)
    canceled_at: str | None = None


class BillingEvent(BaseModel):
    event_type: str
    message: str
    occurred_at: str = Field(default_factory=_timestamp)
    metadata: dict[str, Any] = Field(default_factory=dict)


INVOICES: dict[str, InvoiceRecord] = {}
CUSTOMER_INVOICES: dict[str, list[str]] = {}
ACCOUNT_BALANCES: dict[str, float] = {}
BILLING_ADDRESSES: dict[str, str] = {}
PAYMENT_METHODS: dict[str, dict[str, str]] = {}
BILLING_HISTORY: dict[str, list[BillingEvent]] = {}


def _append_history(customer_id: str, event_type: str, message: str, **metadata: Any) -> None:
    BILLING_HISTORY.setdefault(customer_id, []).append(
        BillingEvent(event_type=event_type, message=message, metadata=metadata)
    )


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


@tool(approval_mode="never_require")
def create_invoice(
    customer_id: str,
    amount: float,
    currency: str = "USD",
    due_date: str | None = None,
    description: str = "",
) -> str:
    """Create a new invoice for a customer."""
    invoice_id = f"inv_{uuid4().hex[:10]}"
    invoice = InvoiceRecord(
        invoice_id=invoice_id,
        customer_id=customer_id,
        amount=round(amount, 2),
        currency=currency,
        due_date=due_date,
        description=description,
    )
    INVOICES[invoice_id] = invoice
    CUSTOMER_INVOICES.setdefault(customer_id, []).append(invoice_id)
    ACCOUNT_BALANCES[customer_id] = round(ACCOUNT_BALANCES.get(customer_id, 0.0) + invoice.amount, 2)
    _append_history(customer_id, "invoice_created", f"Invoice {invoice_id} created.", invoice_id=invoice_id)
    return invoice.model_dump_json(indent=2)


@tool(approval_mode="never_require")
def get_invoice(invoice_id: str) -> str:
    """Get invoice details by invoice ID."""
    invoice = INVOICES.get(invoice_id)
    if not invoice:
        return f'{{"error":"Invoice {invoice_id} not found"}}'
    return invoice.model_dump_json(indent=2)


@tool(approval_mode="never_require")
def list_invoices(customer_id: str, status: str | None = None) -> str:
    """List invoices for a customer."""
    invoice_ids = CUSTOMER_INVOICES.get(customer_id, [])
    invoices = [INVOICES[invoice_id] for invoice_id in invoice_ids]
    if status:
        invoices = [invoice for invoice in invoices if invoice.status == status]
    return _json_response(
        {
            "customer_id": customer_id,
            "invoice_count": len(invoices),
            "invoices": [invoice.model_dump() for invoice in invoices],
        }
    )


@tool(approval_mode="never_require")
def cancel_invoice(invoice_id: str, reason: str = "Canceled by request") -> str:
    """Cancel an open invoice."""
    invoice = INVOICES.get(invoice_id)
    if not invoice:
        return f'{{"error":"Invoice {invoice_id} not found"}}'
    if invoice.status == "canceled":
        return invoice.model_dump_json(indent=2)

    invoice.status = "canceled"
    invoice.canceled_at = _timestamp()
    ACCOUNT_BALANCES[invoice.customer_id] = round(
        ACCOUNT_BALANCES.get(invoice.customer_id, 0.0) - invoice.amount,
        2,
    )
    _append_history(
        invoice.customer_id,
        "invoice_canceled",
        f"Invoice {invoice_id} canceled.",
        invoice_id=invoice_id,
        reason=reason,
    )
    return invoice.model_dump_json(indent=2)


@tool(approval_mode="never_require")
def update_billing_address(customer_id: str, billing_address: str) -> str:
    """Update a customer's billing address."""
    BILLING_ADDRESSES[customer_id] = billing_address
    _append_history(
        customer_id,
        "billing_address_updated",
        "Billing address updated.",
        billing_address=billing_address,
    )
    return _json_response(
        {
            "customer_id": customer_id,
            "billing_address": billing_address,
            "updated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def get_account_balance(customer_id: str) -> str:
    """Get account balance for a customer."""
    return _json_response(
        {
            "customer_id": customer_id,
            "balance": round(ACCOUNT_BALANCES.get(customer_id, 0.0), 2),
            "currency": "USD",
            "retrieved_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def apply_payment(customer_id: str, amount: float, payment_reference: str) -> str:
    """Apply a payment to an account."""
    new_balance = round(ACCOUNT_BALANCES.get(customer_id, 0.0) - amount, 2)
    ACCOUNT_BALANCES[customer_id] = new_balance
    _append_history(
        customer_id,
        "payment_applied",
        f"Payment {payment_reference} applied.",
        amount=round(amount, 2),
        payment_reference=payment_reference,
    )
    return _json_response(
        {
            "customer_id": customer_id,
            "amount_applied": round(amount, 2),
            "payment_reference": payment_reference,
            "remaining_balance": new_balance,
            "processed_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def generate_statement(
    customer_id: str,
    period_start: str | None = None,
    period_end: str | None = None,
) -> str:
    """Generate a simulated account statement."""
    invoice_ids = CUSTOMER_INVOICES.get(customer_id, [])
    invoices = [INVOICES[invoice_id].model_dump() for invoice_id in invoice_ids]
    history = [event.model_dump() for event in BILLING_HISTORY.get(customer_id, [])]
    return _json_response(
        {
            "customer_id": customer_id,
            "period_start": period_start,
            "period_end": period_end,
            "balance": round(ACCOUNT_BALANCES.get(customer_id, 0.0), 2),
            "invoices": invoices,
            "activity": history,
            "generated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def update_payment_method(
    customer_id: str,
    payment_method_token: str,
    payment_method_type: str = "card",
) -> str:
    """Update a customer's payment method."""
    PAYMENT_METHODS[customer_id] = {
        "payment_method_type": payment_method_type,
        "payment_method_token": payment_method_token,
        "updated_at": _timestamp(),
    }
    _append_history(
        customer_id,
        "payment_method_updated",
        "Payment method updated.",
        payment_method_type=payment_method_type,
    )
    return _json_response(
        {
            "customer_id": customer_id,
            "payment_method": PAYMENT_METHODS[customer_id],
        }
    )


@tool(approval_mode="never_require")
def get_billing_history(customer_id: str, limit: int = 20) -> str:
    """Get recent billing history for a customer."""
    events = [event.model_dump() for event in BILLING_HISTORY.get(customer_id, [])[-limit:]]
    return _json_response(
        {
            "customer_id": customer_id,
            "event_count": len(events),
            "events": events,
        }
    )


def create_billing_agent(client: Any) -> Agent:
    return Agent(
        name="billing_specialist",
        client=client,
        instructions=(
            "You are the Billing specialist. Handle billing and invoicing requests only by "
            "using the provided tools. Complete the requested billing task, summarize the "
            "result clearly, and then hand control back to the coordinator."
        ),
        tools=[
            create_invoice,
            get_invoice,
            list_invoices,
            cancel_invoice,
            update_billing_address,
            get_account_balance,
            apply_payment,
            generate_statement,
            update_payment_method,
            get_billing_history,
        ],
        default_options={"store": False},
        require_per_service_call_history_persistence=True,
    )
