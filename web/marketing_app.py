"""Split-View 마케팅 에이전트 — PRD v1.0 §6.4.

STan이 로컬에서 열어 한 달치 흐름을 순서대로 밟는 화면 하나:
맥락(F1) 요약 → 전략(F2) 확인/수정 → 브리프+크리에이티브(F3/F4) 생성 →
승인함(F5) 승인/반려. 왼쪽 패널은 그 달의 진행 단계, 오른쪽 패널은
지금 단계의 실제 산출물 — 두 패널이 같은 (client_slug, month) 상태를
보므로 별도 화면 전환 없이 한 페이지에서 끝난다.

이 앱은 web/app.py(구 프로토타입의 승인 전용 큐)와 별도 프로세스로 띄운다:
    uvicorn web.marketing_app:app --reload --port 8001
구 앱과 데이터/포트를 공유하지 않는다 — PRD v1.0은 새 데이터 모델
(strategy_models/creative_models/review_models)을 쓰는 별도 트랙이기 때문.

발행(publish) 버튼은 없다. F5가 하는 일은 승인/반려까지이고, 승인된
콘텐츠를 실제로 인스타그램에 올리는 것은 F6(P2, 이번 스코프 밖)이다 —
creative_studio.py/pipeline_v1.py와 같은 경계.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sns_marketing_agent.brief_selector import BriefSelector
from sns_marketing_agent.carousel_renderer import CarouselAssetRenderer, NullCarouselRenderer, PlaywrightCarouselRenderer
from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.cofounder_mcp_transport import CofounderMCPTransport
from sns_marketing_agent.context_engine import ContextEngine
from sns_marketing_agent.context_store import SqliteContextStore, SqliteMcpCallLog
from sns_marketing_agent.creative_studio import CreativeStudio
from sns_marketing_agent.llm_client import AnthropicLLMClient, LLMClient
from sns_marketing_agent.masking_filter import MaskingFilter, extract_protected_terms
from sns_marketing_agent.review_models import REASON_LABELS, ReasonCode
from sns_marketing_agent.review_queue import ReviewQueue
from sns_marketing_agent.rubric_scorer import RubricScorer
from sns_marketing_agent.strategy_planner import StrategyPlanner
from sns_marketing_agent.template_llm_v1 import TemplateLLMClientV1
from web.review_store import SqliteReviewStore

WEB_DIR = Path(__file__).parent
FIXTURE_ROOT = WEB_DIR.parent / "sns_marketing_agent" / "fixtures" / "cofounder_recorded"
DATA_DIR = WEB_DIR / "data"
CAROUSELS_DIR = WEB_DIR / "generated_carousels"
DEFAULT_CLIENT_SLUG = "supernova-platform"
DEFAULT_MONTH = "2026-09"
INSTAGRAM_BASE_URL = os.environ.get("COFOUNDER_INSTAGRAM_BASE_URL", "https://spnv.jengablock.com")

CAROUSELS_DIR.mkdir(parents=True, exist_ok=True)

review_queue = ReviewQueue(SqliteReviewStore(DATA_DIR / "reviews_v1.db"))
context_store = SqliteContextStore(DATA_DIR / "context_snapshots_v1.db")

# in-process cache: (client_slug, month) -> pipeline state. Not persisted —
# a restart loses draft briefs/creatives (their text lives only here; only
# review DECISIONS survive in SqliteReviewStore). Fine for a local P1 pilot;
# see this module's docstring.
_state: dict[str, dict] = {}


def _state_key(client_slug: str, month: str) -> str:
    return f"{client_slug}::{month}"


def _build_read_only_client(client_slug: str) -> ReadOnlyCofounderClient:
    fixture_dir = FIXTURE_ROOT / client_slug
    caller = FixtureMCPCaller(client_slug) if fixture_dir.exists() else CofounderMCPTransport()
    call_log = SqliteMcpCallLog(DATA_DIR / "mcp_call_log_v1.db")
    return ReadOnlyCofounderClient(caller, call_log=call_log)


def _build_llm() -> LLMClient:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLMClient()
    return TemplateLLMClientV1()


def _build_renderer() -> CarouselAssetRenderer:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return NullCarouselRenderer()
    try:
        return PlaywrightCarouselRenderer(
            CAROUSELS_DIR, executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
        )
    except Exception:
        return NullCarouselRenderer()


def _build_masking_filter(co_client: ReadOnlyCofounderClient, client_slug: str) -> MaskingFilter:
    clients_resp = co_client.list_clients()
    terms = extract_protected_terms(clients_resp, exclude_slug=client_slug)
    return MaskingFilter(terms)


def _ensure_context_and_strategy(client_slug: str, month: str, force_refresh: bool = False) -> dict:
    key = _state_key(client_slug, month)
    if not force_refresh and key in _state:
        return _state[key]

    co_client = _build_read_only_client(client_slug)
    llm = _build_llm()
    snapshot = ContextEngine(co_client).build_snapshot(client_slug)
    context_store.save(snapshot)
    strategy = StrategyPlanner(llm).build_strategy(snapshot, month=month)

    state = {
        "co_client": co_client,
        "llm": llm,
        "snapshot": snapshot,
        "strategy": strategy,
        "briefs": [],
        "brief_by_id": {},
        "creatives_by_brief": {},
        "creative_by_id": {},
        "review_id_by_creative": {},
    }
    _state[key] = state
    return state


def _generate_briefs_and_creatives(client_slug: str, month: str) -> dict:
    key = _state_key(client_slug, month)
    state = _state.get(key)
    if state is None:
        raise HTTPException(status_code=404, detail="먼저 페이지를 열어 이번 달 전략을 생성해주세요.")
    if state["strategy"].status != "confirmed":
        raise HTTPException(
            status_code=400, detail="브리프를 생성하려면 먼저 이번 달 전략을 확인(승인)해주세요."
        )

    co_client = state["co_client"]
    llm = state["llm"]
    snapshot = state["snapshot"]
    strategy = state["strategy"]

    masking_filter = _build_masking_filter(co_client, client_slug)
    renderer = _build_renderer()
    studio = CreativeStudio(llm, renderer, masking_filter, INSTAGRAM_BASE_URL)
    scorer = RubricScorer(llm)

    avoid_patterns = [
        REASON_LABELS[code] for code in review_queue.recent_rejection_patterns(client_slug)
    ]

    briefs = BriefSelector(llm).select_and_brief(snapshot, strategy, n=3, avoid_patterns=avoid_patterns)

    brief_by_id: dict = {}
    creatives_by_brief: dict = {}
    creative_by_id: dict = {}
    review_id_by_creative: dict = {}

    for brief in briefs:
        brief_by_id[brief.id] = brief
        creatives = studio.build_creatives(brief, campaign_month=month, avoid_patterns=avoid_patterns)
        creatives_by_brief[brief.id] = creatives
        for creative in creatives:
            creative_by_id[creative.id] = creative
            rubric = scorer.score(creative, brief)
            record = review_queue.submit(client_slug, creative.id, brief.id, rubric)
            review_id_by_creative[creative.id] = record.id

    state["briefs"] = briefs
    state["brief_by_id"] = brief_by_id
    state["creatives_by_brief"] = creatives_by_brief
    state["creative_by_id"] = creative_by_id
    state["review_id_by_creative"].update(review_id_by_creative)
    return state


app = FastAPI(title="코파운더 마케팅 에이전트")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.mount("/carousels", StaticFiles(directory=CAROUSELS_DIR), name="carousels")
templates = Jinja2Templates(directory=WEB_DIR / "marketing_templates")


def _carousel_url(file_path: str) -> str | None:
    if not file_path:
        return None
    return f"/carousels/{Path(file_path).name}"


REASON_CODE_CHOICES = [(code.value, REASON_LABELS[code]) for code in ReasonCode]


@app.get("/")
def index():
    return RedirectResponse(url=f"/clients/{DEFAULT_CLIENT_SLUG}?month={DEFAULT_MONTH}")


@app.get("/clients/{client_slug}")
def client_view(request: Request, client_slug: str, month: str = DEFAULT_MONTH):
    state = _ensure_context_and_strategy(client_slug, month)
    snapshot = state["snapshot"]
    strategy = state["strategy"]

    creative_rows = []
    for brief in state["briefs"]:
        for creative in state["creatives_by_brief"].get(brief.id, []):
            record_id = state["review_id_by_creative"].get(creative.id)
            creative_rows.append({"brief": brief, "creative": creative, "record_id": record_id})

    pending = review_queue.pending(client_slug)
    reviewed_sorted = sorted(
        review_queue.reviewed(client_slug),
        key=lambda r: r.reviewed_at or r.created_at,
        reverse=True,
    )
    review_by_id = {r.id: r for r in pending + reviewed_sorted}

    return templates.TemplateResponse(
        request,
        "client.html",
        {
            "client_slug": client_slug,
            "month": month,
            "snapshot": snapshot,
            "strategy": strategy,
            "creative_rows": creative_rows,
            "review_by_id": review_by_id,
            "reviewed": reviewed_sorted,
            "reason_choices": REASON_CODE_CHOICES,
            "carousel_url": _carousel_url,
            "strategy_confirmed": strategy.status == "confirmed",
            "has_creatives": bool(creative_rows),
            "all_reviewed": bool(creative_rows) and not pending,
        },
    )


@app.post("/clients/{client_slug}/refresh")
def refresh_context(client_slug: str, month: str = Form(...)):
    _ensure_context_and_strategy(client_slug, month, force_refresh=True)
    return RedirectResponse(url=f"/clients/{client_slug}?month={month}", status_code=303)


@app.post("/clients/{client_slug}/strategy")
def confirm_strategy(client_slug: str, month: str = Form(...), goal: str = Form(...), reviewer: str = Form("STan")):
    key = _state_key(client_slug, month)
    state = _state.get(key)
    if state is None:
        raise HTTPException(status_code=404, detail="먼저 페이지를 열어 이번 달 전략을 생성해주세요.")

    strategy = state["strategy"]
    goal = goal.strip()
    if goal and goal != strategy.goal:
        strategy.goal = goal
        strategy.edited_by = reviewer.strip() or "STan"
    strategy.status = "confirmed"
    return RedirectResponse(url=f"/clients/{client_slug}?month={month}", status_code=303)


@app.post("/clients/{client_slug}/generate")
def generate(client_slug: str, month: str = Form(...)):
    _generate_briefs_and_creatives(client_slug, month)
    return RedirectResponse(url=f"/clients/{client_slug}?month={month}", status_code=303)


@app.post("/records/{record_id}/approve")
def approve_record(record_id: str, client_slug: str = Form(...), month: str = Form(...), reviewer: str = Form("STan")):
    try:
        review_queue.approve(record_id, reviewer=reviewer.strip() or "STan")
    except KeyError:
        raise HTTPException(status_code=404, detail="해당 콘텐츠를 찾을 수 없습니다")
    return RedirectResponse(url=f"/clients/{client_slug}?month={month}", status_code=303)


@app.post("/records/{record_id}/reject")
def reject_record(
    record_id: str,
    client_slug: str = Form(...),
    month: str = Form(...),
    reviewer: str = Form("STan"),
    reason_codes: list[str] = Form([]),
    note: str = Form(""),
):
    if not reason_codes:
        raise HTTPException(status_code=400, detail="반려 시 반려 사유를 1개 이상 선택해주세요 (PRD §5.4)")
    try:
        codes = [ReasonCode(c) for c in reason_codes]
        review_queue.reject(record_id, reviewer=reviewer.strip() or "STan", reason_codes=codes, note=note.strip())
    except KeyError:
        raise HTTPException(status_code=404, detail="해당 콘텐츠를 찾을 수 없습니다")
    return RedirectResponse(url=f"/clients/{client_slug}?month={month}", status_code=303)
