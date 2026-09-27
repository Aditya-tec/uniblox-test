def _add(client, cart_id, product_id, qty):
    return client.post(f"/carts/{cart_id}/items", json={"product_id": product_id, "quantity": qty})


def test_checkout_happy_path(client):
    cart_id = client.post("/carts").json()["cart_id"]
    _add(client, cart_id, 1, 2)
    r = client.post(f"/carts/{cart_id}/checkout", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["subtotal"] == "398.00"
    assert body["discount"] == "0.00"
    assert body["total"] == "398.00"
    assert body["items"][0]["product_name"] == "Widget"
    assert body["items"][0]["quantity"] == 2


def test_checkout_snapshot_survives_price_change(client):
    from app.db import SessionLocal
    from app.models.product import Product

    cart_id = client.post("/carts").json()["cart_id"]
    _add(client, cart_id, 1, 1)
    order = client.post(f"/carts/{cart_id}/checkout", json={}).json()

    db = SessionLocal()
    try:
        product = db.get(Product, 1)
        product.unit_price_minor = 99999
        db.commit()
    finally:
        db.close()

    refetched = client.get(f"/orders/{order['order_id']}").json()
    assert refetched["items"][0]["unit_price"] == order["items"][0]["unit_price"]
    assert refetched["total"] == order["total"]

    # live catalog price DOES reflect the change
    catalog = client.get("/products/1").json()
    assert catalog["unit_price"] == "999.99"


def test_checkout_insufficient_inventory_leaves_inventory_untouched(client):
    cart_id = client.post("/carts").json()["cart_id"]
    _add(client, cart_id, 4, 10)  # Doohickey has inventory 3
    r = client.post(f"/carts/{cart_id}/checkout", json={})
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "INSUFFICIENT_INVENTORY"
    assert body["error"]["details"]["available"] == 3

    view = client.get(f"/carts/{cart_id}").json()
    assert view["status"] == "OPEN"

    product = client.get("/products/4").json()
    assert product["inventory"] == 3


def test_checkout_empty_cart(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.post(f"/carts/{cart_id}/checkout", json={})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CART_EMPTY"


def test_checkout_cart_not_found(client):
    r = client.post("/carts/does-not-exist/checkout", json={})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CART_NOT_FOUND"


def test_checkout_retry_same_cart_returns_existing_order(client):
    cart_id = client.post("/carts").json()["cart_id"]
    _add(client, cart_id, 1, 1)
    first = client.post(f"/carts/{cart_id}/checkout", json={})
    assert first.status_code == 201

    second = client.post(f"/carts/{cart_id}/checkout", json={})
    assert second.status_code == 200
    assert second.json()["order_id"] == first.json()["order_id"]

    product = client.get("/products/1").json()
    assert product["inventory"] == 49  # decremented exactly once


def test_checkout_idempotency_key_replay(client):
    cart_id = client.post("/carts").json()["cart_id"]
    _add(client, cart_id, 1, 1)
    headers = {"Idempotency-Key": "key-123"}

    first = client.post(f"/carts/{cart_id}/checkout", json={}, headers=headers)
    second = client.post(f"/carts/{cart_id}/checkout", json={}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201  # replayed verbatim, not re-executed
    assert second.json() == first.json()


def test_checkout_idempotency_key_conflict(client):
    cart_a = client.post("/carts").json()["cart_id"]
    cart_b = client.post("/carts").json()["cart_id"]
    _add(client, cart_a, 1, 1)
    _add(client, cart_b, 1, 1)

    headers = {"Idempotency-Key": "shared-key"}
    client.post(f"/carts/{cart_a}/checkout", json={}, headers=headers)
    r = client.post(f"/carts/{cart_b}/checkout", json={}, headers=headers)

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
