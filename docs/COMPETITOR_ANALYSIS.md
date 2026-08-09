# Mutiny — Competitor Analysis

| Field | Value |
|---|---|
| **Status** | Canonical for competitive positioning |
| **Last updated** | 2026-08-07 |
| **Rule** | Be technically honest. No marketing novelty claims. |

Other docs should **link here** instead of restating long competitor tables.

---

## 1. Purpose

Understand overlap so Mutiny:

- Does not pretend to invent agent red teaming  
- Chooses a sharp product wedge  
- Answers judges without defensiveness  

---

## 2. Landscape summary

| System | Category | Primary artifact |
|---|---|---|
| **Garak** | LLM vulnerability scanner | Probe results / reports |
| **Promptfoo** | Eval + red team platform | Test cases, scores, CI evals |
| **PyRIT** | Red team framework/library | Programmatic attack runs |
| **PromptFuzz / genetic tools** | Evolutionary jailbreak fuzzing | Evolved text payloads |
| **GPTFuzz / FuzzLLM / PROMPTFUZZ (academic)** | Research fuzzing | Papers + experimental code |
| **Commercial agent security** | Managed scanning | Vendor reports |

---

## 3. Garak (NVIDIA)

### Strengths

- Broad probe coverage for LLM failures  
- Active OSS community and documentation  
- **Agent Breaker**: multi-turn, tool-aware adaptive attacks; tool YAML / auto-discovery; iterative improvement via red-team model; verification path  

### Weaknesses / limits relative to Mutiny

- Probe/catalog orientation more than productized **user business invariant** campaigns in *your* app repo  
- Success often model-judged rather than deterministic tool-arg predicates  
- Weaker emphasis on install-local → minimize → regression as the default builder loop  

### Overlap

High on “attack agents that use tools.”

### Mutiny response

Do not claim first agent-tool attacks. Claim deterministic invariant oracles + evolutionary search→minimize→regress **as a behavioral fuzz-testing engine** installed into the developer’s agent project via adapter.

---

## 4. Promptfoo

### Strengths

- Custom **policy** plugins  
- Agent red teaming guidance  
- **Trajectory assertions** (`tool-used`, `tool-args-match`, sequences)  
- Tracing integrations  
- Strong CI / regression eval story  

### Weaknesses / limits relative to Mutiny

- Primarily an evaluation and red-team **suite**  
- Less centered on evolutionary **search theater** toward a named tool invariant with live lineage  
- Grading pathways can still involve model judges depending on plugin  

### Overlap

**Very high** on policies, tool trajectories, and turning findings into tests.

### Mutiny response

Acknowledge Promptfoo as the closest product neighbor. Differentiate on policy-guided evolutionary search + deterministic acceptance + minimize/lineage as default—and on **behavioral fuzz testing wired into your agent app via adapter**, not on “we invented policies” or “we only support OpenAI Agents SDK.”

---

## 5. Microsoft PyRIT

### Strengths

- Flexible targets, converters, scorers, memory  
- Multi-turn strategies (Crescendo, TAP, etc.)  
- Built for serious red team operators  

### Weaknesses / limits relative to Mutiny

- Framework/library, not a focused install-and-fuzz product for app builders  
- Scoring frequently LLM-based  
- Higher setup cost for teams who want a narrow policy-fuzz loop  

### Overlap

High on adaptive/tree search concepts.

### Mutiny response

Mutiny is not trying to replace PyRIT for specialist red teams. It productizes a narrower loop for builders of tool-using AI agents (Hackathon MVP: OpenAI Agents SDK via Adapter #1).

---

## 6. PromptFuzz and genetic jailbreak tools

### Strengths

- Demonstrates evolutionary mutation of adversarial prompts  
- Fitness-driven search beyond static lists  

### Weaknesses / limits relative to Mutiny

- Text/jailbreak-centric  
- Fitness often keyword / LLM-judge based  
- Not centered on tool-argument business policies  

### Overlap

High on “evolution,” low on tool-policy oracles.

---

## 7. GPTFuzz / FuzzLLM / academic PROMPTFUZZ

### Strengths

- Research validation that fuzzing/evolution finds novel prompts  
- Useful citations for the search framing  

### Weaknesses / limits relative to Mutiny

- Research artifacts, not installable app-builder products  
- Generally text-injection/jailbreak oriented  

### Overlap

Conceptual (fuzzing LLMs), not product parity.

---

## 8. Commercial agent security products

### Strengths

- Polish, managed ops, reporting  

### Weaknesses / limits relative to Mutiny

- Often closed  
- May not expose a small OSS kernel builders can extend  
- Not the open-build “fuzz your local agent” narrative  

### Overlap

Marketing category overlap only for MVP.

---

## 9. What is actually novel / defensible for Mutiny

Composable wedge—not single-bullet novelty:

1. **Deterministic tool-argument policy oracle** as acceptance  
2. **Policy-conditioned mutation** toward those boundaries  
3. **Delta-debug minimization with mandatory re-exec**  
4. **Regression artifacts** as default product output  
5. **Local install into agent projects** via adapter layer (`mutiny init` / `mutiny run`); which framework adapter is used is an implementation detail  
6. **Optional Hosted attack genealogy** making the search legible  

### What is not novel

- Multi-turn agent attacks  
- Custom policies  
- Tree/evolutionary prompt search  
- CI regression evals in the abstract  
- Shipping a vulnerable demo agent as a “product”  
- Supporting any particular agent framework (adapters are plumbing)  

---

## 10. Positioning statement (approved)

> Mutiny is a behavioral fuzz-testing engine for AI agents—AFL for agent tool policies: install it into your agent project, define invariants, search for breaks, prove them on traces, minimize, and freeze them as tests.  
> The Hackathon MVP ships with support for OpenAI Agents SDK projects through the first adapter. Future frameworks are additional adapters on the same Core.  
> It is not the first agent red-teaming system. It is not an OpenAI Agents SDK testing tool. It is centered on deterministic tool-use invariants and permanent regressions—not a hosted demo-agent showcase.

---

## 11. Judge-facing comparison table

| Capability | Garak | Promptfoo | PyRIT | PromptFuzz-like | Mutiny |
|---|---|---|---|---|---|
| Agent tool attacks | Yes | Yes | Possible | Rare | Yes |
| User business policies | Limited | Strong | DIY | Weak | Strong (narrow) |
| Deterministic tool-arg oracle | Sometimes | Assertions | DIY | No | **Core** |
| Evolutionary search UX | Partial | Strategies | TAP etc. | Yes | **Core** |
| Minimize → regression loop | Weak | Eval-centric | DIY | Weak | **Core** |
| Install into your agent project | Partial | Suite/config | DIY | No | **Primary** |
| Adapter layer (framework plug-in) | N/A | Possible | DIY | No | **Architecture** |
| OpenAI Agents SDK adapter | N/A | Possible | DIY | No | **MVP Adapter #1** |
| Hosted lineage | No | Partial | No | No | Secondary |

---

## 12. Maintenance

Update this file when:

- A competitor ships a feature that collapses our wedge  
- We change Mutiny’s acceptance model or primary install path  
- Judges repeatedly confuse Mutiny with a specific tool  

Do not copy this analysis into PRD beyond a short pointer.
