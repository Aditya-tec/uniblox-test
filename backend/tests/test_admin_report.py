from decimal import Decimal


def test_report_reconciles(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 2})  # 199.00 * 2
    client.post(f"/carts/{cart_id}/checkout", json={})

    cart_id_2 = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id_2}/items", json={"product_id": 2, "quantity": 1})  # 349.00
    client.post(f"/carts/{cart_id_2}/checkout", json={})

    r = client.get("/admin/report")
    assert r.status_code == 200
    body = r.json()

    assert body["total_successful_orders"] == 2
    assert body["gross_revenue"] == "747.00"
    assert body["total_discount"] == "0.00"

    gross = Decimal(body["gross_revenue"])
    discount = Decimal(body["total_discount"])
    net = Decimal(body["net_revenue"])
    assert net == gross - discount

    by_product = {p["product_id"]: p["quantity_sold"] for p in body["quantity_by_product"]}
    assert by_product[1] == 2
    assert by_product[2] == 1

    assert body["coupons"] == {"generated": 0, "available": 0, "redeemed": 0}


def test_report_reflects_discount(client):
    for _ in range(5):
        cid = client.post("/carts").json()["cart_id"]
        client.post(f"/carts/{cid}/items", json={"product_id": 1, "quantity": 1})
        client.post(f"/carts/{cid}/checkout", json={})

    coupon = client.post("/admin/coupons/generate").json()

    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})
    client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": coupon["code"]})

    body = client.get("/admin/report").json()
    gross = Decimal(body["gross_revenue"])
    discount = Decimal(body["total_discount"])
    net = Decimal(body["net_revenue"])
    assert net == gross - discount
    assert discount == Decimal("19.90")
    assert body["coupons"] == {"generated": 1, "available": 0, "redeemed": 1}


def test_report_stable_across_repeated_calls(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})
    client.post(f"/carts/{cart_id}/checkout", json={})

    first = client.get("/admin/report").json()
    second = client.get("/admin/report").json()
    assert first == second
