"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DEFAULT_PROJECT_PATH, mutinyApi } from "@/lib/api";
import { GitHubStarLink } from "@/components/GitHubStarLink";
import { Button, CopyButton } from "@/components/ui";

const JOURNEY: { label: string; detail: string; tone?: "pass" | "fail" }[] = [
  { label: "Install", detail: "pip + init" },
  { label: "Define Rules", detail: "policy.yaml" },
  { label: "Run Campaign", detail: "evolve prompts" },
  { label: "Find Violation", detail: "tool call breaks", tone: "fail" },
  { label: "Save Regression", detail: "freeze FAIL" },
  { label: "Fix Agent", detail: "clamp / refuse" },
  { label: "Run Tests", detail: "mutiny test" },
  { label: "PASS", detail: "suite green", tone: "pass" },
];

const INSTALL_CMDS = [
  {
    id: "install",
    title: "Install",
    command: "pip install mutiny-ai",
    hint: "PyPI package mutiny-ai. CLI command is mutiny.",
  },
  {
    id: "init",
    title: "Scaffold",
    command: "mutiny init",
    hint: "Creates .mutiny/adapter.py · policy.yaml · mutiny.yaml",
  },
  {
    id: "run",
    title: "Hunt",
    command: "mutiny run",
    hint: "Evolve prompts until a verified violation",
  },
  {
    id: "test",
    title: "Replay",
    command: "mutiny test",
    hint: "FAIL until the agent is fixed — then PASS",
  },
] as const;

const PREVIEW_STEPS = [
  { id: "policy", label: "Policy", detail: "refund_limit ≤ 100" },
  { id: "search", label: "Search", detail: "gen 1–4 evolving" },
  { id: "violation", label: "Violation", detail: "amount: 250", tone: "fail" as const },
  { id: "evidence", label: "Evidence", detail: "tool JSON verified" },
  { id: "regress", label: "Regression", detail: "minimized · saved" },
  { id: "pass", label: "PASS", detail: "suite green", tone: "pass" as const },
];

const FAIL_PROOF = `{
  "tool": "issue_refund",
  "args": { "amount": 250.0, "order_id": "ord_9182" },
  "policy": { "rule": "refund_limit", "max": 100 },
  "status": "FAIL",
  "verified": true,
  "generation": 4,
  "fitness": 0.98
}`;

const PASS_PROOF = `{
  "tool": "issue_refund",
  "args": { "amount": 75.0, "order_id": "ord_9182" },
  "policy": { "rule": "refund_limit", "max": 100 },
  "status": "PASS",
  "verified": true,
  "suite": "refund_limit"
}`;

export default function HomePage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attest, setAttest] = useState(false);
  const [previewStep, setPreviewStep] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setPreviewStep((s) => (s + 1) % PREVIEW_STEPS.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, []);

  async function runCampaign() {
    setError(null);
    if (!attest) {
      setError("Check attestation — authorized testing only.");
      return;
    }
    setBusy(true);
    try {
      const camp = await mutinyApi.createCampaign({
        population_size: 8,
        max_generations: 6,
        elite_count: 2,
        stop_on_first_violation: true,
        max_turns: 4,
        rng_seed: 5,
        use_boundary_seeds: true,
        target: "openai_agents",
        project_path: DEFAULT_PROJECT_PATH,
      });
      await mutinyApi.startCampaign(camp.id, true);
      router.push(`/campaign/${camp.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  const active = PREVIEW_STEPS[previewStep];
  const showFail = active.id === "violation" || active.id === "evidence";
  const showPass = active.id === "pass";

  return (
    <div className="landing">
      <div className="landing-atmosphere" aria-hidden>
        <div className="landing-orb landing-orb-a" />
        <div className="landing-orb landing-orb-b" />
      </div>

      <header className="landing-nav">
        <a href="#top" className="landing-brand">
          Mutiny
        </a>
        <nav className="landing-nav-links" aria-label="On this page">
          <a href="#journey">Journey</a>
          <a href="#install">Install</a>
          <a href="#demo">Demo</a>
          <a href="#proof">Proof</a>
        </nav>
        <div className="landing-nav-cta">
          <GitHubStarLink />
          <Link href="/campaigns" className="landing-dash-link">
            Campaigns
          </Link>
          <Link href="/projects" className="landing-dash-link">
            Projects
          </Link>
          <a href="#run" className="btn btn-gold btn-sm">
            Run demo
          </a>
        </div>
      </header>

      <main id="top">
        <section className="landing-hero landing-hero-split">
          <div className="landing-hero-copy">
            <p className="landing-brand-mark reveal">Mutiny</p>
            <h1 className="headline reveal reveal-delay-1">
              Break your agent&apos;s rules.
              <br />
              Prove it. Lock the fix.
            </h1>
            <p className="lede reveal reveal-delay-2">
              Behavioral fuzz testing for AI agents — evolutionary search finds
              tool-call policy violations, then freezes them as regressions you
              replay until they PASS.
            </p>

            <div className="landing-cta reveal reveal-delay-3">
              <a href="#run" className="btn btn-gold btn-lg">
                Try on your agent
              </a>
              <a href="#install" className="btn btn-secondary btn-lg">
                Install locally
              </a>
            </div>

            <p className="landing-hero-meta">
              Fuzz tool-use policies · Evolve → verify on trace · Permanent
              FAIL→PASS regressions
            </p>
          </div>

          <div
            className="landing-hero-preview reveal reveal-delay-2"
            aria-label="Product preview"
          >
            <article className="product-plane product-plane-live">
              <div className="product-plane-bar">
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-title">Campaign · live</span>
                <span
                  className={`story-badge ${
                    showPass
                      ? "story-badge-pass"
                      : showFail
                        ? "story-badge-fail"
                        : "story-badge-live"
                  }`}
                >
                  {showPass ? "PASS" : showFail ? "FAIL" : "SEARCH"}
                </span>
              </div>
              <div className="product-plane-body landing-preview-body">
                <aside className="product-plane-side">
                  {PREVIEW_STEPS.map((step, i) => (
                    <span
                      key={step.id}
                      className={`nav-fake${
                        i === previewStep ? " active" : ""
                      }${step.tone === "fail" ? " tone-fail" : ""}${
                        step.tone === "pass" ? " tone-pass" : ""
                      }`}
                    >
                      {step.label}
                    </span>
                  ))}
                </aside>
                <div className="product-plane-main">
                  <div className="product-issue-meta">
                    {showFail && (
                      <span className="chip chip-violation">
                        Verified violation
                      </span>
                    )}
                    {showPass && (
                      <span className="chip chip-success">Regression PASS</span>
                    )}
                    {!showFail && !showPass && (
                      <span className="chip chip-blue">
                        <span className="pulse-dot" /> searching
                      </span>
                    )}
                    <span className="chip chip-amber">{active.detail}</span>
                  </div>
                  <h3 className="product-issue-title mt-3">
                    {showPass
                      ? "Cap held — suite green"
                      : showFail
                        ? "Break found — refund exceeded"
                        : active.label === "Policy"
                          ? "Policy loaded — refund_limit"
                          : `${active.label} in progress`}
                  </h3>
                  <pre
                    className={`product-stack ${
                      showPass
                        ? "story-stack-pass"
                        : showFail
                          ? "story-stack-fail"
                          : ""
                    }`}
                  >
                    {showPass ? (
                      <>
                        <span className="dim">tool.call</span>{" "}
                        <span className="hl-pass">issue_refund</span>
                        {"\n"}
                        <span className="dim">args.amount</span>{" "}
                        <span className="hl-pass">75.00</span>
                        {"\n"}
                        <span className="dim">status</span>{" "}
                        <span className="hl-pass">PASS · verified</span>
                      </>
                    ) : showFail ? (
                      <>
                        <span className="dim">tool.call</span>{" "}
                        <span className="hl">issue_refund</span>
                        {"\n"}
                        <span className="dim">args.amount</span>{" "}
                        <span className="hl">250.00</span>
                        {"\n"}
                        <span className="dim">policy</span> max ≤ 100
                        {"\n"}
                        <span className="dim">status</span>{" "}
                        <span className="hl">FAIL · verified</span>
                      </>
                    ) : (
                      <>
                        <span className="dim">policy.rule</span> refund_limit
                        {"\n"}
                        <span className="dim">phase</span> {active.detail}
                        {"\n"}
                        <span className="dim">fitness</span> rising…
                      </>
                    )}
                  </pre>
                  <ol className="preview-rail" aria-hidden>
                    {PREVIEW_STEPS.map((step, i) => (
                      <li
                        key={step.id}
                        className={`${i === previewStep ? "is-active" : ""} ${
                          i < previewStep ? "is-done" : ""
                        } ${step.tone === "fail" ? "is-fail" : ""} ${
                          step.tone === "pass" ? "is-pass" : ""
                        }`}
                      />
                    ))}
                  </ol>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          id="journey"
          className="landing-section"
          aria-labelledby="journey-title"
        >
          <h2 id="journey-title" className="landing-section-title">
            The path to PASS
          </h2>
          <p className="landing-section-lede">
            One continuous loop — install, define boundaries, hunt the break,
            freeze it, fix the agent, watch green.
          </p>

          <ol className="journey-rail" aria-label="Mutiny journey">
            {JOURNEY.map((step, i) => (
              <li
                key={step.label}
                className={`journey-rail-step${
                  step.tone === "pass"
                    ? " is-pass"
                    : step.tone === "fail"
                      ? " is-fail"
                      : ""
                }`}
              >
                <span className="journey-rail-index" aria-hidden>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="journey-rail-label">{step.label}</span>
                <span className="journey-rail-detail">{step.detail}</span>
              </li>
            ))}
          </ol>
        </section>

        <section
          id="install"
          className="landing-section"
          aria-labelledby="install-title"
        >
          <h2 id="install-title" className="landing-section-title">
            Install
          </h2>
          <p className="landing-section-lede">
            Install into your agent project, then scaffold and run. Mutiny stays
            outside the agent — your tools stay sandboxed.
          </p>

          <div className="terminal-premium">
            <div className="terminal-premium-bar">
              <span className="product-plane-dot" />
              <span className="product-plane-dot" />
              <span className="product-plane-dot" />
              <span className="terminal-premium-title">terminal · mutiny</span>
            </div>
            <div className="terminal-premium-body">
              {INSTALL_CMDS.map((item, i) => (
                <div key={item.id} className="terminal-line-group">
                  <div className="terminal-line-head">
                    <span className="terminal-step">
                      {String(i + 1).padStart(2, "0")} · {item.title}
                    </span>
                    <CopyButton text={item.command} />
                  </div>
                  <pre className="terminal-cmd">
                    <span className="cmd">$</span> {item.command}
                  </pre>
                  <p className="terminal-hint">{item.hint}</p>
                </div>
              ))}
            </div>
          </div>

          <figure className="code-well install-policy-well">
            <figcaption>
              <span>policy.yaml · example</span>
              <CopyButton
                text={`rules:
  - id: refund_limit
    tool: issue_refund
    assert:
      amount: { lte: 100 }`}
              />
            </figcaption>
            <pre>{`rules:
  - id: refund_limit
    tool: issue_refund
    assert:
      amount: { lte: 100 }`}</pre>
          </figure>
        </section>

        <section
          id="implement"
          className="landing-section landing-section-tight"
          aria-labelledby="implement-title"
        >
          <h2 id="implement-title" className="landing-section-title">
            Wire your agent
          </h2>
          <p className="landing-section-lede">
            Point the adapter at your OpenAI Agents SDK project. Mutiny talks
            to the adapter layer — not your production tools.
          </p>

          <ol className="wire-steps">
            <li>
              <strong>Open</strong> <code>.mutiny/adapter.py</code> and import
              your agent runner.
            </li>
            <li>
              <strong>Expose</strong> tool calls so the oracle can score args
              against <code>policy.yaml</code>.
            </li>
            <li>
              <strong>Run</strong> <code>mutiny run</code> locally — or open{" "}
              <Link href="/campaigns">Campaigns</Link> to watch lineage on the
              sample harness.
            </li>
          </ol>
        </section>

        <section
          id="demo"
          className="landing-section"
          aria-labelledby="demo-title"
        >
          <h2 id="demo-title" className="landing-section-title">
            Sample run story
          </h2>
          <p className="landing-section-lede">
            Same policy. Same suite. Before the fix it burns red. After the
            fix — green. That&apos;s the product.
          </p>

          <div className="story-compare">
            <article className="product-plane story-panel story-panel-fail">
              <div className="product-plane-bar">
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-title">
                  mutiny test · BEFORE
                </span>
                <span className="story-badge story-badge-fail">FAIL</span>
              </div>
              <div className="product-plane-body story-panel-body">
                <aside className="product-plane-side">
                  <span className="nav-fake active">Live run</span>
                  <span className="nav-fake">Evidence</span>
                  <span className="nav-fake">Minimize</span>
                </aside>
                <div className="product-plane-main">
                  <div className="product-issue-meta">
                    <span className="chip chip-violation">
                      Verified violation
                    </span>
                    <span className="chip chip-amber">gen 4</span>
                  </div>
                  <h3 className="product-issue-title mt-3">
                    Break found — refund exceeded policy cap
                  </h3>
                  <pre className="product-stack story-stack-fail">
                    <span className="dim">tool.call</span>{" "}
                    <span className="hl">issue_refund</span>
                    {"\n"}
                    <span className="dim">args.amount</span>{" "}
                    <span className="hl">250.00</span>
                    {"\n"}
                    <span className="dim">status</span>{" "}
                    <span className="hl">FAIL · verified</span>
                  </pre>
                </div>
              </div>
            </article>

            <div className="story-compare-bridge" aria-hidden>
              <span className="story-compare-fix">fix agent · re-run suite</span>
              <span className="story-compare-arrow">↓</span>
            </div>

            <article className="product-plane story-panel story-panel-pass">
              <div className="product-plane-bar">
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-dot" />
                <span className="product-plane-title">
                  mutiny test · AFTER
                </span>
                <span className="story-badge story-badge-pass">PASS</span>
              </div>
              <div className="product-plane-body story-panel-body">
                <aside className="product-plane-side">
                  <span className="nav-fake">Live run</span>
                  <span className="nav-fake">Evidence</span>
                  <span className="nav-fake active">Suite</span>
                </aside>
                <div className="product-plane-main">
                  <div className="product-issue-meta">
                    <span className="chip chip-success">Regression PASS</span>
                  </div>
                  <h3 className="product-issue-title mt-3">
                    Cap held — refund stays inside policy
                  </h3>
                  <pre className="product-stack story-stack-pass">
                    <span className="dim">tool.call</span>{" "}
                    <span className="hl-pass">issue_refund</span>
                    {"\n"}
                    <span className="dim">args.amount</span>{" "}
                    <span className="hl-pass">75.00</span>
                    {"\n"}
                    <span className="dim">status</span>{" "}
                    <span className="hl-pass">PASS · verified</span>
                  </pre>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          id="proof"
          className="landing-section landing-section-close"
          aria-labelledby="proof-title"
        >
          <h2 id="proof-title" className="landing-section-title">
            Proof, not vibes
          </h2>
          <p className="landing-section-lede">
            Every break ships with tool-call JSON you can read, minimize, and
            replay. No LLM judge guessing whether it broke.
          </p>

          <div className="proof-split">
            <figure className="code-well code-well-fail">
              <figcaption>
                <span className="story-badge story-badge-fail">FAIL</span>
                Verified violation evidence
                <CopyButton text={FAIL_PROOF} className="ml-auto" />
              </figcaption>
              <pre>{FAIL_PROOF}</pre>
            </figure>
            <figure className="code-well code-well-pass">
              <figcaption>
                <span className="story-badge story-badge-pass">PASS</span>
                Same suite after the fix
                <CopyButton text={PASS_PROOF} className="ml-auto" />
              </figcaption>
              <pre>{PASS_PROOF}</pre>
            </figure>
          </div>
        </section>

        <section
          id="run"
          className="landing-footer-cta"
          aria-labelledby="cta-title"
        >
          <div className="landing-footer-cta-inner">
            <h2 id="cta-title">Your turn. Run the campaign.</h2>
            <p>
              Start a hosted sample campaign and watch the FAIL land with
              deterministic tool-call proof — then freeze it as a regression.
            </p>
            <div className="landing-cta">
              <Button
                variant="gold"
                size="lg"
                disabled={busy}
                onClick={runCampaign}
              >
                {busy ? "Starting…" : "Run Campaign"}
              </Button>
              <Link href="/campaigns" className="btn btn-secondary btn-lg">
                Open Campaigns
              </Link>
            </div>

            <label className="checkbox-row landing-attest">
              <input
                type="checkbox"
                checked={attest}
                onChange={(e) => setAttest(e.target.checked)}
              />
              <span>
                I attest this campaign targets only systems I am authorized to
                test (sample / owned agents).
              </span>
            </label>

            {error && (
              <p className="alert alert-error mt-6 mx-auto max-w-lg">{error}</p>
            )}
          </div>

          <nav className="landing-footer-links" aria-label="Operate">
            <Link href="/projects">Projects</Link>
            <Link href="/campaigns">Campaigns</Link>
            <Link href="/policies">Policies</Link>
            <Link href="/tests">Tests</Link>
            <Link href="/regressions">Regressions</Link>
          </nav>
        </section>
      </main>
    </div>
  );
}
