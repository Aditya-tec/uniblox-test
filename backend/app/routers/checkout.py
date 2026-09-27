from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.order import CheckoutRequest, OrderOut
from ..services import checkout_service

router = APIRouter(prefix="/carts", tags=["checkout"])


@router.post("/{cart_id}/checkout", response_model=OrderOut)
def checkout(
    cart_id: str,
    body: CheckoutRequest,
    response: Response,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    status_code, order = checkout_service.checkout(db, cart_id, body.coupon_code, idempotency_key)
    response.status_code = status_code
    return order
