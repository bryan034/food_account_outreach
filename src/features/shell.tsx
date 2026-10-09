import { Link, useRouterState } from "@tanstack/react-router";
import {
  ArrowUpRight,
  ChevronRight,
  Compass,
  FlaskConical,
  Leaf,
  LockKeyhole,
  Menu,
  MessageSquare,
  Settings2,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "./workspace";
export function AppShell({ children }: { children: ReactNode }) {
  const { mode } = useWorkspace();
  const [open, setOpen] = useState(false);
  const path = useRouterState({ select: (s) => s.location.pathname });
  const items = [
    { to: "/" as const, label: "Discover", icon: Compass },
    { to: "/outreach" as const, label: "Outreach", icon: MessageSquare },
    { to: "/settings" as const, label: "Settings", icon: Settings2 },
  ];
  const current = items.find((i) => i.to === path)?.label || "Workspace";
  return (
    <div className="app-shell">
      {open && <div className="mobile-backdrop" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "mobile-open" : ""}`}>
        <Link to="/" className="brand" onClick={() => setOpen(false)}>
          <span className="brand-mark">
            <Leaf size={20} />
          </span>
          foodfolio<span className="text-primary">.</span>
        </Link>
        <div className="brand-sub">Good food. Great connections.</div>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {items.map((i) => (
            <Link
              key={i.label}
              to={i.to}
              onClick={() => setOpen(false)}
              className={`nav-item ${path === i.to ? "active" : ""}`}
            >
              <i.icon size={18} />
              {i.label}
              {path === i.to && <ChevronRight size={14} className="nav-arrow" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <strong>
              <LockKeyhole size={14} />
              Your workspace, your data
            </strong>
            Connected mode keeps your records in your own local backend.
          </div>
          <div className="creator">
            <div className="avatar">B</div>
            <div>
              <strong className="text-xs font-semibold">Bryan</strong>
              <small>Food creator · Singapore</small>
            </div>
            <ArrowUpRight size={14} className="ml-auto text-muted-foreground" />
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={12} />
            <strong>{current}</strong>
          </div>
          <div className="mobile-brand">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle navigation"
              className="menu-button"
              onClick={() => setOpen(!open)}
            >
              <Menu />
            </Button>
            foodfolio.
          </div>
          <div className="topbar-right">
            <span>Made for meaningful collaborations</span>
            <Link to="/settings" className="connection-pill">
              <span className="connection-dot" />
              {mode === "demo" ? "Demo workspace" : "Connected mode"}
            </Link>
          </div>
        </header>
        {mode === "demo" && (
          <div className="demo-banner">
            <FlaskConical size={13} />
            <strong>Demo — sample data</strong>
            <span className="demo-detail">
              Explore freely. No live requests or actual messages sent.
            </span>
            <Link to="/settings">
              Connection settings <span aria-hidden>↗</span>
            </Link>
          </div>
        )}
        <main>{children}</main>
      </div>
    </div>
  );
}
export function PageFooter() {
  const { mode } = useWorkspace();
  return (
    <footer className="page-footer">
      <span>Made for good food and genuine connections.</span>
      <span>{mode === "demo" ? "Sample workspace" : "Your local workspace"} · Singapore</span>
    </footer>
  );
}
