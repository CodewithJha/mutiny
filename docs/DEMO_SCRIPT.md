# Mutiny — Demo Script

| Field | Value |
|---|---|
| **Status** | Canonical demo playbook |
| **Last updated** | 2026-08-07 |
| **Product surface** | Sample agent project → `mutiny init` → `mutiny run` (MVP via OpenAI Agents SDK adapter); Hosted UI secondary for lineage |

Do not invent a different demo narrative in README or slides without updating this file.

**Honesty:** Until M2–M4 land, live demos may use the interim bundled harness. Say so explicitly (“sample / reference agent”) — do **not** pitch “our vulnerable demo agent” as the product. Do **not** pitch Mutiny as “an OpenAI Agents SDK testing tool.”

**Opening pitch:** Mutiny is a behavioral fuzz-testing engine for AI agents. The Hackathon MVP ships with support for OpenAI Agents SDK projects through the first adapter.

---

## 0. Preconditions (T−30 min)

- [ ] Sample agent project ready (MVP: OpenAI Agents SDK; or interim demo labeled as sample)  
- [ ] `mutiny init` / `mutiny run` available **or** Hosted backup path rehearsed and labeled  
- [ ] `GET /api/health` green if showing Hosted (API, DB, model probe)  
- [ ] Smoke: `scripts/smoke_reliability.py` → `SMOKE GATE PASSED` (≥2/3 on pin) when using harness  
- [ ] Pinned config matches [`config/demo_pin.json`](../config/demo_pin.json) when applicable  
- [ ] Browser ready for Hosted lineage (optional beat)  
- [ ] Backup path verified: `scripts/backup_fixture_demo.py` → `BACKUP FIXTURE PATH OK`  
- [ ] Agent “fix” patch ready (remove APR trust / enforce approval server-side)  
- [ ] Authorization / safety messaging known  

**Nuclear options:** guided/template pin; smaller N/G; Hosted against sample; fixture backup / video.

---

## 1. Two-minute version (default)

**Spine:** clone sample → init → run → prove → Hosted lineage → regress.

| Time | Say | Show |
|---|---|---|
| 0:00–0:15 | “Agents don’t just chat—they call tools that move money. Prompts aren’t tests.” | Sample project tree |
| 0:15–0:30 | “Mutiny is a behavioral fuzz-testing engine. You install it into *your* agent project.” | `pip install mutiny` → `mutiny init` artifacts |
| 0:30–0:45 | “You connect via an adapter and declare invariants—e.g. refunds over $200 need approval. MVP adapter: OpenAI Agents SDK.” | `.mutiny/adapter.py` + `policy.yaml` / `refund_limit` |
| 0:45–1:05 | “`mutiny run` fuzzes your agent against those invariants.” | Campaign progress (CLI or Hosted) |
| 1:05–1:20 | “Violation—deterministic proof from the tool call.” | `issue_refund(amount=…, approved=false)` + rule id |
| 1:20–1:35 | “Lineage from seed to exploit.” | Hosted graph or CLI parent trail |
| 1:35–1:50 | “Minimize, save regression. Before fix: fail. After fix: pass.” | Minimize → FAIL → patch → PASS |
| 1:50–2:00 | “Mutiny doesn’t ask if it looks safe—it proves where *your* policy breaks and locks the fix.” | Closing frame |

**Timing checklist**

- [ ] Rehearsal 1 ≤2:00  
- [ ] Rehearsal 2 ≤2:00  
- [ ] Rehearsal 3 ≤2:00  

---

## 2. Five-minute version

Use the 2-minute spine, then deepen:

1. **Problem (45s):** tool-call failures as software defects in *shipped* agents.  
2. **Install path (45s):** engine + adapter layer; Hackathon Adapter #1 = OpenAI Agents SDK; future adapters same Core.  
3. **Principles (30s):** AI proposes; code proves.  
4. **Live campaign (2:00):** init → run → violation.  
5. **Hosted lineage (30s):** optional.  
6. **Related work (30s):** credit Promptfoo/Garak; state wedge (engine, not framework lock-in).  
7. **Q&A buffer.**  

---

## 3. Technical judge version (deep dive)

Audience: engineers who will poke holes.

1. Show adapter boundary: Core never imports the app or framework SDK; OpenAI Agents SDK adapter maps tool calls.  
2. Show **PolicyEvaluator** unit test or pure function on a fixture trace.  
3. Show a **near-miss** vs **violation** fitness distinction.  
4. Open raw **ExecutionTrace** JSON.  
5. Run minimize; show a rejected shortening that fails re-exec.  
6. Explain trust boundaries: local project / localhost; authorized use.  
7. Honest competitor answer (see §6).  
8. Optional: CLI `mutiny test` as same Core replay path.  

Avoid: claiming LangGraph/CrewAI support today; MCP setup; cloud multi-tenant claims; “the product is our demo agent”; “Mutiny is an OpenAI Agents SDK tool.”

---

## 4. Backup demo

If live search or CLI path fails:

1. Play screen recording of a green campaign (same thesis).  
2. State clearly it is a recording; then switch live to **minimize/replay** if possible on a stored violator.  
3. If no stored violator, walk fixture trace + unit oracle + regression replay against a known failing conversation checked into `examples/`.  
4. Never paste a fake violation row.  
5. If only Hosted+demo harness works: call it a **sample reference agent**, then pivot narrative to “same engine loop on your agent project via adapter.”

---

## 5. Failure recovery cheat sheet

| Symptom | Action |
|---|---|
| No violation by gen 3 | Guided mode / soften sample agent; restart |
| `mutiny init` not shipped | Show hand-authored sample artifacts; label WIP |
| Model errors | Fallback Ollama/templates; or recording |
| UI SSE stall | Refresh; rely on candidates snapshot |
| Demo too slow | Lower N/G; jump to pre-warmed campaign |
| Judge says “hardcoded” | Show lineage + near-misses + seed ≠ final |
| Judge says “just your demo agent?” | Agree sample is a harness; product = engine + adapter into *their* project |
| Judge says “Promptfoo?” | Agree on overlap; show search+oracle+minimize + install path |
| Judge says “only OpenAI Agents SDK?” | Agree MVP Adapter #1; Core is framework-neutral; more adapters on roadmap |

---

## 6. Q&A cheat sheet

| Question | Answer |
|---|---|
| vs Promptfoo? | Strong overlap on policies/trajectories/CI. Mutiny productizes evolutionary search + deterministic tool oracle + minimize→regress as an installable engine. |
| vs Garak Agent Breaker? | They attack tools well. We center user invariants, deterministic acceptance, lineage, regression artifacts, local install. |
| Why no LLM judge? | Tool-arg violations are predicates; judges add flake. |
| Why only OpenAI Agents SDK? | Hackathon ships Adapter #1. LangGraph/CrewAI/PydanticAI/AutoGen/HTTP are Beta/v1 adapters—same Core. |
| Isn’t the sample agent weak on purpose? | Yes—like a fuzz harness. Integrity = real execution + oracle. Product is the engine testing *your* agent. |
| Production zero-days? | MVP finds breaks of **defined** policies; search is incomplete; false negatives expected. |
| Safety? | Authorized use; local/localhost; mock tools in demos; no open proxy. |
| Fitness without logits? | Heuristic for search only; acceptance is binary violation. |

**Closing line (canonical):**

> Mutiny doesn’t ask whether your agent looks safe. It keeps attacking until it proves where your policy breaks—then makes sure that failure never comes back.

---

## 7. Demo do / don’t

**Do:** Lead with engine + install-into-your-project; show tool JSON; show re-exec minimize; FAIL→PASS; call demo a sample/harness; name OpenAI Agents SDK as first adapter.  
**Don’t:** Pitch bundled demo as the product; claim multi-framework support today; claim Mutiny *is* an OpenAI Agents SDK tool; claim novelty over Promptfoo/Garak; fake DB violations; open arbitrary URLs.
