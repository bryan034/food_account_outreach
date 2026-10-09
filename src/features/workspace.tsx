import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createApiClient } from "@/lib/api/client";
import { createDemoClient } from "@/lib/api/demo";
import type { ApiClient } from "@/lib/api/types";
type Mode = "demo" | "connected";
interface Workspace {
  mode: Mode;
  base: string;
  api: ApiClient;
  configure: (mode: Mode, base: string) => void;
}
const Context = createContext<Workspace | null>(null);
const defaultBase = import.meta.env["VITE_API_BASE_URL"] || "http://localhost:8000";
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("demo");
  const [base, setBase] = useState(defaultBase);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("foodfolio-config") || "null");
      if (saved?.base) setBase(saved.base);
      if (saved?.mode === "connected") setMode("connected");
    } catch {
      /* default to isolated demo */
    }
  }, []);
  const api = useMemo(
    () => (mode === "demo" ? createDemoClient() : createApiClient(base)),
    [mode, base],
  );
  const configure = (next: Mode, url: string) => {
    setMode(next);
    setBase(url);
    localStorage.setItem("foodfolio-config", JSON.stringify({ mode: next, base: url }));
  };
  return <Context.Provider value={{ mode, base, api, configure }}>{children}</Context.Provider>;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("Workspace provider is required");
  return value;
}
