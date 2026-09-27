import random
import string

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import commit_with_retry
from ..errors import MilestoneNotYetEligible
from ..models.coupon import Coupon
from ..models.order import Order
from ..schemas.coupon import CouponListItem, CouponOut


def _random_code(discount_percent: int) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"SAVE{discount_percent}-{suffix}"


def generate_coupon(db: Session) -> CouponOut:
    n = settings.n
    x = settings.x

    successful_orders = db.execute(select(func.count()).select_from(Order)).scalar_one()
    last_milestone = db.execute(
        select(func.coalesce(func.max(Coupon.milestone_number), 0))
    ).scalar_one()
    next_milestone = last_milestone + 1
    required = next_milestone * n

    if successful_orders < required:
        raise MilestoneNotYetEligible(successful_orders, required, next_milestone)

    code = _random_code(x)
    coupon = Coupon(
        code=code, milestone_number=next_milestone, discount_percent=x, status="AVAILABLE"
    )
    db.add(coupon)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent admin call already generated this milestone's coupon
        # (or, astronomically unlikely, a random code collision).
        db.rollback()
        raise MilestoneNotYetEligible(successful_orders, required, next_milestone) from None

    commit_with_retry(db)

    return CouponOut(
        code=coupon.code,
        milestone_number=coupon.milestone_number,
        discount_percent=coupon.discount_percent,
        status=coupon.status,
    )


def list_coupons(db: Session) -> list[CouponListItem]:
    coupons = db.execute(select(Coupon).order_by(Coupon.id)).scalars().all()
    return [
        CouponListItem(
            code=c.code,
            milestone_number=c.milestone_number,
            discount_percent=c.discount_percent,
            status=c.status,
            redeemed_by_order_id=c.redeemed_by_order_id,
            created_at=c.created_at,
            redeemed_at=c.redeemed_at,
        )
        for c in coupons
    ]
