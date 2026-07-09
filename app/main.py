from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.execution.runner import run_test
from app.llm.compiler import compile_intent
from app.models import PromotionCandidate
from app.storage import (
    list_promotions,
    list_runs,
    list_tests,
    load_promotion,
    load_run,
    load_test,
    save_promotion,
    save_test,
)
from app.target_app.router import router as target_app_router

app = FastAPI(title="Hybrid Test Execution Prototype")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
app.include_router(target_app_router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "tests": list_tests()})


@app.post("/tests")
async def create_test(request: Request, intent: str = Form(...)):
    try:
        test = compile_intent(intent)
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "tests": list_tests(), "error": str(exc), "default_intent": intent},
            status_code=500,
        )
    save_test(test)
    return RedirectResponse(url=f"/tests/{test.test_id}", status_code=303)


@app.get("/tests/{test_id}")
async def test_detail(request: Request, test_id: str):
    test = load_test(test_id)
    if test is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "test_detail.html", {"request": request, "test": test, "runs": list_runs(test_id)}
    )


@app.post("/tests/{test_id}/run")
async def trigger_run(test_id: str):
    test = load_test(test_id)
    if test is None:
        return RedirectResponse(url="/", status_code=303)
    run = await run_test(test)
    return RedirectResponse(url=f"/runs/{run.run_id}", status_code=303)


@app.get("/runs/{run_id}")
async def run_detail(request: Request, run_id: str):
    run = load_run(run_id)
    if run is None:
        return RedirectResponse(url="/", status_code=303)
    test = load_test(run.test_id)
    promotions = list_promotions(run_id=run_id)
    return templates.TemplateResponse(
        "run_detail.html", {"request": request, "run": run, "test": test, "promotions": promotions}
    )


def _apply_promotion(promo: PromotionCandidate) -> None:
    test = load_test(promo.test_id)
    if test is None:
        return
    for step in test.steps:
        if step.step_id == promo.step_id:
            step.selector = promo.new_selector
            step.action = promo.new_action
            step.value = promo.new_value
            break
    save_test(test)


@app.post("/promotions/{promotion_id}/approve")
async def approve_promotion(promotion_id: str):
    promo = load_promotion(promotion_id)
    if promo is None:
        return RedirectResponse(url="/", status_code=303)
    promo.status = "approved"
    _apply_promotion(promo)
    save_promotion(promo)
    return RedirectResponse(url=f"/runs/{promo.run_id}", status_code=303)


@app.post("/promotions/{promotion_id}/reject")
async def reject_promotion(promotion_id: str):
    promo = load_promotion(promotion_id)
    if promo is None:
        return RedirectResponse(url="/", status_code=303)
    promo.status = "rejected"
    save_promotion(promo)
    return RedirectResponse(url=f"/runs/{promo.run_id}", status_code=303)
