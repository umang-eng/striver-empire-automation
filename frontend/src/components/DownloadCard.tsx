"use client";

import { Download, FileSpreadsheet, FileText } from "lucide-react";

interface DownloadCardProps {
  kind: "excel" | "pdf";
  filename: string;
  href: string;
}

export function DownloadCard({ kind, filename, href }: DownloadCardProps) {
  const isExcel = kind === "excel";

  return (
    <div className="rounded-2xl border border-white/18 bg-black/25 p-4 flex flex-col justify-between gap-4 backdrop-blur-xl">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
            isExcel
              ? "border-emerald-400/30 bg-emerald-400/15 text-emerald-300"
              : "border-sky-400/30 bg-sky-400/15 text-sky-300"
          }`}
        >
          {isExcel ? (
            <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
          ) : (
            <FileText className="h-5 w-5" aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-white/55">
            {isExcel ? "Excel File" : "PDF File"}
          </p>
          <p className="mt-0.5 break-all text-xs font-medium text-white/90">{filename}</p>
        </div>
      </div>

      <a
        href={href}
        download={filename}
        className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 ${
          isExcel
            ? "bg-emerald-400 text-neutral-950 hover:bg-emerald-300"
            : "bg-white text-neutral-950 hover:bg-white/90"
        }`}
      >
        <Download className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{isExcel ? "Download Excel" : "Download PDF"}</span>
      </a>
    </div>
  );
}
