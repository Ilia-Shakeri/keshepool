import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";

interface UserAvatarProps {
  firstName?: string | null;
  username?: string | null;
  telegramId?: string | number | null;
  className?: string;
  style?: CSSProperties;
}

function firstGrapheme(value?: string | null): string {
  const text = value?.trim();
  if (!text) return "";

  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    const segmenter = new Intl.Segmenter("fa", { granularity: "grapheme" });
    return segmenter.segment(text)[Symbol.iterator]().next().value?.segment ?? "";
  }

  return Array.from(text)[0] ?? "";
}

function getAvatarInitial(firstName?: string | null, username?: string | null, telegramId?: string | number | null): string {
  return (
    firstGrapheme(firstName) ||
    firstGrapheme(username?.replace(/^@+/, "")) ||
    firstGrapheme(String(telegramId ?? "")) ||
    "\u06a9"
  );
}

export default function UserAvatar({ firstName, username, telegramId, className, style }: UserAvatarProps) {
  const initial = getAvatarInitial(firstName, username, telegramId);

  return (
    <div
      role="img"
      aria-label={`نشان کاربر ${initial}`}
      style={style}
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/10 bg-gradient-to-br from-white/10 to-white/[0.04] font-bold text-[#F5F5F5]",
        className,
      )}
    >
      <span aria-hidden="true">{initial}</span>
    </div>
  );
}
