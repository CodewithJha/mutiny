"use client";

import { useEffect, useState } from "react";

export const MUTINY_GITHUB_URL = "https://github.com/CodewithJha/mutiny";
const GITHUB_API_URL = "https://api.github.com/repos/CodewithJha/mutiny";
const CACHE_KEY = "mutiny-gh-stars";
const CACHE_TTL_MS = 60 * 60 * 1000;

function formatStars(n: number): string {
  if (n >= 1000) {
    const k = n / 1000;
    return `${k >= 10 ? Math.round(k) : k.toFixed(1).replace(/\.0$/, "")}k`;
  }
  return String(n);
}

function readCachedStars(): number | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { count: number; at: number };
    if (
      typeof parsed.count !== "number" ||
      typeof parsed.at !== "number" ||
      Date.now() - parsed.at > CACHE_TTL_MS
    ) {
      return null;
    }
    return parsed.count;
  } catch {
    return null;
  }
}

function writeCachedStars(count: number) {
  try {
    sessionStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ count, at: Date.now() }),
    );
  } catch {
    /* ignore quota / private mode */
  }
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function useGitHubStars() {
  const [stars, setStars] = useState<number | null>(null);

  useEffect(() => {
    const cached = readCachedStars();
    if (cached != null) setStars(cached);

    let cancelled = false;
    fetch(GITHUB_API_URL, {
      headers: { Accept: "application/vnd.github+json" },
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data: { stargazers_count?: number }) => {
        if (cancelled) return;
        if (typeof data.stargazers_count === "number") {
          setStars(data.stargazers_count);
          writeCachedStars(data.stargazers_count);
        }
      })
      .catch(() => {
        /* keep cache / omit count */
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return stars;
}

/** Compact GitHub star control for landing sticky nav. */
export function GitHubStarLink() {
  const stars = useGitHubStars();
  const label =
    stars != null
      ? `Star Mutiny on GitHub (${formatStars(stars)} stars)`
      : "Star Mutiny on GitHub";

  return (
    <a
      href={MUTINY_GITHUB_URL}
      className="github-star"
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      title={label}
    >
      <GitHubIcon className="github-star-icon" />
      <span className="github-star-label">Star</span>
      {stars != null && (
        <span className="github-star-count" aria-hidden="true">
          {formatStars(stars)}
        </span>
      )}
    </a>
  );
}

/** Small sidebar footer link (icon + GitHub). */
export function GitHubFooterLink() {
  return (
    <a
      href={MUTINY_GITHUB_URL}
      className="sidebar-github"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Mutiny on GitHub"
    >
      <GitHubIcon className="sidebar-github-icon" />
      <span>GitHub</span>
    </a>
  );
}
