"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { ViewMode } from "@/lib/types";

interface ViewModeContextValue {
  mode: ViewMode;
  toggleMode: () => void;
}

const ViewModeContext = createContext<ViewModeContextValue>({
  mode: "product",
  toggleMode: () => {},
});

export function useViewMode() {
  return useContext(ViewModeContext);
}

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ViewMode>("product");

  const toggleMode = () => {
    setMode((prev) => (prev === "product" ? "dev" : "product"));
  };

  return (
    <ViewModeContext.Provider value={{ mode, toggleMode }}>
      {children}
    </ViewModeContext.Provider>
  );
}
