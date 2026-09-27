def test_create_cart(client):
    r = client.post("/carts")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "OPEN"
    assert body["items"] == []
    assert body["subtotal"] == "0.00"


def test_get_cart_not_found(client):
    r = client.get("/carts/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CART_NOT_FOUND"


def test_add_item_happy_path(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 2})
    assert r.status_code == 201
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["product_name"] == "Widget"
    assert body["subtotal"] == "398.00"


def test_add_item_invalid_product(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.post(f"/carts/{cart_id}/items", json={"product_id": 999999, "quantity": 1})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_add_item_invalid_quantity(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 0})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_QUANTITY"


def test_add_duplicate_item_rejected(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})
    r = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_item_quantity(client):
    cart_id = client.post("/carts").json()["cart_id"]
    add = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1}).json()
    item_id = add["items"][0]["item_id"]
    r = client.patch(f"/carts/{cart_id}/items/{item_id}", json={"quantity": 5})
    assert r.status_code == 200
    assert r.json()["items"][0]["quantity"] == 5


def test_update_item_invalid_quantity(client):
    cart_id = client.post("/carts").json()["cart_id"]
    add = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1}).json()
    item_id = add["items"][0]["item_id"]
    r = client.patch(f"/carts/{cart_id}/items/{item_id}", json={"quantity": 0})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_QUANTITY"


def test_update_item_not_found(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.patch(f"/carts/{cart_id}/items/99999", json={"quantity": 5})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CART_ITEM_NOT_FOUND"


def test_remove_item(client):
    cart_id = client.post("/carts").json()["cart_id"]
    add = client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1}).json()
    item_id = add["items"][0]["item_id"]
    r = client.delete(f"/carts/{cart_id}/items/{item_id}")
    assert r.status_code == 204
    view = client.get(f"/carts/{cart_id}").json()
    assert view["items"] == []


def test_remove_item_not_found(client):
    cart_id = client.post("/carts").json()["cart_id"]
    r = client.delete(f"/carts/{cart_id}/items/99999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CART_ITEM_NOT_FOUND"


def test_mutate_checked_out_cart_rejected(client):
    cart_id = client.post("/carts").json()["cart_id"]
    client.post(f"/carts/{cart_id}/items", json={"product_id": 1, "quantity": 1})
    client.post(f"/carts/{cart_id}/checkout", json={})

    r = client.post(f"/carts/{cart_id}/items", json={"product_id": 2, "quantity": 1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CART_ALREADY_CHECKED_OUT"
