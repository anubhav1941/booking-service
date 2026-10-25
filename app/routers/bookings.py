"""Booking API.

createBooking is an orchestrated saga owned by this service:
  1. save booking as PENDING                         (local transaction)
  2. inventory-service: hold seats                   (REST)  -> on failure: booking FAILED
  3. payment: charge                                 (mock)  -> on failure: release seats, booking FAILED
  4. inventory-service: confirm hold                 (REST)
  5. booking CONFIRMED                               (local transaction)

cancelBooking: release seats in inventory, refund, mark CANCELLED.
"""
import logging
import random

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import inventory_client as inventory
from app import payment
from app.database import get_db
from app.models import Booking, Passenger
from app.schemas import BookingCreate, BookingOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _new_pnr(db: Session) -> str:
    while True:
        pnr = str(random.randint(2_000_000_000, 9_999_999_999))  # 10-digit PNR
        if not db.get(Booking, pnr):
            return pnr


def _fail(db: Session, booking: Booking, reason: str, http_status: int) -> JSONResponse:
    booking.status = "FAILED"
    booking.failure_reason = reason
    db.commit()
    log.warning("Booking %s FAILED: %s", booking.pnr, reason)
    return JSONResponse(
        status_code=http_status,
        content=BookingOut.model_validate(booking).model_dump(mode="json"),
    )


# ---------- Commands ----------

@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED, summary="Book a ticket",
             responses={409: {"description": "Seats not available"}, 402: {"description": "Payment failed"},
                        404: {"description": "Train/date/class not found"},
                        503: {"description": "inventory-service unavailable"}})
def create_booking(body: BookingCreate, db: Session = Depends(get_db)):
    # Step 1: local PENDING record
    booking = Booking(
        pnr=_new_pnr(db),
        user_id=body.user_id,
        train_no=body.train_no,
        journey_date=body.journey_date,
        travel_class=body.travel_class,
        status="PENDING",
        passengers=[Passenger(**p.model_dump()) for p in body.passengers],
    )
    db.add(booking)
    db.commit()
    log.info("Booking %s PENDING for %s passenger(s)", booking.pnr, len(body.passengers))

    # Step 2: hold seats in inventory-service
    try:
        hold = inventory.hold_seats(body.train_no, body.journey_date.isoformat(), body.travel_class,
                                    len(body.passengers), booking.pnr)
    except inventory.InventoryError as e:
        return _fail(db, booking, e.detail, e.status_code)
    except inventory.InventoryUnavailable:
        return _fail(db, booking, "Inventory service unavailable, try again", status.HTTP_503_SERVICE_UNAVAILABLE)

    booking.hold_id = hold["hold_id"]
    booking.total_fare = hold["total_fare"]
    db.commit()

    # Step 3: payment (compensate by releasing seats if it fails)
    try:
        booking.payment_ref = payment.charge(booking.pnr, hold["total_fare"], body.simulate_payment_failure)
    except payment.PaymentFailed as e:
        try:
            inventory.release_hold(booking.hold_id)
        except (inventory.InventoryError, inventory.InventoryUnavailable):
            log.error("Could not release hold %s for %s, needs manual cleanup", booking.hold_id, booking.pnr)
        return _fail(db, booking, f"{e}. Seats released.", status.HTTP_402_PAYMENT_REQUIRED)

    # Step 4 + 5: confirm hold, confirm booking
    try:
        inventory.confirm_hold(booking.hold_id)
    except (inventory.InventoryError, inventory.InventoryUnavailable):
        # Seats are still held for this PNR, so we keep the booking confirmed and log it.
        log.error("Confirm call failed for hold %s, hold stays HELD", booking.hold_id)
    booking.status = "CONFIRMED"
    db.commit()
    log.info("Booking %s CONFIRMED, fare %s", booking.pnr, booking.total_fare)
    return booking


@router.post("/{pnr}/cancel", response_model=BookingOut, summary="Cancel a booking and refund")
def cancel_booking(pnr: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, pnr)
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"PNR {pnr} not found")
    if booking.status != "CONFIRMED":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only CONFIRMED bookings can be cancelled (current: {booking.status})")
    try:
        inventory.release_hold(booking.hold_id)
    except inventory.InventoryUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Inventory service unavailable, try again")
    except inventory.InventoryError as e:
        raise HTTPException(e.status_code, e.detail)
    booking.refund_ref = payment.refund(pnr, float(booking.total_fare or 0))
    booking.status = "CANCELLED"
    db.commit()
    log.info("Booking %s CANCELLED, refund %s", pnr, booking.refund_ref)
    return booking


# ---------- Queries ----------

@router.get("/{pnr}", response_model=BookingOut, summary="PNR status")
def get_booking(pnr: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, pnr)
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"PNR {pnr} not found")
    return booking


@router.get("", response_model=list[BookingOut], summary="List bookings of a user")
def list_bookings(user_id: str = Query(examples=["user-101"]), db: Session = Depends(get_db)):
    return db.scalars(select(Booking).where(Booking.user_id == user_id).order_by(Booking.created_at.desc())).all()
