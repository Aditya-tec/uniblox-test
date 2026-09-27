import { friendlyError } from "../errors";

export function CartView({ cart, busy, error, onUpdateQuantity, onRemove, onCheckout }) {
  if (!cart || cart.items.length === 0) {
    return <p className="text-slate-500">Your cart is empty. Add something from the catalog!</p>;
  }

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {friendlyError(error)}
        </p>
      )}

      {cart.items.map((item) => (
        <div
          key={item.item_id}
          className="flex items-center justify-between border border-slate-200 rounded-lg p-3 bg-white"
        >
          <div>
            <p className="font-medium">{item.product_name}</p>
            <p className="text-sm text-slate-500">₹{item.unit_price} each</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="w-7 h-7 rounded border border-slate-300 disabled:opacity-40"
              disabled={busy || item.quantity <= 1}
              onClick={() => onUpdateQuantity(item.item_id, item.quantity - 1)}
            >
              −
            </button>
            <span className="w-6 text-center">{item.quantity}</span>
            <button
              className="w-7 h-7 rounded border border-slate-300 disabled:opacity-40"
              disabled={busy}
              onClick={() => onUpdateQuantity(item.item_id, item.quantity + 1)}
            >
              +
            </button>
            <span className="w-20 text-right font-medium">₹{item.line_total}</span>
            <button
              className="text-red-500 text-sm ml-2 disabled:opacity-40"
              disabled={busy}
              onClick={() => onRemove(item.item_id)}
            >
              Remove
            </button>
          </div>
        </div>
      ))}

      <div className="flex items-center justify-between pt-3 border-t border-slate-200">
        <span className="font-semibold">Subtotal</span>
        <span className="font-semibold">₹{cart.subtotal}</span>
      </div>

      <button
        onClick={onCheckout}
        disabled={busy}
        className="w-full rounded-md bg-slate-900 text-white py-2.5 font-medium disabled:opacity-40"
      >
        Checkout
      </button>
    </div>
  );
}
