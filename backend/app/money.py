from decimal import ROUND_HALF_UP, Decimal


def format_minor(amount_minor: int) -> str:
    sign = "-" if amount_minor < 0 else ""
    amount_minor = abs(amount_minor)
    whole, fraction = divmod(amount_minor, 100)
    return f"{sign}{whole}.{fraction:02d}"


def compute_discount_minor(subtotal_minor: int, discount_percent: int) -> int:
    raw = Decimal(subtotal_minor) * Decimal(discount_percent) / Decimal(100)
    discount_minor = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return min(discount_minor, subtotal_minor)
