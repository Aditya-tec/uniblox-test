import { useEffect, useState } from "react";
import { api } from "../api";
import { friendlyError } from "../errors";

export function Catalog({ onAddToCart, addingProductId }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listProducts()
      .then((data) => {
        if (!cancelled) setProducts(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="text-slate-500">Loading products…</p>;
  if (error) return <p className="text-red-600">{friendlyError(error)}</p>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {products.map((p) => (
        <div
          key={p.id}
          className="border border-slate-200 rounded-lg p-4 bg-white flex flex-col shadow-sm"
        >
          <h3 className="font-semibold text-lg">{p.name}</h3>
          <p className="text-slate-500 text-sm flex-1 mt-1">{p.description}</p>
          <div className="mt-3 flex items-center justify-between">
            <span className="font-medium">₹{p.unit_price}</span>
            <span className={`text-xs ${p.inventory === 0 ? "text-red-600" : "text-slate-500"}`}>
              {p.inventory === 0 ? "Out of stock" : `${p.inventory} left`}
            </span>
          </div>
          <button
            disabled={p.inventory === 0 || addingProductId === p.id}
            onClick={() => onAddToCart(p.id)}
            className="mt-3 w-full rounded-md bg-slate-900 text-white py-2 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 transition"
          >
            {addingProductId === p.id ? "Adding…" : p.inventory === 0 ? "Out of stock" : "Add to cart"}
          </button>
        </div>
      ))}
    </div>
  );
}
