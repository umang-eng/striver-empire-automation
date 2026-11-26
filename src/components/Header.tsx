"use client";

import { Aperture } from "lucide-react";

interface HeaderProps {
  backendOnline: boolean | null;
}

export function Header({ backendOnline }: HeaderProps) {
  return (
    <header className="w-full max-w-6xl mx-auto px-4 sm:px-6 pt-5 pb-2">
      <div className="flex items-center justify-between rounded-2xl border border-white/45 bg-white/80 px-4 py-2.5 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.85),0_12px_32px_rgba(0,0,0,0.3)]">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-black/15 bg-black/10">
            <Aperture className="h-5 w-5 text-black" aria-hidden="true" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm sm:text-lg font-extrabold tracking-[0.14em] text-black uppercase leading-tight">
              Striver Empire Automation
            </span>
            <span className="text-xs font-bold text-black/75 hidden sm:block">
              Live Catalog Extraction &amp; Report Engine
            </span>
          </div>
        </div>

        <div
          className="inline-flex items-center gap-2 rounded-full border border-black/15 bg-black/10 px-3.5 py-1.5"
          aria-live="polite"
        >
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              backendOnline === true
                ? "bg-emerald-600 shadow-[0_0_8px_rgba(5,150,105,0.7)]"
                : backendOnline === false
                ? "bg-rose-600 shadow-[0_0_8px_rgba(225,29,72,0.7)]"
                : "bg-amber-500 animate-pulse"
            }`}
          />
          <span
            className={`text-xs sm:text-sm font-bold ${
              backendOnline === true
                ? "text-black"
                : backendOnline === false
                ? "text-rose-800"
                : "text-black/80"
            }`}
          >
            {backendOnline === true ? "Online" : backendOnline === false ? "Worker Offline" : "Checking"}
          </span>
        </div>
      </div>
    </header>
  );
}
