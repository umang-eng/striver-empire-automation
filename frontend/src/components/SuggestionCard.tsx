"use client";

import { Check, Copy } from "lucide-react";
import { MouseEvent, useState } from "react";

interface SuggestionCardProps {
  label: string;
  template: string;
  onUseTemplate: (template: string) => void;
}

export function SuggestionCard({ label, template, onUseTemplate }: SuggestionCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(template);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = template;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group flex items-center justify-between gap-1.5 rounded-xl border border-white/12 bg-white/[0.05] p-1 transition-all duration-150 hover:border-white/30 hover:bg-white/[0.11]">
      <button
        type="button"
        onClick={() => onUseTemplate(template)}
        title={`Click to use "${template}"`}
        className="min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 cursor-pointer"
      >
        <p className="truncate text-xs font-medium text-white/90 group-hover:text-white">
          {template}
        </p>
        <p className="truncate text-[10px] text-white/45">{label}</p>
      </button>

      <button
        type="button"
        onClick={handleCopy}
        aria-label={`Copy ${template}`}
        title={`Copy "${template}"`}
        className="shrink-0 mr-1 inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1.5 text-[10px] font-medium text-white/75 transition-colors hover:border-white/25 hover:bg-white/15 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 cursor-pointer"
      >
        {copied ? (
          <>
            <Check className="h-3 w-3 text-emerald-300" aria-hidden="true" />
            <span className="text-emerald-300">Copied!</span>
          </>
        ) : (
          <Copy className="h-3 w-3" aria-hidden="true" />
        )}
      </button>
    </div>
  );
}
