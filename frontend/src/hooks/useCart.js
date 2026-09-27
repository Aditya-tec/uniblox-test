import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

const STORAGE_KEY = "checkout_cart_id";

export function useCart() {
  const [cartId, setCartId] = useState(() => localStorage.getItem(STORAGE_KEY));
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const persistCartId = (id) => {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
    setCartId(id);
  };

  const refresh = useCallback(async (id) => {
    const targetId = id ?? cartId;
    if (!targetId) return null;
    try {
      const data = await api.getCart(targetId);
      setCart(data);
      return data;
    } catch (err) {
      if (err.code === "CART_NOT_FOUND") {
        persistCartId(null);
        setCart(null);
      }
      throw err;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cartId]);

  useEffect(() => {
    if (cartId) {
      refresh(cartId).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ensureCart = useCallback(async () => {
    if (cartId && cart && cart.status === "OPEN") return cartId;
    const created = await api.createCart();
    persistCartId(created.cart_id);
    setCart(created);
    return created.cart_id;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cartId, cart]);

  const addItem = useCallback(
    async (productId, quantity = 1) => {
      setLoading(true);
      setError(null);
      try {
        const id = await ensureCart();
        try {
          const updated = await api.addItem(id, productId, quantity);
          setCart(updated);
          return updated;
        } catch (err) {
          // Product already in cart: bump quantity instead, per the API's
          // documented add-vs-update distinction (POST rejects duplicates).
          if (err.code === "VALIDATION_ERROR" && err.details?.item_id) {
            const existing = cart?.items?.find((i) => i.item_id === err.details.item_id);
            const newQuantity = (existing?.quantity ?? 0) + quantity;
            const updated = await api.updateItem(id, err.details.item_id, newQuantity);
            setCart(updated);
            return updated;
          }
          throw err;
        }
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [ensureCart, cart]
  );

  const updateItem = useCallback(
    async (itemId, quantity) => {
      setLoading(true);
      setError(null);
      try {
        const updated = await api.updateItem(cartId, itemId, quantity);
        setCart(updated);
        return updated;
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [cartId]
  );

  const removeItem = useCallback(
    async (itemId) => {
      setLoading(true);
      setError(null);
      try {
        await api.removeItem(cartId, itemId);
        const updated = await api.getCart(cartId);
        setCart(updated);
        return updated;
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [cartId]
  );

  const startNewCart = useCallback(async () => {
    const created = await api.createCart();
    persistCartId(created.cart_id);
    setCart(created);
    return created;
  }, []);

  return {
    cartId,
    cart,
    loading,
    error,
    addItem,
    updateItem,
    removeItem,
    refresh,
    startNewCart,
  };
}
