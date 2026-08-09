"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { mutinyApi, type Health } from "@/lib/api";

const NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/policies", label: "Policies" },
  { href: "/regressions", label: "Regressions" },
  { href: "/tests", label: "Tests" },
] as const;

/**
 * Landing `/` is chrome-free (story entry).
 * All operate routes get the workspace sidebar.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  if (isLanding) {
    return <>{children}</>;
  }

  return <OperateShell pathname={pathname}>{children}</OperateShell>;
}

function OperateShell({
  children,
  pathname,
}: {
  children: React.ReactNode;
  pathname: string;
}) {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      mutinyApi
        .health()
        .then((h) => {
          if (!cancelled) {
            setHealth(h);
            setHealthErr(null);
          }
        })
        .catch((e) => {
          if (!cancelled) {
            setHealth(null);
            setHealthErr(e instanceof Error ? e.message : "API unavailable");
          }
        });
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const apiOk = !healthErr && !!health?.api;

  return (
    <div className={`app-shell${navOpen ? " nav-open" : ""}`}>
      <header className="app-mobile-bar">
        <button
          type="button"
          className="btn btn-ghost btn-sm app-mobile-toggle"
          aria-expanded={navOpen}
          aria-controls="app-sidebar"
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? "Close" : "Menu"}
        </button>
        <Link href="/" className="app-mobile-brand">
          Mutiny
        </Link>
        <span className="app-mobile-status">
          <span
            className={`status-dot ${apiOk ? "status-dot-ok" : "status-dot-bad"}`}
          />
        </span>
      </header>

      {navOpen && (
        <button
          type="button"
          className="app-nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      )}

      <aside id="app-sidebar" className="app-sidebar">
        <Link href="/" className="app-sidebar-brand">
          <span className="brand-name">Mutiny</span>
          <span className="brand-tag">Behavioral fuzz engine</span>
        </Link>

        <div className="nav-section">
          <p className="nav-section-label">Workspace</p>
          {NAV.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${active ? " nav-link-active" : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="nav-section mt-2">
          <p className="nav-section-label">Story</p>
          <Link
            href="/"
            className={`nav-link${pathname === "/" ? " nav-link-active" : ""}`}
          >
            Landing
          </Link>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className="label">API</span>
            <span className="value">
              <span
                className={`status-dot ${
                  apiOk ? "status-dot-ok" : "status-dot-bad"
                }`}
              />
              {healthErr ? "down" : health?.status || "…"}
            </span>
          </div>
          {healthErr && (
            <p className="alert alert-error sidebar-health-error" title={healthErr}>
              {healthErr}
            </p>
          )}
          {health?.version != null && (
            <div className="sidebar-status">
              <span className="label">Version</span>
              <span className="value">{health.version}</span>
            </div>
          )}
          {health?.db != null && (
            <div className="sidebar-status">
              <span className="label">DB</span>
              <span className="value">
                <span
                  className={`status-dot ${
                    health.db ? "status-dot-ok" : "status-dot-bad"
                  }`}
                />
                {health.db ? "ok" : "down"}
              </span>
            </div>
          )}
        </div>
      </aside>

      <main className="app-main">{children}</main>
    </div>
  );
}
