"""Client-facing frontend for stage 4 (the approval gate).

This is the one screen a client's founder actually uses: it does not expose
stages 1-3 (history collection, brief/draft generation happen automatically
in the background) — it shows what's ready for review and lets them
approve or reject it. There is no "publish" button anywhere in this app,
on purpose: see sns_marketing_agent/approval_gate.py.

Known limitations (prototype, not production):
- No login. A client's queue is reachable at /clients/<client_id> with no
  access check — fine for a demo shown over someone's shoulder, not fine
  for a real client to be given a bookmark to. Needs real auth before that.
- State is in-memory only (the `gate` below). Restarting the process loses
  all approve/reject history.
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

from sns_marketing_agent.approval_gate import ApprovalGate
from sns_marketing_agent.history_collector import StaticHistorySource
from sns_marketing_agent.image_generator import ImageAssetGenerator, NullImageGenerator, PlaywrightCardRenderer
from sns_marketing_agent.llm_client import LLMClient, TemplateLLMClient
from sns_marketing_agent.models import ApprovalRecord, Channel
from sns_marketing_agent.pipeline import run_pipeline

WEB_DIR = Path(__file__).parent
FIXTURE = WEB_DIR.parent / "sns_marketing_agent" / "fixtures" / "sample_client_history.json"
IMAGES_DIR = WEB_DIR / "generated_images"
DEMO_CLIENT_ID = "demo-bakery"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)

gate = ApprovalGate()


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
    if not gate.all(client_id=DEMO_CLIENT_ID):
        # PlaywrightCardRenderer uses Playwright's sync API, which refuses to
        # run directly on an asyncio event loop — push the whole seed call
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
    return RedirectResponse(url=f"/clients/{DEMO_CLIENT_ID}")


@app.get("/clients/{client_id}")
def client_queue(request: Request, client_id: str):
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


@app.post("/records/{record_id}/approve")
def approve(record_id: str, reviewer: str = Form("대표")):
    record = _record_or_404(record_id)
    gate.approve(record_id, reviewer=reviewer.strip() or "대표")
    return RedirectResponse(url=f"/clients/{record.draft.brief.client_id}", status_code=303)


@app.post("/records/{record_id}/reject")
def reject(record_id: str, reviewer: str = Form("대표"), notes: str = Form("")):
    record = _record_or_404(record_id)
    gate.reject(record_id, reviewer=reviewer.strip() or "대표", notes=notes.strip())
    return RedirectResponse(url=f"/clients/{record.draft.brief.client_id}", status_code=303)
