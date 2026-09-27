from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import commit_with_retry, get_db
from ..schemas.cart import AddItemRequest, CartOut, UpdateItemRequest
from ..services import cart_service

router = APIRouter(prefix="/carts", tags=["carts"])


@router.post("", response_model=CartOut, status_code=201)
def create_cart(db: Session = Depends(get_db)):
    cart = cart_service.create_cart(db)
    commit_with_retry(db)
    return cart


@router.get("/{cart_id}", response_model=CartOut)
def get_cart(cart_id: str, db: Session = Depends(get_db)):
    return cart_service.get_cart(db, cart_id)


@router.post("/{cart_id}/items", response_model=CartOut, status_code=201)
def add_item(cart_id: str, body: AddItemRequest, db: Session = Depends(get_db)):
    cart = cart_service.add_item(db, cart_id, body.product_id, body.quantity)
    commit_with_retry(db)
    return cart


@router.patch("/{cart_id}/items/{item_id}", response_model=CartOut)
def update_item(cart_id: str, item_id: int, body: UpdateItemRequest, db: Session = Depends(get_db)):
    cart = cart_service.update_item(db, cart_id, item_id, body.quantity)
    commit_with_retry(db)
    return cart


@router.delete("/{cart_id}/items/{item_id}", status_code=204)
def remove_item(cart_id: str, item_id: int, db: Session = Depends(get_db)):
    cart_service.remove_item(db, cart_id, item_id)
    commit_with_retry(db)
