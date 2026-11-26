"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { BackgroundVideo } from "@/components/BackgroundVideo";
import { CategorySuggestions } from "@/components/CategorySuggestions";
import { CompletionCard } from "@/components/CompletionCard";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { TaskInput } from "@/components/TaskInput";
import { TaskProgress } from "@/components/TaskProgress";
import { DEFAULT_CATEGORY_GROUPS } from "@/lib/defaultCategories";
import { CategoryGroup, TaskStatusResponse } from "@/lib/types";

const ACTIVE_TASK_STORAGE_KEY = "striver_active_task_id";

export default function HomePage() {
  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [categoryGroups, setCategoryGroups] = useState<CategoryGroup[]>(DEFAULT_CATEGORY_GROUPS);
  const [activeTask, setActiveTask] = useState<TaskStatusResponse | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  const stopTracking = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const startTrackingTask = useCallback(
    (taskId: string) => {
      stopTracking();
      window.localStorage.setItem(ACTIVE_TASK_STORAGE_KEY, taskId);

      const fetchProgressFallback = async () => {
        try {
          const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/progress`, {
            cache: "no-store",
          });
          if (res.status === 404) {
            window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
            stopTracking();
            setActiveTask(null);
            return;
          }
          if (!res.ok) return;
          const data: TaskStatusResponse = await res.json();
          setActiveTask(data);
          if (data.status === "completed" || data.status === "failed") {
            stopTracking();
          }
        } catch {
          // Keep polling quietly on transient network hiccups
        }
      };

      const startPolling = () => {
        if (pollTimerRef.current !== null) return;
        void fetchProgressFallback();
        pollTimerRef.current = window.setInterval(() => {
          void fetchProgressFallback();
        }, 1500);
      };

      if (typeof EventSource !== "undefined") {
        const es = new EventSource(`/api/tasks/${encodeURIComponent(taskId)}/events`);
        eventSourceRef.current = es;

        es.onmessage = (event) => {
          try {
            const data: TaskStatusResponse = JSON.parse(event.data);
            setActiveTask(data);
            if (data.status === "completed" || data.status === "failed") {
              stopTracking();
            }
          } catch {
            // Ignore malformed keepalive frames
          }
        };

        es.onerror = () => {
          es.close();
          eventSourceRef.current = null;
          startPolling();
        };
      } else {
        startPolling();
      }
    },
    [stopTracking]
  );

  // Initial health check, live categories fetch, and persisted task restoration
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      try {
        const healthRes = await fetch("/api/health", { cache: "no-store" });
        if (!cancelled) setBackendOnline(healthRes.ok);
      } catch {
        if (!cancelled) setBackendOnline(false);
      }

      try {
        const catRes = await fetch("/api/categories", { cache: "no-store" });
        if (catRes.ok) {
          const catData = await catRes.json();
          if (!cancelled && Array.isArray(catData.groups) && catData.groups.length > 0) {
            setCategoryGroups(catData.groups);
          }
        }
      } catch {
        // Retain static fallback categories
      }

      const savedId = window.localStorage.getItem(ACTIVE_TASK_STORAGE_KEY);
      if (savedId && !cancelled) {
        try {
          const res = await fetch(`/api/tasks/${encodeURIComponent(savedId)}`, {
            cache: "no-store",
          });
          if (res.ok) {
            const data: TaskStatusResponse = await res.json();
            if (!cancelled) {
              setActiveTask(data);
              if (data.status === "queued" || data.status === "running") {
                startTrackingTask(savedId);
              }
            }
          } else if (res.status === 404) {
            window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
          }
        } catch {
          // Ignore restore error if offline
        }
      }
    };

    void init();
    return () => {
      cancelled = true;
      stopTracking();
    };
  }, [startTrackingTask, stopTracking]);

  const handleSubmit = async () => {
    if (isSubmitting) return;
    setSubmitError(null);
    setIsSubmitting(true);

    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: inputValue }),
      });

      const data = await res.json();
      if (!res.ok) {
        setSubmitError(data.detail || "Unable to submit task.");
        return;
      }

      const task = data as TaskStatusResponse;
      setActiveTask(task);
      setBackendOnline(true);
      if (task.status === "queued" || task.status === "running") {
        startTrackingTask(task.task_id);
      }
    } catch {
      setSubmitError("Could not reach the automation server. Please try again.");
      setBackendOnline(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUseTemplate = (template: string) => {
    setInputValue(template);
    setSubmitError(null);
    if (activeTask && (activeTask.status === "completed" || activeTask.status === "failed")) {
      window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
      setActiveTask(null);
    }
    window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
  };

  const handleCancel = async () => {
    if (!activeTask) return;
    const id = activeTask.task_id;
    stopTracking();
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
    setActiveTask(null);
    try {
      await fetch(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
    } catch {
      // Ignore cleanup errors
    }
  };

  const handleReset = () => {
    stopTracking();
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
    setActiveTask(null);
    setSubmitError(null);
    window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
  };

  const showProgress =
    activeTask && (activeTask.status === "queued" || activeTask.status === "running");
  const showCompleted = activeTask && activeTask.status === "completed";
  const showFailed = activeTask && activeTask.status === "failed";

  return (
    <div
      className="relative min-h-screen flex flex-col justify-between"
      onContextMenu={(e) => {
        if ((e.target as HTMLElement)?.tagName === "VIDEO") {
          e.preventDefault();
        }
      }}
    >
      <BackgroundVideo />
      <div className="relative z-10 flex flex-col justify-between min-h-screen">
        <Header backendOnline={backendOnline} />

        <main className="w-full max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10 flex-1 flex flex-col justify-center gap-7">
        {/* Hero Headline */}
        <div className="text-center max-w-2xl mx-auto space-y-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/60">
            Product Automation Assistant
          </p>
          <h1 className="text-3xl sm:text-5xl font-semibold tracking-tight text-white">
            Product reports, simplified.
          </h1>
          <p className="text-sm sm:text-base text-white/65">
            Enter a category and discount to extract live products and generate matching Excel
            &amp; PDF reports.
          </p>
        </div>

        {/* Main Responsive Workspace Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          <div className="lg:col-span-7 space-y-4">
            {showProgress ? (
              <TaskProgress task={activeTask} onCancel={handleCancel} />
            ) : showCompleted ? (
              <CompletionCard task={activeTask} onReset={handleReset} />
            ) : showFailed ? (
              <section className="rounded-3xl border border-rose-400/30 bg-rose-950/35 p-5 sm:p-6 backdrop-blur-2xl shadow-[0_24px_60px_rgba(0,0,0,0.45)] space-y-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-rose-300 shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <h2 className="text-base font-semibold text-white">Extraction Failed</h2>
                    <p className="mt-1 text-xs text-rose-200/90">
                      {activeTask.error_message || "An unexpected error occurred."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleReset}
                  className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-colors cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Try Another Task</span>
                </button>
              </section>
            ) : (
              <TaskInput
                value={inputValue}
                onChange={(v) => {
                  setInputValue(v);
                  if (submitError) setSubmitError(null);
                }}
                onSubmit={handleSubmit}
                isSubmitting={isSubmitting}
                serverError={submitError}
                inputRef={inputRef}
              />
            )}
          </div>

          <div className="lg:col-span-5">
            <CategorySuggestions groups={categoryGroups} onUseTemplate={handleUseTemplate} />
          </div>
        </div>
      </main>

        <Footer />
      </div>
    </div>
  );
}
