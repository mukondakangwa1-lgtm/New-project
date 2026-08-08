import { useEffect, useRef, useState } from "react";

export type ProgressTone = "primary" | "green" | "red";

/**
 * Tracks a long-running operation. The bar stays hidden until the operation
 * has run for `graceMs` (default 2s) so fast operations never flicker a bar,
 * then shows with a live elapsed-seconds counter.
 *
 * `start(label)` resets and shows; `update(label, percent?, tone?)` refreshes
 * in place without resetting the elapsed timer (used by polling loops).
 */
export function useLongProcess(graceMs = 2000) {
  const [label, setLabel] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [percent, setPercent] = useState<number | undefined>(undefined);
  const [tone, setTone] = useState<ProgressTone>("primary");
  const [visible, setVisible] = useState(false);
  const startedAt = useRef<number | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const grace = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = () => {
    if (timer.current) clearInterval(timer.current);
    if (grace.current) clearTimeout(grace.current);
    timer.current = null;
    grace.current = null;
    startedAt.current = null;
    setLabel("");
    setElapsed(0);
    setPercent(undefined);
    setTone("primary");
    setVisible(false);
  };

  const start = (nextLabel: string, nextPercent?: number, nextTone: ProgressTone = "primary") => {
    if (timer.current) clearInterval(timer.current);
    if (grace.current) clearTimeout(grace.current);
    setLabel(nextLabel);
    setPercent(nextPercent);
    setTone(nextTone);
    startedAt.current = Date.now();
    setElapsed(0);
    setVisible(false);
    grace.current = setTimeout(() => setVisible(true), graceMs);
    timer.current = setInterval(() => {
      if (startedAt.current) {
        const secs = Math.floor((Date.now() - startedAt.current) / 1000);
        setElapsed((prev) => (secs > prev ? secs : prev));
      }
    }, 1000);
  };

  const update = (nextLabel: string, nextPercent?: number, nextTone?: ProgressTone) => {
    setLabel(nextLabel);
    if (nextPercent !== undefined) setPercent(nextPercent);
    if (nextTone) setTone(nextTone);
  };

  useEffect(() => stop, []);

  return {
    active: visible,
    label,
    elapsed,
    percent,
    tone,
    start,
    update,
    stop,
  };
}

/**
 * Inline progress bar — determinate when `percent` is given, otherwise an
 * animated indeterminate bar. Shows a live elapsed counter when provided.
 */
export function ProgressBar({
  label,
  percent,
  elapsed,
  tone = "primary",
  slim = false,
}: {
  label: string;
  percent?: number;
  elapsed?: number;
  tone?: ProgressTone;
  slim?: boolean;
}) {
  const fill = percent != null ? `${Math.max(0, Math.min(100, percent))}%` : undefined;
  const toneClasses = {
    primary: "bg-primary",
    green: "bg-green-600",
    red: "bg-red-600",
  }[tone];

  return (
    <div className="w-full" role="status" aria-live="polite">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-600">{label}</span>
        {elapsed != null && elapsed > 0 && (
          <span className="text-xs text-gray-400 tabular-nums">{elapsed}s</span>
        )}
      </div>
      <div className={`w-full rounded-full bg-gray-200 overflow-hidden ${slim ? "h-1.5" : "h-2.5"}`}>
        {fill != null ? (
          <div
            className={`h-full rounded-full ${toneClasses} transition-all duration-300`}
            style={{ width: fill }}
          />
        ) : (
          <div className={`h-full rounded-full ${toneClasses} indeterminate-bar`} />
        )}
      </div>
    </div>
  );
}
