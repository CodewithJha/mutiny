# Design

<!-- impeccable:design-schema 1 -->

## World

**Canon:** Mutiny Hosted — Sentry-inspired purple-black operate + marketing language refined into a cohesive Mutiny identity (not a clone). Rubik UI + IBM Plex Mono data. Gold CTA gradient on marketing; blurple primary in the app. Pink accent for selection / focus; red for verified violations; lime for PASS.

Landing `/` is Persuade (story entry). Operate routes (Projects, Campaigns, Policies, Regressions, Tests, Campaign detail, Exploit) share one sidebar shell.

## Color strategy

| Token | Hex | Role |
|-------|-----|------|
| `--bg` | `#1F1633` | Page / marketing ground |
| `--bg-elevated` | `#181225` | Sidebar / elevated ground |
| `--surface` | `#2D1B57` | Panels |
| `--raised` | `#362D59` | Raised / hover panels |
| `--inset` | `#150F23` | Code wells, timeline, graph |
| `--primary` | `#6A5FC1` | Blurple — app primary |
| `--pink` | `#FD44B0` | Hot accent / focus |
| `--gold-from` → `--gold-to` | `#FFB287` → `#FEDB4B` | Marketing CTA gradient |
| `--blue` | `#7553FF` | Live / searching |
| `--amber` | `#F2B712` | Near-miss / warning |
| `--violation` | `#E1567C` | Verified violation / FAIL |
| `--success` | `#C2EF4E` | PASS |
| `--muted` | `#9093C1` | Secondary labels |
| `--text` | `#F5F3FA` | Primary text |
| `--border` | `rgba(144,147,193,0.18)` | Hairlines |

**Atmosphere (landing):** purple descent gradient + pink/blurple orbs + CSS noise.

## Typography

| Role | Face | Spec |
|------|------|------|
| UI / display | Rubik 400–800 | Hero `clamp(3.1rem, 8vw, 5.5rem)` · weight 500–600 |
| Code / data | IBM Plex Mono 400–600 | 11–13px in wells |
| CTA | Rubik 700 | Uppercase · tracked on large buttons |

## Spacing & craft

- 8px rhythm; radius 8–10px
- Sticky translucent landing nav; compact ~220–240px sidebar
- Motion: fade-up reveals, CTA gradient shift (~200ms), intentional pulse on FAIL→PASS bridge
- Copy affordance on every install / proof command
- Tables Linear-dense; evidence inspector above the fold on campaign detail

## Components

`apps/web/src/app/globals.css` + `apps/web/src/components/ui/`:

Button, Chip, Panel, CodeBlock/JsonBlock (IDE well + Copy), CopyButton, EmptyState, Skeleton, Timeline, Collapsible.

Shell: `AppShell` — landing bypass; operate sidebar with Workspace + Story links + API health.

## Modes

| Route | Mode |
|-------|------|
| `/` | Persuade — hero → journey → install → wire → FAIL→PASS → proof → Run Campaign |
| `/projects`, `/campaigns`, `/policies`, `/tests`, `/regressions`, `/campaign/[id]`, `/exploit/*` | Operate |

## Campaign = evidence hero

Story order: Policy → Campaign → Evolution → Verified Violation → Tool Call → Evidence → Minimize → Regression → Test History.

Layout: status + meta strip → evolution graph + inspector → collapsible live events.

## Responsive

- ≤960px: mobile top bar + slide-over sidebar; single-column campaign + install grids
- ≤640px: stacked CTAs; journey rail vertical; meta strip 2-col
- ≥1440px: wider page-wide + slightly wider sidebar
