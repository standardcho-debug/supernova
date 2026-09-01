#!/usr/bin/env python3
"""PreToolUse guard — Playwright MCP 스크린샷을 .artifacts/ 로 강제.

**왜 훅인가 (`.mcp.json --output-dir` 로는 못 막는다)**:
@playwright/mcp 는 `filename` 을 준 호출에서 `--output-dir` 을 통첐 우회하고,
그 이름을 *클라이언트 워크스페이스*(=프로젝트 루트) 기준으로 해석한다.
번들 코드(playwright-core/lib/coreBundle.js) 판정부:

    async resolveClientFile(template, title) {
      if (template.suggestedFilename)  // filename 을 준 경우
        fileName = await this.resolveClientFilename(...)  // path.resolve(clientWorkspace, name) = 루트
      else
        fileName = await this._context.outputFile(...)  // ← 여기서만 outputDir 적용
    }

즉 `--output-dir` 은 자동 생성 이름(page-*.yml·console-*.log)에만 듣는다.
2026-07-24 커밋 fbf9c40 이 이 인자를 넣고 "루트 png 누적 차단"이라 적었으나
이후 루트 png 70개가 그대로 쌊였다(트랜스크립트 전수: 경로 없는 filename 254회).
파일을 지워도 생성 경로가 그대로라 재발한다 → 기계 강제가 유일한 결정적 처방이다.

판정 원리:
  차단: filename 이 프로젝트 루트에 직접 떨어지는 경우(= 디렉터리 없는 맨 이름,
  또는 루트를 부모로 갖는 상대/절대 경로).
  통과: filename 미지정(자동 이름 → --output-dir 이 정상 동작) ·
  .artifacts/ 아래 · 루트가 아닌 다른 하위 디렉터리(클라 repo 등).

Fail-open: 파싱 오류·예외는 exit 0(허용) — 세션을 절대 wedge 하지 않는다.
"""
import sys, json, os

SUGGEST_DIR = ".artifacts/screenshots"


def deny(reason: str) -> None:
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout, ensure_ascii=False)
    sys.exit(0)


def main() -> None:
    payload = json.load(sys.stdin)
    filename = (payload.get("tool_input") or {}).get("filename")
    if not filename or not isinstance(filename, str):
        return  # 자동 이름 → --output-dir 이 듣는다

    root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    parent = os.path.realpath(os.path.dirname(os.path.join(root, filename)))
    if parent != root:
        return  # 하위 디렉터리로 명시됐다 — 루트 오염 아님

    base = os.path.basename(filename)
    deny(
        f"스크린샷이 프로젝트 루트로 떨어집니다 — filename='{filename}'.\n"
        f"`--output-dir` 은 filename 을 준 호출엔 적용되지 않으므로 경로를 직접 붙여야 합니다.\n"
        f"filename='{SUGGEST_DIR}/{base}' 로 다시 호출하세요"
        f"(클라 repo 산출물이면 그 repo 의 .artifacts/ 아래로)."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open
    sys.exit(0)
