/**
 * Safe formatting utilities for rendering API data.
 *
 * Every display value in the app should go through one of these helpers.
 * They handle: undefined, null, NaN, Infinity, empty strings, and
 * unexpected types — returning a safe, truthful fallback instead of crashing.
 *
 * RULE: No fake values. If data is missing, show "—" or a contextual empty state.
 *       Never invent numbers or show "0" when the real answer is "unknown".
 */

// ─── Currency ────────────────────────────────────────────────────────────────

/**
 * Format a number as USD currency. Returns "—" for missing/invalid values.
 * @param value - The numeric value (may be undefined/null/NaN)
 * @param opts.compact - Use compact notation for large numbers (e.g. "$1.2K")
 * @param opts.fallback - Custom fallback string (default "—")
 * @param opts.zeroIsValid - If true, 0 renders as "$0"; if false, 0 renders as fallback
 */
export function fmtCurrency(
  value: number | null | undefined,
  opts: { compact?: boolean; fallback?: string; zeroIsValid?: boolean } = {},
): string {
  const { compact = false, fallback = "—", zeroIsValid = true } = opts;
  if (value === null || value === undefined || Number.isNaN(value) || !Number.isFinite(value)) {
    return fallback;
  }
  if (value === 0 && !zeroIsValid) return fallback;
  try {
    return value.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: value % 1 === 0 ? 0 : 2,
      maximumFractionDigits: 2,
      ...(compact ? { notation: "compact", compactDisplay: "short" } : {}),
    });
  } catch {
    return fallback;
  }
}

// ─── Percentages ─────────────────────────────────────────────────────────────

/**
 * Format a number as a percentage. Accepts either 0-1 decimals or 0-100 values.
 * @param value - The numeric value
 * @param opts.isDecimal - If true, multiply by 100 (e.g. 0.75 → "75%")
 * @param opts.decimals - Decimal places (default 1)
 * @param opts.fallback - Fallback for missing values
 */
export function fmtPercent(
  value: number | null | undefined,
  opts: { isDecimal?: boolean; decimals?: number; fallback?: string } = {},
): string {
  const { isDecimal = false, decimals = 1, fallback = "—" } = opts;
  if (value === null || value === undefined || Number.isNaN(value) || !Number.isFinite(value)) {
    return fallback;
  }
  const pct = isDecimal ? value * 100 : value;
  return `${pct.toFixed(decimals)}%`;
}

// ─── Counts / Integers ───────────────────────────────────────────────────────

/**
 * Format a count/integer with locale separators. Returns "—" for missing.
 */
export function fmtCount(
  value: number | null | undefined,
  opts: { fallback?: string; compact?: boolean } = {},
): string {
  const { fallback = "—", compact = false } = opts;
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  if (compact && Math.abs(value) >= 1000) {
    return value.toLocaleString("en-US", { notation: "compact", compactDisplay: "short" });
  }
  return value.toLocaleString("en-US");
}

// ─── Ratios / Multipliers ────────────────────────────────────────────────────

/**
 * Format a ratio like LTV:CAC (e.g. "3.2x"). Returns "—" for missing.
 */
export function fmtRatio(
  value: number | null | undefined,
  opts: { decimals?: number; suffix?: string; fallback?: string } = {},
): string {
  const { decimals = 1, suffix = "x", fallback = "—" } = opts;
  if (value === null || value === undefined || Number.isNaN(value) || !Number.isFinite(value)) {
    return fallback;
  }
  return `${value.toFixed(decimals)}${suffix}`;
}

// ─── Scores ──────────────────────────────────────────────────────────────────

/**
 * Format a score (0-100 typically). Returns letter grade or numeric display.
 */
export function fmtScore(
  value: number | null | undefined,
  opts: { fallback?: string; showGrade?: boolean } = {},
): string {
  const { fallback = "—", showGrade = false } = opts;
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  if (showGrade) {
    if (value >= 90) return `${value} (A)`;
    if (value >= 80) return `${value} (B)`;
    if (value >= 70) return `${value} (C)`;
    if (value >= 60) return `${value} (D)`;
    return `${value} (F)`;
  }
  return String(Math.round(value));
}

// ─── Dates ───────────────────────────────────────────────────────────────────

/**
 * Format a date/datetime string. Returns "—" for missing/invalid.
 * @param value - ISO string, Date, or timestamp
 * @param opts.format - "date" | "datetime" | "relative" | "short"
 */
export function fmtDate(
  value: string | Date | number | null | undefined,
  opts: { format?: "date" | "datetime" | "relative" | "short"; fallback?: string } = {},
): string {
  const { format = "date", fallback = "—" } = opts;
  if (!value) return fallback;

  let d: Date;
  try {
    d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return fallback;
  } catch {
    return fallback;
  }

  if (format === "relative") {
    const now = Date.now();
    const diff = now - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  if (format === "short") {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  if (format === "datetime") {
    return d.toLocaleString("en-US", {
      month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  }

  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// ─── Safe Array Access ───────────────────────────────────────────────────────

/**
 * Safely get an array from an API response that might be undefined, null,
 * or an object with an items/data/results key.
 */
export function safeArray<T>(value: T[] | { items?: T[]; data?: T[]; results?: T[] } | null | undefined): T[] {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "object") {
    if (Array.isArray((value as any).items)) return (value as any).items;
    if (Array.isArray((value as any).data)) return (value as any).data;
    if (Array.isArray((value as any).results)) return (value as any).results;
  }
  return [];
}

// ─── Safe Object Access ──────────────────────────────────────────────────────

/**
 * Safely access a nested property path. Returns fallback if any part is missing.
 * Usage: safeGet(data, "forecast.points", [])
 */
export function safeGet<T>(obj: any, path: string, fallback: T): T {
  const keys = path.split(".");
  let current = obj;
  for (const key of keys) {
    if (current === null || current === undefined || typeof current !== "object") {
      return fallback;
    }
    current = current[key];
  }
  return (current ?? fallback) as T;
}

// ─── Safe Number ─────────────────────────────────────────────────────────────

/**
 * Coerce a value to a number, returning fallback for anything non-numeric.
 */
export function safeNum(value: any, fallback: number = 0): number {
  if (value === null || value === undefined) return fallback;
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

// ─── Status Badge Helpers ────────────────────────────────────────────────────

type StatusKind = "success" | "warning" | "error" | "info" | "neutral";

const STATUS_MAP: Record<string, StatusKind> = {
  // Common statuses across the system
  configured: "success", live: "success", healthy: "success", completed: "success",
  approved: "success", active: "success", pass: "success",
  partial: "warning", warning: "warning", degraded: "warning", starting: "warning",
  pending: "info", draft: "info", queued: "info", processing: "info", running: "info",
  not_configured: "error", blocked_by_credentials: "error", failed: "error",
  critical: "error", suspended: "error", rejected: "error", fail: "error",
  insufficient_data: "neutral",
};

export function statusKind(status: string | null | undefined): StatusKind {
  if (!status) return "neutral";
  return STATUS_MAP[status.toLowerCase()] ?? "neutral";
}

export const STATUS_COLORS: Record<StatusKind, string> = {
  success: "bg-green-600 text-white",
  warning: "bg-yellow-600 text-white",
  error: "bg-red-600 text-white",
  info: "bg-blue-600 text-white",
  neutral: "bg-gray-600 text-white",
};
