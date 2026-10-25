import os

os.environ["DATABASE_URL"] = "sqlite:///./test_booking.db"

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import inventory_client  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

TODAY = date.today().isoformat()


class FakeInventory:
    """Stands in for inventory-service so booking logic can be tested alone."""

    def __init__(self, seats=4, fare=1000.0):
        self.available = seats
        self.fare = fare
        self.holds = {}

    def hold_seats(self, train_no, journey_date, travel_class, seats, booking_ref):
        if self.available < seats:
            raise inventory_client.InventoryError(409, "Only %s seat(s) available" % self.available)
        self.available -= seats
        hid = f"hold-{booking_ref}"
        self.holds[hid] = {"seats": seats, "status": "HELD"}
        return {"hold_id": hid, "total_fare": self.fare * seats}

    def confirm_hold(self, hold_id):
        self.holds[hold_id]["status"] = "CONFIRMED"
        return {}

    def release_hold(self, hold_id):
        h = self.holds[hold_id]
        if h["status"] != "RELEASED":
            self.available += h["seats"]
            h["status"] = "RELEASED"
        return {}


@pytest.fixture()
def fake(monkeypatch):
    f = FakeInventory()
    for name in ("hold_seats", "confirm_hold", "release_hold"):
        monkeypatch.setattr(inventory_client, name, getattr(f, name))
    return f


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)
    engine.dispose()
    if os.path.exists("test_booking.db"):
        os.remove("test_booking.db")


def _req(n=2, fail=False):
    return {"user_id": "user-101", "train_no": "12952", "journey_date": TODAY, "travel_class": "1A",
            "passengers": [{"name": f"P{i}", "age": 30, "gender": "M"} for i in range(n)],
            "simulate_payment_failure": fail}


def test_booking_confirmed(client, fake):
    r = client.post("/bookings", json=_req(2))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "CONFIRMED" and len(b["pnr"]) == 10
    assert b["total_fare"] == 2000.0 and b["payment_ref"].startswith("PAY-")
    assert fake.available == 2
    assert client.get(f"/bookings/{b['pnr']}").json()["status"] == "CONFIRMED"


def test_sold_out_returns_409(client, fake):
    r = client.post("/bookings", json=_req(5))
    assert r.status_code == 409
    assert r.json()["status"] == "FAILED"


def test_payment_failure_releases_seats(client, fake):
    r = client.post("/bookings", json=_req(3, fail=True))
    assert r.status_code == 402
    assert "Seats released" in r.json()["failure_reason"]
    assert fake.available == 4  # compensation gave the seats back


def test_cancel_releases_seats(client, fake):
    pnr = client.post("/bookings", json=_req(4)).json()["pnr"]
    assert fake.available == 0
    c = client.post(f"/bookings/{pnr}/cancel")
    assert c.status_code == 200 and c.json()["status"] == "CANCELLED"
    assert fake.available == 4
    assert client.post(f"/bookings/{pnr}/cancel").status_code == 409


def test_inventory_down_returns_503(client, monkeypatch):
    def boom(*a, **k):
        raise inventory_client.InventoryUnavailable("connection refused")
    monkeypatch.setattr(inventory_client, "hold_seats", boom)
    r = client.post("/bookings", json=_req(1))
    assert r.status_code == 503 and r.json()["status"] == "FAILED"


def test_list_by_user(client):
    r = client.get("/bookings", params={"user_id": "user-101"})
    assert r.status_code == 200 and len(r.json()) >= 1
