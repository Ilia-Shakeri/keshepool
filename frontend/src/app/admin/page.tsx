"use client";

import { useState } from "react";
import { Upload, Database, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AdminDashboard() {
  const [configs, setConfigs] = useState("");
  const [planType, setPlanType] = useState("plan1");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  const handleBulkUpload = async () => {
    setStatus("loading");

    // Execution context for filtering operational payloads
    const configArray = configs.split("\n").map(c => c.trim()).filter(c => c.length > 0);
    
    if (configArray.length === 0) {
      setStatus("error");
      return;
    }

    try {
      const response = await fetch("/api/admin/inventory/bulk-upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          product_id: "vpn_config",
          plan_type: planType,
          credentials: configArray
        })
      });

      if (!response.ok) throw new Error("Infrastructure sync failed");
      
      setStatus("success");
      setConfigs("");
      setTimeout(() => setStatus("idle"), 3000);
    } catch (error) {
      console.error(error);
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] p-6 font-sans dir-rtl max-w-2xl mx-auto">
      <header className="flex items-center gap-3 mb-8 border-b border-[#33383F] pb-4">
        <Database className="w-6 h-6 text-[#1E3C5A]" />
        <h1 className="text-2xl font-bold">مدیریت موجودی (Admin)</h1>
      </header>

      <main className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-[#F5F5F5]/70" />
          افزودن کانفیگ‌های V2Ray
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[#F5F5F5]/70 mb-2">نوع پلن (Plan Type)</label>
            <select 
              value={planType}
              onChange={(e) => setPlanType(e.target.value)}
              className="w-full bg-[#0F0F10] border border-[#33383F] rounded-xl p-3 text-sm focus:outline-none focus:border-[#1E3C5A] transition-colors"
            >
              <option value="plan1">پلن استاندارد (۱۵۰,۰۰۰)</option>
              <option value="plan2">پلن پرو (۲۸۰,۰۰۰)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-[#F5F5F5]/70 mb-2">لیست کانفیگ‌ها (هر خط یک کانفیگ)</label>
            <textarea 
              rows={8}
              value={configs}
              onChange={(e) => setConfigs(e.target.value)}
              placeholder="vless://...\nvmess://..."
              className="w-full bg-[#0F0F10] border border-[#33383F] rounded-xl p-3 text-sm font-mono dir-ltr focus:outline-none focus:border-[#1E3C5A] transition-colors"
            />
          </div>

          <Button 
            onClick={handleBulkUpload} 
            disabled={status === "loading"}
            className="w-full bg-[#1E3C5A] hover:bg-[#1E3C5A]/80 text-[#F5F5F5] py-6 rounded-xl font-bold border-none"
           >
            {status === "loading" ? "در حال آپلود..." : "آپلود و ذخیره در دیتابیس"}
          </Button>

          {status === "success" && (
            <div className="bg-[#1E3C5A]/10 border border-[#1E3C5A]/20 text-[#1E3C5A] p-3 rounded-xl flex items-center gap-2 text-sm">
              <CheckCircle2 className="w-4 h-4" /> کانفیگ‌ها با موفقیت به انبار اضافه شدند.
            </div>
          )}
          {status === "error" && (
            <div className="bg-[#E63946]/10 border border-[#E63946]/20 text-[#E63946] p-3 rounded-xl flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4" /> خطا در آپلود. لطفاً دوباره تلاش کنید.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}