import * as React from 'react';

export function Button({ className = '', children, variant = 'default', size = 'default', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string; size?: string }) {
  const base = 'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50';
  const variants: Record<string, string> = {
    default: 'bg-brand-500 text-white hover:bg-brand-600',
    destructive: 'bg-red-600 text-white hover:bg-red-700',
    outline: 'border border-gray-700 bg-transparent hover:bg-gray-800 text-gray-200',
    secondary: 'bg-gray-800 text-gray-200 hover:bg-gray-700',
    ghost: 'hover:bg-gray-800 text-gray-200',
    link: 'text-brand-400 underline-offset-4 hover:underline',
  };
  const sizes: Record<string, string> = {
    default: 'h-10 px-4 py-2',
    sm: 'h-9 rounded-md px-3',
    lg: 'h-11 rounded-md px-8',
    icon: 'h-10 w-10',
  };
  return <button className={`${base} ${variants[variant] || variants.default} ${sizes[size] || sizes.default} ${className}`} {...props}>{children}</button>;
}
