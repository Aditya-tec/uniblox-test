from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    code = "APP_ERROR"
    http_status = 400

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422


class CartNotFound(AppError):
    code = "CART_NOT_FOUND"
    http_status = 404

    def __init__(self, cart_id: str):
        super().__init__(f"No cart with id {cart_id}", {"cart_id": cart_id})


class ProductNotFound(AppError):
    code = "PRODUCT_NOT_FOUND"
    http_status = 404

    def __init__(self, product_id: int):
        super().__init__(f"No product with id {product_id}", {"product_id": product_id})


class CartItemNotFound(AppError):
    code = "CART_ITEM_NOT_FOUND"
    http_status = 404

    def __init__(self, item_id: int):
        super().__init__(f"No such item {item_id} on this cart", {"item_id": item_id})


class InvalidQuantity(AppError):
    code = "INVALID_QUANTITY"
    http_status = 400

    def __init__(self, quantity: int):
        super().__init__(f"Quantity must be >= 1, got {quantity}", {"quantity": quantity})


class CartAlreadyCheckedOut(AppError):
    code = "CART_ALREADY_CHECKED_OUT"
    http_status = 409

    def __init__(self, cart_id: str):
        super().__init__(f"Cart {cart_id} is already checked out", {"cart_id": cart_id})


class CartEmpty(AppError):
    code = "CART_EMPTY"
    http_status = 409

    def __init__(self, cart_id: str):
        super().__init__(f"Cart {cart_id} has no items", {"cart_id": cart_id})


class InsufficientInventory(AppError):
    code = "INSUFFICIENT_INVENTORY"
    http_status = 409

    def __init__(self, product_id: int, requested: int, available: int):
        super().__init__(
            f"Not enough stock for product {product_id}",
            {"product_id": product_id, "requested": requested, "available": available},
        )


class CouponNotFound(AppError):
    code = "COUPON_NOT_FOUND"
    http_status = 400

    def __init__(self, coupon_code: str):
        super().__init__(f"No coupon with code {coupon_code}", {"coupon_code": coupon_code})


class CouponAlreadyRedeemed(AppError):
    code = "COUPON_ALREADY_REDEEMED"
    http_status = 409

    def __init__(self, coupon_code: str):
        super().__init__(
            f"Coupon {coupon_code} has already been redeemed", {"coupon_code": coupon_code}
        )


class IdempotencyKeyConflict(AppError):
    code = "IDEMPOTENCY_KEY_CONFLICT"
    http_status = 409

    def __init__(self, key: str):
        super().__init__(
            f"Idempotency-Key {key} was already used for a different cart",
            {"idempotency_key": key},
        )


class MilestoneNotYetEligible(AppError):
    code = "MILESTONE_NOT_YET_ELIGIBLE"
    http_status = 409

    def __init__(self, current: int, required: int, next_milestone: int):
        super().__init__(
            "No new milestone reached since last coupon generation",
            {
                "current_orders": current,
                "required_orders": required,
                "next_milestone": next_milestone,
            },
        )


class OrderNotFound(AppError):
    code = "ORDER_NOT_FOUND"
    http_status = 404

    def __init__(self, order_id: str):
        super().__init__(f"No order with id {order_id}", {"order_id": order_id})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_response())

    @app.exception_handler(RequestValidationError)
    def handle_request_validation_error(request: Request, exc: RequestValidationError):
        err = ValidationError(
            "Request validation failed", {"errors": jsonable_encoder(exc.errors())}
        )
        return JSONResponse(status_code=err.http_status, content=err.to_response())
