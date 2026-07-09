# Architecture — Hybrid Test Execution Prototype

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser (control UI)                                                │
│  intent form · test detail · decision trace · promotion review       │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │  FastAPI (app/main.py)
                                 ▼
        ┌───────────────────────────────────────────┐
        │ 1. COMPILER            (app/llm/compiler.py)│
        │    NL intent + app manifest (reference DOM) │
        │    ──LLM function call──▶ structured TestCase │
        └───────────────────────┬────────────────────┘
                                 ▼
        ┌───────────────────────────────────────────┐
        │ 2. DETERMINISTIC EXECUTOR (execution/runner)│
        │    Playwright drives the live target app    │
        │    step by step, in order                   │
        └───────┬───────────────────────┬─────────────┘
                │ selector resolves     │ selector does NOT resolve
                │ (or resolves but      │ (structural UI drift)
                │  assertion is wrong)  │
                ▼                       ▼
        ┌───────────────┐   ┌─────────────────────────────────────┐
        │ FAIL LOUDLY     │   │ 3. AGENTIC EXECUTOR (llm/recovery.py)│
        │ (no fallback —  │   │    live DOM + original step intent   │
        │  a real defect  │   │    ──LLM function call──▶ recovery      │
        │  must not be    │   │    action (selector/action/reasoning)│
        │  silently       │   │    Playwright executes it            │
        │  "recovered")   │   └───────────────┬───────────────────────┘
        └───────┬─────────┘                   │ success
                │                             ▼
                │                 ┌─────────────────────────────┐
                │                 │ 4. PROMOTION CANDIDATE        │
                │                 │    old selector → new selector│
                │                 │    + agent's reasoning         │
                │                 │    status: pending             │
                │                 └───────────────┬─────────────────┘
                │                                 │ human approves
                │                                 ▼
                │                 ┌─────────────────────────────┐
                │                 │ Test JSON step rewritten      │
                │                 │ → next run is deterministic   │
                │                 │   again (the learning loop)   │
                │                 └───────────────────────────────┘
                ▼
        ┌───────────────────────────────────────────────────────┐
        │ 5. TRACE STORE (one record per step, every run)         │
        │    step_id · mode · selector_used · latency · success   │
        │    · agent_reasoning · customer_narrative                │
        │    → same records feed both:                             │
        │       - the decision-trace UI (per-run, per-step)         │
        │       - the promotion-review UI                            │
        └───────────────────────────────────────────────────────┘
```

## The one non-obvious design choice worth calling out

Step 2 branches on **why** a step failed, not just **that** it failed:

- **Selector doesn't resolve at all** → treated as structural UI drift. Safe
  to hand to the agent, because the *mechanism* for finding the element
  broke, not necessarily the *outcome* the step was checking for.
- **Selector resolves, but the asserted text is wrong** → treated as a
  candidate real defect. The run fails loudly. It is never handed to the
  agent, because "let the agent quietly make this pass anyway" is exactly
  the false-pass failure mode described in the assignment's escalation #2.

This is the single architectural decision in the prototype that's a direct,
falsifiable answer to "how do you keep hybrid execution from silently
passing things that should have failed" — small system, same question a
production version has to answer at scale.

## Target app

A two-page stub ("MiniCart") served by the same FastAPI process:
`/target/login` (unchanged between "as-authored" and "live") and
`/target/orders` (deliberately reshaped in the live version — see
`app/target_app/reference_dom.py` vs. `app/templates/target/orders.html`).
Self-hosting the target app means the drift is reproducible on every run,
not dependent on a third-party site not changing on demo day.
