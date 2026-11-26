"use client";

import { Aperture } from "lucide-react";

interface HeaderProps {
  backendOnline: boolean | null;
}

export function Header({ backendOnline }: HeaderProps) {
  return (
    <header className="w-full max-w-6xl mx-auto px-4 sm:px-6 pt-5 pb-2 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/20 bg-white/10 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]">
          <Aperture className="h-4.5 w-4.5 text-white" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs sm:text-sm font-semibold tracking-[0.16em] text-white/95 uppercase">
            Striver Empire Automation
          </span>
          <span className="text-[11px] text-white/55 hidden sm:block">
            Live Catalog Extraction &amp; Report Engine
          </span>
        </div>
      </div>

      <div
        className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.07] px-3 py-1.5 backdrop-blur-xl"
        aria-live="polite"
      >
        <span
          className={`h-2 w-2 rounded-full ${
            backendOnline === true
              ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]"
              : backendOnline === false
              ? "bg-rose-400 shadow-[0_0_8px_rgba(251,113,133,0.8)]"
              : "bg-amber-300 animate-pulse"
          }`}
        />
        <span
          className={`text-xs font-medium ${
            backendOnline === true
              ? "text-emerald-300"
              : backendOnline === false
              ? "text-rose-300"
              : "text-white/75"
          }`}
        >
          {backendOnline === true ? "Online" : backendOnline === false ? "Worker Offline" : "Checking"}
        </span>
      </div>
    </header>
  );
}
