import { useState } from "react";
import { friendlyError } from "../errors";

export function CheckoutView({ cart, submitting, error, onSubmit, onBack }) {
  const [couponCode, setCouponCode] = useState("");

  return (
    <div className="max-w-md mx-auto space-y-4">
      <button onClick={onBack} className="text-sm text-slate-500 hover:underline">
        &larr; Back to cart
      </button>
      <h2 className="text-xl font-semibold">Checkout</h2>

      <div className="border border-slate-200 rounded-lg p-4 bg-white space-y-2">
        {cart.items.map((item) => (
          <div key={item.item_id} className="flex justify-between text-sm">
            <span>
              {item.product_name} × {item.quantity}
            </span>
            <span>₹{item.line_total}</span>
          </div>
        ))}
        <div className="flex justify-between font-semibold pt-2 border-t border-slate-200">
          <span>Subtotal</span>
          <span>₹{cart.subtotal}</span>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Coupon code (optional)</label>
        <input
          value={couponCode}
          onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
          placeholder="SAVE10-AB12CD"
          className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
        />
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {friendlyError(error)}
        </p>
      )}

      <button
        onClick={() => onSubmit(couponCode.trim() || null)}
        disabled={submitting}
        className="w-full rounded-md bg-emerald-600 text-white py-2.5 font-medium disabled:opacity-40"
      >
        {submitting ? "Placing order…" : "Place order"}
      </button>
    </div>
  );
}
