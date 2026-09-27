from concurrent.futures import ThreadPoolExecutor


def test_oversell_prevention(client):
    # Doohickey (product_id=4) seeded with inventory 3
    cart_ids = [client.post("/carts").json()["cart_id"] for _ in range(10)]
    for cid in cart_ids:
        client.post(f"/carts/{cid}/items", json={"product_id": 4, "quantity": 1})

    def do_checkout(cid):
        return client.post(f"/carts/{cid}/checkout", json={})

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(do_checkout, cart_ids))

    successes = [r for r in results if r.status_code == 201]
    failures = [r for r in results if r.status_code == 409]
    assert len(successes) == 3
    assert len(failures) == 7
    for f in failures:
        assert f.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"

    product = client.get("/products/4").json()
    assert product["inventory"] == 0


def test_coupon_double_redemption(client):
    for _ in range(5):
        cid = client.post("/carts").json()["cart_id"]
        client.post(f"/carts/{cid}/items", json={"product_id": 1, "quantity": 1})
        client.post(f"/carts/{cid}/checkout", json={})

    coupon = client.post("/admin/coupons/generate").json()["code"]

    cart_ids = [client.post("/carts").json()["cart_id"] for _ in range(5)]
    for cid in cart_ids:
        client.post(f"/carts/{cid}/items", json={"product_id": 1, "quantity": 1})

    def do_checkout(cid):
        return client.post(f"/carts/{cid}/checkout", json={"coupon_code": coupon})

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(do_checkout, cart_ids))

    successes = [r for r in results if r.status_code == 201]
    failures = [r for r in results if r.status_code == 409]
    assert len(successes) == 1
    assert successes[0].json()["discount"] != "0.00"
    assert len(failures) == 4
    for f in failures:
        assert f.json()["error"]["code"] == "COUPON_ALREADY_REDEEMED"

    coupons = client.get("/admin/coupons").json()
    target = next(c for c in coupons if c["code"] == coupon)
    assert target["status"] == "REDEEMED"


def test_duplicate_checkout_retry_same_cart(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})

    def do_checkout(_):
        return client.post(
            f"/carts/{cart_id}/checkout", json={}, headers={"Idempotency-Key": "retry-key"}
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(do_checkout, range(5)))

    order_ids = {r.json()["order_id"] for r in results if r.status_code in (200, 201)}
    assert len(order_ids) == 1

    product = client.get("/products/1").json()
    assert product["inventory"] == 49  # decremented exactly once


def test_duplicate_checkout_retry_without_idempotency_key(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})

    def do_checkout(_):
        return client.post(f"/carts/{cart_id}/checkout", json={})

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(do_checkout, range(5)))

    order_ids = {r.json()["order_id"] for r in results}
    assert len(order_ids) == 1
    assert sum(1 for r in results if r.status_code == 201) == 1
    assert sum(1 for r in results if r.status_code == 200) == 4

    product = client.get("/products/1").json()
    assert product["inventory"] == 49


def test_double_coupon_generation(client):
    for _ in range(5):
        cid = client.post("/carts").json()["cart_id"]
        client.post(f"/carts/{cid}/items", json={"product_id": 1, "quantity": 1})
        client.post(f"/carts/{cid}/checkout", json={})

    def do_generate(_):
        return client.post("/admin/coupons/generate")

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(do_generate, range(5)))

    successes = [r for r in results if r.status_code == 201]
    failures = [r for r in results if r.status_code == 409]
    assert len(successes) == 1
    assert len(failures) == 4

    coupons = client.get("/admin/coupons").json()
    milestone_1 = [c for c in coupons if c["milestone_number"] == 1]
    assert len(milestone_1) == 1
