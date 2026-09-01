#!/usr/bin/env python3
"""공유 파일(함대 규칙)을 편집하면 중립 코어 동기화를 상기시킨다.

함대 규칙은 두 repo 에 복제돼 있다 — internal `kangju1/supernova` 와 중립 코어
`kangju1/supernova-core`(여러 PM 공용). 한쪽에서만 고치면 다른 쪽 사람의 에이전트가
낡은 규칙으로 움직이는데 **빨간 불이 안 들어온다**. 좌표 유출보다 발견이 늘다.

끝 상태는 repo 하나다(운영자가 코어로 전환하고 internal 잔재는 중첩 repo 로).
이 훅은 그때까지의 안전장치이며, 차단하지 않고 상기시킨다 — 편집 자체는 정당하다.
"""
from __future__ import annotations

import json
import os
import sys

# 코어로도 가는 경로. internal 전용(infra/·triggers·onboard·원장·ops 실기록)은 제외.
SHARED_PREFIXES = (
    "CLAUDE.md", "README.md", ".claude/", "boilerplates/", "docs/references/",
    "docs/playbooks/", "docs/decisions/", "docs/designer/", "docs/interfaces/",
    "docs/gating/", "scripts/",
)
INTERNAL_ONLY = (
    "infra/", "scripts/gating/triggers/", "scripts/gating/onboard/",
    "docs/gating/promotion-ledger.json", "ops/",
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path:
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return 0
    if rel.startswith(".."):
        return 0  # repo 밖 — 무관

    if any(rel.startswith(p) for p in INTERNAL_ONLY):
        return 0
    if not any(rel.startswith(p) for p in SHARED_PREFIXES):
        return 0

    print(
        f"[core-sync] `{rel}` 은 중립 코어(kangju1/supernova-core)와 **공유되는 파일**이다.\n"
        "  한쪽만 고치면 다른 PM 의 에이전트가 낡은 규칙으로 움직이고, 그 사실은 아무도 모른다.\n"
        "  이 작업 단위를 마칠 때: `bash scripts/sync-core.sh --check` → 다르면 `--apply` 후\n"
        "  코어에서 좌표 스캔·커밋·push 까지 한다.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
