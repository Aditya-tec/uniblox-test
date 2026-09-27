from sqlalchemy import CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price_minor >= 0", name="ck_products_price_nonneg"),
        CheckConstraint("inventory >= 0", name="ck_products_inventory_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )
    updated_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("(datetime('now'))")
    )
