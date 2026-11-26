"use client";

import { AlertTriangle, CheckCircle2, RotateCcw } from "lucide-react";
import { TaskStatusResponse } from "@/lib/types";
import { DownloadCard } from "./DownloadCard";

interface CompletionCardProps {
  task: TaskStatusResponse;
  onReset: () => void;
}

export function CompletionCard({ task, onReset }: CompletionCardProps) {
  return (
    <section
      aria-label="Report generated successfully"
      className="rounded-3xl border border-white/20 bg-white/[0.08] p-5 sm:p-6 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_24px_60px_rgba(0,0,0,0.45)] space-y-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-emerald-400/35 bg-emerald-400/15 text-emerald-300">
            <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
              Report Generated Successfully
            </p>
            <h2 className="mt-1 text-lg sm:text-xl font-semibold text-white">
              {task.category} ({task.discount_percent}%)
            </h2>
            <p className="text-xs text-white/65 mt-0.5">
              Products extracted: <strong className="text-white">{task.products_extracted}</strong>
              {task.failed_products > 0 ? (
                <span className="text-amber-300"> · Failed: {task.failed_products}</span>
              ) : null}
            </p>
          </div>
        </div>
      </div>

      {task.warnings.length > 0 && (
        <div className="rounded-2xl border border-amber-400/25 bg-amber-400/10 p-3 text-xs text-amber-200 space-y-1">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>Notices</span>
          </div>
          {task.warnings.map((w, i) => (
            <p key={i} className="text-amber-200/85 pl-5">
              {w}
            </p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {task.excel_ready && (
          <DownloadCard
            kind="excel"
            filename={task.excel_filename}
            href={`/api/tasks/${encodeURIComponent(task.task_id)}/download/excel`}
          />
        )}
        {task.pdf_ready && (
          <DownloadCard
            kind="pdf"
            filename={task.pdf_filename}
            href={`/api/tasks/${encodeURIComponent(task.task_id)}/download/pdf`}
          />
        )}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="w-full inline-flex items-center justify-center gap-2 rounded-2xl border border-white/18 bg-white/[0.06] px-4 py-3 text-sm font-medium text-white hover:bg-white/[0.12] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        <span>Generate Another Report</span>
      </button>
    </section>
  );
}
