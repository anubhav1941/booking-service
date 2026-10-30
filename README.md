<div align="center">

# 🎫 RailBook — Booking Service

[![CI](https://github.com/anubhav1941/booking-service/actions/workflows/ci.yml/badge.svg)](https://github.com/anubhav1941/booking-service/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

</div>

Part of **RailBook**, a microservices train ticket reservation system.
See [**railbook-deploy**](https://github.com/anubhav1941/railbook-deploy) for the architecture, Kubernetes manifests and full-system setup,
and [**inventory-service**](https://github.com/anubhav1941/inventory-service) for the seat inventory service.

Owns bookings and passengers (PNR). Orchestrates the booking saga:
hold seats in `inventory-service` (REST) → take payment (mocked) → confirm, or compensate by releasing seats.

> Academic project: BITS WILP, SEZG583 Scalable Services (2025MT03101).

## Tech
Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, httpx (REST client), Docker, Kubernetes.

## API

| Type | Method | Path | Purpose |
|---|---|---|---|
| Command | POST | `/bookings` | Book a ticket (1 to 6 passengers) |
| Command | POST | `/bookings/{pnr}/cancel` | Cancel, refund, release seats |
| Query | GET | `/bookings/{pnr}` | PNR status |
| Query | GET | `/bookings?user_id=` | Bookings of a user |
| Ops | GET | `/health`, `/ready` | Liveness / readiness probes |

Swagger UI: `http://<host>:<port>/docs`

### Booking outcomes
| Case | HTTP | Booking status |
|---|---|---|
| Seats held, payment OK | 201 | CONFIRMED |
| Not enough seats | 409 | FAILED |
| Payment fails (`"simulate_payment_failure": true`) | 402 | FAILED, seats released |
| Train/date/class not found | 404 | FAILED |
| inventory-service down (after 3 retries) | 503 | FAILED |

### Inter-service communication
- Synchronous REST over HTTP to `INVENTORY_SERVICE_URL` (in Kubernetes: `http://inventory-service`, resolved by cluster DNS and load balanced across inventory pods).
- 3 s timeout, 3 retries with exponential backoff on network errors / 5xx only.
- Retries are safe because inventory treats the PNR as an idempotency key.
- Payment Service is in the design but not implemented; `app/payment.py` is a stub with the same interface.

## Configuration (env vars)

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://booking:booking@localhost:5433/booking_db` |
| `INVENTORY_SERVICE_URL` | `http://localhost:8001` |
| `INVENTORY_TIMEOUT_SECONDS` | `3` |
| `INVENTORY_RETRIES` | `3` |
| `LOG_LEVEL` | `INFO` |

## Project structure
```
booking-service/
├── app/
│   ├── main.py              # FastAPI app, startup, probes
│   ├── config.py            # env based settings
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # Booking, Passenger tables
│   ├── schemas.py           # Pydantic models
│   ├── inventory_client.py  # REST client for inventory-service (timeout, retry)
│   ├── payment.py           # payment stub
│   └── routers/bookings.py  # saga orchestration, cancel, queries
├── tests/test_bookings.py   # inventory faked, covers confirm / sold out / payment fail / cancel / inventory down
├── Dockerfile
├── requirements.txt / requirements-dev.txt
└── .github/workflows/ci.yml
```

## Run
```bash
pip install -r requirements-dev.txt
python -m pytest -v
INVENTORY_SERVICE_URL=http://localhost:8001 uvicorn app.main:app --port 8002

docker build -t railbook/booking-service:1.0 .
```
Kubernetes manifests are in the `railbook-deploy` repo.

## CI/CD
GitHub Actions: test → build → push `<user>/booking-service` to Docker Hub. Needs secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.
