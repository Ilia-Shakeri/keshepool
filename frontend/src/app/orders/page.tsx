"use client";

import { useState } from "react";
import { ChevronLeft, Copy, Check, Headphones } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogHeader } from "@/components/ui/dialog";
import { toPersianDigits } from "@/lib/utils";

type OrderStatus = 'all' | 'active' | 'expired';

const MOCK_ORDERS = [
  { id: "#HA-2024-1298", title: "Claude Pro", duration: "۱ ماهه", daysLeft: `۲۳ روز باقیمانده`, status: "active", icon: "C", bg: "bg-[#E63946]", date: "۱۴۰۳/۱۱/۲۰ - ۲۱:۴۱", email: "example@mail.com" },
  { id: "#HA-2024-1102", title: "ChatGPT Plus", duration: "۱ ماهه", daysLeft: `۱۲ روز باقیمانده`, status: "active", icon: "G", bg: "bg-[#1E3C5A]", date: "۱۴۰۳/۱۰/۰۵ - ۱۴:۲۰", email: "example@mail.com" },
  { id: "#HA-2024-0988", title: "Netflix Premium", duration: "۱ ماهه", daysLeft: "منقضی شده", status: "expired", icon: "N", bg: "bg-[#33383F]", date: "۱۴۰۳/۰۸/۱۲ - ۰۹:۱۵", email: "example@mail.com" },
];

export default function OrdersPage() {
  const [activeTab, setActiveTab] = useState<OrderStatus>('all');
  const [selectedOrder, setSelectedOrder] = useState<typeof MOCK_ORDERS[0] | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const filteredOrders = MOCK_ORDERS.filter(order => 
    activeTab === 'all' ? true : order.status === activeTab
  );

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (err) {
      console.error("Clipboard sequence failed", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-between items-center relative">
        <div className="w-6"></div> 
        <h1 className="text-base font-bold text-[#F5F5F5] absolute left-1/2 -translate-x-1/2">سفارش‌ها</h1>
        <div className="w-6"></div> 
      </header>

      <main className="px-5 mt-2">
        <div className="bg-[#0B1D33] p-1 rounded-xl flex items-center justify-between mb-6 border border-[#33383F]">
          <button onClick={() => setActiveTab('all')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'all' ? 'bg-[#33383F] text-[#F5F5F5]' : 'text-[#F5F5F5]/50'}`}>همه</button>
          <button onClick={() => setActiveTab('active')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'active' ? 'bg-[#33383F] text-[#F5F5F5]' : 'text-[#F5F5F5]/50'}`}>فعال</button>
          <button onClick={() => setActiveTab('expired')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'expired' ? 'bg-[#33383F] text-[#F5F5F5]' : 'text-[#F5F5F5]/50'}`}>منقضی شده</button>
        </div>

        <div className="space-y-3">
          {filteredOrders.map((order) => (
            <div 
              key={order.id} 
              onClick={() => setSelectedOrder(order)}
              className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-[#1E3C5A]/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 ${order.bg} rounded-full flex items-center justify-center text-[#F5F5F5] font-bold text-xl shadow-lg`}>
                  {order.icon}
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-bold text-[#F5F5F5]">{order.title}</h3>
                  <p className="text-[10px] text-[#F5F5F5]/70">{order.duration}</p>
                  <p className="text-[10px] text-[#F5F5F5]/50 mt-1">{toPersianDigits(order.daysLeft)}</p>
                </div>
              </div>
              
              <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${
                order.status === 'active' ? 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10' : 'text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5'
              }`}>
                {order.status === 'active' ? 'فعال' : 'منقضی'}
              </div>
            </div>
          ))}
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
                  <div className={`w-10 h-10 ${selectedOrder.bg} rounded-full flex items-center justify-center text-[#F5F5F5] font-bold shadow-lg`}>
                    {selectedOrder.icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#F5F5F5]">{selectedOrder.title}</h3>
                    <p className="text-[10px] text-[#F5F5F5]/70 mt-1">{selectedOrder.duration} - اکانت اشتراکی</p>
                  </div>
                </div>
                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${
                  selectedOrder.status === 'active' ? 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10' : 'text-[#E63946] border-[#E63946]/20 bg-[#E63946]/5'
                }`}>
                  {selectedOrder.status === 'active' ? 'فعال' : 'منقضی'}
                </div>
              </div>

              <div className="space-y-4 px-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/50">تاریخ خرید</span>
                  <span className="text-[#F5F5F5] font-medium">{toPersianDigits(selectedOrder.date)}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#F5F5F5]/50">شماره سفارش</span>
                  <span className="text-[#F5F5F5] font-mono font-medium">{toPersianDigits(selectedOrder.id)}</span>
                </div>
              </div>

              <div className="pt-4 border-t border-[#33383F]">
                <h4 className="text-sm font-bold text-[#F5F5F5] mb-4">اطلاعات اکانت</h4>
                <div className="space-y-2">
                  <div className="bg-[#0B1D33] border border-[#33383F] rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-[#F5F5F5]/80 font-mono">{selectedOrder.email}</span>
                    <button onClick={() => handleCopy(selectedOrder.email, 'email')} className="text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
                      {copiedField === 'email' ? <Check className="w-4 h-4 text-[#1E3C5A]" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                  <div className="bg-[#0B1D33] border border-[#33383F] rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-[#F5F5F5]/80 font-mono">••••••••••</span>
                    <button onClick={() => handleCopy('secure_password_123', 'password')} className="text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
                      {copiedField === 'password' ? <Check className="w-4 h-4 text-[#1E3C5A]" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                  <div className="bg-[#0B1D33] border border-[#33383F] rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-[#F5F5F5]/80 font-mono">https://claude.ai/login</span>
                    <button onClick={() => handleCopy('https://claude.ai/login', 'link')} className="text-[#F5F5F5]/50 hover:text-[#F5F5F5] transition-colors">
                      {copiedField === 'link' ? <Check className="w-4 h-4 text-[#1E3C5A]" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>

              <button className="w-full bg-[#0B1D33] border border-[#33383F] hover:bg-[#1E3C5A]/50 transition-colors rounded-xl p-4 flex items-center justify-between mt-2">
                <span className="text-sm font-medium text-[#F5F5F5]">راهنمای استفاده</span>
                <div className="w-5 h-5 rounded-full border border-[#F5F5F5]/50 flex items-center justify-center text-[#F5F5F5]/50 text-[10px] font-bold">?</div>
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}