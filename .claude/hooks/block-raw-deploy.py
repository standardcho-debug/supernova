#!/usr/bin/env python3
"""PreToolUse guard — 클라 배포는 승격 원장 정문으로만.

Bash 명령이 클라 백엔드 배포를 *정문 우회*로 **실행**하려 하면 차단하고
scripts/gating/deploy.sh 로 redirect. 정문 우회 시 promo.py 의 check(게이트
판정)·record(무사고/인시던트)가 건너뛰어져 빨강→초록 사다리가 끊긴다.

CLAUDE.md 산문 규칙의 기계 강제판. 정본:
docs/decisions/2026-08-17-human-gate-to-machine-gate-red-to-green.md

판정 원리 (2026-08-17 정련 — ketovibe 온보딩 실측 오탐 반영,
2026-08-23 보강 — 원격 migrate/pull 을 초입에서 차단):
  substring "deploy" 로 막지 않는다(read-only 진단·가드 프로비저닝·git 조작 오탐).
  "배포를 *실행*하는가"로 판정한다.
  차단: deploy.sh/deploy-guard.sh 를 실행(sudo/bash/./로) · 수동배포(git pull|reset
  --hard + supervisorctl/systemctl restart) · 이를 SSM 페이로드로 원격 실행 ·
  **원격(ssh/ssm)에서의 manage.py migrate 또는 git pull/reset --hard**(반쪽 배포 예방).
  통과: 정문(scripts/gating/deploy.sh) · 읽기(cat/ls/curl/grep…) · git 조작(첫 토큰
  git — add/commit/diff/rev-parse) · 가드 프로비저닝(install/cp/tee 로 파일 배치) ·
  read-only SSM(cat/curl/rev-parse/supervisorctl status).

탈출구 (에이전트가 세션 내 사용 가능): 마커 파일
  ${CLAUDE_PROJECT_DIR}/.claude/.allow-raw-deploy 존재 시 통과.
  (인라인 env `VAR=x cmd` 는 훅 프로세스에 안 보이므로 마커 파일을 쓴다:
  touch .claude/.allow-raw-deploy → raw 작업 → rm. 지속 export env 도 병행 지원.)

Fail-open: 파싱 오류는 exit 0(허용) — 세션을 절대 wedge 하지 않는다.
"""
import sys, json, os, re

FRONT = "scripts/gating/deploy.sh"
READERS = {"cat", "less", "head", "tail", "grep", "egrep", "fgrep", "rg", "bat",
           "vim", "nano", "wc", "diff", "stat", "ls", "find", "awk", "sed",
           "cp", "mv", "chmod", "mkdir", "touch", "rm", "tee", "install", "curl", "echo"}

# deploy.sh / deploy-guard.sh 를 *실행*. 파일명 앞의 접두사도 포함해서 본다 —
# 클라별 가드는 `spnv-platform-deploy-guard.sh` 처럼 이름이 갈리므로
# (가드 파일명은 클라마다 다르고 플랫폼이 알려준다), `deploy` 로 시작하는 이름만 보면 정작 쓰이는
# 가드를 통첐 놓친다(회귀 2026-08-25). 두 형태:
# (A) 직접 실행: sudo /opt/x/deploy.sh · ./deploy.sh · ; /opt/x/deploy-guard.sh
# (B) 인터프리터: bash /opt/x/deploy.sh · sudo sh deploy-guard.sh
# 인터프리터는 *명령 위치*(^|;&||sudo)로 한정 — 안 그러면 `g.sh /opt/x/deploy-guard.sh`
# 처럼 다른 파일의 .sh 확장자를 sh 로 오인해 프로비저닝(install/cp)을 오탐한다.
# 실행 컨텍스트를 요구하므로 `cat …deploy.sh`·`install … deploy-guard.sh`·`git add …`는 통과.
_EXEC = re.compile(
    r"(?:^|[;&|]\s*|\bsudo\s+|\./)(?:/\S+/)?[\w.-]*deploy(?:-guard)?\.sh\b"
    r"|(?:^|[;&|]\s*|\bsudo\s+)(?:bash|sh)\s+(?:-\S+\s+)*(?:/\S+/)?[\w.-]*deploy(?:-guard)?\.sh\b")
# 수동 배포: (git pull | git reset --hard) 와 (supervisorctl|systemctl (re)start) 동반.
_GIT_PULL = re.compile(r"git\s+(?:-C\s+\S+\s+)?(?:pull|reset\s+--hard)")
_SVC_RESTART = re.compile(r"(?:supervisorctl\s+(?:restart|start)\b|systemctl\s+(?:restart|reload)\b)")
# 원격 실행 채널 — 로컬 dev 명령과 구분하는 유일한 신호. 명령 위치로 앵커하지 않는다:
# `timeout 300 ssh …`·`sudo ssh …` 처럼 래퍼가 하나만 붙어도 원격이 아닌 걸로 읽혀
# 정작 막아야 할 원격 마이그가 새다(회귀 2026-08-25). 대신 아래 _segments 로 조각을
# 나눠 *그 조각 안에서만* 채널과 페이로드를 짝짓는다.
_REMOTE = re.compile(r"\b(?:ssh|scp)\s|aws\s+ssm\s+send-command")
_MIGRATE = re.compile(r"manage\.py\s+migrate\b")


def _segments(cmd: str):
    """따옴표 *밖*의 top-level 구분자(; && || | & 개행)로만 나눈 조각들.

    원격 호출과 그 페이로드를 같은 조각에 묶기 위한 것이다. 나누지 않고 전체
    문자열에 정규식을 OR 로 걸면, 한 명령 안에 우연히 같이 등장한 무관한 토큰끼리
    짝지어져 read-only 진단까지 차단된다(회귀 2026-08-25):
    `aws ssm … 'commands=["git rev-parse HEAD"]' ; echo '로컬에서 manage.py migrate 필요'`
    따옴표 *안*의 구분자는 원격에 그대로 전달되는 페이로드의 일부라 자르지 않는다
    (`ssh h 'cd /srv && manage.py migrate'` 는 한 조각으로 남아야 걸린다).
    """
    segs, buf, quote, i, n = [], [], None, 0, len(cmd)
    while i < n:
        ch = cmd[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
        elif ch == "\\" and i + 1 < n:  # 줄 계속(\ + 개행) 포함 — 자르지 않는다
            buf.append(cmd[i:i + 2])
            i += 2
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            segs.append("".join(buf)); buf = []; i += 2
        elif ch in ";|&\n":
            segs.append("".join(buf)); buf = []; i += 1
        else:
            buf.append(ch)
            i += 1
    segs.append("".join(buf))
    return [s.strip() for s in segs if s.strip()]


def executes_deploy(cmd: str) -> bool:
    if _EXEC.search(cmd):
        return True
    if _GIT_PULL.search(cmd) and _SVC_RESTART.search(cmd):
        return True
    # 원격에서 마이그 적용·코드 전진 = 배포의 일부. 한 명령에 restart 가 같이 없어도
    # **여기서** 막아야 한다 — 안 그러면 pull 은 통과하고 migrate 만 분류기에 막혀
    # "코드만 올라가고 마이그 미적용" 반쪽 배포가 남는다(RCA 2026-08-23, banchan).
    # 그 상태는 가드의 noop 판정(SHA 동등)까지 무력화해 자동 복구도 안 된다.
    # 판정 단위는 조각이고, 채널 토큰 *뒤쪽*(= 원격에 전달되는 페이로드)만 본다.
    # 로컬 dev/test 의 manage.py migrate 는 조각에 채널 토큰이 없어 걸리지 않는다.
    for seg in _segments(cmd):
        hit = _REMOTE.search(seg)
        if not hit:
            continue
        payload = seg[hit.end():]
        if _MIGRATE.search(payload) or _GIT_PULL.search(payload):
            return True
    return False


def is_raw_deploy(cmd: str) -> bool:
    if FRONT in cmd:
        return False  # 정문
    first = (cmd.strip().split() or [""])[0].rsplit("/", 1)[-1]
    if first == "git":
        return False  # git add/commit/diff/rev-parse … 가드 파일 조작 허용
    if first in READERS:
        return False  # 읽기·복사·설치 등
    return executes_deploy(cmd)  # aws ssm 포함 — 페이로드에 실행 토큰이 있으면 걸림


def _escape_hatch() -> bool:
    if os.environ.get("SPNV_ALLOW_RAW_DEPLOY") == "1":
        return True
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.exists(os.path.join(proj, ".claude", ".allow-raw-deploy"))


def main():
    if _escape_hatch():
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # malformed → allow (fail-open)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd or not is_raw_deploy(cmd):
        return
    reason = (
        "🔴 클라 배포를 정문 우회로 실행하려 합니다.\n"
        "정문 우회 시 승격 원장의 check(게이트 판정)·record(무사고/인시던트 이력)가 "
        "건너뛰어져 빨강→초록 사다리가 끊깁니다.\n"
        "→ 대신: scripts/gating/deploy.sh <client> [op-type]\n"
        "정당한 예외(테스트·긴급 수동·가드 프로비저닝)면 마커 파일로 세션 내 우회:\n"
        "  touch .claude/.allow-raw-deploy → (raw 작업) → rm .claude/.allow-raw-deploy\n"
        "원리: docs/decisions/2026-08-17-human-gate-to-machine-gate-red-to-green.md · docs/gating/"
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
