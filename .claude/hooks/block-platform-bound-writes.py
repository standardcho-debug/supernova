#!/usr/bin/env python3
"""PreToolUse guard — spnv-platform SoT write protection.

Blocks Write/Edit/MultiEdit to repo-root directories that are owned by
spnv-platform (the single source of truth post 2026-06-01 cut-over):
    ops/responses/, ops/incidents/, ops/comms/, docs/prd/

Writing local files there creates orphaned data that diverges from the
platform DB — the exact failure that lost 4 Responder analyses on 2026-06-15.
Agents must call mcp__spnv-platform__create_document instead.

Anchored to the project root: client working copies under clients/<x>/...
(e.g. clients/ketovibe/docs/superpowers/plans/) are NOT affected.
Reads are never blocked (PreToolUse fires on Write/Edit/MultiEdit only).

Fail-open by design: any parsing error exits 0 (allow) so the guard can
never wedge the session; the doc-level §99 banners remain the backstop.
"""
import sys, json, os

PROTECTED = ("ops/responses/", "ops/incidents/", "ops/comms/", "docs/prd/")

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # malformed input → allow (fail-open)

    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return

    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        rel = os.path.relpath(os.path.realpath(fp), os.path.realpath(proj)).replace(os.sep, "/")
    except Exception:
        rel = fp.replace(os.sep, "/")

    if any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED):
        reason = (
            "🔴 이 경로는 spnv-platform 이 단일 SoT 인 디렉터리입니다 "
            "(ops/responses·incidents·comms, docs/prd — 2026-06-01 cut-over §99).\n"
            "로컬 파일 작성은 platform DB 와 분기되는 orphan 데이터를 만듭니다 "
            "(2026-06-15 Responder 분석 4건 유실 사고의 직접 원인).\n"
            "→ 대신 mcp__spnv-platform__create_document(kind=response|incident|comms-thread|prd, ...) 를 사용하세요.\n"
            "파일 사본이 꼭 필요한 예외라도 platform 등록(create_document)이 단일 SoT 이고, "
            "파일은 그로부터의 편의 export 일 뿐 — 절대 파일을 유일본으로 두지 마세요.\n"
            "상세: 각 함대 .md §99 + docs/decisions/2026-06-20-platform-soT-write-guard.md"
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
