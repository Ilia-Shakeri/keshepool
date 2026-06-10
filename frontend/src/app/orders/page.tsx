"use client";

import { Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogClose
} from "@/components/ui/dialog";

// Mock database layer for current client-side rendering evaluation
const MOCK_ORDERS = [
  { id: "ORD-981X", title: "اسپاتیفای پرمیوم ۱ ماهه", date: "۱۴۰۳/۰۳/۱۱", status: "فعال", price: "۱۶۰,۰۰۰", method: "روی اکانت شخصی", email: "ilia@example.com" },
  { id: "ORD-982X", title: "نتفلیکس پرمیوم ۳ ماهه", date: "۱۴۰۳/۰۲/۱۵", status: "پایان یافته", price: "۷۰۰,۰۰۰", method: "اکانت آماده", email: "-" },
  { id: "ORD-983X", title: "تلگرام پرمیوم ۶ ماهه", date: "۱۴۰۲/۱۱/۲۰", status: "پایان یافته", price: "۱,۶۰۰,۰۰۰", method: "ارسال گیفت", email: "@ilia_devops" }
];

export default function OrdersPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-32 relative">
      
      {/* Consistent Sticky Header */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">سفارشات من</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors bg-slate-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col gap-4 w-full px-4 max-w-lg mx-auto">
        {MOCK_ORDERS.map((order) => (
          <Dialog key={order.id}>
            <div className="bg-slate-800/60 backdrop-blur-sm rounded-3xl p-5 border border-slate-700 flex flex-col gap-3 shadow-md hover:border-cyan-500/30 transition-colors">
              <div className="flex justify-between items-center border-b border-slate-700/50 pb-3">
                <span className={`text-xs px-3 py-1 rounded-full font-medium ${order.status === 'فعال' ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-slate-700/50 text-slate-400 border border-slate-600/50'}`}>
                  {order.status}
                </span>
                <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" /> {order.date}</span>
              </div>
              <div className="flex justify-between items-center mt-2">
                <div className="text-right">
                  <h4 className="font-bold text-sm text-white mb-1">{order.title}</h4>
                  <p className="text-[10px] text-slate-400 font-mono">کد سفارش: {order.id}</p>
                </div>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 shrink-0 ml-2 rounded-xl">مشاهده</Button>
                </DialogTrigger>
              </div>
            </div>

            {/* Dynamic Modal populated securely with state context */}
            <DialogContent className="bg-slate-900 border border-slate-700 text-white rounded-3xl w-[90%] max-w-md mx-auto">
              <DialogHeader className="border-b border-slate-800 pb-4 mb-2">
                <DialogTitle className="text-right text-lg font-bold text-cyan-400">
                  جزئیات سفارش
                </DialogTitle>
              </DialogHeader>
              
              <div className="flex flex-col gap-4 text-sm mt-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">محصول:</span>
                  <span className="font-bold text-white">{order.title}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">کد سفارش:</span>
                  <span className="font-mono text-cyan-400 bg-cyan-500/10 px-2 py-1 rounded-md">{order.id}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">تاریخ ثبت:</span>
                  <span>{order.date}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">وضعیت:</span>
                  <span className={order.status === 'فعال' ? 'text-green-400 font-bold' : 'text-slate-500'}>{order.status}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">نوع فعالسازی:</span>
                  <span>{order.method}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">ایمیل / آیدی:</span>
                  <span className="font-mono text-left dir-ltr">{order.email}</span>
                </div>
                
                {/* Visual grouping identical to the transaction payload interface */}
                <div className="mt-2 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 flex justify-between items-center">
                  <span className="font-bold text-slate-300">مبلغ پرداخت شده:</span>
                  <span className="text-cyan-400 font-bold text-lg dir-ltr">{order.price} <span className="text-sm font-normal text-slate-400">تومان</span></span>
                </div>
              </div>

              <div className="mt-6">
                <DialogClose asChild>
                  <Button className="w-full bg-slate-800 hover:bg-slate-700 text-white py-6 rounded-xl border border-slate-600 transition-colors">
                    بستن
                  </Button>
                </DialogClose>
              </div>
            </DialogContent>
          </Dialog>
        ))}
      </main>
    </div>
  );
}