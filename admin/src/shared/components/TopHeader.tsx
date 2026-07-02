import { type ReactNode } from 'react';

interface TopHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function TopHeader({ title, subtitle, actions }: TopHeaderProps) {
  return (
    <div className="sticky top-0 z-30 border-b border-border bg-bg-card/95 px-4 py-4 backdrop-blur-sm sm:px-6 md:px-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-main sm:text-2xl" style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif" }}>{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-text-muted">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}