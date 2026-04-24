'use client';

import { useEffect } from 'react';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Dashboard error:', error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center max-w-lg mx-auto p-8">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-900/30 border border-red-800 flex items-center justify-center">
          <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Something went wrong</h2>
        <p className="text-gray-400 text-sm mb-6">
          {error.message || 'An unexpected error occurred. The system is still operational.'}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-6 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-500 transition-colors"
          >
            Try Again
          </button>
          <a
            href="/dashboard"
            className="px-6 py-2.5 bg-gray-800 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors border border-gray-700"
          >
            Back to Dashboard
          </a>
        </div>
        {error.digest && (
          <p className="text-xs text-gray-600 mt-4 font-mono">Error ID: {error.digest}</p>
        )}
      </div>
    </div>
  );
}
