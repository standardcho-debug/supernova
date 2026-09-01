#!/usr/bin/env python3
"""PreToolUse guard — 외부 소유 repo 에 우리 도구 파일이 남는 것을 막는다.

인수인계형 외주(프로젝트 repo 가 클라이언트 소유)에서, 우리 QA·에이전트 도구가
남의 저장소에 남으면 안 된다. 이 가드는 두 경로를 본다.

  1) Write/Edit/MultiEdit — 도구 파일 패턴 경로를 클라 소유 repo 안에 쓰려는 시도
  2) Bash — 쉘 리다이렉션/cp/tee 로 같은 짓을 하려는 시도,
     그리고 git add / git commit 로 그걸 굳히려는 시도

(2)가 핵심이다. 2026-08-25 세션이 실제로 만든 파일(apps/admin/.qa-mkcookie.mjs)은
Write 툴이 아니라 Bash 헤리도크로 생겼다 — Write 훅만으로는 못 잡는다.

## 소유 판정

경로에서 위로 걸어 .git 을 찾고 origin remote 를 본다. remote 가 우리 계정
(kangju1)이 아니면 클라 소유로 본다. registry 필드를 쓰지 않는 이유는 그쪽은
드리프트하지만 remote 는 자동으로 참이기 때문이다 (2026-08-26 clients/ 17개
전수에서 celest 만 정확히 갈림).

## 무엇을 막나

제품 코드 수정은 막지 않는다. 아래 도구 파일 패턴만 막는다 — 오탐을 0 에 가깝게
두기 위해 화이트리스트가 아니라 좋은 denylist 를 쓴다.

fail-open: 파싱·git 오류는 모두 exit 0(허용). 가드가 세션을 wedge 하지 않는다.

정본: docs/decisions/2026-08-26-external-repo-client-workspace.md
"""
import sys, json, os, re, subprocess

OUR_REMOTE_MARKERS = ("kangju1",)

# 도구 파일 패턴 — 경로 어디가 이 조각이 있으면 우리 것으로 본다.
TOOL_PATTERNS = (
    ".claude/",
    "docs/superpowers/",
    ".artifacts/",
    ".qa-",
    "qa-report",
    "mkcookie",
    "qa.config.yaml",
    "crystallization-ledger",
    ".mcp.json",
    "CLAUDE.local.md",
)

_GIT_ROOT_CACHE: dict = {}
_OWNER_CACHE: dict = {}


def git_root(path: str):
    d = path if os.path.isdir(path) else os.path.dirname(path)
    d = os.path.realpath(d or ".")
    if d in _GIT_ROOT_CACHE:
        return _GIT_ROOT_CACHE[d]
    cur = d
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            _GIT_ROOT_CACHE[d] = cur
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            _GIT_ROOT_CACHE[d] = None
            return None
        cur = parent


def is_client_owned(root: str) -> bool:
    """origin remote 가 우리 계정이 아니면 클라 소유."""
    if root in _OWNER_CACHE:
        return _OWNER_CACHE[root]
    try:
        url = subprocess.run(
            ["git", "-C", root, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        _OWNER_CACHE[root] = False  # 알 수 없으면 허용(fail-open)
        return False
    if not url:
        _OWNER_CACHE[root] = False
        return False
    owned = not any(m in url for m in OUR_REMOTE_MARKERS)
    _OWNER_CACHE[root] = owned
    return owned


def is_tool_path(path: str) -> bool:
    p = path.replace(os.sep, "/")
    base = os.path.basename(p)
    return any(t in p for t in TOOL_PATTERNS) or base.startswith(".qa-")


def deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def explain(paths, root) -> str:
    listed = "\n".join(f"  · {p}" for p in paths[:6])
    return (
        f"🔴 이 repo 는 **클라이언트 소유**입니다 ({os.path.basename(root)}). "
        "우리 도구 파일을 남기면 안 됩니다.\n"
        f"차단된 경로:\n{listed}\n\n"
        "→ 우리 자산은 **우산 워크스페이스**에 둡니다: "
        "`clients/<client>/qa/` · `clients/<client>/scripts/`\n"
        "→ 클라 패키지의 node_modules 가 필요해 스크립트를 만들려던 것이라면, "
        "파일 없이 실행할 수 있습니다:\n"
        "  `cd <클라repo>/<패키지> && node --input-type=module -e '...'`\n"
        "→ 스크린샷·리포트는 fleet `.artifacts/` 로 (force-screenshot-outdir 훅 참조)\n\n"
        "이 repo 에는 이미 다른 벤더가 남긴 .claude/ 3개와 docs/superpowers/ 15개가 "
        "커밋돼 있습니다. 같은 실수를 반복하지 않기 위한 가드입니다.\n"
        "정본: docs/decisions/2026-08-26-external-repo-client-workspace.md"
    )


# ── Bash 명령에서 쓰기 대상 경로를 추출 ────────────────────────
_REDIR = re.compile(r">>?\s*([^\s;|&]+)")
_TEE = re.compile(r"\btee\s+(?:-a\s+)?([^\s;|&]+)")
_CP_MV = re.compile(r"\b(?:cp|mv|install)\s+(?:-[^\s]+\s+)*[^\s]+\s+([^\s;|&]+)")
_TOUCH = re.compile(r"\btouch\s+([^\s;|&]+)")
_GIT_ADD = re.compile(r"\bgit\s+(?:-C\s+([^\s]+)\s+)?add\s+(.+?)(?:$|;|&&|\|\|)")
_GIT_COMMIT = re.compile(r"\bgit\s+(?:-C\s+([^\s]+)\s+)?commit\b")


def bash_write_targets(cmd: str):
    out = []
    for rx in (_REDIR, _TEE, _CP_MV, _TOUCH):
        out += [m if isinstance(m, str) else m[-1] for m in rx.findall(cmd)]
    return [t.strip("'\"") for t in out if t and not t.startswith("/dev/")]


def check_paths(paths, cwd):
    hits, root = [], None
    for p in paths:
        ap = p if os.path.isabs(p) else os.path.join(cwd, p)
        if not is_tool_path(ap):
            continue
        r = git_root(ap)
        if r and is_client_owned(r):
            hits.append(os.path.relpath(os.path.realpath(ap), r))
            root = r
    return hits, root


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()

    # ── 1) Write / Edit / MultiEdit ──────────────────────
    if tool in ("Write", "Edit", "MultiEdit"):
        fp = ti.get("file_path") or ""
        if not fp:
            return
        hits, root = check_paths([fp], cwd)
        if hits:
            deny(explain(hits, root))
        return

    # ── 2) Bash ────────────────────────────────
    if tool != "Bash":
        return
    cmd = ti.get("command") or ""
    if not cmd:
        return

    # 2a. 쉘로 파일을 만드는 경우
    hits, root = check_paths(bash_write_targets(cmd), cwd)
    if hits:
        deny(explain(hits, root))

    # 2b. git add — 인자 경로를 본다
    m = _GIT_ADD.search(cmd)
    if m:
        base = m.group(1) or cwd
        base = base if os.path.isabs(base) else os.path.join(cwd, base)
        args = [a for a in m.group(2).split() if not a.startswith("-")]
        # `git add -A` / `.` 처럼 전체를 담는 경우는 스테이징 결과로 판단
        if any(a in ("-A", "--all", ".", ":/") for a in m.group(2).split()):
            r = git_root(base)
            if r and is_client_owned(r):
                try:
                    untracked = subprocess.run(
                        ["git", "-C", r, "status", "--porcelain"],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.splitlines()
                    cand = [ln[3:].strip() for ln in untracked if ln[3:].strip()]
                    bad = [c for c in cand if is_tool_path(os.path.join(r, c))]
                    if bad:
                        deny(explain(bad, r))
                except Exception:
                    pass
        else:
            hits, root = check_paths([os.path.join(base, a) for a in args], cwd)
            if hits:
                deny(explain(hits, root))

    # 2c. git commit — 이미 스테이징된 것을 본다 (마지막 방어선)
    m = _GIT_COMMIT.search(cmd)
    if m:
        base = m.group(1) or cwd
        base = base if os.path.isabs(base) else os.path.join(cwd, base)
        r = git_root(base)
        if r and is_client_owned(r):
            try:
                staged = subprocess.run(
                    ["git", "-C", r, "diff", "--cached", "--name-only"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.split()
                bad = [s for s in staged if is_tool_path(os.path.join(r, s))]
                if bad:
                    deny(explain(bad, r))
            except Exception:
                pass


if __name__ == "__main__":
    main()
