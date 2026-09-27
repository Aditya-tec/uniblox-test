export function OrderConfirmation({ order, onStartNewCart }) {
  return (
    <div className="max-w-md mx-auto space-y-4 text-center">
      <div className="text-emerald-600 text-4xl">✓</div>
      <h2 className="text-xl font-semibold">Order confirmed</h2>
      <p className="text-sm text-slate-500">Order #{order.order_id.slice(0, 8)}</p>

      <div className="border border-slate-200 rounded-lg p-4 bg-white text-left space-y-2">
        {order.items.map((item) => (
          <div key={item.product_id} className="flex justify-between text-sm">
            <span>
              {item.product_name} × {item.quantity}
            </span>
            <span>₹{item.line_total}</span>
          </div>
        ))}
        <div className="pt-2 border-t border-slate-200 space-y-1 text-sm">
          <div className="flex justify-between">
            <span>Subtotal</span>
            <span>₹{order.subtotal}</span>
          </div>
          {order.discount !== "0.00" && (
            <div className="flex justify-between text-emerald-600">
              <span>Discount {order.coupon_code ? `(${order.coupon_code})` : ""}</span>
              <span>−₹{order.discount}</span>
            </div>
          )}
          <div className="flex justify-between font-semibold text-base pt-1">
            <span>Total</span>
            <span>₹{order.total}</span>
          </div>
        </div>
      </div>

      <button
        onClick={onStartNewCart}
        className="rounded-md bg-slate-900 text-white px-4 py-2 text-sm font-medium"
      >
        Start a new order
      </button>
    </div>
  );
}
