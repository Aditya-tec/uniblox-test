export function friendlyError(err) {
  if (!err) return "Something went wrong.";

  const details = err.details || {};

  switch (err.code) {
    case "PRODUCT_NOT_FOUND":
      return "That product no longer exists.";
    case "INVALID_QUANTITY":
      return "Quantity must be at least 1.";
    case "CART_NOT_FOUND":
      return "This cart could not be found. Try starting a new one.";
    case "CART_ITEM_NOT_FOUND":
      return "That item is no longer in your cart.";
    case "CART_ALREADY_CHECKED_OUT":
      return "This cart has already been checked out.";
    case "CART_EMPTY":
      return "Your cart is empty.";
    case "INSUFFICIENT_INVENTORY":
      return `Only ${details.available ?? 0} left in stock for that item.`;
    case "COUPON_NOT_FOUND":
      return "That coupon code doesn't exist.";
    case "COUPON_ALREADY_REDEEMED":
      return "This coupon has already been used.";
    case "IDEMPOTENCY_KEY_CONFLICT":
      return "This request conflicted with another in-flight request. Please retry.";
    case "MILESTONE_NOT_YET_ELIGIBLE":
      return `Not yet eligible: ${details.current_orders ?? 0} of ${
        details.required_orders ?? "?"
      } orders needed for the next reward.`;
    case "ORDER_NOT_FOUND":
      return "That order could not be found.";
    case "VALIDATION_ERROR":
      return err.message || "Some of the submitted data was invalid.";
    default:
      return err.message || "Something went wrong.";
  }
}
