"use client";

import { Check, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { PROGRESS_STAGES, TaskStatusResponse } from "@/lib/types";

interface TaskProgressProps {
  task: TaskStatusResponse;
  onCancel: () => void;
}

function formatElapsed(startedIso: string, createdIso: string, nowMs: number): string {
  const base = Date.parse(startedIso || createdIso);
  if (!Number.isFinite(base)) return "0s";
  const sec = Math.max(0, Math.floor((nowMs - base) / 1000));
  const mins = Math.floor(sec / 60);
  const rem = sec % 60;
  return mins > 0 ? `${mins}m ${rem}s` : `${rem}s`;
}

export function TaskProgress({ task, onCancel }: TaskProgressProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const elapsed = formatElapsed(task.started_at, task.created_at, nowMs);

  return (
    <section
      aria-label="Live extraction progress"
      className="rounded-3xl border border-white/20 bg-white/[0.08] p-5 sm:p-6 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_24px_60px_rgba(0,0,0,0.45)] space-y-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300">
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            <span>
              Stage {task.stage_index} of {task.total_stages}
            </span>
          </span>
          <h2 className="mt-2 text-lg sm:text-xl font-semibold text-white">
            {task.stage}
          </h2>
          <p className="text-xs text-white/60">
            Task: <span className="text-white/90 font-medium">{task.raw_message}</span>
            {task.current_subcategory ? (
              <>
                {" "}
                · Subcategory:{" "}
                <span className="text-white/90 font-medium">{task.current_subcategory}</span>
              </>
            ) : null}
          </p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-white/75 hover:bg-rose-500/20 hover:border-rose-400/30 hover:text-rose-200 transition-colors cursor-pointer"
        >
          <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Cancel</span>
        </button>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-white/70">Extraction Progress</span>
          <span className="font-semibold text-white">{task.progress_percent}%</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/10 border border-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-green-400 to-teal-300 transition-all duration-500 ease-out shadow-[0_0_16px_rgba(52,211,153,0.65)]"
            style={{ width: `${Math.min(100, Math.max(4, task.progress_percent))}%` }}
          />
        </div>
      </div>

      {/* Live Backend Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="rounded-2xl border border-white/12 bg-black/25 p-3">
          <p className="text-[11px] text-white/50">Discovered</p>
          <p className="mt-0.5 text-lg font-semibold text-white">{task.products_discovered}</p>
        </div>
        <div className="rounded-2xl border border-white/12 bg-black/25 p-3">
          <p className="text-[11px] text-white/50">Extracted</p>
          <p className="mt-0.5 text-lg font-semibold text-emerald-300">
            {task.products_extracted}
          </p>
        </div>
        <div className="rounded-2xl border border-white/12 bg-black/25 p-3">
          <p className="text-[11px] text-white/50">Failed</p>
          <p className="mt-0.5 text-lg font-semibold text-rose-300">{task.failed_products}</p>
        </div>
        <div className="rounded-2xl border border-white/12 bg-black/25 p-3">
          <p className="text-[11px] text-white/50">Elapsed Time</p>
          <p className="mt-0.5 text-lg font-semibold text-white">{elapsed}</p>
        </div>
      </div>

      {/* 11-Stage Checklist */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
        {PROGRESS_STAGES.map((stageLabel, idx) => {
          const stageNum = idx + 1;
          const isDone = stageNum < task.stage_index;
          const isCurrent = stageNum === task.stage_index;
          return (
            <div
              key={stageLabel}
              className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-xs border ${
                isCurrent
                  ? "border-emerald-400/35 bg-emerald-400/12 text-white font-medium"
                  : isDone
                  ? "border-white/10 bg-white/[0.04] text-white/75"
                  : "border-transparent text-white/35"
              }`}
            >
              {isDone ? (
                <Check className="h-3.5 w-3.5 text-emerald-300 shrink-0" aria-hidden="true" />
              ) : isCurrent ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-300 shrink-0" aria-hidden="true" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-white/25 mx-1 shrink-0" />
              )}
              <span className="truncate">
                {stageNum}. {stageLabel}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
