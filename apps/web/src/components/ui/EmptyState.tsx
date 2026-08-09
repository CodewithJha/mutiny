import type { ReactNode } from "react";

export function EmptyState({
  title,
  children,
  action,
  className = "",
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`empty-state ${className}`.trim()}>
      <h3>{title}</h3>
      {children ? <div>{children}</div> : null}
      {action}
    </div>
  );
}
