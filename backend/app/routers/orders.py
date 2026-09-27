from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import OrderNotFound
from ..models.order import Order
from ..schemas.order import OrderOut
from ..services.checkout_service import build_order_out

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise OrderNotFound(order_id)
    return build_order_out(db, order)
