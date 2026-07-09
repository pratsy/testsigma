import time

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.config import APP_BASE_URL, DETERMINISTIC_STEP_TIMEOUT_MS
from app.llm.recovery import recover_step
from app.models import PromotionCandidate, RunTrace, StepResult, TestCase, TestStep, now_iso
from app.storage import save_promotion, save_run

MAX_LIVE_DOM_CHARS = 4000


class SelectorNotFound(Exception):
    """The selector doesn't resolve on the live page -- structural UI drift.
    Distinct from AssertionError (found the element, outcome was wrong),
    because only drift is safe to hand off to agentic recovery."""


async def _wait_for(page, selector: str) -> None:
    try:
        await page.wait_for_selector(selector, timeout=DETERMINISTIC_STEP_TIMEOUT_MS, state="visible")
    except PlaywrightTimeoutError:
        raise SelectorNotFound(selector)


async def _execute_deterministic(page, step: TestStep) -> None:
    if step.action == "goto":
        await page.goto(f"{APP_BASE_URL}{step.value}")
    elif step.action == "fill":
        await _wait_for(page, step.selector)
        await page.fill(step.selector, step.value or "")
    elif step.action == "click":
        await _wait_for(page, step.selector)
        await page.click(step.selector)
    elif step.action == "assert_text":
        await _wait_for(page, step.selector)
        text = await page.locator(step.selector).inner_text()
        if step.value and step.value not in text:
            raise AssertionError(f"expected text '{step.value}' but found '{text.strip()}'")


async def _execute_recovered_action(page, action: str, selector: str, value: str | None) -> None:
    if action == "click":
        await _wait_for(page, selector)
        await page.click(selector)
    elif action == "fill":
        await _wait_for(page, selector)
        await page.fill(selector, value or "")
    elif action == "assert_text":
        await _wait_for(page, selector)
        text = await page.locator(selector).inner_text()
        if value and value not in text:
            raise AssertionError(f"recovered element found but text '{value}' not present in '{text.strip()}'")


def _narrate_deterministic(step: TestStep) -> str:
    return f"Executed as scripted: {step.expected}"


async def _run_agentic_recovery(page, step: TestStep, run: RunTrace, start: float, drift_reason: str):
    live_dom = (await page.locator("body").inner_html())[:MAX_LIVE_DOM_CHARS]

    try:
        recovery = recover_step(step, live_dom)
    except Exception as exc:  # LLM/API failure -- the agent itself couldn't respond
        latency_ms = (time.perf_counter() - start) * 1000
        return StepResult(
            step_id=step.step_id,
            order=step.order,
            action=step.action,
            mode="agentic",
            selector_used=step.selector,
            success=False,
            latency_ms=latency_ms,
            error=f"recovery agent call failed: {exc}",
            customer_narrative=(
                f"The original element ('{drift_reason}') could not be found and the recovery "
                f"agent could not be reached, so this step failed rather than being silently skipped."
            ),
        )

    action, selector, value, reasoning = (
        recovery["action"],
        recovery["selector"],
        recovery.get("value"),
        recovery["reasoning"],
    )

    success, error = True, None
    try:
        await _execute_recovered_action(page, action, selector, value)
    except Exception as exc:
        success, error = False, str(exc)

    latency_ms = (time.perf_counter() - start) * 1000
    result = StepResult(
        step_id=step.step_id,
        order=step.order,
        action=action,
        mode="agentic",
        selector_used=selector,
        value_used=value,
        success=success,
        latency_ms=latency_ms,
        error=error,
        agent_reasoning=reasoning,
        customer_narrative=(
            f"The original element ('{step.selector}') no longer matched the page -- the UI changed "
            f"since this test was written. An AI agent inspected the live page and "
            f"{'completed the step using a different element' if success else 'attempted a recovery that also failed'}: "
            f"{reasoning}"
        ),
    )

    if success:
        promo = PromotionCandidate(
            run_id=run.run_id,
            test_id=run.test_id,
            step_id=step.step_id,
            old_selector=step.selector,
            new_selector=selector,
            new_action=action,
            new_value=value,
            reasoning=reasoning,
        )
        save_promotion(promo)
        run.promotion_ids.append(promo.promotion_id)

    return result


async def _execute_step(page, step: TestStep, run: RunTrace):
    start = time.perf_counter()
    try:
        await _execute_deterministic(page, step)
        latency_ms = (time.perf_counter() - start) * 1000
        return StepResult(
            step_id=step.step_id,
            order=step.order,
            action=step.action,
            mode="deterministic",
            selector_used=step.selector,
            value_used=step.value,
            success=True,
            latency_ms=latency_ms,
            customer_narrative=_narrate_deterministic(step),
        )
    except SelectorNotFound as exc:
        # Record the failed deterministic attempt as its own trace event,
        # sharing this step's UUID with whatever the agent produces next.
        # Without this row the trace only shows the eventual outcome and
        # silently loses the fact that a real attempt was made and failed
        # first -- exactly the kind of gap that makes "what did the agent
        # decide and why" hard to reconstruct after the fact.
        failed_latency_ms = (time.perf_counter() - start) * 1000
        run.steps.append(
            StepResult(
                step_id=step.step_id,
                order=step.order,
                action=step.action,
                mode="deterministic",
                selector_used=step.selector,
                value_used=step.value,
                success=False,
                latency_ms=failed_latency_ms,
                error=f"selector did not resolve within {DETERMINISTIC_STEP_TIMEOUT_MS}ms: {exc}",
                customer_narrative=(
                    f"Step failed as scripted: {step.expected} -- the selector '{step.selector}' did not "
                    f"match any element on the live page within {DETERMINISTIC_STEP_TIMEOUT_MS}ms. "
                    f"Handing off to agentic recovery."
                ),
            )
        )
        recovery_start = time.perf_counter()
        return await _run_agentic_recovery(page, step, run, recovery_start, drift_reason=str(exc))
    except AssertionError as exc:
        # Element existed, outcome didn't match: a real failure candidate,
        # not drift. We deliberately do NOT fall back to the agent here --
        # doing so would risk exactly the "silent pass on a real defect"
        # failure mode this system must never produce.
        latency_ms = (time.perf_counter() - start) * 1000
        return StepResult(
            step_id=step.step_id,
            order=step.order,
            action=step.action,
            mode="deterministic",
            selector_used=step.selector,
            value_used=step.value,
            success=False,
            latency_ms=latency_ms,
            error=str(exc),
            customer_narrative=f"Step failed (not a drift case, not recovered): {step.expected} -- {exc}",
        )


async def run_test(test: TestCase) -> RunTrace:
    run = RunTrace(test_id=test.test_id)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            ordered_steps = sorted(test.steps, key=lambda s: s.order)
            for step in ordered_steps:
                result = await _execute_step(page, step, run)
                run.steps.append(result)
                if not result.success:
                    break
            else:
                run.overall_success = True
        finally:
            await browser.close()

    run.finished_at = now_iso()
    save_run(run)
    return run
