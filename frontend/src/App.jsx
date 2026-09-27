import { useState } from "react";
import { api } from "./api";
import { AdminDashboard } from "./components/AdminDashboard";
import { CartView } from "./components/CartView";
import { Catalog } from "./components/Catalog";
import { CheckoutView } from "./components/CheckoutView";
import { OrderConfirmation } from "./components/OrderConfirmation";
import { friendlyError } from "./errors";
import { useCart } from "./hooks/useCart";

const VIEWS = {
  CATALOG: "catalog",
  CART: "cart",
  CHECKOUT: "checkout",
  CONFIRMATION: "confirmation",
};

export default function App() {
  const [tab, setTab] = useState("shop");
  const [view, setView] = useState(VIEWS.CATALOG);
  const [order, setOrder] = useState(null);
  const [checkoutError, setCheckoutError] = useState(null);
  const [checking, setChecking] = useState(false);
  const [addingProductId, setAddingProductId] = useState(null);
  const [addError, setAddError] = useState(null);

  const { cart, loading: cartBusy, error: cartError, addItem, updateItem, removeItem, startNewCart } =
    useCart();

  const handleAddToCart = async (productId) => {
    setAddingProductId(productId);
    setAddError(null);
    try {
      await addItem(productId, 1);
    } catch (err) {
      setAddError(err);
    } finally {
      setAddingProductId(null);
    }
  };

  const handleUpdateQuantity = (itemId, quantity) => {
    if (quantity <= 0) return removeItem(itemId).catch(() => {});
    return updateItem(itemId, quantity).catch(() => {});
  };

  const handleCheckout = async (couponCode) => {
    setChecking(true);
    setCheckoutError(null);
    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random()}`;
      const placedOrder = await api.checkout(cart.cart_id, couponCode, idempotencyKey);
      setOrder(placedOrder);
      setView(VIEWS.CONFIRMATION);
    } catch (err) {
      setCheckoutError(err);
    } finally {
      setChecking(false);
    }
  };

  const handleStartNewCart = async () => {
    await startNewCart();
    setOrder(null);
    setCheckoutError(null);
    setView(VIEWS.CATALOG);
  };

  const itemCount = cart?.items?.reduce((sum, i) => sum + i.quantity, 0) ?? 0;
  const showCartButton = tab === "shop" && view !== VIEWS.CHECKOUT && view !== VIEWS.CONFIRMATION;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="font-semibold text-lg">Reliable Checkout</h1>
          <nav className="flex items-center gap-2">
            <TabButton active={tab === "shop"} onClick={() => setTab("shop")}>
              Shop
            </TabButton>
            <TabButton active={tab === "admin"} onClick={() => setTab("admin")}>
              Admin
            </TabButton>
            {showCartButton && (
              <button
                onClick={() => setView(view === VIEWS.CART ? VIEWS.CATALOG : VIEWS.CART)}
                className="ml-2 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
              >
                {view === VIEWS.CART ? "Catalog" : `Cart (${itemCount})`}
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {tab === "admin" ? (
          <AdminDashboard />
        ) : (
          <>
            {addError && (
              <p className="max-w-2xl mx-auto mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {friendlyError(addError)}
              </p>
            )}

            {view === VIEWS.CATALOG && (
              <Catalog onAddToCart={handleAddToCart} addingProductId={addingProductId} />
            )}

            {view === VIEWS.CART && (
              <CartView
                cart={cart}
                busy={cartBusy}
                error={cartError}
                onUpdateQuantity={handleUpdateQuantity}
                onRemove={(itemId) => removeItem(itemId).catch(() => {})}
                onCheckout={() => setView(VIEWS.CHECKOUT)}
              />
            )}

            {view === VIEWS.CHECKOUT && cart && (
              <CheckoutView
                cart={cart}
                submitting={checking}
                error={checkoutError}
                onSubmit={handleCheckout}
                onBack={() => setView(VIEWS.CART)}
              />
            )}

            {view === VIEWS.CONFIRMATION && order && (
              <OrderConfirmation order={order} onStartNewCart={handleStartNewCart} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function TabButton({ active, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
        active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {children}
    </button>
  );
}
