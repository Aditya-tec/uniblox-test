from app.money import compute_discount_minor, format_minor


def test_format_minor_basic():
    assert format_minor(19900) == "199.00"
    assert format_minor(5) == "0.05"
    assert format_minor(0) == "0.00"


def test_discount_exact():
    assert compute_discount_minor(10000, 10) == 1000


def test_discount_rounds_up():
    # 33333 * 15% = 4999.95 -> rounds to 5000 (ROUND_HALF_UP)
    assert compute_discount_minor(33333, 15) == 5000


def test_discount_rounds_down():
    # 10001 * 10% = 1000.1 -> rounds to 1000
    assert compute_discount_minor(10001, 10) == 1000


def test_discount_never_exceeds_subtotal():
    assert compute_discount_minor(100, 500) == 100


def test_total_never_negative():
    subtotal = 100
    discount = compute_discount_minor(subtotal, 500)
    assert subtotal - discount == 0
