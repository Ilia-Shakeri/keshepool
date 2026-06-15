"use client";

import { useState } from "react";
import { Search, ChevronLeft, Copy, Check, Headphones } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogHeader } from "@/components/ui/dialog";

type OrderStatus = 'all' | 'active' | 'expired';

// Mock Data representing the visual states in the UI
const MOCK_ORDERS = [
  { id: "#HA-2024-1298", title: "Claude Pro", duration: "1 ماهه", daysLeft: "23 روز باقیمانده", status: "active", icon: "C", bg: "bg-orange-500", date: "1403/11/20 - 21:41", email: "example@mail.com" },
  { id: "#HA-2024-1102", title: "ChatGPT Plus", duration: "1 ماهه", daysLeft: "12 روز باقیمانده", status: "active", icon: "G", bg: "bg-emerald-500", date: "1403/10/05 - 14:20", email: "example@mail.com" },
  { id: "#HA-2024-0988", title: "Netflix Premium", duration: "1 ماهه", daysLeft: "منقضی شده", status: "expired", icon: "N", bg: "bg-red-600", date: "1403/08/12 - 09:15", email: "example@mail.com" },
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
      console.error("Failed to copy", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-white font-sans pb-32">
      <header className="p-5 pt-6 flex justify-between items-center relative">
        <div className="w-6"></div> {/* Spacer for alignment */}
        <h1 className="text-base font-bold text-white">سفارش‌ها</h1>
        <Search className="w-5 h-5 text-zinc-300" />
      </header>

      <main className="px-5 mt-2">
        {/* Custom Segmented Control Tabs */}
        <div className="bg-[#121217] p-1 rounded-xl flex items-center justify-between mb-6 border border-zinc-800/80">
          <button onClick={() => setActiveTab('all')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'all' ? 'bg-[#2a2a32] text-white' : 'text-zinc-500'}`}>همه</button>
          <button onClick={() => setActiveTab('active')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'active' ? 'bg-[#2a2a32] text-white' : 'text-zinc-500'}`}>فعال</button>
          <button onClick={() => setActiveTab('expired')} className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${activeTab === 'expired' ? 'bg-[#2a2a32] text-white' : 'text-zinc-500'}`}>منقضی شده</button>
        </div>

        {/* Orders List */}
        <div className="space-y-3">
          {filteredOrders.map((order) => (
            <div 
              key={order.id} 
              onClick={() => setSelectedOrder(order)}
              className="bg-[#121217] border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-zinc-900 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 ${order.bg} rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg`}>
                  {order.icon}
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-bold text-white">{order.title}</h3>
                  <p className="text-[10px] text-zinc-400">{order.duration}</p>
                  <p className="text-[10px] text-zinc-500 mt-1">{order.daysLeft}</p>
                </div>
              </div>
              
              <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${
                order.status === 'active' ? 'text-green-500 border-green-500/20 bg-green-500/5' : 'text-red-500 border-red-500/20 bg-red-500/5'
              }`}>
                {order.status === 'active' ? 'فعال' : 'منقضی'}
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Order Details Modal (Screen 5) */}
      <Dialog open={!!selectedOrder} onOpenChange={(open) => !open && setSelectedOrder(null)}>
        <DialogContent className="bg-[#0a0a0c] border-none text-white w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col">
          <DialogTitle className="sr-only">Order Details</DialogTitle>
          
          <DialogHeader className="flex flex-row justify-between items-center p-5 pt-6 border-b border-zinc-800/60 sticky top-0 bg-[#0a0a0c]/90 backdrop-blur-md z-20">
            <button onClick={() => setSelectedOrder(null)} className="p-2 -mr-2 text-zinc-400 hover:text-white transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold">جزئیات سفارش</h2>
            <button className="p-2 -ml-2 text-zinc-400 hover:text-white transition-colors">
              <Headphones className="w-5 h-5" />
            </button>
          </DialogHeader>

          {selectedOrder && (
            <div className="p-5 space-y-6 flex-1 overflow-y-auto pb-24">
              
              {/* Status & Title Card */}
              <div className="bg-[#121217] border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 ${selectedOrder.bg} rounded-full flex items-center justify-center text-white font-bold shadow-lg`}>
                    {selectedOrder.icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{selectedOrder.title}</h3>
                    <p className="text-[10px] text-zinc-400 mt-1">{selectedOrder.duration} - اکانت اشتراکی</p>
                  </div>
                </div>
                <div className={`text-[10px] font-bold px-3 py-1 rounded-full border ${
                  selectedOrder.status === 'active' ? 'text-green-500 border-green-500/20 bg-green-500/5' : 'text-red-500 border-red-500/20 bg-red-500/5'
                }`}>
                  {selectedOrder.status === 'active' ? 'فعال' : 'منقضی'}
                </div>
              </div>

              {/* Order Meta */}
              <div className="space-y-4 px-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">تاریخ خرید</span>
                  <span className="text-zinc-300 font-medium">{selectedOrder.date}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">شماره سفارش</span>
                  <span className="text-zinc-300 font-mono font-medium">{selectedOrder.id}</span>
                </div>
              </div>

              {/* Credentials Section */}
              <div className="pt-4 border-t border-zinc-800/60">
                <h4 className="text-sm font-bold text-white mb-4">اطلاعات اکانت</h4>
                <div className="space-y-2">
                  
                  {/* Email Row */}
                  <div className="bg-[#121217] border border-zinc-800/80 rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-zinc-300 font-mono">{selectedOrder.email}</span>
                    <button onClick={() => handleCopy(selectedOrder.email, 'email')} className="text-zinc-500 hover:text-white transition-colors">
                      {copiedField === 'email' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Password Row */}
                  <div className="bg-[#121217] border border-zinc-800/80 rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-zinc-300 font-mono">••••••••••</span>
                    <button onClick={() => handleCopy('secure_password_123', 'password')} className="text-zinc-500 hover:text-white transition-colors">
                      {copiedField === 'password' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Login Link Row */}
                  <div className="bg-[#121217] border border-zinc-800/80 rounded-xl p-3.5 flex items-center justify-between">
                    <span className="text-sm text-zinc-300 font-mono">https://claude.ai/login</span>
                    <button onClick={() => handleCopy('https://claude.ai/login', 'link')} className="text-zinc-500 hover:text-white transition-colors">
                      {copiedField === 'link' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                </div>
              </div>

              {/* Usage Guide Button */}
              <button className="w-full bg-[#121217] border border-zinc-800/80 hover:bg-zinc-900 transition-colors rounded-xl p-4 flex items-center justify-between mt-2">
                <span className="text-sm font-medium text-zinc-300">راهنمای استفاده</span>
                <div className="w-5 h-5 rounded-full border border-zinc-500 flex items-center justify-center text-zinc-500 text-[10px] font-bold">?</div>
              </button>

            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}