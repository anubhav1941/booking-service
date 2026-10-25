"""Mock of the Payment Service.

Payment Service is part of the design but not one of the two implemented services,
so booking-service talks to this stub through the same function signatures a real
client would have. Swapping it for an HTTP client later does not touch the saga logic.
"""
import uuid


class PaymentFailed(Exception):
    pass


def charge(pnr: str, amount: float, simulate_failure: bool = False) -> str:
    if simulate_failure:
        raise PaymentFailed(f"Payment of Rs {amount:.2f} declined for {pnr}")
    return "PAY-" + uuid.uuid4().hex[:10].upper()


def refund(pnr: str, amount: float) -> str:
    return "RFND-" + uuid.uuid4().hex[:10].upper()
