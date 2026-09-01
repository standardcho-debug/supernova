#!/usr/bin/env python3
"""PostToolUse 알림 — 클라 대면 **문서**의 의문형 AI-호스트 어투 검출.

**왜 이 훅이 필요한가 (선행 판단의 빈 구멍)**

`voice-axes.md` 불변 레일 3 "의문형 AI-호스트 헤더 금지" 는 모든 브랜드에 항상
참인 바닥이다. 그런데 그 강제는 이렇게 배분돼 있었다:

  레일 1 (내부어) → 기계 넷 `check-internal-lexicon` (화면 카피)
  레일 2·3 (AI 어투) → 판단층: designer P3.5 크리틱 · frontend-dev DoD

`check-internal-lexicon.mjs` docstring 이 레일 3 을 기계에서 빼 이유로 든 것은
**"기계로 판별하면 도메인어를 오차단"** 이다. 그 논거는 레일 1 에는 맞다 —
RDS(호흡곴란증후군)·감독(영화)·에이전트(보험)처럼 *어휘* 가 도메인과 충돌한다.
그러나 레일 3 의 위반은 어휘가 아니라 **구조**(문서가 독자에게 되묻는 형태)이고,
오탐 위험은 "정당한 FAQ" 하나로 훨씬 좋다. 두 레일의 오탐 성격이 다른데 한
묶음으로 처리된 것이 첫 번째 구멍이다.

두 번째이자 더 큰 구멍: **판단층 담당자가 둘 다 화면 담당이다.** designer 는
화면을 보고, frontend-dev 는 컴포넌트를 본다. **문서에는 주인이 아무도 없었다.**
"항상 참" 이라 선언된 레일이 특정 표면에서 무주공산이었다.

실측(2026-08-30): koreal 문서 사이트를 클라 대면으로 전환하며 로드맵을 쓰는데
같은 세션이 이 레일을 15곳에서 어겨다("무엇이 문제였나"·"왜 지금 바로 주문을
못 만드나"·"무엇으로 잘 되고 있다고 판단하나"…). 규칙을 알고 있었고 CLAUDE.md
에도 있었으나, 화면 규칙으로 좋게 읽었고 잡아줄 기계가 없었다.

**왜 차단(deny)이 아니라 알림인가**

문체 규칙엔 정당한 예외가 있다 — 진짜 FAQ 절, 기술 문서의 인용("어느 메일이
트리거했는가"). 휴리스틱으로 Write 를 막으면 그 예외에서 세션이 막힌다. 반면
이번 실패 모드는 *쓰고도 못 알아채린 것* 이라, **쓰기 직후 surface 하면 커밋 전에
고쳐진다.** 기존 규범-birth PostToolUse 알림과 같은 계열.

**Scope**: `clients/*/docs/` 아래 `.md` 중 클라가 읽는 절만. `technical/`·
`decisions/`·`superpowers/` 는 개발자 독자라 제외(인용·주석의 의문형이 정당).

Fail-open: 파싱 오류·예외는 조용히 exit 0 — 세션을 절대 wedge 하지 않는다.

CLI 로도 쓔다(디렉터리 일괄 점검):
    python3 warn-ai-register-in-client-docs.py <path.md|dir> [...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 개발자 독자 — 인용·기술 주석의 의문형이 정당하므로 제외.
EXCLUDED_SEGMENTS = ("technical", "decisions", "superpowers", "node_modules")

# ── 탐지 규칙 ───────────────────────────────────────────────────────────────
# 오탐 0 지향: "의문형이면 다 잡는다" 가 아니라 **AI-호스트 상투구** 만 잡는다.
# 진짜 FAQ("배송은 언제 되나요?")나 도메인 질문은 대상이 아니다.

# ① 의문형 마크다운 헤더 — 문서가 자기 절 제목을 질문으로 단다.
_HEADER_Q = re.compile(
    r"^\s{0,3}#{1,6}\s+.*?(?:무엇|어디로|어디까지|왜)\s*.*?(?:나|가|은가|는가|인가|한가|까)\s*\??\s*$"
)

# ② 자문자답 강조구 — **무엇이 문제였나** / **무엇을 만들었나** / **왜 ~인가**
_BOLD_Q = re.compile(
    r"\*\*\s*(?:무엇(?:을|이|으로)|어디로|어디까지|왜)\b[^*]{0,40}?"
    r"(?:나|은가|는가|인가|한가|까)\s*\??\s*\*\*"
)

# ③ 링크 라벨·목록의 상투구 — "현재 무엇이 됐나?" → [문서]
_STOCK = re.compile(
    r"(?:현재\s*)?무엇이\s*(?:됨|되었|만들어졌)나|"
    r"무엇을\s*(?:했|만들었|고쳤)나|"
    r"어디로\s*가고\s*있나|"
    r"왜\s*그렇게\s*만들었나|"
    r"지금\s*어디까지\s*왔나"
)

RULES = (("의문형 헤더", _HEADER_Q), ("자문자답 강조구", _BOLD_Q), ("AI-호스트 상투구", _STOCK))


def in_scope(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    if path.suffix.lower() != ".md":
        return False
    if "docs" not in parts or "clients" not in parts:
        return False
    return not any(seg in parts for seg in EXCLUDED_SEGMENTS)


def scan(text: str) -> list[tuple[int, str, str]]:
    """(줄번호, 규칙명, 줄내용). 코드펜스 안은 건너뛴다."""
    hits: list[tuple[int, str, str]] = []
    fenced = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        for name, rx in RULES:
            if rx.search(line):
                hits.append((i, name, line.strip()[:90]))
                break
    return hits


def report(path: Path, hits: list[tuple[int, str, str]]) -> str:
    lines = [
        f"⚠️ 의문형 AI-호스트 어투 {len(hits)}건 — {path}",
        "",
        "불변 레일 3(voice-axes.md): 문서 제목이 독자에게 되묻지 않는다.",
        "명사구·서술형으로 바꿀 것 — 예: \"무엇이 문제였나\" → \"이전 상태\",",
        "\"어디로 가고 있나?\" → \"앞으로의 계획\".",
        "",
    ]
    lines += [f"  L{n} [{kind}] {snippet}" for n, kind, snippet in hits[:12]]
    if len(hits) > 12:
        lines.append(f"  … 외 {len(hits) - 12}건")
    lines += ["", "진짜 FAQ 절이라 정당하면 이 알림은 무시해도 된다(차단 아님)."]
    return "\n".join(lines)


def main() -> None:
    # CLI 모드 — 경로 인자를 주면 일괄 점검.
    if len(sys.argv) > 1:
        total = 0
        for arg in sys.argv[1:]:
            root = Path(arg)
            files = sorted(root.rglob("*.md")) if root.is_dir() else [root]
            for f in files:
                if not in_scope(f):
                    continue
                hits = scan(f.read_text(encoding="utf-8", errors="replace"))
                if hits:
                    total += len(hits)
                    print(report(f, hits) + "\n")
        print(f"총 {total}건" if total else "✅ 0건")
        sys.exit(1 if total else 0)

    # 훅 모드 — PostToolUse payload.
    payload = json.load(sys.stdin)
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return
    path = Path(raw)
    if not in_scope(path) or not path.exists():
        return
    hits = scan(path.read_text(encoding="utf-8", errors="replace"))
    if not hits:
        return
    json.dump(
        {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": report(path, hits),
        }},
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # fail-open — 세션을 wedge 하지 않는다
        sys.exit(0)
