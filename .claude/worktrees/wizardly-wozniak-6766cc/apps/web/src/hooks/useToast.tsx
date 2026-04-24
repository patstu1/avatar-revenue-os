'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import type { SystemEventPayload } from './useSystemEvents';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type ToastSeverity = 'info' | 'success' | 'warning' | 'error';

export type Toast = {
  id: string;
  title: string;
  description?: string;
  severity: ToastSeverity;
  /** Sticky toasts remain until manually dismissed */
  sticky?: boolean;
  /** Auto-dismiss duration in ms (default 5000) */
  duration?: number;
  createdAt: number;
};

type ToastContextValue = {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id' | 'createdAt'>) => void;
  dismissToast: (id: string) => void;
  /** Convenience: push a toast derived from a SystemEvent */
  pushEventToast: (event: SystemEventPayload) => void;
};

/* ------------------------------------------------------------------ */
/* Context                                                             */
/* ------------------------------------------------------------------ */

const ToastContext = createContext<ToastContextValue | null>(null);

let _nextId = 0;
function genId() {
  _nextId += 1;
  return `toast-${_nextId}-${Date.now()}`;
}

const DEFAULT_DURATION = 5_000;
const ERROR_DURATION = 0; // sticky

/* ------------------------------------------------------------------ */
/* Provider                                                            */
/* ------------------------------------------------------------------ */

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const addToast = useCallback(
    (partial: Omit<Toast, 'id' | 'createdAt'>) => {
      const id = genId();
      const toast: Toast = {
        ...partial,
        id,
        createdAt: Date.now(),
      };
      setToasts((prev) => [...prev, toast].slice(-20)); // cap at 20

      // Auto-dismiss unless sticky or severity is error
      const isSticky = partial.sticky || partial.severity === 'error';
      const duration = isSticky ? 0 : partial.duration ?? DEFAULT_DURATION;

      if (duration > 0) {
        const timer = setTimeout(() => dismissToast(id), duration);
        timers.current.set(id, timer);
      }
    },
    [dismissToast],
  );

  const pushEventToast = useCallback(
    (event: SystemEventPayload) => {
      const toast = eventToToast(event);
      if (toast) addToast(toast);
    },
    [addToast],
  );

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      timers.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, dismissToast, pushEventToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a <ToastProvider>');
  }
  return ctx;
}

/* ------------------------------------------------------------------ */
/* Event -> Toast mapping                                              */
/* ------------------------------------------------------------------ */

/**
 * Decides whether a SystemEvent warrants a user-visible toast,
 * and maps it to toast props. Returns null for events that
 * should be silent.
 */
function eventToToast(
  event: SystemEventPayload,
): Omit<Toast, 'id' | 'createdAt'> | null {
  const etype = event.event_type || '';
  const severity = event.event_severity || 'info';
  const summary = event.summary || etype;

  // Content published
  if (etype.includes('published') || (etype.includes('state_changed') && event.new_state === 'published')) {
    return {
      title: 'Content Published',
      description: summary,
      severity: 'success',
      duration: 5_000,
    };
  }

  // Revenue / monetization event
  if (event.event_domain === 'monetization') {
    return {
      title: 'Revenue Received',
      description: summary,
      severity: 'success',
      duration: 6_000,
    };
  }

  // Trend detected
  if (etype.includes('trend') || etype.includes('viral')) {
    return {
      title: 'Trend Detected',
      description: summary,
      severity: 'info',
      duration: 8_000,
    };
  }

  // Failures / errors
  if (severity === 'error' || severity === 'critical') {
    return {
      title: severity === 'critical' ? 'Critical Alert' : 'Error',
      description: summary,
      severity: 'error',
      sticky: true,
    };
  }

  // Warnings worth surfacing
  if (severity === 'warning') {
    return {
      title: 'Warning',
      description: summary,
      severity: 'warning',
      duration: 7_000,
    };
  }

  // Job failures
  if (etype.includes('failed')) {
    return {
      title: 'Job Failed',
      description: summary,
      severity: 'error',
      sticky: true,
    };
  }

  // Everything else: no toast
  return null;
}

/* ------------------------------------------------------------------ */
/* Toast UI                                                            */
/* ------------------------------------------------------------------ */

const severityStyles: Record<ToastSeverity, { bg: string; border: string; text: string; icon: string }> = {
  info: {
    bg: 'bg-gray-900/95',
    border: 'border-cyan-500/40',
    text: 'text-cyan-300',
    icon: 'i',
  },
  success: {
    bg: 'bg-gray-900/95',
    border: 'border-emerald-500/40',
    text: 'text-emerald-300',
    icon: '\u2713',
  },
  warning: {
    bg: 'bg-gray-900/95',
    border: 'border-yellow-500/40',
    text: 'text-yellow-300',
    icon: '\u26A0',
  },
  error: {
    bg: 'bg-gray-900/95',
    border: 'border-red-500/40',
    text: 'text-red-300',
    icon: '\u2717',
  },
};

function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[9999] flex flex-col-reverse gap-2 max-w-sm w-full pointer-events-none"
      aria-live="polite"
    >
      {toasts.map((t) => {
        const style = severityStyles[t.severity];
        return (
          <div
            key={t.id}
            className={`
              pointer-events-auto
              ${style.bg} ${style.border} border
              rounded-lg px-4 py-3 shadow-xl shadow-black/30
              animate-in slide-in-from-right duration-300
            `}
            role="alert"
          >
            <div className="flex items-start gap-3">
              <span className={`text-lg ${style.text} shrink-0 mt-0.5`}>
                {style.icon}
              </span>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-semibold ${style.text}`}>{t.title}</p>
                {t.description && (
                  <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{t.description}</p>
                )}
              </div>
              <button
                onClick={() => onDismiss(t.id)}
                className="text-gray-500 hover:text-gray-300 transition text-sm shrink-0 ml-2"
                aria-label="Dismiss"
              >
                \u2715
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
