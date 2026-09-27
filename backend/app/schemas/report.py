from pydantic import BaseModel


class ProductQuantity(BaseModel):
    product_id: int
    product_name: str
    quantity_sold: int


class CouponCounts(BaseModel):
    generated: int
    available: int
    redeemed: int


class ReportOut(BaseModel):
    quantity_by_product: list[ProductQuantity]
    gross_revenue: str
    total_discount: str
    net_revenue: str
    coupons: CouponCounts
    total_successful_orders: int
