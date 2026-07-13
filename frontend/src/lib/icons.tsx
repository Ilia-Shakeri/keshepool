import { Shield, Music, MonitorPlay, MessageCircle, Sparkles, Gamepad2, Twitter, Bot, PenTool, Briefcase, BookOpen, LineChart, Video, Box, Wrench } from "lucide-react";
import React from "react";
import type { ProductCategory } from "@/lib/products";

type IconRenderer = (sizeClass?: string) => React.ReactNode;

const makeIcon = (Component: React.ElementType): IconRenderer =>
  function IconRenderer(sizeClass = "w-5 h-5") {
    return <Component className={`${sizeClass} text-white`} />;
  };

export const IconMap: Record<string, IconRenderer> = {
  Shield: makeIcon(Shield),
  Music: makeIcon(Music),
  MonitorPlay: makeIcon(MonitorPlay),
  MessageCircle: makeIcon(MessageCircle),
  Sparkles: makeIcon(Sparkles),
  Gamepad2: makeIcon(Gamepad2),
  Twitter: makeIcon(Twitter),
  Bot: makeIcon(Bot),
  Video: makeIcon(Video),
  PenTool: makeIcon(PenTool),
  Briefcase: makeIcon(Briefcase),
  BookOpen: makeIcon(BookOpen),
  LineChart: makeIcon(LineChart),
  Wrench: makeIcon(Wrench),
  Box: makeIcon(Box),
};

export const CATEGORY_ICON_MAP: Record<ProductCategory, { icon: string; gradient: string }> = {
  vpn:     { icon: "Shield",       gradient: "from-blue-500 to-indigo-800" },
  music:   { icon: "Music",        gradient: "from-pink-500 to-purple-800" },
  video:   { icon: "MonitorPlay",  gradient: "from-red-500 to-rose-900" },
  ai:      { icon: "Bot",          gradient: "from-cyan-500 to-blue-800" },
  social:  { icon: "MessageCircle",gradient: "from-green-500 to-teal-800" },
  gaming:  { icon: "Gamepad2",     gradient: "from-violet-500 to-purple-900" },
  tools:   { icon: "Wrench",       gradient: "from-amber-500 to-orange-800" },
  edu:     { icon: "BookOpen",     gradient: "from-yellow-500 to-amber-800" },
  finance: { icon: "LineChart",    gradient: "from-emerald-500 to-green-800" },
};
