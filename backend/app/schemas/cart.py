from pydantic import BaseModel


class AddItemRequest(BaseModel):
    product_id: int
    quantity: int


class UpdateItemRequest(BaseModel):
    quantity: int


class CartItemOut(BaseModel):
    item_id: int
    product_id: int
    product_name: str
    unit_price: str
    quantity: int
    line_total: str


class CartOut(BaseModel):
    cart_id: str
    status: str
    items: list[CartItemOut]
    subtotal: str
    currency: str = "INR"
