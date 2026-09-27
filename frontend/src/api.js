const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(code, message, details) {
    super(message);
    this.code = code;
    this.details = details || {};
  }
}

async function request(path, { headers, ...rest } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: { "Content-Type": "application/json", ...(headers || {}) },
  });

  if (res.status === 204) return null;

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    const err = body && body.error;
    throw new ApiError(
      err?.code ?? "UNKNOWN_ERROR",
      err?.message ?? "Something went wrong.",
      err?.details ?? {}
    );
  }

  return body;
}

export const api = {
  listProducts: () => request("/products"),
  getProduct: (productId) => request(`/products/${productId}`),

  createCart: () => request("/carts", { method: "POST" }),
  getCart: (cartId) => request(`/carts/${cartId}`),
  addItem: (cartId, productId, quantity) =>
    request(`/carts/${cartId}/items`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity }),
    }),
  updateItem: (cartId, itemId, quantity) =>
    request(`/carts/${cartId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }),
  removeItem: (cartId, itemId) =>
    request(`/carts/${cartId}/items/${itemId}`, { method: "DELETE" }),

  checkout: (cartId, couponCode, idempotencyKey) =>
    request(`/carts/${cartId}/checkout`, {
      method: "POST",
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
      body: JSON.stringify({ coupon_code: couponCode || null }),
    }),
  getOrder: (orderId) => request(`/orders/${orderId}`),

  generateCoupon: () => request("/admin/coupons/generate", { method: "POST" }),
  listCoupons: () => request("/admin/coupons"),
  getReport: () => request("/admin/report"),
};
