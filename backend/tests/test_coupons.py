def _create_and_add(client, product_id=1, qty=1):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": product_id, "quantity": qty})
    return cart_id


def _place_orders(client, count, product_id=1):
    for _ in range(count):
        cart_id = _create_and_add(client, product_id=product_id)
        r = client.post(f"/carts/{cart_id}/checkout", json={})
        assert r.status_code == 201


def test_generate_coupon_before_milestone(client):
    r = client.post("/admin/coupons/generate")
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "MILESTONE_NOT_YET_ELIGIBLE"
    assert body["error"]["details"]["next_milestone"] == 1
    assert body["error"]["details"]["required_orders"] == 5


def test_generate_coupon_after_milestone(client):
    _place_orders(client, 5)  # N=5
    r = client.post("/admin/coupons/generate")
    assert r.status_code == 201
    body = r.json()
    assert body["milestone_number"] == 1
    assert body["discount_percent"] == 10  # X=10
    assert body["status"] == "AVAILABLE"
    assert body["code"].startswith("SAVE10-")

    # immediately again -> milestone 2 not yet reached
    r2 = client.post("/admin/coupons/generate")
    assert r2.status_code == 409


def test_milestone_boundary_conditions(client):
    _place_orders(client, 4)
    assert client.post("/admin/coupons/generate").status_code == 409

    _place_orders(client, 1)  # now at 5 (== 1 * N)
    assert client.post("/admin/coupons/generate").status_code == 201

    _place_orders(client, 4)  # now at 9
    assert client.post("/admin/coupons/generate").status_code == 409

    _place_orders(client, 1)  # now at 10 (== 2 * N)
    r = client.post("/admin/coupons/generate")
    assert r.status_code == 201
    assert r.json()["milestone_number"] == 2


def test_coupon_redemption_reduces_total(client):
    _place_orders(client, 5)
    coupon = client.post("/admin/coupons/generate").json()

    cart_id = _create_and_add(client, product_id=1, qty=1)
    r = client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": coupon["code"]})
    assert r.status_code == 201
    body = r.json()
    assert body["discount"] == "19.90"  # 199.00 * 10%
    assert body["total"] == "179.10"
    assert body["coupon_code"] == coupon["code"]


def test_coupon_reuse_after_redemption(client):
    _place_orders(client, 5)
    coupon = client.post("/admin/coupons/generate").json()

    cart_a = _create_and_add(client)
    client.post(f"/carts/{cart_a}/checkout", json={"coupon_code": coupon["code"]})

    cart_b = _create_and_add(client)
    r = client.post(f"/carts/{cart_b}/checkout", json={"coupon_code": coupon["code"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "COUPON_ALREADY_REDEEMED"


def test_coupon_unknown_code(client):
    cart_id = _create_and_add(client)
    r = client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": "NOPE-000000"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "COUPON_NOT_FOUND"


def test_coupon_survives_unrelated_checkout_failure(client):
    _place_orders(client, 5)
    coupon = client.post("/admin/coupons/generate").json()

    cart_id = client.post("/carts").json()["cart_id"]
    client.post(
        f"/carts/{cart_id}/items", json={"product_id": 4, "quantity": 10}
    )  # only 3 in stock
    r = client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": coupon["code"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"

    coupons = client.get("/admin/coupons").json()
    target = next(c for c in coupons if c["code"] == coupon["code"])
    assert target["status"] == "AVAILABLE"


def test_discounted_order_still_counts_toward_next_milestone(client):
    _place_orders(client, 5)
    coupon = client.post("/admin/coupons/generate").json()

    cart_id = _create_and_add(client)
    client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": coupon["code"]})

    _place_orders(client, 3)  # total orders now 5 + 1 (discounted) + 3 = 9
    assert client.post("/admin/coupons/generate").status_code == 409

    _place_orders(client, 1)  # total orders now 10
    assert client.post("/admin/coupons/generate").status_code == 201
