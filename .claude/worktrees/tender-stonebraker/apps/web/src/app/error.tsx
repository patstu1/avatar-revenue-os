'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="text-center max-w-md">
        <h1 className="text-3xl font-bold text-white mb-4">System Error</h1>
        <p className="text-gray-400 mb-6">{error.message || 'Something unexpected happened.'}</p>
        <button
          onClick={reset}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-500 transition-colors"
        >
          Reload
        </button>
      </div>
    </div>
  );
}
