import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import commit_with_retry
from ..errors import (
    CartEmpty,
    CartNotFound,
    CouponAlreadyRedeemed,
    CouponNotFound,
    IdempotencyKeyConflict,
    InsufficientInventory,
)
from ..models.cart import Cart, CartItem
from ..models.coupon import Coupon
from ..models.idempotency import IdempotencyKey
from ..models.order import Order, OrderItem
from ..models.product import Product
from ..money import compute_discount_minor, format_minor
from ..schemas.order import OrderItemOut, OrderOut


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def build_order_out(db: Session, order: Order) -> OrderOut:
    items = (
        db.execute(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id))
        .scalars()
        .all()
    )

    item_outs = [
        OrderItemOut(
            product_id=i.product_id,
            product_name=i.product_name_snapshot,
            unit_price=format_minor(i.unit_price_snapshot_minor),
            quantity=i.quantity,
            line_total=format_minor(i.line_total_minor),
        )
        for i in items
    ]

    return OrderOut(
        order_id=order.id,
        cart_id=order.cart_id,
        items=item_outs,
        subtotal=format_minor(order.subtotal_minor),
        discount=format_minor(order.discount_minor),
        total=format_minor(order.total_minor),
        coupon_code=order.coupon_code,
        created_at=order.created_at,
    )


def _store_idempotency_key(
    db: Session, key: str, cart_id: str, status: int, body: OrderOut
) -> None:
    db.add(
        IdempotencyKey(
            key=key,
            cart_id=cart_id,
            response_status=status,
            response_body=body.model_dump_json(),
        )
    )


def _store_idempotency_key_safe(
    db: Session, key: str, cart_id: str, status: int, body: OrderOut
) -> None:
    """Store the key, tolerating a concurrent racer inserting the same key first.

    Multiple losers of the cart-claim race can reach this point for the same
    cart at roughly the same time; only one of their inserts should win, and
    the rest must not blow up the response.
    """
    _store_idempotency_key(db, key, cart_id, status, body)
    try:
        commit_with_retry(db)
    except IntegrityError:
        db.rollback()


def checkout(
    db: Session, cart_id: str, coupon_code: str | None, idempotency_key: str | None
) -> tuple[int, OrderOut]:
    if idempotency_key:
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if existing.cart_id != cart_id:
                raise IdempotencyKeyConflict(idempotency_key)
            return existing.response_status, OrderOut.model_validate_json(existing.response_body)

    cart = db.get(Cart, cart_id)
    if cart is None:
        raise CartNotFound(cart_id)

    # Claim the cart FIRST: this is the real concurrency gate. Only one concurrent
    # request can win this UPDATE for a given cart; the loser sees CHECKED_OUT
    # immediately and returns the existing order instead of racing through
    # inventory/coupon logic pointlessly.
    claim = db.execute(
        update(Cart).where(Cart.id == cart_id, Cart.status == "OPEN").values(status="CHECKED_OUT")
    )

    if claim.rowcount == 0:
        db.rollback()
        fresh = db.get(Cart, cart_id)
        if fresh is not None and fresh.status == "CHECKED_OUT" and fresh.order_id:
            order = db.get(Order, fresh.order_id)
            body = build_order_out(db, order)
            if idempotency_key:
                _store_idempotency_key_safe(db, idempotency_key, cart_id, 200, body)
            return 200, body
        raise CartNotFound(cart_id)  # defensive; should not happen

    items = db.execute(select(CartItem).where(CartItem.cart_id == cart_id)).scalars().all()
    if not items:
        raise CartEmpty(cart_id)

    subtotal_minor = 0
    snapshots: list[tuple[Product, int, int]] = []
    for item in items:
        product = db.get(Product, item.product_id)
        dec = db.execute(
            update(Product)
            .where(Product.id == item.product_id, Product.inventory >= item.quantity)
            .values(inventory=Product.inventory - item.quantity)
        )
        if dec.rowcount == 0:
            db.refresh(product)
            raise InsufficientInventory(item.product_id, item.quantity, product.inventory)
        line_total = product.unit_price_minor * item.quantity
        subtotal_minor += line_total
        snapshots.append((product, item.quantity, line_total))

    order_id = str(uuid.uuid4())
    discount_minor = 0

    if coupon_code:
        redeem = db.execute(
            update(Coupon)
            .where(Coupon.code == coupon_code, Coupon.status == "AVAILABLE")
            .values(status="REDEEMED", redeemed_by_order_id=order_id, redeemed_at=_now())
        )
        if redeem.rowcount == 0:
            coupon = db.execute(
                select(Coupon).where(Coupon.code == coupon_code)
            ).scalar_one_or_none()
            if coupon is None:
                raise CouponNotFound(coupon_code)
            raise CouponAlreadyRedeemed(coupon_code)

        coupon = db.execute(select(Coupon).where(Coupon.code == coupon_code)).scalar_one()
        discount_minor = compute_discount_minor(subtotal_minor, coupon.discount_percent)

    total_minor = subtotal_minor - discount_minor

    order = Order(
        id=order_id,
        cart_id=cart_id,
        subtotal_minor=subtotal_minor,
        discount_minor=discount_minor,
        total_minor=total_minor,
        coupon_code=coupon_code,
    )
    db.add(order)
    db.flush()

    for product, qty, line_total in snapshots:
        db.add(
            OrderItem(
                order_id=order_id,
                product_id=product.id,
                product_name_snapshot=product.name,
                unit_price_snapshot_minor=product.unit_price_minor,
                quantity=qty,
                line_total_minor=line_total,
            )
        )

    db.execute(
        update(Cart).where(Cart.id == cart_id).values(order_id=order_id, checked_out_at=_now())
    )
    db.flush()
    db.refresh(order)

    body = build_order_out(db, order)

    if idempotency_key:
        _store_idempotency_key(db, idempotency_key, cart_id, 201, body)
        try:
            commit_with_retry(db)
        except IntegrityError:
            # A concurrent request already used this key for a different cart.
            db.rollback()
            raise IdempotencyKeyConflict(idempotency_key) from None
    else:
        commit_with_retry(db)

    return 201, body
