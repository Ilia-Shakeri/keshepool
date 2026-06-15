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
    
    // Split text area by newlines and filter out empty strings
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
          // In a real scenario, attach Admin JWT here
          // "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          product_id: "vpn_config",
          plan_type: planType,
          credentials: configArray
        })
      });

      if (!response.ok) throw new Error("Upload failed");
      
      setStatus("success");
      setConfigs(""); // Clear text area on success
      setTimeout(() => setStatus("idle"), 3000);
    } catch (error) {
      console.error(error);
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 font-sans dir-rtl max-w-2xl mx-auto">
      <header className="flex items-center gap-3 mb-8 border-b border-zinc-800 pb-4">
        <Database className="w-6 h-6 text-emerald-500" />
        <h1 className="text-2xl font-bold">مدیریت موجودی (Admin)</h1>
      </header>

      <main className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-zinc-400" />
          افزودن کانفیگ‌های V2Ray
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-2">نوع پلن (Plan Type)</label>
            <select 
              value={planType}
              onChange={(e) => setPlanType(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            >
              <option value="plan1">پلن استاندارد (۱۵۰,۰۰۰)</option>
              <option value="plan2">پلن پرو (۲۸۰,۰۰۰)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-2">لیست کانفیگ‌ها (هر خط یک کانفیگ)</label>
            <textarea 
              rows={8}
              value={configs}
              onChange={(e) => setConfigs(e.target.value)}
              placeholder="vless://...\nvmess://..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-sm font-mono dir-ltr focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <Button 
            onClick={handleBulkUpload} 
            disabled={status === "loading"}
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-6 rounded-xl font-bold"
          >
            {status === "loading" ? "در حال آپلود..." : "آپلود و ذخیره در دیتابیس"}
          </Button>

          {/* Status Messages */}
          {status === "success" && (
            <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 p-3 rounded-xl flex items-center gap-2 text-sm">
              <CheckCircle2 className="w-4 h-4" /> کانفیگ‌ها با موفقیت به انبار اضافه شدند.
            </div>
          )}
          {status === "error" && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4" /> خطا در آپلود. لطفاً دوباره تلاش کنید.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}