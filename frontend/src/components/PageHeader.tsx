"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  className?: string;
}

export default function PageHeader({ title, className }: PageHeaderProps) {
  const router = useRouter();
  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.replace("/");
    }
  }, [router]);

  useTelegramBackButton(goBack);

  return (
    <header className={cn("relative flex min-h-[60px] items-center justify-center px-5 py-2", className)}>
      <button
        type="button"
        onClick={goBack}
        className="absolute right-4 flex size-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-[#F5F5F5]/75 transition-colors hover:bg-white/10 hover:text-[#F5F5F5]"
        aria-label="بازگشت"
      >
        <ChevronRight className="size-5" />
      </button>
      <h1 className="px-14 text-center text-base font-bold text-[#F5F5F5]">{title}</h1>
    </header>
  );
}
