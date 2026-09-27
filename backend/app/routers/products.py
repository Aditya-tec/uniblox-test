from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ProductNotFound
from ..models.product import Product
from ..money import format_minor
from ..schemas.product import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


def _to_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        description=p.description,
        unit_price=format_minor(p.unit_price_minor),
        inventory=p.inventory,
    )


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    products = db.execute(select(Product).order_by(Product.id)).scalars().all()
    return [_to_out(p) for p in products]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFound(product_id)
    return _to_out(product)
