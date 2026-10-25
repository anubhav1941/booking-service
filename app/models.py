from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Booking(Base):
    """Booking aggregate. Status flow: PENDING -> CONFIRMED -> CANCELLED, or PENDING -> FAILED."""

    __tablename__ = "bookings"

    pnr: Mapped[str] = mapped_column(String(10), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    train_no: Mapped[str] = mapped_column(String(10))
    journey_date: Mapped[date] = mapped_column(Date)
    travel_class: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    total_fare: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    hold_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # reference to inventory-service
    payment_ref: Mapped[str | None] = mapped_column(String(30), nullable=True)
    refund_ref: Mapped[str | None] = mapped_column(String(30), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    passengers: Mapped[list["Passenger"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", lazy="selectin"
    )


class Passenger(Base):
    __tablename__ = "passengers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(ForeignKey("bookings.pnr"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(1))

    booking: Mapped[Booking] = relationship(back_populates="passengers")
