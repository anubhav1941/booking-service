"""HTTP client for inventory-service (synchronous REST).

- Timeout on every call so a slow inventory pod cannot hang booking requests.
- Retries with backoff only on network errors and 5xx. 4xx (e.g. 409 sold out) are business
  answers and are never retried.
- Retrying is safe because inventory-service treats booking_ref (PNR) as an idempotency key.
"""
import logging
import time

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class InventoryUnavailable(Exception):
    """inventory-service could not be reached / kept failing."""


class InventoryError(Exception):
    """inventory-service answered with a 4xx business error."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _request(method: str, path: str, json: dict | None = None) -> dict:
    url = f"{settings.inventory_url}{path}"
    last_exc: Exception | None = None
    for attempt in range(1, settings.inventory_retries + 1):
        try:
            resp = httpx.request(method, url, json=json, timeout=settings.inventory_timeout_s)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(f"{resp.status_code} from inventory", request=resp.request, response=resp)
            if resp.status_code >= 400:
                detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith(
                    "application/json") else resp.text
                raise InventoryError(resp.status_code, str(detail))
            log.info("%s %s -> %s (served by %s)", method, path, resp.status_code, resp.headers.get("X-Served-By"))
            return resp.json()
        except InventoryError:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            log.warning("inventory call %s %s failed (attempt %s/%s): %s",
                        method, path, attempt, settings.inventory_retries, exc)
            if attempt < settings.inventory_retries:
                time.sleep(0.3 * 2 ** (attempt - 1))  # 0.3s, 0.6s, 1.2s ...
    raise InventoryUnavailable(str(last_exc))


def hold_seats(train_no: str, journey_date: str, travel_class: str, seats: int, booking_ref: str) -> dict:
    return _request("POST", "/inventory/holds", json={
        "train_no": train_no,
        "journey_date": journey_date,
        "travel_class": travel_class,
        "seats": seats,
        "booking_ref": booking_ref,
    })


def confirm_hold(hold_id: str) -> dict:
    return _request("POST", f"/inventory/holds/{hold_id}/confirm")


def release_hold(hold_id: str) -> dict:
    return _request("POST", f"/inventory/holds/{hold_id}/release")


def is_reachable() -> bool:
    try:
        return httpx.get(f"{settings.inventory_url}/health", timeout=1.5).status_code == 200
    except httpx.HTTPError:
        return False
