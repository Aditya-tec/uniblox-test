import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import (
    CartAlreadyCheckedOut,
    CartItemNotFound,
    CartNotFound,
    InvalidQuantity,
    ProductNotFound,
    ValidationError,
)
from ..models.cart import Cart, CartItem
from ..models.product import Product
from ..money import format_minor
from ..schemas.cart import CartItemOut, CartOut


def _get_cart_or_404(db: Session, cart_id: str) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None:
        raise CartNotFound(cart_id)
    return cart


def _require_open(cart: Cart) -> None:
    if cart.status != "OPEN":
        raise CartAlreadyCheckedOut(cart.id)


def build_cart_out(db: Session, cart: Cart) -> CartOut:
    rows = db.execute(
        select(CartItem, Product)
        .join(Product, Product.id == CartItem.product_id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()

    item_outs = []
    subtotal = 0
    for cart_item, product in rows:
        line_total = product.unit_price_minor * cart_item.quantity
        subtotal += line_total
        item_outs.append(
            CartItemOut(
                item_id=cart_item.id,
                product_id=product.id,
                product_name=product.name,
                unit_price=format_minor(product.unit_price_minor),
                quantity=cart_item.quantity,
                line_total=format_minor(line_total),
            )
        )

    return CartOut(
        cart_id=cart.id,
        status=cart.status,
        items=item_outs,
        subtotal=format_minor(subtotal),
    )


def create_cart(db: Session) -> CartOut:
    cart = Cart(id=str(uuid.uuid4()), status="OPEN")
    db.add(cart)
    db.flush()
    return build_cart_out(db, cart)


def get_cart(db: Session, cart_id: str) -> CartOut:
    cart = _get_cart_or_404(db, cart_id)
    return build_cart_out(db, cart)


def add_item(db: Session, cart_id: str, product_id: int, quantity: int) -> CartOut:
    if quantity <= 0:
        raise InvalidQuantity(quantity)

    cart = _get_cart_or_404(db, cart_id)
    _require_open(cart)

    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFound(product_id)

    existing = db.execute(
        select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationError(
            "Item already in cart, use PATCH to change quantity",
            {"product_id": product_id, "item_id": existing.id},
        )

    item = CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity)
    db.add(item)
    db.flush()
    return build_cart_out(db, cart)


def update_item(db: Session, cart_id: str, item_id: int, quantity: int) -> CartOut:
    if quantity <= 0:
        raise InvalidQuantity(quantity)

    cart = _get_cart_or_404(db, cart_id)
    _require_open(cart)

    item = db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    ).scalar_one_or_none()
    if item is None:
        raise CartItemNotFound(item_id)

    item.quantity = quantity
    db.flush()
    return build_cart_out(db, cart)


def remove_item(db: Session, cart_id: str, item_id: int) -> None:
    cart = _get_cart_or_404(db, cart_id)
    _require_open(cart)

    item = db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    ).scalar_one_or_none()
    if item is None:
        raise CartItemNotFound(item_id)

    db.delete(item)
    db.flush()
