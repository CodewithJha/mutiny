import type { ReactNode } from "react";

export function Panel({
  children,
  className = "",
  raised = false,
}: {
  children: ReactNode;
  className?: string;
  raised?: boolean;
}) {
  return (
    <div className={`${raised ? "panel-raised" : "panel"} ${className}`.trim()}>
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  actions,
}: {
  title: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="panel-header">
      <h2 className="panel-title">{title}</h2>
      {actions ? <div className="action-bar">{actions}</div> : null}
    </div>
  );
}

export function PanelBody({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`panel-body ${className}`.trim()}>{children}</div>;
}
