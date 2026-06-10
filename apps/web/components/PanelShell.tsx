import React from "react";

interface PanelShellProps {
  title: string;
  children: React.ReactNode;
  hasData?: boolean;
}

/**
 * Shared panel wrapper with header and "No data" fallback.
 */
export default function PanelShell({
  title,
  children,
  hasData = true,
}: PanelShellProps) {
  return (
    <div className="panel">
      <div className="panel-header">{title}</div>
      {hasData ? children : <p className="no-data">No data</p>}
    </div>
  );
}
