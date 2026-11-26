"use client";

import { AlertCircle, CheckCircle2, Sparkles } from "lucide-react";
import { FormEvent, KeyboardEvent, RefObject } from "react";
import { validateTaskMessage } from "@/lib/validation";
import { GenerateButton } from "./GenerateButton";

interface TaskInputProps {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  serverError: string | null;
  inputRef: RefObject<HTMLInputElement | null>;
}

export function TaskInput({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  serverError,
  inputRef,
}: TaskInputProps) {
  const hasTyped = value.trim().length > 0;
  const validation = validateTaskMessage(value);

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!validation.valid || isSubmitting) return;
    onSubmit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (validation.valid && !isSubmitting) {
        onSubmit();
      }
    }
  };

  return (
    <form
      onSubmit={handleFormSubmit}
      className="relative rounded-3xl border border-white/20 bg-white/[0.08] p-4 sm:p-6 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_24px_60px_rgba(0,0,0,0.45)] transition-all duration-300 focus-within:border-white/35 focus-within:bg-white/[0.11] focus-within:shadow-[inset_0_1px_0_rgba(255,255,255,0.3),0_24px_70px_rgba(255,255,255,0.08)]"
      noValidate
    >
      <div className="flex flex-col gap-3">
        <label htmlFor="task-message-input" className="sr-only">
          Category and discount task message
        </label>
        <input
          ref={inputRef}
          id="task-message-input"
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter your task... e.g. women 25%"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={hasTyped && !validation.valid}
          aria-describedby="task-input-hint"
          className="w-full bg-transparent text-base sm:text-lg font-medium text-white placeholder:text-white/40 focus:outline-none py-1.5"
        />

        <div className="h-px w-full bg-white/12" />

        <div id="task-input-hint" className="min-h-[24px] flex items-center justify-between gap-2 text-xs">
          {serverError ? (
            <span className="inline-flex items-center gap-1.5 text-rose-300">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>{serverError}</span>
            </span>
          ) : hasTyped && !validation.valid ? (
            <span className="inline-flex items-center gap-1.5 text-amber-300/95">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>{validation.error}</span>
            </span>
          ) : hasTyped && validation.valid ? (
            <span className="inline-flex items-center gap-1.5 text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>
                Ready: <strong>{validation.category}</strong> at{" "}
                <strong>{validation.discount}%</strong> discount
              </span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-white/50">
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-white/45" aria-hidden="true" />
              <span>Format: &lt;Category&gt; &lt;Discount&gt;% (0% to 99.9%)</span>
            </span>
          )}
        </div>

        <GenerateButton disabled={!validation.valid} loading={isSubmitting} />
      </div>
    </form>
  );
}
