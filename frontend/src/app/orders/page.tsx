"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, Copy, Headphones } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import { getOrders, type UserOrder } from "@/lib/api";
import { toPersianDigits } from "@/lib/utils";

type OrderStatusFilter = "all" | "active" | "expired";

export default function OrdersPage() {
  const [activeTab, setActiveTab] = useState<OrderStatusFilter>("all");
  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<UserOrder | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  useEffect(() => {
    getOrders().then(setOrders).catch((error) => console.error("Orders load failed:", error));
  }, []);

  const filteredOrders = useMemo(
    () => orders.filter((order) => (activeTab === "all" ? true : order.status === activeTab)),
    [orders, activeTab]
  );

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      console.error("Clipboard copy failed:", error);
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-between items-center relative">
        <div className="w-6" />
        <h1 className="text-base font-bold text-[#F5F5F5] absolute left-1/2 -translate-x-1/2">سفارش‌ها</h1>
        <div className="w-6" />
      </header>

      <main className="px-5 mt-2">
        <div className="bg-[#0B1D33] p-1 rounded-xl flex items-center justify-between mb-6 border border-[#33383F]">
          <button onClick={() => setActiveTab("all")} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === "all" ? "bg-[#33383F] text-[#F5F5F5]" : "text-[#F5F5F5]/50"}`}>همه</button>
          <button onClick={() => setActiveTab("active")} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === "active" ? "bg-[#33383F] text-[#F5F5F5]" : "text-[#F5F5F5]/50"}`}>فعال</button>
          <button onClick={() => setActiveTab("expired")} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === "expired" ? "bg-[#33383F] text-[#F5F5F5]" : "text-[#F5F5F5]/50"}`}>منقضی شده</button>
        </div>

        <div className="space-y-3">
          {filteredOrders.length === 0 ? (
            <div className="text-center py-10 text-sm text-[#F5F5F5]/50">سفارشی ثبت نشده است.</div>
          ) : (
            filteredOrders.map((order) => (
              <div key={order.id} onClick={() => setSelectedOrder(order)} className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-[#1E3C5A]/50 transition-colors">
                <div className="flex items-center gap-4">
                  <ProductIcon icon={order.icon} assetUrl={order.assetUrl} gradient={order.gradient} />
                  <div className="flex flex-col gap-1">
                    <h3 className="text-sm font-bold text-[#F5F5F5]">{order.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/70">{order.duration}</p>
                    <p className="text-[10px] text-[#F5F5F5]/50 mt-1">{new Date(order.createdAt).toLocaleDateString("fa-IR")}</p>
                  </div>
                </div>

                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${order.status === "active" ? "text-emerald-400 border-emerald-400/40 bg-emerald-400/10" : "text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5"}`}>
                  {order.status === "active" ? "فعال" : "منقضی"}
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      <Dialog open={!!selectedOrder} onOpenChange={(open) => !open && setSelectedOrder(null)}>
        <DialogContent className="bg-[#0F0F10] border-none text-[#F5F5F5] w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col">
          <DialogTitle className="sr-only">Order Details</DialogTitle>

          <DialogHeader className="flex flex-row justify-between items-center p-5 pt-6 border-b border-[#33383F] sticky top-0 bg-[#0F0F10]/90 backdrop-blur-md z-20">
            <button onClick={() => setSelectedOrder(null)} className="p-2 -mr-2 text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold">جزئیات سفارش</h2>
            <button className="p-2 -ml-2 text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
              <Headphones className="w-5 h-5" />
            </button>
          </DialogHeader>

          {selectedOrder && (
            <div className="p-5 space-y-6 flex-1 overflow-y-auto pb-24">
              <div className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ProductIcon icon={selectedOrder.icon} assetUrl={selectedOrder.assetUrl} gradient={selectedOrder.gradient} sizeClassName="w-10 h-10" />
                  <div>
                    <h3 className="text-sm font-bold text-[#F5F5F5]">{selectedOrder.brand}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{selectedOrder.duration}</p>
                  </div>
                </div>
                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${selectedOrder.status === "active" ? "text-emerald-400 border-emerald-400/40 bg-emerald-400/10" : "text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5"}`}>
                  {selectedOrder.status === "active" ? "فعال" : "منقضی"}
                </div>
              </div>

              <div className="space-y-4 px-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/50">تاریخ خرید</span>
                  <span className="text-[#F5F5F5] font-medium">{new Date(selectedOrder.createdAt).toLocaleString("fa-IR")}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/50">شماره سفارش</span>
                  <span className="text-[#F5F5F5] font-mono font-medium">{toPersianDigits(selectedOrder.id)}</span>
                </div>
              </div>

              <div className="pt-4 border-t border-[#33383F]">
                <h4 className="text-sm font-bold text-[#F5F5F5] mb-4">اطلاعات سرویس</h4>
                <div className="bg-[#0B1D33] border border-[#33383F] rounded-xl p-3.5 flex items-center justify-between">
                  <span className="text-sm text-[#F5F5F5]/80 font-mono whitespace-pre-wrap break-all">{selectedOrder.credentials}</span>
                  <button onClick={() => handleCopy(selectedOrder.credentials, "credentials")} className="text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
                    {copiedField === "credentials" ? <Check className="w-4 h-4 text-[#1E3C5A]" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}