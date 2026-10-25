from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PassengerIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Anubhav Arora"])
    age: int = Field(gt=0, lt=125, examples=[25])
    gender: Literal["M", "F", "O"] = Field(examples=["M"])


class PassengerOut(PassengerIn):
    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    user_id: str = Field(examples=["user-101"])
    train_no: str = Field(examples=["12952"])
    journey_date: date
    travel_class: Literal["SL", "3A", "2A", "1A", "CC"] = Field(examples=["3A"])
    passengers: list[PassengerIn] = Field(min_length=1, max_length=6)
    simulate_payment_failure: bool = Field(
        default=False,
        description="Demo switch: makes the mock payment fail so you can see seats being released (compensation).",
    )


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pnr: str
    user_id: str
    train_no: str
    journey_date: date
    travel_class: str
    status: str
    total_fare: float | None
    hold_id: str | None
    payment_ref: str | None
    refund_ref: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    passengers: list[PassengerOut]
