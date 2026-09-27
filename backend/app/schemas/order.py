from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    coupon_code: str | None = None


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    unit_price: str
    quantity: int
    line_total: str


class OrderOut(BaseModel):
    order_id: str
    cart_id: str
    items: list[OrderItemOut]
    subtotal: str
    discount: str
    total: str
    coupon_code: str | None
    currency: str = "INR"
    created_at: str
