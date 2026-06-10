"use client";

import { useViewMode } from "@/providers/ViewModeProvider";

export default function ModeToggle() {
  const { mode, toggleMode } = useViewMode();

  return (
    <button
      className="mode-toggle"
      onClick={toggleMode}
      aria-label={`Switch to ${mode === "product" ? "dev" : "product"} mode`}
    >
      <span className={`mode-option ${mode === "product" ? "active" : ""}`}>
        Product
      </span>
      <span className={`mode-option ${mode === "dev" ? "active" : ""}`}>
        Dev
      </span>
    </button>
  );
}
