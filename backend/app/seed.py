from .db import Base, SessionLocal, engine
from .models.product import Product

PRODUCTS = [
    {
        "name": "Widget",
        "description": "A reliable widget for everyday use.",
        "unit_price_minor": 19900,
        "inventory": 50,
    },
    {
        "name": "Gadget",
        "description": "A gadget that does gadget things.",
        "unit_price_minor": 34900,
        "inventory": 30,
    },
    {
        "name": "Gizmo",
        "description": "A gizmo of unknown but useful purpose.",
        "unit_price_minor": 9900,
        "inventory": 100,
    },
    {
        "name": "Doohickey",
        "description": "You know, a doohickey. Low stock, on purpose.",
        "unit_price_minor": 4900,
        "inventory": 3,
    },
    {
        "name": "Thingamajig",
        "description": "The last thingamajig you'll ever need.",
        "unit_price_minor": 129900,
        "inventory": 10,
    },
    {
        "name": "Contraption",
        "description": "An elaborate contraption.",
        "unit_price_minor": 59900,
        "inventory": 15,
    },
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("Products already seeded, skipping.")
            return
        for p in PRODUCTS:
            db.add(Product(**p))
        db.commit()
        print(f"Seeded {len(PRODUCTS)} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
