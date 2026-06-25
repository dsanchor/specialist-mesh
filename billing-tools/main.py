from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4


OPENAPI_DOCUMENT = Path(__file__).with_name("openapi.yaml")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InvoiceRecord:
    invoice_id: str
    customer_id: str
    amount: float
    currency: str = "USD"
    due_date: str | None = None
    description: str = ""
    status: str = "open"
    created_at: str = field(default_factory=_timestamp)
    canceled_at: str | None = None


@dataclass
class BillingEvent:
    event_type: str
    message: str
    occurred_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)


INVOICES: dict[str, InvoiceRecord] = {}
CUSTOMER_INVOICES: dict[str, list[str]] = {}
ACCOUNT_BALANCES: dict[str, float] = {}
BILLING_ADDRESSES: dict[str, str] = {}
PAYMENT_METHODS: dict[str, dict[str, str]] = {}
BILLING_HISTORY: dict[str, list[BillingEvent]] = {}


def _seed_billing_data() -> None:
    samples = [
        InvoiceRecord(
            invoice_id="inv_001",
            customer_id="cust_acme",
            amount=1500.00,
            currency="USD",
            due_date="2026-07-15",
            description="Cloud hosting - June 2026",
            status="open",
        ),
        InvoiceRecord(
            invoice_id="inv_002",
            customer_id="cust_acme",
            amount=320.50,
            currency="USD",
            due_date="2026-06-30",
            description="API usage overage - May 2026",
            status="paid",
        ),
        InvoiceRecord(
            invoice_id="inv_003",
            customer_id="cust_globex",
            amount=8750.00,
            currency="EUR",
            due_date="2026-07-01",
            description="Enterprise license Q3 2026",
            status="open",
        ),
        InvoiceRecord(
            invoice_id="inv_004",
            customer_id="cust_globex",
            amount=450.00,
            currency="EUR",
            due_date="2026-05-15",
            description="Support add-on - April 2026",
            status="paid",
        ),
        InvoiceRecord(
            invoice_id="inv_005",
            customer_id="cust_wayne",
            amount=12000.00,
            currency="USD",
            due_date="2026-08-01",
            description="Annual platform subscription",
            status="open",
        ),
    ]
    for invoice in samples:
        INVOICES[invoice.invoice_id] = invoice
        CUSTOMER_INVOICES.setdefault(invoice.customer_id, []).append(invoice.invoice_id)

    ACCOUNT_BALANCES.update(
        {
            "cust_acme": 1500.00,
            "cust_globex": 8750.00,
            "cust_wayne": 12000.00,
        }
    )
    BILLING_ADDRESSES.update(
        {
            "cust_acme": "742 Evergreen Terrace, Springfield, IL 62704",
            "cust_globex": "100 Industrial Way, Shelbyville, IL 62565",
            "cust_wayne": "1007 Mountain Drive, Gotham, NJ 07001",
        }
    )
    PAYMENT_METHODS.update(
        {
            "cust_acme": {"payment_method_type": "card", "payment_method_token": "tok_visa_4242", "updated_at": "2026-01-10T09:00:00+00:00"},
            "cust_globex": {"payment_method_type": "sepa", "payment_method_token": "tok_sepa_de89", "updated_at": "2026-02-20T14:30:00+00:00"},
            "cust_wayne": {"payment_method_type": "card", "payment_method_token": "tok_amex_1234", "updated_at": "2026-03-05T11:00:00+00:00"},
        }
    )


_seed_billing_data()


def _append_history(customer_id: str, event_type: str, message: str, **metadata: Any) -> None:
    BILLING_HISTORY.setdefault(customer_id, []).append(
        BillingEvent(event_type=event_type, message=message, metadata=metadata)
    )


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int = 20) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def create_invoice(
    customer_id: str,
    amount: float,
    currency: str = "USD",
    due_date: str | None = None,
    description: str = "",
) -> str:
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
    return _json_response(asdict(invoice))


def get_invoice(invoice_id: str) -> str:
    invoice = INVOICES.get(invoice_id)
    if not invoice:
        return f'{{"error":"Invoice {invoice_id} not found"}}'
    return _json_response(asdict(invoice))


def list_invoices(customer_id: str, status: str | None = None) -> str:
    invoice_ids = CUSTOMER_INVOICES.get(customer_id, [])
    invoices = [INVOICES[invoice_id] for invoice_id in invoice_ids]
    if status:
        invoices = [invoice for invoice in invoices if invoice.status == status]
    return _json_response(
        {
            "customer_id": customer_id,
            "invoice_count": len(invoices),
            "invoices": [asdict(invoice) for invoice in invoices],
        }
    )


def cancel_invoice(invoice_id: str, reason: str = "Canceled by request") -> str:
    invoice = INVOICES.get(invoice_id)
    if not invoice:
        return f'{{"error":"Invoice {invoice_id} not found"}}'
    if invoice.status == "canceled":
        return _json_response(asdict(invoice))

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
    return _json_response(asdict(invoice))


def update_billing_address(customer_id: str, billing_address: str) -> str:
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


def get_account_balance(customer_id: str) -> str:
    return _json_response(
        {
            "customer_id": customer_id,
            "balance": round(ACCOUNT_BALANCES.get(customer_id, 0.0), 2),
            "currency": "USD",
            "retrieved_at": _timestamp(),
        }
    )


def apply_payment(customer_id: str, amount: float, payment_reference: str) -> str:
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


def generate_statement(
    customer_id: str,
    period_start: str | None = None,
    period_end: str | None = None,
) -> str:
    invoice_ids = CUSTOMER_INVOICES.get(customer_id, [])
    invoices = [asdict(INVOICES[invoice_id]) for invoice_id in invoice_ids]
    history = [asdict(event) for event in BILLING_HISTORY.get(customer_id, [])]
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


def update_payment_method(
    customer_id: str,
    payment_method_token: str,
    payment_method_type: str = "card",
) -> str:
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


def get_billing_history(customer_id: str, limit: int = 20) -> str:
    events = [asdict(event) for event in BILLING_HISTORY.get(customer_id, [])[-limit:]]
    return _json_response(
        {
            "customer_id": customer_id,
            "event_count": len(events),
            "events": events,
        }
    )


class BillingRequestHandler(BaseHTTPRequestHandler):
    server_version = "BillingToolsREST/1.0"

    def do_GET(self) -> None:
        path_parts = self._path_parts()
        query = self._query_params()

        if path_parts == ["health"]:
            self._send_json(_json_response({"status": "ok"}))
            return
        if path_parts == ["openapi.yaml"]:
            self._send_text(OPENAPI_DOCUMENT.read_text(encoding="utf-8"), "application/yaml")
            return
        if len(path_parts) == 2 and path_parts[0] == "invoices":
            self._send_json(get_invoice(path_parts[1]))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "invoices":
            self._send_json(list_invoices(path_parts[1], query.get("status", [None])[0]))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "balance":
            self._send_json(get_account_balance(path_parts[1]))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "billing-history":
            self._send_json(get_billing_history(path_parts[1], _int_value(query.get("limit", [20])[0])))
            return
        self._send_not_found()

    def do_POST(self) -> None:
        path_parts = self._path_parts()
        body = self._read_json_body()

        if path_parts == ["invoices"]:
            self._send_json(
                create_invoice(
                    body.get("customer_id", ""),
                    _float_value(body.get("amount")),
                    body.get("currency", "USD"),
                    body.get("due_date"),
                    body.get("description", ""),
                )
            )
            return
        if len(path_parts) == 3 and path_parts[0] == "invoices" and path_parts[2] == "cancel":
            self._send_json(cancel_invoice(path_parts[1], body.get("reason", "Canceled by request")))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "payments":
            self._send_json(apply_payment(path_parts[1], _float_value(body.get("amount")), body.get("payment_reference", "")))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "statement":
            self._send_json(generate_statement(path_parts[1], body.get("period_start"), body.get("period_end")))
            return
        self._send_not_found()

    def do_PUT(self) -> None:
        path_parts = self._path_parts()
        body = self._read_json_body()

        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "billing-address":
            self._send_json(update_billing_address(path_parts[1], body.get("billing_address", "")))
            return
        if len(path_parts) == 3 and path_parts[0] == "customers" and path_parts[2] == "payment-method":
            self._send_json(
                update_payment_method(
                    path_parts[1],
                    body.get("payment_method_token", ""),
                    body.get("payment_method_type", "card"),
                )
            )
            return
        self._send_not_found()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _path_parts(self) -> list[str]:
        path = urlparse(self.path).path.strip("/")
        return [unquote(part) for part in path.split("/") if part]

    def _query_params(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return {}
        if isinstance(body, dict):
            return body
        return {}

    def _send_json(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_text(payload, "application/json", status)

    def _send_text(self, payload: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        response = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _send_not_found(self) -> None:
        self._send_json(_json_response({"error": "Endpoint not found"}), HTTPStatus.NOT_FOUND)


def run(host: str = "0.0.0.0", port: int = 8091) -> None:
    server = ThreadingHTTPServer((host, port), BillingRequestHandler)
    print(f"Billing tools REST service listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
