from pydantic import BaseModel


class ProductOut(BaseModel):
    id: int
    name: str
    description: str | None
    unit_price: str
    inventory: int
    currency: str = "INR"
