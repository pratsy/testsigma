# Hybrid Test Execution — Prototype

A minimal, honest end-to-end demonstration of the hybrid execution loop:
**capture (NL → structured test) → run deterministically → detect UI drift →
recover with an agent → review → promote back to deterministic.**

Everything runs as a single Python process: FastAPI serves both the control
UI and a tiny stub target app ("MiniCart"), Playwright drives the browser,
and OpenAI's GPT-4o powers both the NL→test compiler and the in-run recovery agent.

## Why it's built this way

- **LLM choice: OpenAI (GPT-4o) via function-calling.** Any LLM works for
  this prototype's purposes — what matters is reliable structured-output
  support, since both the compiler and the recovery agent must return
  parseable actions, not prose. The provider-specific code is isolated to
  `app/llm/client.py::call_tool()`; `compiler.py` and `recovery.py` describe
  their tools in a provider-agnostic `{name, description, input_schema}`
  shape and never touch the OpenAI SDK directly, so swapping providers (e.g.
  to Claude) is a change to one file, not a rewrite.
- **The target app is self-hosted, not a real public site**, so the UI drift
  that triggers the fallback can be planted deliberately and reproducibly
  (see `app/target_app/reference_dom.py` and `app/templates/target/orders.html`)
  instead of hoping a third-party site's DOM cooperates on demo day.
- **The agentic recovery call is a real, structured LLM function call
  against the live DOM at run time** (`app/llm/recovery.py`) — not an
  `if/else` dressed up as an agent. You can watch it happen in the terminal
  logs and in the run's decision trace.
- **A found-but-wrong assertion never triggers the fallback.** The runner
  distinguishes "selector doesn't resolve" (structural drift → safe to hand
  to the agent) from "selector resolved but the text is wrong" (a real
  failure candidate → must fail loudly, not be silently recovered). See the
  comment in `app/execution/runner.py::_execute_step`. This is a direct
  answer to one of the three escalations described in the assignment
  ("silent test passes that should have failed").
- **One trace store, two readers.** Every step (deterministic or agentic)
  writes the same `StepResult` record. The decision-trace UI and the
  promotion-review UI both read from it — there's no separate "debug log"
  that can drift out of sync with what the customer-facing report says.

## Prerequisites

- Python 3.11+
- An OpenAI API key ([platform.openai.com/api-keys](https://platform.openai.com/api-keys))

## Setup (should take under 15 minutes)

```bash
cd hybrid-test-execution
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env
# edit .env and paste your real OPENAI_API_KEY
```

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

> If port 8000 is already in use on your machine, run on another port
> (`--port 8010`) and also set `APP_BASE_URL=http://127.0.0.1:8010` in `.env`
> — Playwright needs to know which port to drive the target app on.

## Walking through the demo yourself

1. **Capture.** On the home page, enter an intent, e.g.:
   > Log in as a returning user and verify the order history page shows their last order

   Click **Compile test**. The LLM turns this into a structured, five-step
   test (goto → fill → fill → click → assert_text) using the app's known
   selectors.
2. **Run it.** Open the test and click **Run test**. The first four steps
   (login) execute deterministically and pass. The fifth step
   (`#last-order-summary`) fails — the live orders page has been
   intentionally reshaped (see "Why it's built this way" above) so that
   selector no longer exists.
3. **Watch the fallback.** The runner detects the missing selector, grabs the
   live page's DOM, and calls the recovery agent. The agent finds the order
   card under its new markup and completes the assertion. The run still
   ends in PASS, but the decision trace shows step 5 ran in **agentic** mode,
   with the agent's reasoning attached, and took noticeably longer than the
   deterministic steps.
4. **Review the promotion.** Below the trace, a promotion candidate shows the
   old selector, the new one the agent found, and its reasoning. Click
   **Approve & promote to deterministic**.
5. **Run it again.** Open the test — step 5's selector has been rewritten.
   Run it again: all five steps now execute in **deterministic** mode, and
   the last step's latency drops by roughly two orders of magnitude (from a
   ~2s agentic recovery down to tens of milliseconds). This is the learning
   loop: agentic recovery → human review → deterministic update.

## What's deliberately out of scope

Per the assignment's own scope note ("a working three-step flow with all
four layers is far stronger than an elaborate UI with the fallback faked"):
no auth, no multi-test suites, no CI integration, no Neo4j/knowledge graph,
no parallel execution, no design system. One target app, one test, one
forced failure, one promotion — done honestly.

## Project layout

```
app/
  main.py                 FastAPI routes (capture, run, promote, trace UI)
  models.py                TestCase / TestStep / RunTrace / StepResult / PromotionCandidate
  storage.py                JSON-file persistence (data/tests, data/runs, data/promotions)
  llm/
    compiler.py              NL intent -> structured TestCase (LLM function-calling)
    recovery.py               live DOM -> recovery action (LLM function-calling)
  execution/
    runner.py                 deterministic executor + drift detection + fallback orchestration
  target_app/
    reference_dom.py           "as-authored" DOM snapshot, given to the compiler only
    router.py                   the live (intentionally drifted) MiniCart stub app
  templates/                 Jinja2 UI (capture form, test detail, decision trace)
data/                        JSON-backed test/run/promotion storage (gitignored contents)
```

See `ARCHITECTURE.md` for a one-page diagram of how these pieces connect.
