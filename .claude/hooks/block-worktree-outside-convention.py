#!/usr/bin/env python3
"""PreToolUse guard — git worktree 는 정본 위치에만.

정본: `<spnv-root>/.worktrees/<client>/<name>` (fleet .gitignore 로 추적 제외).

왜 기계로 강제하나 (2026-08-27 실측):
함대 지침(2026-07-13 감독 세션 설계 §7)은 "동시 작업 세션은 worktree 격리"라고만
하고 **어디에 두라는 말이 없었다.** 그 결과 위치가 4종으로 갈렸고 둘이 `clients/`
바로 아래였다:
clients/ketovibe-inquiry ← 클라와 같은 위계·같은 이름 형태
clients/spnv-platform-worktrees/wt-* ← 컨테이너
그래서 **"clients/<x> = 클라이언트"라는 불변식이 깨졌고**, 그걸 믿은 도구가
worktree 를 클라로 오인해 결정화 원장을 중복 생성했다(같은 경로 원장이 두 브랜치에
생겨 병합 시 증거 0 이 실측 증거를 덮을 뻔했다).
superpowers using-git-worktrees 스킬의 기본값(.worktrees/)을 따랐어도 안 생겼을
일이지만 **안 따랐다** — 규약을 문서에만 두면 샌다는 것이 이미 실증됐다.

판정: `git worktree add <path>` 의 대상 경로가 `<repo-root>/.worktrees/` 밖이면 차단.
(list/move/remove/prune 등 다른 서브커맨드는 통과.)
Fail-open: 파싱 오류는 허용 — 세션을 wedge 하지 않는다.
"""
import sys, json, os, re, shlex

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
ROOT_REAL = os.path.realpath(ROOT)
CONV = os.path.join(ROOT_REAL, ".worktrees")
CLIENTS = os.path.join(ROOT_REAL, "clients")


def targets(cmd: str):
    """`git worktree add` 호출들의 대상 경로. 없으면 빈 리스트."""
    out = []
    for seg in re.split(r"&&|\|\||;|\|", cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            continue
        if len(toks) < 3:
            continue
        # `git [-C dir] worktree add <path>` 형태만
        if toks[0] != "git" or "worktree" not in toks or "add" not in toks:
            continue
        i = toks.index("worktree")
        if i + 1 >= len(toks) or toks[i + 1] != "add":
            continue
        cwd = ROOT
        if "-C" in toks[:i]:
            j = toks.index("-C")
            if j + 1 < len(toks):
                cwd = os.path.join(ROOT, toks[j + 1])
        for t in toks[i + 2:]:
            if t.startswith("-"):
                continue
            out.append(os.path.realpath(os.path.join(cwd, t)))
            break  # add 의 첫 비-플래그 인자 = 경로
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return
    # 지켜야 할 불변식은 "worktree 가 clients/ 아래에 있으면 안 된다"이다.
    # · repo 밖(세션 scratchpad·/tmp 의 throwaway) → 통과. 불변식을 안 깨고, 여기서
    #   막으면 정당한 격리까지 걸려 **무관한 차단이 반복되고 결국 가드를 끄게 된다.**
    # · repo 안 → 정본 .worktrees/ 아래여야 한다.
    bad = [
        p for p in targets(cmd)
        if p.startswith(CLIENTS + os.sep)
        or (p.startswith(ROOT_REAL + os.sep) and not p.startswith(CONV + os.sep))
    ]
    if not bad:
        return
    reason = (
        "🔴 worktree 를 정본 위치 밖에 만들려 합니다: " + ", ".join(bad) + "\n"
        f"정본은 `{CONV}/<client>/<name>` 입니다(fleet .gitignore 로 추적 제외).\n"
        "→ 예: git -C clients/<client> worktree add "
        f"{CONV}/<client>/<branch-name> -b <branch>\n"
        "이유: clients/ 아래에 worktree 를 두면 **클라이언트와 같은 위계가 되어** "
        "'clients/<x> = 클라' 불변식이 깨지고, 그걸 믿는 도구(QA 결정화 원장 등)가 "
        "worktree 를 클라로 오인합니다. 2026-08-27 실측 사고: 같은 경로 원장이 두 "
        "브랜치에 생겨 병합 시 증거 0 이 실측 증거를 덮을 뻔했습니다."
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
