# Billing Tools REST Service

REST service in Python that exposes the same billing operations and JSON payloads as the Billing agent tools.

## Run

```bash
python billing-tools/main.py
```

The service listens on `http://0.0.0.0:8091` by default.

The OpenAPI document is available in [openapi.yaml](openapi.yaml) and [openapi.json](openapi.json), and from the running service at `GET /openapi.yaml` and `GET /openapi.json`.

## Docker

Build and run locally:

```bash
docker build -t billing-tools:local billing-tools
docker run --rm -p 8091:8091 billing-tools:local
```

The GitHub Actions workflow publishes the image to:

```text
ghcr.io/dsanchor/specialist-mesh/billing-tools
```

## Operations

| Tool operation | Method | Endpoint | Body |
| --- | --- | --- | --- |
| `create_invoice` | `POST` | `/invoices` | `{"customer_id":"cust_acme","amount":99.95,"currency":"USD","due_date":"2026-08-15","description":"Support package"}` |
| `get_invoice` | `GET` | `/invoices/{invoice_id}` | None |
| `list_invoices` | `GET` | `/customers/{customer_id}/invoices?status=open` | None |
| `cancel_invoice` | `POST` | `/invoices/{invoice_id}/cancel` | Optional: `{"reason":"Canceled by request"}` |
| `update_billing_address` | `PUT` | `/customers/{customer_id}/billing-address` | `{"billing_address":"1 Market Street, San Francisco, CA 94105"}` |
| `get_account_balance` | `GET` | `/customers/{customer_id}/balance` | None |
| `apply_payment` | `POST` | `/customers/{customer_id}/payments` | `{"amount":100.0,"payment_reference":"pay_123"}` |
| `generate_statement` | `POST` | `/customers/{customer_id}/statement` | Optional: `{"period_start":"2026-06-01","period_end":"2026-06-30"}` |
| `update_payment_method` | `PUT` | `/customers/{customer_id}/payment-method` | `{"payment_method_token":"tok_visa_9999","payment_method_type":"card"}` |
| `get_billing_history` | `GET` | `/customers/{customer_id}/billing-history?limit=20` | None |

## Examples

```bash
curl http://localhost:8091/invoices/inv_001
curl http://localhost:8091/customers/cust_acme/invoices
curl http://localhost:8091/customers/cust_acme/balance
curl -X POST http://localhost:8091/customers/cust_acme/payments \
  -H 'Content-Type: application/json' \
  -d '{"amount":100.0,"payment_reference":"pay_123"}'
curl http://localhost:8091/openapi.yaml
curl http://localhost:8091/openapi.json
```
