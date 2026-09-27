from pydantic import BaseModel


class CouponOut(BaseModel):
    code: str
    milestone_number: int
    discount_percent: int
    status: str


class CouponListItem(CouponOut):
    redeemed_by_order_id: str | None = None
    created_at: str
    redeemed_at: str | None = None
