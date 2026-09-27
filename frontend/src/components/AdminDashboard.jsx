import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { friendlyError } from "../errors";

export function AdminDashboard() {
  const [report, setReport] = useState(null);
  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [generateError, setGenerateError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [r, c] = await Promise.all([api.getReport(), api.listCoupons()]);
      setReport(r);
      setCoupons(c);
    } catch (err) {
      setLoadError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    setLastGenerated(null);
    try {
      const coupon = await api.generateCoupon();
      setLastGenerated(coupon);
      await load();
    } catch (err) {
      setGenerateError(err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <p className="text-slate-500">Loading admin dashboard…</p>;
  if (loadError) return <p className="text-red-600">{friendlyError(loadError)}</p>;

  const progress = generateError?.code === "MILESTONE_NOT_YET_ELIGIBLE" ? generateError.details : null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Admin dashboard</h2>
        <button onClick={load} className="text-sm text-slate-500 hover:underline">
          Refresh
        </button>
      </div>

      <div className="border border-slate-200 rounded-lg p-4 bg-white space-y-3">
        <h3 className="font-medium">Rewards</h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-md bg-slate-900 text-white px-4 py-2 text-sm font-medium disabled:opacity-40"
        >
          {generating ? "Generating…" : "Generate coupon"}
        </button>

        {lastGenerated && (
          <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md px-3 py-2">
            Generated <span className="font-mono">{lastGenerated.code}</span> (
            {lastGenerated.discount_percent}% off, milestone #{lastGenerated.milestone_number})
          </p>
        )}
        {progress && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            {progress.current_orders} of {progress.required_orders} orders to the next reward
            (milestone #{progress.next_milestone}).
          </p>
        )}
        {generateError && !progress && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
            {friendlyError(generateError)}
          </p>
        )}
      </div>

      <div className="border border-slate-200 rounded-lg p-4 bg-white">
        <h3 className="font-medium mb-3">Revenue report</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <Stat label="Orders" value={report.total_successful_orders} />
          <Stat label="Gross revenue" value={`₹${report.gross_revenue}`} />
          <Stat label="Discounts" value={`₹${report.total_discount}`} />
          <Stat label="Net revenue" value={`₹${report.net_revenue}`} />
        </div>

        <h4 className="font-medium mt-4 mb-2 text-sm">Quantity sold by product</h4>
        {report.quantity_by_product.length === 0 ? (
          <p className="text-sm text-slate-400">No orders yet.</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {report.quantity_by_product.map((p) => (
                <tr key={p.product_id} className="border-t border-slate-100">
                  <td className="py-1">{p.product_name}</td>
                  <td className="py-1 text-right">{p.quantity_sold}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <h4 className="font-medium mt-4 mb-2 text-sm">Coupons</h4>
        <div className="flex gap-4 text-sm">
          <span>Generated: {report.coupons.generated}</span>
          <span>Available: {report.coupons.available}</span>
          <span>Redeemed: {report.coupons.redeemed}</span>
        </div>
      </div>

      <div className="border border-slate-200 rounded-lg p-4 bg-white">
        <h3 className="font-medium mb-3">All coupons</h3>
        {coupons.length === 0 ? (
          <p className="text-sm text-slate-400">No coupons generated yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 font-medium">Code</th>
                <th className="py-1 font-medium">Milestone</th>
                <th className="py-1 font-medium">%</th>
                <th className="py-1 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map((c) => (
                <tr key={c.code} className="border-t border-slate-100">
                  <td className="py-1 font-mono">{c.code}</td>
                  <td className="py-1">{c.milestone_number}</td>
                  <td className="py-1">{c.discount_percent}%</td>
                  <td className="py-1">
                    <span className={c.status === "AVAILABLE" ? "text-emerald-600" : "text-slate-400"}>
                      {c.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <p className="text-slate-500 text-xs">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}
