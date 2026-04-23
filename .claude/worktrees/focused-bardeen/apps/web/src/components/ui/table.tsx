import * as React from 'react';

export function Table({ className = '', children, ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return <div className="relative w-full overflow-auto"><table className={`w-full caption-bottom text-sm ${className}`} {...props}>{children}</table></div>;
}

export function TableHeader({ className = '', children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`border-b border-gray-800 ${className}`} {...props}>{children}</thead>;
}

export function TableBody({ className = '', children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={`${className}`} {...props}>{children}</tbody>;
}

export function TableRow({ className = '', children, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={`border-b border-gray-800/50 transition-colors hover:bg-gray-800/30 ${className}`} {...props}>{children}</tr>;
}

export function TableHead({ className = '', children, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={`h-10 px-2 text-left align-middle font-medium text-gray-400 ${className}`} {...props}>{children}</th>;
}

export function TableCell({ className = '', children, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`p-2 align-middle text-gray-200 ${className}`} {...props}>{children}</td>;
}
