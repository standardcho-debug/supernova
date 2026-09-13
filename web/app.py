"""Client-facing frontend for stage 4 (the approval gate).

This is the one screen a client's founder actually uses: it does not expose
stages 1-3 (history collection, brief/draft generation happen automatically
in the background) — it shows what's ready for review and lets them
approve or reject it. There is no "publish" button anywhere in this app,
on purpose: see sns_marketing_agent/approval_gate.py.

/admin lists every client's link (with its access token) — that's Stan's
view, for grabbing a link to hand to a client or to open in a private
window and simulate being one.

Known limitations (prototype, not production):
- Access tokens (web/access.py) are not a real auth system — no login, no
  expiry, no way for a client to revoke their own link. See that module's
  docstring.
- /admin itself has no access control — anyone who can reach this server
  can list every client's link. Fine for Stan running this locally; not
  fine exposed on the internet as-is.
- Only one demo client (`demo-bakery`, from sns_marketing_agent/fixtures)
  is seeded. Wiring in real Cofounder clients is separate work — see the
  main README.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sns_marketing_agent.history_collector import StaticHistorySource
from sns_marketing_agent.image_generator import ImageAssetGenerator, NullImageGenerator, PlaywrightCardRenderer
from sns_marketing_agent.llm_client import LLMClient, TemplateLLMClient
from sns_marketing_agent.models import ApprovalRecord, Channel
from sns_marketing_agent.pipeline import run_pipeline
from web.access import ClientAccessStore
from web.sqlite_store import SqliteApprovalGate

WEB_DIR = Path(__file__).parent
FIXTURE = WEB_DIR.parent / "sns_marketing_agent" / "fixtures" / "sample_client_history.json"
DATA_DIR = WEB_DIR / "data"
IMAGES_DIR = WEB_DIR / "generated_images"
DEMO_CLIENT_ID = "demo-bakery"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)

gate = SqliteApprovalGate(DATA_DIR / "approvals.db")
access_store = ClientAccessStore(DATA_DIR / "access.db")


def _build_llm_client() -> LLMClient:
    if os.environ.get("ANTHROPIC_API_KEY"):
        from sns_marketing_agent.llm_client import AnthropicLLMClient

        return AnthropicLLMClient()
    return TemplateLLMClient()


def _build_image_generator() -> ImageAssetGenerator:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return NullImageGenerator()
    try:
        return PlaywrightCardRenderer(
            IMAGES_DIR, executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
        )
    except Exception:
        return NullImageGenerator()


def _seed_demo_content_sync() -> None:
    if not gate.all(client_id=DEMO_CLIENT_ID):
        run_pipeline(
            client_id=DEMO_CLIENT_ID,
            channels=list(Channel),
            history_source=StaticHistorySource(FIXTURE),
            llm=_build_llm_client(),
            image_generator=_build_image_generator(),
            gate=gate,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    access_store.token_for(DEMO_CLIENT_ID)  # mint once, reused across restarts
    # PlaywrightCardRenderer uses Playwright's sync API, which refuses to run
    # directly on an asyncio event loop — push the (possibly slow) seed call
    # to a worker thread instead.
    await anyio.to_thread.run_sync(_seed_demo_content_sync)
    yield


app = FastAPI(title="코파운더 SNS 콘텐츠 승인함", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def _image_url(file_path: str) -> str | None:
    if not file_path:
        return None
    return f"/images/{Path(file_path).name}"


@app.get("/")
def index():
    return RedirectResponse(url="/admin")


@app.get("/admin")
def admin_index(request: Request):
    links = [
        {"client_id": cid, "token": access_store.token_for(cid)}
        for cid in access_store.all_clients()
    ]
    return templates.TemplateResponse(request, "admin.html", {"links": links})


@app.get("/clients/{client_id}")
def client_queue(request: Request, client_id: str, token: str | None = None):
    if not access_store.verify(client_id, token):
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다. 링크를 다시 확인해주세요.")

    pending = gate.pending(client_id=client_id)
    reviewed = sorted(
        gate.reviewed(client_id=client_id),
        key=lambda r: r.reviewed_at or r.draft.brief.created_at,
        reverse=True,
    )
    return templates.TemplateResponse(
        request,
        "queue.html",
        {
            "client_id": client_id,
            "token": token,
            "pending": pending,
            "reviewed": reviewed,
            "image_url": _image_url,
        },
    )


def _record_or_404(record_id: str) -> ApprovalRecord:
    try:
        return gate.get(record_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="해당 콘텐츠를 찾을 수 없습니다")


def _require_access(record: ApprovalRecord, token: str | None) -> None:
    if not access_store.verify(record.draft.brief.client_id, token):
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다. 링크를 다시 확인해주세요.")


@app.post("/records/{record_id}/approve")
def approve(record_id: str, token: str = Form(...), reviewer: str = Form("대표")):
    record = _record_or_404(record_id)
    _require_access(record, token)
    gate.approve(record_id, reviewer=reviewer.strip() or "대표")
    return RedirectResponse(
        url=f"/clients/{record.draft.brief.client_id}?token={token}", status_code=303
    )


@app.post("/records/{record_id}/reject")
def reject(record_id: str, token: str = Form(...), reviewer: str = Form("대표"), notes: str = Form("")):
    record = _record_or_404(record_id)
    _require_access(record, token)
    gate.reject(record_id, reviewer=reviewer.strip() or "대표", notes=notes.strip())
    return RedirectResponse(
        url=f"/clients/{record.draft.brief.client_id}?token={token}", status_code=303
    )
