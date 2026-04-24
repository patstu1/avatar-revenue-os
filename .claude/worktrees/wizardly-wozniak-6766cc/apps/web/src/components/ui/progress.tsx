import * as React from 'react';

export function Progress({ value = 0, className = '', ...props }: React.HTMLAttributes<HTMLDivElement> & { value?: number }) {
  return (
    <div className={`relative h-2 w-full overflow-hidden rounded-full bg-gray-800 ${className}`} {...props}>
      <div className="h-full bg-brand-500 transition-all" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}
