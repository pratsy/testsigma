from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR

router = APIRouter(prefix="/target", tags=["target-app"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("target/login.html", {"request": request})


@router.post("/login")
async def login_submit():
    # The target app is a stub: any credentials "work" so the demo stays
    # deterministic on the login step. What matters for this prototype is
    # what happens on the page after login, not authentication logic.
    return RedirectResponse(url="/target/orders", status_code=303)


@router.get("/orders")
async def orders_page(request: Request):
    return templates.TemplateResponse("target/orders.html", {"request": request})
