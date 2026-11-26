"use client";

import { ArrowUpRight, Loader2 } from "lucide-react";

interface GenerateButtonProps {
  disabled: boolean;
  loading: boolean;
  onClick?: () => void;
}

export function GenerateButton({ disabled, loading, onClick }: GenerateButtonProps) {
  return (
    <button
      type="submit"
      disabled={disabled || loading}
      onClick={onClick}
      className={`group relative w-full flex items-center justify-center gap-2.5 rounded-2xl px-6 py-3.5 text-sm sm:text-base font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black/50 ${
        disabled || loading
          ? "cursor-not-allowed bg-white/15 text-white/45 border border-white/10"
          : "cursor-pointer bg-white text-neutral-950 shadow-[0_8px_30px_rgba(255,255,255,0.18)] hover:bg-white/95 hover:shadow-[0_12px_36px_rgba(255,255,255,0.28)] active:scale-[0.99]"
      }`}
    >
      {loading ? (
        <>
          <Loader2 className="h-4.5 w-4.5 animate-spin" aria-hidden="true" />
          <span>Starting Extraction...</span>
        </>
      ) : (
        <>
          <span>Generate Report</span>
          <ArrowUpRight
            className="h-4.5 w-4.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            aria-hidden="true"
          />
        </>
      )}
    </button>
  );
}
