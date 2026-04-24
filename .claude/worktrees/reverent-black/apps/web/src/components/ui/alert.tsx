import * as React from 'react';

export function Alert({ className = '', children, variant = 'default', ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: string }) {
  const variants: Record<string, string> = {
    default: 'border-gray-700 bg-gray-900/50 text-gray-200',
    destructive: 'border-red-900/50 bg-red-950/30 text-red-300',
  };
  return <div role="alert" className={`relative w-full rounded-lg border p-4 ${variants[variant] || variants.default} ${className}`} {...props}>{children}</div>;
}

export function AlertTitle({ className = '', children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={`mb-1 font-medium leading-none tracking-tight ${className}`} {...props}>{children}</h5>;
}

export function AlertDescription({ className = '', children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <div className={`text-sm opacity-90 ${className}`} {...props}>{children}</div>;
}
