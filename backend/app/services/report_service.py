from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.coupon import Coupon
from ..models.order import Order, OrderItem
from ..money import format_minor
from ..schemas.report import CouponCounts, ProductQuantity, ReportOut


def build_report(db: Session) -> ReportOut:
    total_orders = db.execute(select(func.count()).select_from(Order)).scalar_one()
    gross = db.execute(select(func.coalesce(func.sum(Order.subtotal_minor), 0))).scalar_one()
    discount = db.execute(select(func.coalesce(func.sum(Order.discount_minor), 0))).scalar_one()
    net = db.execute(select(func.coalesce(func.sum(Order.total_minor), 0))).scalar_one()

    rows = db.execute(
        select(
            OrderItem.product_id,
            func.max(OrderItem.product_name_snapshot),
            func.sum(OrderItem.quantity),
        )
        .group_by(OrderItem.product_id)
        .order_by(OrderItem.product_id)
    ).all()
    quantity_by_product = [
        ProductQuantity(product_id=pid, product_name=name, quantity_sold=qty)
        for pid, name, qty in rows
    ]

    generated = db.execute(select(func.count()).select_from(Coupon)).scalar_one()
    available = db.execute(
        select(func.count()).select_from(Coupon).where(Coupon.status == "AVAILABLE")
    ).scalar_one()
    redeemed = db.execute(
        select(func.count()).select_from(Coupon).where(Coupon.status == "REDEEMED")
    ).scalar_one()

    return ReportOut(
        quantity_by_product=quantity_by_product,
        gross_revenue=format_minor(gross),
        total_discount=format_minor(discount),
        net_revenue=format_minor(net),
        coupons=CouponCounts(generated=generated, available=available, redeemed=redeemed),
        total_successful_orders=total_orders,
    )
