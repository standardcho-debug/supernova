# SI Portfolio — Project Memory

이 디렉터리는 여러 SI 클라이언트 프로젝트의 운영 베이스다. **한 명이 100개까지 운영 가능한 구조**를 목표로 하며, 각 클라이언트는 자체 AWS 계정을 보유하고 본인 카드로 결제한다 (AWS 비용 격리 원칙 — 상세: [`docs/decisions/2026-06-18-cost-risk-clarity.md`](docs/decisions/2026-06-18-cost-risk-clarity.md)).

**원격 저장소**: 이 함대 자산은 두 곳에 있다 — 중립 코어 `kangju1/supernova-core`(여러 PM 공용, 클라 좌표 없음)와 internal 전용 `kangju1/supernova`(좌표·원장 스냅샷·가드 설치본). **두 곳의 공유 파일은 동일해야 한다** — `scripts/sync-core.sh --check` 가 검사하고 훅이 편집 시 상기시킨다. 좌표는 배포 정문이 플랫폼에서 런타임에 받는다. 변경은 항상 git 커밋 후 push 권장.

## 프로젝트 토폴로지

- 클라이언트별 sub-directory (`clients/<client>/`, 클라이언트당 하나) = 실제 프로젝트 코드 위치 (`.gitignore` 로 supernova 추적 제외, 각자 별개 repo)
- **클라이언트 유형 2종** — ① *우리 소유 repo*(기본, `kangju1/*`) ② **외부 소유 repo**(인수인계형 외주 — 프로젝트 repo 가 클라 소유). ②는 우리 도구·QA 자산이 그 repo 에 들어가면 안 된다. 유형 판정은 git remote 소유자로 한다. 정본: [`docs/decisions/2026-08-26-external-repo-client-workspace.md`](docs/decisions/2026-08-26-external-repo-client-workspace.md) · 유형 ② 현재 해당: `celest`
- **우산 워크스페이스 repo(`kangju1/<client>-workspace`)는 두 유형 모두에 쓴다** — 이유가 다르다. 유형 ②는 *클라 repo 에 우리 것을 넣을 수 없어서*, 유형 ①은 *컴포넌트별 repo 가 여럿이라 인프라를 넣을 단일 repo 가 없어서*(예: dodam 은 `dodam-commerce-front`·`dodam-commerce-server`·`mgmt-excel-builder`). 생성: `scripts/init-client-workspace.sh <client> <client-repo-dir>`.
  ⚠️ **`.gitignore` 는 allowlist 로 쓴다** — 그 디렉터리엔 클라 소유 코드 repo 와 DB 덤프(`_db_backups`)가 함께 산다. denylist 면 열거하지 않은 것이 올라간다(2026-09-01 이관 시 실제 위험).
- 각 클라이언트 프로젝트는 monorepo 표준: `frontend/` Next.js + `backend/` Django + `infra/` OpenTofu (신규 init 기본값 — 기존 클라는 컴포넌트별 다중 repo 다)
- **클라 인프라(OpenTofu)는 그 클라 repo 에 있다 — `clients/<client>/infra/`** (2026-09-01 fleet `infra/clients/` 에서 이관. 좌표가 fleet 에 있으면 담당 아닌 사람에게도 보인다). 그 디렉터리가 **어느 repo 인지는 클라마다 다르다** — 우산 워크스페이스이거나 제품 repo다. `git -C clients/<client> remote get-url origin` 으로 확인하고, **fleet 이 아니라 그 repo 에 커밋·push 한다**(fleet 에서 `git status` 를 봐도 안 뜬다).
  ⚠️ `infra/.gitignore` 가 state·프로바이더를 막는다. `*.tfstate` 는 리소스 속성을 평문으로 담아 시크릿이 들어갈 수 있고, `.terraform/` 은 수백 MB 다 — 둘 다 커밋 금지.
- 클라이언트별 별도 AWS 계정 (Organizations 사용 안 함)
- 운영자 접근: **클라이언트가 발급한 AWS Access Key** → `~/.aws/credentials` 의 `[client-<name>]` 프로파일로 보관 → OpenTofu `provider "aws" { profile = "client-<name>" }` 로 참조
- **유형 ①(우리 소유 repo)** 클라이언트 git 저장소는 `kangju1` GitHub 계정 (private). ⚠️ **"모든 클라"가 아니다** — **유형 ②는 클라 소유 계정**이다(실례: `celest/celeste` = `celeste-mapket/celeste`). 우리가 만드는 것은 그 위의 우산 repo `kangju1/<client>-workspace` 뿐이다.
- **prod DB 접속**: 직결 timeout (대개 접속 네트워크 egress 정책) 시 → [`docs/playbooks/db-access-ssm-tunnel.md`](docs/playbooks/db-access-ssm-tunnel.md) (SSM-backed SSH 터널). 클라이언트별 접속 파라미터는 플랫폼이 준다 — `GET /api/authz/deploy-check/?client=<slug>` 의 `tunnel` 블록(그 클라가 보이는 사람에게만). 2026-09-01 `infra/registry.yaml` 에서 이관(그 파일은 internal 잔재·동결 스냅샷).

## 보일러플레이트 (`boilerplates/`)

검증된 빌드 자산을 supernova 안에 보관해 에이전트가 직접 Read·참조 가능.

| 디렉터리 | 무엇 | 상태 |
|---|---|---|
| `boilerplates/backend-django/` | Django 5.2 LTS + DRF + MediaImage 얇은 스캐폴드 | ✅ |
| `boilerplates/frontend-nextjs/` | Next.js 16 + BFF + Auth.js v5 얇은 스캐폴드 | ✅ |
| `boilerplates/infra-aws-monorepo/` | OpenTofu 단일 스택 (EC2+RDS+S3+Amplify+GitHub+Secrets+Budget) | ✅ |
| `boilerplates/mobile-flutter-webview/` | Flutter 인앱웹뷰 셸 (2 flavor·PG·카카오 네이티브·fastlane) | ✅ |
| `boilerplates/workspace-external-repo/` | **외부 소유 repo 클라이언트**용 우산 워크스페이스 (도구·QA 자산 보관, 클라 repo 는 ignore) | ✅ |

신규 client init 시 `scripts/init-client-{backend,frontend,infra,flutter}.sh <client>` 한 줄로 cp+sed 자동화 (`flutter`는 모바일 앱 — 별도 트랙, `flutter-dev` 에이전트). 자세한 내부 동작·placeholder 표·다음 단계 안내는 각 보일러의 `README.md` + `scripts/README.md` 참조.

보일러 진화는 supernova 의 일반 commit — 같은 commit 안에 `.claude/agents/<x>.md`·`docs/decisions/...` 동기화. **별도 GitHub template repo 모델은 채택 안 함** (이유: 에이전트의 직접 접근성, [`docs/decisions/2026-05-29-boilerplates-in-supernova.md`](docs/decisions/2026-05-29-boilerplates-in-supernova.md) 참조).

## 에이전트 함대 (`.claude/agents/`)

**에이전트 목록·설명은 세션 시작 시 하니스가 자동 주입한다 — 여기에 표로 중복 기재하지 않는다**(2026-08-31 정리: 표와 주입 목록이 이중 관리되고 있었다).

- **빌드 함대**(신규 init·코드·인프라): `frontend-dev` · `designer` · `backend-dev` · `infra` · `flutter-dev` · `bizmsg-templates` · `bizmsg-console`
- **운영 함대**(감시·대응·커뮤·문서화): `watcher` · `responder` · `comms` · `librarian`
- **게이트·산출**: `qa`(배포 전 브라우저 검증 — GO/NO-GO 리포트, push·deploy·코드수정 권한 0) · `guide`(ship 한 과제의 사장님용 사용자 가이드 산출 — 클라 전달은 사람 게이트)

주입 목록에 없는 **기동 방식**만 여기 남긴다 — `watcher`(Routines cron + CloudWatch alarm) · `librarian`(**운영자 호출** — "패턴 정리해줘"·"라이브러리안 돌려". 2026-08-31 cron 자동실행에서 강등: 배선이 한 번도 된 적 없어 산출 0건이었다) · `responder`(Slack `/respond`) · `comms`(운영자가 텍스트 붙여넣기). 나머지는 Task tool 호출.

각 에이전트는 자기 영역만 책임. 영역 밖 코드 수정 금지 (해당 .md 의 게이트 섹션 참조).

## 슬래시 커맨드 (`.claude/commands/`)

**커맨드 목록·설명도 하니스가 자동 주입한다 — 표 중복 금지**(동 정리). 주입 설명에 안 실리는 **게이트·경로**만 남긴다:

- `/build-project` — 6 Phase, **사람 게이트 3회**
- `/estimate` — 크레딧 단독(원화 미노출), **draft 까지만. `send_estimate` 는 운영자 게이트**
- `/contract` — draft 생성까지. **자동 체결 안 함**
- `/fill-doc` — 툴킷 `scripts/fill-doc/docform.py`

견적 정본 절차: [`docs/playbooks/estimate-drafting.md`](docs/playbooks/estimate-drafting.md) (`/estimate`가 로드). 클라이언트용 [`docs/guides/2026-07-02-견적-정산-플로우-가이드.pdf`](docs/guides/2026-07-02-견적-정산-플로우-가이드.pdf)(사용자 가이드)와 구분.

**QA·가이드 keep-alive 라우팅** (main context 규칙): QA 타겟은 `scripts/qa/qa-env.mjs`(`up [--keep]`/`down`/`status`/`reap`)가 소유 — DB·프로세스 라이프사이클 결정적. **기본은 hermetic**(매번 fresh, 종료 시 drop). 단 운영자가 **"qa + 가이드"를 한 번에** 요청하거나 **QA→수정→재QA 반복 루프**를 명시하면, 그 흐름에 한해 **`--keep` 을 자동 사용**한다(물어보지 않음): `qa-env up <client> --keep` → guide 가 같은 keep env 에 attach(재시드 X, build+seed 1회) → **흐름 끝(가이드까지)에 `qa-env down <client>` 자동 teardown**. 격리는 유지(`*_qa` throwaway·dev DB/포트 충돌 거부·자기 pidfile 만·prod 무경로) + teardown 항상 붙어 orphan 0 → "hermetic 기본"이 지키려는 격리 불변식을 안 깬다. 단독 "qa 해주세요"(가이드·반복 언급 없음)는 hermetic 유지. 반복 루프 중 마이그 델타 없으면 seed 재사용(가장 비싼 단계 절약). 정본: [`docs/decisions/2026-07-10-qa-keepalive-reuse-seed-design.md`](docs/decisions/2026-07-10-qa-keepalive-reuse-seed-design.md).

디자인(브랜딩-정합)은 **`designer` 에이전트**가 담당: 비즈니스 컨셉 청취·레퍼런스 vision 관찰 → 아키타입 목업으로 2~3 방향 제시 → 운영자 육안 픽 → `deriveTokens` 토큰화 + `design/guidelines.md`. 설계 정본: [`docs/decisions/2026-07-08-designer-agent-design.md`](docs/decisions/2026-07-08-designer-agent-design.md). 화면-특정 레이아웃(재구성·신규 화면)은 3-티어로 designer(B/C 방향·픽)와 frontend-dev(A 구현)가 분담 — 정본: [`docs/decisions/2026-07-08-designer-bespoke-screen-design.md`](docs/decisions/2026-07-08-designer-bespoke-screen-design.md). (구 "디자인 레인" 3-벽돌 명령 모델은 이 에이전트로 대체됨 — 역사 spec은 supersede 노트로 보존.) **designer 자기개선 루프**: designer/frontend-dev 디자인 작업이 끝나면 main context 가 [`docs/designer/self-improvement.md`](docs/designer/self-improvement.md) §2 루브릭(8축)을 돌려 gap 을 §3 백로그에 append. 운영자가 **"개선 진행"**(또는 "디자이너 개선"·"개선 진행 N건") 하면 그 문서 §4 프로토콜을 실행 — 백로그 우선순위(severity×recurrence×leverage) 산정 → 이번 항목 1줄 통보 → 저리스크 자율 배선(편집·grep·단일 커밋). 정본: [`docs/decisions/2026-07-09-designer-self-improvement-loop-design.md`](docs/decisions/2026-07-09-designer-self-improvement-loop-design.md). **디자인 자산 도입 원칙("생성기만 공유")**: 외부 라이브러리/스킬(팔레트·폰트·스타일 카탈로그 등) 도입 판정은 *그 자산이 값을 주나 함수를 주나*로 결정 — 해결된 값(팔레트·결론)은 100클라 동질화라 배제, 생성기(커널·축·물음)만 seed 파이프 통과로 흡수. 또 designer 픽 직후 **40% 크리틱 패스**(위계·강조 관계·여백 리듬·브랜드 정합·보이스 정합 5축 심문) 필수. 실측 근거·정본: [`docs/decisions/2026-07-23-generator-not-value-and-40pct-critic-pass.md`](docs/decisions/2026-07-23-generator-not-value-and-40pct-critic-pass.md). **UX 라이팅 보이스도 같은 계보의 브랜드별 1급 자산**: 공유는 축(`docs/designer/voice-axes.md` 5축)+불변 레일(내부어 금지·사용자 쪽에서 쓰기·의문형 헤더 금지)뿐, 톤·어휘·예문은 제품별 `design/guidelines.md` `## 보이스·톤` 절에 착지(전역 톤 기본값 박기 금지). 절대-내부 토큰은 `check-internal-lexicon` lint 가 자동 차단(오탐 0). 산출·게이트: designer P4·P3.5 5번째 축, frontend-dev DoD. **불변 레일 자체는 카피 쓰는 누구에게나 적용(서브에이전트+main 인라인) — 아래 "커뮤니케이션·문체 규칙" 절의 UX 라이팅 규칙 참조.** 정본: [`docs/decisions/2026-07-28-designer-voice-tone-brand-asset.md`](docs/decisions/2026-07-28-designer-voice-tone-brand-asset.md)(ship 시 승격).

**도메인 큐레이터 트리거** (지식 substrate 유지): 운영자가 **"도메인 큐레이터 돌려"**(또는 "큐레이터 패스"·"도메인 어휘 점검") 하면, spnv-platform runbook `runbook/supernova-platform/domain-curator-pass.md`(read-only 탐지 패스)를 그대로 실행 — `uncategorized` 배수·신규 도메인 승격·동의어 병합 후보를 `decision` 리포트로 surface(적용은 운영자 판단 = Piece 1b). 즉흥 재구성 금지, runbook 정본을 따른다. 정본: [`docs/decisions/2026-07-20-domain-curator-detection-pass-design.md`](docs/decisions/2026-07-20-domain-curator-detection-pass-design.md).

**git worktree 정본 위치 (2026-08-27 운영자 확정)**: 클라 repo 의 격리 작업 공간은 **`<spnv-root>/.worktrees/<client>/<name>`** 에 만든다(fleet `.gitignore` 로 추적 제외). **`clients/` 아래에 worktree 를 두지 말 것** — 클라이언트와 같은 위계가 되어 *"`clients/<x>` = 클라이언트"* 불변식이 깨지고, 그걸 믿는 도구가 worktree 를 클라로 오인한다(2026-08-27 실측: `clients/ketovibe-inquiry` 를 클라로 오인해 QA 결정화 원장을 중복 생성 → 같은 경로 원장이 두 브랜치에 생겨 병합 시 증거 0 이 실측 증거를 덮을 뻔함). 세션 scratchpad 의 throwaway worktree 는 repo 밖이라 무관. **PreToolUse 훅 `block-worktree-outside-convention.py` 가 기계로 강제** — 규약을 문서에만 두면 샌다는 것이 이미 실증됐다(2026-08-17 세션이 superpowers 스킬 기본값 `.worktrees/` 를 안 따르고 즉흥 경로를 골랐음).

## 핵심 운영 원칙

1. **에이전트끼리 직접 통신 X** — 메인 컨텍스트가 Task tool 로 호출, 결과는 파일로 핸드오프
2. **리스크 기반 게이트** — 5축 리스크 스코어(롤백·비용·프로덕션·보안·되돌림) 총점으로 게이트 수준 결정
   - **0-2점**: 자율 실행 (plan 보고 후 자동 apply) — 보일러 표준 init이 여기 해당
   - **3-5점**: 사람 게이트 (plan + 리스크 스코어 제시 → 승인 후 apply)
   - **6-10점**: 사람 게이트 2단계 (영향 분석 + 롤백 계획 → 2회 confirm)
   - 자세한 축·점수표는 `infra.md §5.2` + [`docs/decisions/2026-06-18-risk-based-gating.md`](docs/decisions/2026-06-18-risk-based-gating.md) 참조
2.5. **클라 백엔드 배포는 정문으로만** — `bash scripts/gating/deploy.sh <client> [op-type]`. **raw `ssh`/`aws ssm` 로 `git pull`·`manage.py migrate`·`supervisorctl restart` 를 직접 실행하지 말 것**(PreToolUse 훅이 차단·유도). 정문이 하는 일: 승격 원장 게이트 판정 → 박스 가드 트리거(known-good SHA → **safe 마이그 자동 적용**(순수 additive) → 배포 → 2겹 헬스체크 → 실패 시 자동 롤백) → 무사고/인시던트 원장 기록. 정문을 우회하면 **빨강→초록 사다리가 끊기고**, 코드만 올라가고 마이그가 안 된 **반쪽 배포**가 남는다(가드의 noop 판정까지 무력화). 클라별 트리거 파라미터는 그 클라 배포 런북 참조 — 런북은 정문 호출을 먼저 적고, raw 절차는 정문 실패 시 진단용으로만 둔다. 정본: [`docs/decisions/2026-08-17-human-gate-to-machine-gate-red-to-green.md`](docs/decisions/2026-08-17-human-gate-to-machine-gate-red-to-green.md) · 온보딩 [`docs/gating/onboarding.md`](docs/gating/onboarding.md). (근거: 2026-08-23 RCA — 런북이 게이트보다 앞선 raw 절차만 담고 있어 세션이 충실히 따를수록 반쪽 배포로 wedge 됐음.)
3. **모든 핸드오프는 파일** — 휘발성 컨텍스트 의존 금지
   - **빌드 함대**:
     - `clients/<client>/infra/outputs.json` — OpenTofu outputs (RDS endpoint, EC2 IP 등)
     - `<client>/backend/schema.yml` — drf-spectacular OpenAPI schema 발행 위치
     - `<client>/frontend/schema.yml` — orval 이 빌드 시 참조하는 위치
     - 클라이언트별 상태·인프라 메타데이터 — 플랫폼 `Client` 행(`mcp__spnv-platform__list_clients`). 좌표는 `deploy-check` 로만 나간다
   - **운영 함대**:
     - `ops/incidents/<client>-<alarm-id>.md` — Watcher 출력 → Responder 입력
     - `ops/responses/<client>-<alarm-id>.md` — Responder 출력
     - `ops/comms/<client>-thread-<id>.md` — Comms 출력
     - Librarian 산출(패턴·digest)은 **플랫폼 DB** — `kind="concept"`·`kind="digest"`, `client="_system"`. ⚠️ 구 경로 `docs/patterns/`·`docs/digests/` 는 cut-over 로 폐기됐고 디렉터리도 없다(2026-08-31 확인). 정본: `librarian.md` §2.3·§99
   - **핸드오프 프로토콜** (`docs/decisions/2026-06-18-handoff-protocol.md`):
     - Atomic write (`.pending` → rename)
     - Stale detection (`.meta` TTL)
     - Conflict prevention (single producer per path)
     - Retry/timeout (notification-based, not polling)
4. **재현 가능 우선** — AWS 콘솔 직접 변경 금지 (drift 의 원천)
5. **풀 라이프사이클 모델** — 한 에이전트가 한 도메인 코드의 전체 이력을 책임
6. **신규 init 은 보일러 우선** — frontend/backend 신규 init 은 항상 `boilerplates/{backend-django,frontend-nextjs}/` 의 검증 자산을 cp+sed 로 시작. from-scratch (`create-next-app`, `django-admin startproject`) 금지.

## 용어·약자 컨벤션 (2026-06-03 도입)

이 repo 안에는 두 개의 독립 시스템이 있고, 약자 충돌이 운영 혼선의 원천이었음 (2026-06-02 한 클라이언트 작업에서 메인 컨텍스트가 두 시스템을 혼동) → **단독 "spnv" 사용 금지**.

| 용어 | 의미 | 위치 |
|---|---|---|
| **spnv-fleet** | 함대 자산 = 빌드 함대 + 운영 함대 + 보일러 + 결정 문서. 작업의 *주체* | 중립 코어 `kangju1/supernova-core` + internal 잔재 `kangju1/supernova` |
| **spnv-platform** | **생산화된 PM-as-a-service** — 1인 PM이 100 프로젝트를 매니징하는 시스템(개발=AI 자동, 사람 PM의 소통·요건판단·일정이 희소가치). 그 PM의 연장이 대면 비즈니스 플랫폼(`Client → Venture → 서비스`: 코파운더·forge·estimates·billing·지갑/정산)이며, 커널은 동시에 함대 데이터 substrate. 두 가격 레이어: ①플랫폼 이용료 ②PM 고용. **방향·전략 정본: [[docs/decisions/2026-08-02-pm-as-a-service-repositioning.md]]**; 구조: [[docs/decisions/2026-07-09-spnv-platform-multi-service-architecture.md]] | `clients/supernova-platform/` · **클라우드**: `cofounder-api.jengablock.com`(백엔드/MCP) · `spnv.jengablock.com`(프론트) · forge 프리뷰 `<slug>.jengablock.com` |
| **supernova** | 위 둘을 묶는 브랜드 우산 (GitHub repo 이름) | — |

**규칙**:
- 약자 "spnv" 단독 사용 금지. 항상 `-fleet` 또는 `-platform` 접미사 명시 — 메모/대화/결정 문서/커밋 메시지 공통.
- 기존 문서·메모리의 단독 "spnv" 표기는 in-place 정정 안 함 (cost ↔ benefit). 새로 작성하는 것부터 적용.

## 커뮤니케이션·문체 규칙

- **은유·비유 표현 금지** — 진단·분석·보고에서 "자가 봉합", "꼬였다", "숨을 쉰다", "치유", "봉인" 같은 비유/의인화 표현을 쓰지 말 것. 무슨 일이 일어났는지 **문자 그대로** 서술한다. 예: "자가 봉합됨" (X) → "연기 조작으로 스케줄이 7/22 정규값과 정확히 동일해짐 — 의도된 수정이 아닌 우연한 일치" (O). 정확한 사실 서술 > 압축적 은유. (2026-07-12 운영자 지시)
- **클라이언트 대면 산출물은 규격 고정 — 매번 새로 디자인 금지** — 진척 현황 카드 등 반복 산출물은 세션마다 임의로 재디자인하지 말고, 정본 템플릿을 **먼저 Read 하고 데이터만 치환**한다. **진척 현황 카드 정본**: [`docs/references/progress-card-template.html`](docs/references/progress-card-template.html) (표 형식 항목·배포일자·상태·비고, 딥 슬레이트 헤더 = 전 클라이언트 공용·클라이언트 브랜드색 아님, 풀블리드·콤팩트, 크레딧/원화 미노출). 디자인 변경은 개별 카드가 아니라 이 템플릿 파일을 고쳐 반영. (근거: 2026-07-16 진척 카드 포맷 세션간 드리프트로 운영자 규격화 지시 — 알림톡 브랜드 접두 사고와 동일 계열. [[docs/references/progress-card-template.html]])
- **클라이언트 통화·미팅 정리는 회의록 정본 템플릿 사용 — 정본 2종, 성격에 따라 분기** — 매번 새로 디자인하지 말고 **정본을 먼저 Read 하고 데이터만 치환**한다. 판단 기준: 산출물이 **"할 일 목록"이면 ①**, **"무엇을 왜 그렇게 하기로 했는가"면 ②**.
  - **① 간이형** [`docs/references/meeting-minutes-template.html`](docs/references/meeting-minutes-template.html) — 통화로 논의한 처리 항목 정리. 오류 수정/기능 개선/신규 기능/진행·확인 4구획 + 상태 배지, 딥 슬레이트 헤더 카드형. 예: dodam 기능 요청 통화.
  - **② 전략형** [`docs/references/meeting-minutes-strategy-template.html`](docs/references/meeting-minutes-strategy-template.html) — **신규 클라이언트 킥오프·사업 방향·로드맵·협업/계약 구조 등 중대 사안**. A4 백서 규격(표제 → 개요표 → 한 줄 요약 → 주제별 번호 섹션 → **합의 사항** → **향후 결정 사항**), 황색 음영 = 핵심 구간, 인쇄·PDF 전달 지향. 두 섹션은 필수("미결 사항" 표기 금지). 문체는 **공문서 개조식**(~함/~임/~됨), 자사 측 참석자는 이름만 표기. 예: 2026-08-22 맵켓 개발 방향 워크샵, 2026-08-11 셀리스트 미팅.
  - 공통: 라이트/다크·인쇄 대응, 크레딧/원화·내부용어(file:line·repo·감독/작업세션 등) 배제, **특정 개인의 업무 수행에 대한 평가·추정 금지**(사실 관계만), Artifact 게시 favicon 📋. 섹션·구획은 내용에 맞게 가감. 디자인 변경은 개별 회의록이 아니라 템플릿 파일을 고쳐 반영. (근거: 2026-07-22 규격화 지시 + **2026-08-22 운영자 지시** — 간이 통화 회의록과 중대 사안 회의록의 형식 분리. 참조 규격: 엘라스타 미팅 회의록. [[docs/references/progress-card-template.html]])
- **견적서는 정본 양식으로만 — 매번 새로 조판하지 말 것** — 클라이언트에 보내는 견적서는 [`docs/references/quotation-template.html`](docs/references/quotation-template.html) 규격이며, 생성기는 `scripts/make-quotation.py`(견적 JSON → A4 HTML → Chrome PDF)다. 기준 규격은 운영자 제시 `젠가블록 견적서 양식.pdf`(2026-08-27 셀리스트 확인필). **로고·직인 이미지는 `docs/contracts/_assets/`(gitignored — 직인은 서명에 준하므로 git 에 올리지 않는다)**, 생성기가 base64 로 인라인한다. 견적 JSON 도 `docs/contracts/<client>/`(gitignored). 소계·합계·최종금액 행의 음영과 2단 메타 표는 규격이므로 임의 변경 금지. **HTML 첫 줄 `<meta charset="utf-8">` 필수** — 없으면 Chrome 이 로케일 기본값으로 해석해 한글이 전부 깨진다(2026-08-27 실제 발생). 견적서는 크레딧 규약의 예외로 **원화를 표기**한다(계약서·조건안과 동일).

- **가격 안내는 정본 가격표를 쓴다 — 매번 새로 만들지 말 것** — 크레딧 단가·이용 방식을 클라이언트에게 안내할 때는 [`docs/references/pricing-sheet.html`](docs/references/pricing-sheet.html) 를 Read 해 값만 갱신하고 A4 PDF 로 렌더한다(Chrome `--print-to-pdf`). **하드룰 5개**: ① 요금표에 **할인율 표기 금지**(정가 노출은 의도된 것이나 "50% 할인"을 우리가 먼저 말하지 않는다 — 갱신 시 할인 축소가 "인상"으로 읽힘) ② **400크레딧 이상 충전 단위 신설 금지**(3개월 만료 안에 소진 불가능한 상품 = 만료 분쟁) ③ 작업 유형에 **특정 고객 도메인 용어 금지**(범용 가격표) ④ **FIFO(먼저 생성된 크레딧부터 소진) 삭제 금지** — 없으면 새 크레딧을 먼저 쓰고 오래된 것이 만료돼 계속 쓰는 고객도 매달 잃는다(3개월 일괄 만료 정책의 성패가 이 한 줄) ⑤ **우리 결함으로 인한 장애 대응은 무상** 삭제 금지 — 운영 구독을 없앤 대신 명시하는 것으로, 없으면 우리가 낸 버그를 고객 크레딧으로 차감하는 구도가 된다. 규범·근거 정본: spnv-platform `decisions/_shared/2026-08-24-credit-pricing-policy.md`. 크레딧 기준값 근거는 [`docs/playbooks/estimate-drafting.md`](docs/playbooks/estimate-drafting.md) 의 실측 앵커. **계약서 산출은 별도 정본** — [`docs/templates/README-contracts.md`](docs/templates/README-contracts.md)(유형 분기·.docx 파이프라인·검증은 Word 아닌 LibreOffice 렌더). (근거: 2026-08-24 가격 정책 확립 세션.)

- **사용가이드는 정본 파이프라인만 — Artifact·손그림 목업 절대 금지** — 사용자 가이드(운영자·클라 전달용, spnv-platform 자체 기능 포함)를 만들 때 **Artifact(웹페이지)나 손으로 그린 목업/일러스트로 만들지 말 것.** 반드시 **`guide` 에이전트 정본 파이프라인**을 쓴다: **QA가 로컬+폐기형 seed DB로 실제 화면을 렌더·데이터 시딩·캡처한 *실 스크린샷* 재활용 → A4 가로 자체완결 HTML→PDF(guide 엔진 `guide/gen-guide.mjs`, 오버플로 게이트·한글 word-break 보존) → `mcp__spnv-platform__create_asset` 로 드라이브 정본화**(`files/<client>/guides/<date>-<topic>.pdf`) → change-log 에 wikilink fold. **"실 화면 렌더링 + 데이터 시딩" 필수**(목업 금지 — 목업은 규격 위반). 정본: `.claude/agents/guide.md`·`.claude/commands/guide.md`. ⚠️ **spnv-platform 자체 기능 가이드도 동일** — 플랫폼 `frontend/` 에 guide/QA 엔진이 없으면 **먼저 클라 repo(dodam 등)에서 이식**하고 파이프라인으로 산출한다(엔진 부재를 Artifact 즉흥의 핑계로 쓰지 말 것). (근거: 2026-08-14 운영자 지시 — 플랫폼 가이드를 반복해서 Artifact+목업으로 만든 실수. 진척카드·회의록 규격화와 동일 계열.)

- **화면 디자인 시안 제안서는 정본 템플릿으로 — 매번 조판하지 말 것** — 클라이언트에게 화면 안(1~3개)을 제시하고 픽을 받는 문서는 [`docs/references/design-proposal-template.html`](docs/references/design-proposal-template.html) 를 **먼저 Read 하고 데이터만 치환**한다. 장 구성 고정(표지 개요표 → 현행 화면 → 개선안 N장 → 비교·추천·확인 요청), 안 개수·상태별 장만 가변. **하드룰**: ① **제목은 명사구** — 서술형·의문형 금지(`문의 답변 화면을 다시 짜는 두 가지 방향`·`나란히 놓고 보실 수 있게`·`무엇이 편지처럼 보이게 하는가` ✗ / `1:1 문의 답변 화면 개선안`·`현행 화면`·`비교` ○) ② **em dash 부제 금지**(`제목 — 부연` 은 영어 편집 관습) ③ **문서가 자기 자신을 설명하지 않는다**(그 장이 왜 있는지 쓰지 말 것 — 화면이 옆에 있으면 배치가 말한다) ④ **본문은 문단이 아니라 항목**(라벨 아래 명사구로 끊고, 화면을 말로 다시 설명하는 문단은 전부 삭제) ⑤ **온기는 인사·맺음말에만** — 제목·라벨마다 존대와 안심을 바르지 않는다 ⑥ **중간 결론 문장 금지**(`이 두 가지는 공통입니다` 류는 영어 단락 구조의 잔재) ⑦ 서술형 문장은 **추천 문단 하나**에만 허용, 추천이 뒤집히는 조건을 반드시 적는다 ⑧ 캡처는 **실 렌더 실물만**, 오류 화면(지도 로드 실패 등)이 섞였으면 잘라내고 쓴다. 렌더 후 **전 페이지 래스터화 육안 확인 의무**(구조 검증만으로 GO 금지). (근거: 2026-08-30 운영자 지적 — *"영어로 먼저 쓰고 한국어로 직역한 느낌입니다. 한국어 정서에 맞지가 않아요."* 원인은 문장 골격이 영어에서 잡히고 어휘만 한국어로 갈아입는 것 + 제목·라벨을 매번 **지어내는** 것. 어휘를 지어내지 않고 **고르게** 만들어 번역체가 끼어들 자리를 없앤다. 진척카드·회의록·견적서 규격화와 동일 계열.)
- **클라 대면 UX 라이팅 불변 레일 (main 인라인 작성 시에도 적용)** — 클라이언트가 볼 카피(화면 텍스트·회신·채팅·문서)를 frontend-dev/designer dispatch 없이 직접 쓸 때도 5개 레일을 지킨다: ① 내부·시스템 어휘(file:line·repo·감독/작업세션·serializer·endpoint 등) UI 노출 금지 ② 화면의 사용자 쪽에서 쓰기(시스템이 자기 행동을 1인칭/의문형으로 말하지 않음) ③ 의문형 AI-호스트 헤더 금지("무엇을 했나요"→"작업 결과") ④ 라벨=명사구·오류=사용자가 할 다음 행동 ⑤ **자칭 "저희" 금지 — 주어를 빼거나 "제가"로 쓴다**(클라이언트는 젠가블록을 복수 인원이 아니라 담당자 한 사람으로 인식한다. "저희가 확인하겠습니다"(X) → "확인하겠습니다"/"제가 확인하겠습니다"(O)) ⑥ **과잉 사과·자책 언어 금지** — "탓이 큽니다"·"죄송합니다"·"제 착오로 혼선을 드렸습니다"·"숨기지 않고" 류를 붙이지 않는다. **사실 → 현재 상태 → 다음 액션** 으로 끝낸다("이미 된다고 말씀드렸는데 확인 결과 아직 안 되어 있습니다. 견적에 넣을지 알려주시면 반영하겠습니다"). 정정 자체는 정확히 하되 사과문을 덧대지 말 것 — 반복되면 신뢰가 아니라 불안을 준다. 레일 ⑤·⑥ 은 회신·카톡·메일·견적 문구·화면 카피 전부 해당. **전달 형식**: 운영자가 복붙할 클라 대면 텍스트는 코드블록으로 감싸되 **수동 줄바꿈(하드랩) 금지 — 문단·항목당 한 줄**로 쓴다. 카톡·메일이 자체적으로 줄을 접으므로, 하드랩을 넣으면 문장이 중간에 끊겨 보인다(빈 줄로 문단 구분만). (2026-08-27 운영자 지시) 브랜드별 톤·어휘는 그 클라 `design/guidelines.md` `## 보이스·톤` 절(있으면 Read). 축·상세: [[docs/designer/voice-axes.md]]. (근거: 2026-07-27 포털 카피 AI톤 사고 + 2026-07-28 콜드세션 실측 — 레일이 서브에이전트 프롬프트에만 있으면 인라인 경로로 누수·미발견.)

## 메타 작업 (회고·감사·분석) 컨벤션

메인 컨텍스트가 cross-system 분석할 때 — 과거 cross-system 혼선 같은 실수 재발 방지:

- **시스템 태그 의무**: 모든 P0/P1/갭 항목 첫 줄에 `[spnv-fleet]` / `[spnv-platform]` / `[<client-slug>]` 명시
- **메모리 인용 시**: `[memory:<name>]` 표기 + 3일 이상 된 메모리는 점검 명령 1개로 verify 후 인용. memory 사용 원칙(시스템 프롬프트 "Before recommending from memory") 엄격 적용
- **사용자 ack 게이트**: 사용자가 "진행해주세요" 라 응답하면, 다음 액션 1줄을 먼저 명시(어느 시스템·어느 작업·어떤 명령)하고 ack 받은 후 시작

## 기술 스택 (신규 init 기본값 — 유형 ① 우리 소유 repo)

- **Frontend**: Next.js (App Router) + TypeScript + pnpm + Tailwind + shadcn/ui + orval + TanStack Query + Auth.js + Vitest/Playwright + Biome
- **Backend**: Django 5.x + DRF + uv + ruff + mypy + pytest-django + drf-spectacular + SimpleJWT
- **Infra**: OpenTofu + cloud-init + GitHub App + Amplify (default region `ap-northeast-2`)
- **EC2 환경**: Ubuntu LTS + Supervisor + Nginx + uwsgi/asgi + Let's Encrypt
- **DB**: PostgreSQL 16 (RDS)
- **시크릿**: AWS Secrets Manager 통일

⚠️ **"모든 클라이언트 공통"이 아니다** — 이건 *우리가 새로 만들 때의 기본값*이지 현황이 아니다.
- **유형 ② 외부 소유 repo(인수인계형 외주)는 그 repo 의 스택을 따른다.** 실례: `celest` = pnpm + turborepo 모노레포(apps: admin·hq·order·bot-extension) + **Supabase**(Django 없음, `bot-extension` 은 Next 도 아닌 vite). 우리가 고른 스택이 아니라 넘겨받은 것이라 이 표가 적용되지 않는다.
- **기존 클라의 실제 스택은 그 repo 코드가 정본이다** — 버전도 제각각이다(2026-08 기준 Next 13.4 ~ 16.2). 여기 적힌 버전으로 단정하지 말 것.

상세 결정·이유·컨벤션은 각 에이전트 `.md` 본문 참조.

## 디자인 결정·이력

- `docs/decisions/` — 큰 디자인 결정의 brainstorming 결과·이유 (날짜순)
- 새로운 큰 결정 시 새 파일 (`YYYY-MM-DD-<topic>.md`) 추가
- 결정의 *why* 를 먼저, *how* 는 에이전트 `.md` 가 들고 있음
- **`docs/superpowers/` 는 gitignored 워킹 파일** — brainstorming/writing-plans/subagent-driven 산출물(spec·plan·brief·qa-report)은 born-local·die-local. git force-add 금지. 내구 기록은 ship 시 **platform change-log**(+ 영향 policy revision), **근원적 fleet 결정에 한해** `docs/decisions/` 로 손 승격. 클라 제품 설계는 platform decision 으로. 근거: [`docs/decisions/2026-07-20-superpowers-lifecycle-git-hygiene.md`](docs/decisions/2026-07-20-superpowers-lifecycle-git-hygiene.md).

## 함대 간 인터페이스 계약

- `docs/interfaces/build-to-ops.md` — 빌드 함대 ↔ 운영 함대 인터페이스 SSoT (로깅·alarm·IAM·에러 트래킹)
- 양쪽 에이전트 `.md` 가 이 문서를 reference. 단독 명세 작성 금지 — 충돌 시 이 문서가 truth.

## 보류 중인 작업

- **designer 고도화 로드맵** (2026-07-24 도출, 미착수) — 3 프런티어 후보: A 디자인 드리프트 가디언(추천 1순위·init→lifetime) / B cross-client 판단 축 라이브러리 / C 컴포넌트 캐릭터 층. 착수 시 각각 brainstorm→spec→plan.  
  → [`docs/decisions/2026-07-24-designer-advancement-roadmap.md`](docs/decisions/2026-07-24-designer-advancement-roadmap.md)
- **QA 시스템 고도화 로드맵** (2026-08-18 도출) — **E1(결정화=배포 승격 통합 원장)·A1(ketovibe `qa_seed`→admin 11/11 crystallized) 완료·ship(2026-08-18~20)**; **§F(배포-시점 깊이)는 §F 재평가로 풀빌드 이연**(트리거 기준 기록). **알려진 상태**: crystallized spec은 render-깊이라 green이 기능 거동을 보증 안 함(#4). 열린 후보(랭킹 미확정·pick 없음): A2(spec-0 클라 확대)·D2(dodam authed 복구)·B2(프론트 배포 verifier)·E3(QA↔가이드)·거동 spec 깊이(A)·에이전트-게이트(B).  
  → [`docs/decisions/2026-08-18-qa-system-advancement-roadmap.md`](docs/decisions/2026-08-18-qa-system-advancement-roadmap.md)
- **결정적·자기개선 함대 비전 (북극성)** (2026-08-18) — 배포(게이팅=구현됨)·QA(결정화=로드맵)를 잇는 관통축: *"비싼 판단 한 번 → 결정적으로 얼려 기계로 강제, 잘 쓸수록 싸지는 하나의 earn 루프"*. 영상(루프→그래프)에서 도출. 새 세션이 방향 전체를 grok 하고 이어갈 **진입점** — 개별 트랙 전술문서(2026-08-17 게이팅·2026-08-18 QA 로드맵)의 허브.  
  → [`docs/decisions/2026-08-18-deterministic-self-improving-fleet-vision.md`](docs/decisions/2026-08-18-deterministic-self-improving-fleet-vision.md)
- **SI 100 운영 함대 (Watcher / Responder / Comms / Librarian)** 디자인  
  → `docs/decisions/2026-05-28-solo-100-phase1-design.md` 의 진행 상태 참조
- ~~**git rm 클라이언트 데이터 원본**~~ — **완료(2026-08-31 확인)**. `docs/runbook-*`·`docs/infra-snapshot-*` 는 이미 삭제됐고 `docs/prd`·`ops/incidents`·`ops/comms` 는 `.gitkeep` 만 남았다. 데이터 SoT 는 spnv-platform DB.
  ⚠️ **`ops/*` 디렉터리와 `.gitkeep` 은 지우지 말 것** — 운영자가 건별로 *"파일을 이번 건의 정본으로"* 지시하는 예외 경로가 살아 있다(실례: `ops/responses/dodam-dodam-app-error-warn-20260831T051930Z.md`, 플랫폼 DB 쪽이 그 사본임을 본문에 명시). 그때 쓸 자리가 필요하다.

## spnv-platform (2026-06-01 cut-over 이후)

**정체성 (먼저 읽을 것)**: spnv-platform 은 **생산화된 PM-as-a-service** — *1인 PM이 100 프로젝트를 매니징하는 시스템*. **자동화된 것은 개발(AI)이고, 남은 희소가치는 PM 업무**(대표 소통·막연한 의도→요건정의·일감/일정 관리·판단)다. 우리가 만든 모든 것은 그 PM의 연장이다. 표면은 대면 온라인 비즈니스 플랫폼(내부 백오피스 아님), 위계는 `Client → Venture → 서비스`.

**배경 상세는 중복하지 않는다** — 고객유형(proxy-PM/self-PM)·두 가격 레이어·forge·유닛 이코노믹스는 정본이 들고 있다. 방향 판단이 필요할 때 읽는다: 포지셔닝 [[docs/decisions/2026-08-02-pm-as-a-service-repositioning.md]] · 구조 [[docs/decisions/2026-07-09-spnv-platform-multi-service-architecture.md]] · forge [[docs/decisions/2026-07-18-prompt-to-app-preview-platform-design.md]] · 가격전략 [[docs/decisions/2026-08-01-pricing-strategy-and-market-validation.md]]

아래는 그 플랫폼 **커널의 두 번째 얼굴** — 함대의 데이터 substrate로서의 배관이다.

**클라이언트 데이터 SoT** 가 git → **spnv-platform 웹 DB** (**클라우드 2026-07-10 이후**: jengablock RDS `spnv_platform_db` + banchan EC2 daphne `cofounder-api.jengablock.com` + Amplify `spnv.jengablock.com`. 로컬 dev 폴백: Postgres `localhost:5432` + Django `localhost:8001` + Next.js `localhost:3001`). 함대 4종 (Watcher/Responder/Comms/Librarian) 은 file 작성 대신 **MCP `mcp__spnv-platform__create_document`** 호출 — 각 함대 `.md` 의 §99 (cut-over 섹션) 가 §2.3/§3 의 file 경로를 override.

- 백업 S3: `s3://spnv-platform-backup-ea8372` (`[supernova]` profile)
- 클라이언트 드라이브 S3 (asset kind, 비-.md 대외 산출물): `s3://spnv-platform-drive-a8863c` (`[supernova]` profile, ap-northeast-2, BPA·SSE·버전관리). 키 = DB path = `files/<client>/[<category>/]<YYYY-MM-DD>-<topic>.<ext>`. 설계: [[decisions/supernova-platform/2026-06-22-client-drive-s3-assets.md]] (클라이언트별 이관 현황은 그 설계 doc·spnv-platform 참조). **`S3_DRIVE_BUCKET` env 필요** (backend `.env.local`, gitignored)
- MCP server URL: `https://cofounder-api.jengablock.com/mcp/` (**클라우드 2026-07-10** — `.mcp.json` 이 이 URL 을 가리킴). 로컬 dev 폴백: `http://localhost:8001/mcp/`. PAT 는 `SPNV_PLATFORM_TOKEN` env (gitignored). 배포 상세: 위 "보류 중인 작업" 의 완료 노트
- 디자인 doc: `docs/decisions/2026-06-01-supernova-platform-design.md`
- **병렬 세션 git 격리 (의무·대개 자동)** — 플랫폼 repo(`clients/supernova-platform`)를 **여러 세션 병렬**로 작업하면 같은 폴더=같은 `main` 공유로 충돌·발산("rebase 하세요" 무한 루프)이 난다. 근본 처방: **세션별 worktree 격리 + `main` FF-only**. 두 겹으로 자동 강제됨 — (1) pre-push 가드가 `main` non-FF/force push 물리 차단, (2) **PreToolUse 편집 가드가 공유 primary 폴더의 플랫폼 코드 수정을 차단하고 worktree 로 유도**(읽기·분석엔 안 걸림, 우회 `SPNV_ALLOW_SHARED_EDIT=1`). 그래도 세션은 `scripts/session-worktree.sh {start|integrate|cleanup|sync}`(⚠️ 경로는 **플랫폼 repo 안** = `clients/supernova-platform/scripts/…`. fleet 루트의 `scripts/` 가 아니다 — 2026-08-31 감독이 fleet 루트에서 찾다 "스크립트 없음"으로 오판) 로 작업하고 primary main 직접 커밋 금지. ⚠️ 편집 가드는 세션 시작 시 로드 → 이미 뜬 세션엔 재시작 후 유효. 정본 절차: [[runbook/supernova-platform/parallel-session-git-isolation.md]] (spnv-platform), 설계: `clients/supernova-platform/docs/superpowers/specs/2026-07-27-parallel-session-git-isolation-design.md`.

### 클라이언트 인바운드 routing (메인 컨텍스트 = 클로드)

함대 4종뿐 아니라 **빌드 함대 트래픽도 spnv-platform 에 기록** — 100개 운영의 핵심은 "컨텍스트 복원"이고, 그 데이터의 양적 대부분이 빌드 트래픽이기 때문 (`docs/decisions/2026-06-01-supernova-platform-design.md` §4.2 의 kind 표에 `feature-request` + `change-log` 2종 추가됨, 0003 마이그레이션).

**채팅 인바운드도 동일 적용** — 자체 채팅(spnv-platform messaging)의 클라이언트 메시지는 `mcp__spnv-platform__list_unread_inbound` 로 확인하고, 아래 step 0~2 를 동일하게 거친다 (feature-request 의 `metadata.channel="chat"`, 메시지의 `document_refs` 에 생성한 문서 path 역참조). 처리 완료 시 `read_conversation(mark_read=true)`. 발신 티어 정책은 `comms.md §5.1` 예외 조항 참조 (Tier 0 자율 / Tier 1 draft→승인).

**[제보] 위젯 인바운드도 별도 채널로 확인 (의무)** — 클라 직원이 웹 제품 화면(스토어·`/admin`)의 **[제보] 버튼**으로 올린 버그·요청은 **채팅이 아니라 `kind="feature-request"`, `tags=["from-widget","reply-needed"]`, `status="requested"` 문서**(경로 `requests/<client>/…-widget-<uuid>.md`, 캡처·주석 스크린샷 동반)로 저장된다. ⚠️ **`list_unread_inbound`(채팅발)로는 구조적으로 안 보인다** — 위젯은 채팅방에 system 알림만 남기고 클라이언트발 메시지가 아니기 때문이다. 반드시 **`mcp__spnv-platform__list_documents(client=<slug>, kind="feature-request", tags=["from-widget"])`** 로 픽업하고(=클로드 인바운드 픽업 큐), `status="requested"` 미처리분을 위 step 0~6 으로 처리한다. 클라 대면 요청 트래커(`/v/<ventureId>/ops/requests`)엔 안 뜬다(승격=운영자 수동) — ⚠️ **`/portal/requests` 아님**. `frontend/src/app/portal/requests/` 는 부품(로직·evidence 패널)이고 사람이 보는 표면은 `/v/<ventureId>/ops/requests` 다(2026-08-21 IA 재구성). 2026-08-31 감독이 옛 경로를 클라 회신에 넣을 뻔함. 정본: [[runbook/supernova-platform/feedback-widget-onboarding.md]] §"카드 확인처", 설계: [[changelog/supernova-platform/2026-07-28-client-web-feedback-widget.md]]. (2026-07-30 감독 세션에서 위젯 제보를 `list_unread_inbound` 로만 확인해 놓친 사고 재발방지 — 최근 배포 채널의 소비 가이드 전파 누락.)

**규칙 — 클라이언트로부터 신규 요청·문의·버그 리포트가 메시지로 들어오면:**

0. **(절차 runbook 조회 — 의무, 제일 먼저)** 이 클라이언트·이 요청 유형의 *정본 처리 절차*가 이미 있는지 확인: `mcp__spnv-platform__list_documents(client=<slug>, kind="runbook")` (+ 요청 성격으로 `mcp__spnv-platform__search_documents(query=..., kind="runbook")`). **있으면 그 runbook 을 읽고 그대로 따른다** — 절차를 즉흥 재구성하지 말 것(매 세션 헤매는 근본 원인). 없고 반복 가능성이 있으면 작업 *후* `kind="runbook"`, path `runbook/<client>/<topic>.md` 로 절차를 남긴다(다음 세션의 자산 = 자가치유). 근거(정본): spnv-platform `decisions/_system/2026-06-22-runbook-driven-inbound-routing.md` (kind=decision).
1. **(컨텍스트 조회)** 먼저 `mcp__spnv-platform__list_documents(client=<slug>, limit=20)` 으로 최근 활동·진행 중 요청 확인 — 같은 요청 반복, 미완료, 약속 마감 누락 등 파악.
2. **(요청 기록)** `mcp__spnv-platform__create_document(kind="feature-request", client=<slug>, body=<원본 텍스트 + 정리된 요약>, metadata={"date":"YYYY-MM-DD","topic":"<kebab-slug>"}, status="requested")` — path 자동 생성: `requests/<client>/<YYYY-MM-DD>-<topic>.md`.
   - **반환된 `created_at` 값을 기억** — step 4 에서 토큰·비용 합산의 anchor 로 사용.
   - **(회신 차원 태그 — 생성 시 판단)** 이 요청이 *완료되면 클라이언트에 회신해야 하는가* 를 판단해 `tags` 에 1개 넣는다: 클라이언트-발 요청·문의·버그 = `reply-needed`; 운영자 내부 발(인프라·리팩토링·운영자 발견 조사 등 클라이언트가 인지 못 하는 작업) = `reply-na`. 애매하면 `reply-needed`(보수적). **이 태그는 접수 시점의 분류이지 완료 표시가 아니다 — 회신을 보냈다고 손으로 바꾸지 말 것**(완료는 step 6 의 발송 원장이 기록하고 주의 큐가 거기서 도출한다).
   - **(능력 도메인 태그 — 2026-07-19~)** `create_document` 에 `domains=[<레지스트리 슬러그>]` 부여(그 클라 고유 ∪ `_shared`). 유효 슬러그·문서수는 `mcp__spnv-platform__list_domains(client=<slug>)` 로 확인(무효 슬러그는 거부됨, 별칭은 자동 정규화). 걸침 문서는 다중값. step 4 change-log 에도 같은 domains. 근거: [[docs/decisions/2026-07-19-knowledge-domain-facet-design.md]] — 도메인 축 navigable(고도화 도출을 전수 재독 대신 도메인 질의로).
   - **(이니셔티브 귀속 — 2026-08-23~, 2026-08-24 다중값)** `create_document` 에 **`initiative_ids=[...]`** 를 함께 준다(step 2.5 에서 정한 과제). 요청·회의록(comms-thread)·결정(decision)·변경기록(change-log)은 귀속을 채우는 것이 기본이며, 이렇게 해야 클라 문서함·요청 보드에서 **과제별로 갈라 보인다**. **한 문서가 여러 과제에 걸치면 전부 적는다** — 워크샵 회의록·방향 결정처럼 두 과제 모두에 관한 문서가 정상이다(문서의 과제는 소유가 아니라 주제 축이라 단수일 이유가 없다; 대조로 견적·Feature 는 소유라서 단수가 맞다). **접수 시점에 어느 과제인지 모르면 생략(=미분류)** — 빈 값이 정상 상태이고, 나중에 `update_document(initiative_ids=[...])` 로 배정한다(`[]`/`0` 이면 귀속 해제, 주는 값이 곧 전체 집합=치환). 사업 전체 자산(런북·정책·개념)은 귀속하지 않는다. cross-client 이니셔티브는 거부됨. 단수 `initiative_id` 는 하위호환으로 계속 받는다. 근거: [[changelog/supernova-platform/2026-08-23-document-initiative-scope.md]] · [[changelog/supernova-platform/2026-08-24-document-initiative-multivalue.md]].
   - **⚠️ 카톡·이미지로 들어온 요청의 전사 충실도 (의무 — 근거 보존)**: 요청이 **money·prod·data-integrity 성격**이거나 `reply-needed`이거나 **건별/1인당 예외**를 담으면, body 에 `## 원본 전사` 절을 두고 — ① **발화자 신원**(호칭 포함)·**메시지 시각**·**첨부파일명**을 명시, ② **모든 named 대상과 대상별 규칙을 표로 축자 전사**한다(요약으로 압축 금지 — 예: `송승희=받는사람 가람요양원원장·주소 가람요양원 / 김승규=3주문 3곳 상이 / 최동주=2곳 부부+1곳 아버지`). **캡처 이미지 원본은 raw PII(클라의 end-customer 실명·주소)라 S3 자산으로 올리지 않는다** — `create_asset` 계약이 raw PII 를 금지("stay local")하고, chat 붙임 이미지는 디스크 미접근이라 배관도 막힘. **정본은 이 무손실 전사이며, 이미지는 운영자 로컬/원 채널에 남는다.** 근거: 2026-08-21 운영자 지시 — 카톡 캡처 요청이 재진술로 열화돼 1인당 예외가 소실되던 누수(오배송=money·prod 직결)를 전사 규약으로 차단. 분쟁 대비 이미지 provenance 정본화가 정말 필요하면 자산정책 PII 예외를 별건 결정으로. (전사 충실도 하드룰은 comms 서브에이전트뿐 아니라 **main 인라인 접수에도 적용** — "커뮤니케이션·문체 규칙" UX 라이팅 레일과 같은 계열.)
2.5. **(roadmap 귀속 결정 — 요청 기록 후, `create_feature` 전)** `mcp__spnv-platform__get_roadmap(client=<slug>)` 로 그 클라의 이니셔티브를 조회한다. 귀속은 **2단으로 판단한다**(2026-08-25~): ① **큰 축(부모 과제)** 을 고른다 — 없고 새 사업·대형 작업이면 `create_initiative`. ② 그 안에서 **세부 과제**를 고르거나 `create_initiative(parent_id=<부모>)` 로 만든다(깊이 2단까지 — 세부 과제 아래엔 안 붙는다. venture 는 부모 것을 따른다). 재배치·해제는 `set_initiative_parent(initiative_id, parent_id|null)`. 큰 축 하나에 세부 과제가 여럿 자라는 것이 정상이며, 작은 묶음마다 최상위 과제를 새로 만들면 사이드바가 평면으로 쌓여 "지금 뭐가 굴러가는지"가 안 보인다(dodam 실측 20줄이 그렇게 생겼다). 이어 `create_feature` 는 **세부 과제**에 걸고(`initiative_id|page_id`), **step 2 의 `create_document` 에도 같은 과제를 `initiative_ids` 로 준다**(문서·과제가 같은 축으로 갈려야 과제별 열람이 성립). 문서 귀속은 **가장 좁은 단위(세부 과제)** 를 적는다 — 부모로 조회하면 세부 과제 문서까지 합쳐 올라오고, 문서함 칩도 부모만 뜬다. 요청이 여러 과제에 걸치면 문서 쪽은 전부 적고, Feature 는 주된 과제 하나에 만든다(작업은 한 과제에 속한다). 자동 LLM 분류가 아니라 **감독 판단**(요청 성격 ↔ 이니셔티브 objective 매칭) — 반복 매칭 패턴이 확인되면 그때 도구화. 이유: 통화·카톡 요청이 feature-request *문서*까지만 정형화돼 있고 roadmap Feature·이니셔티브 귀속 판단 레일이 부재했음. **커밋먼트 날짜(약속 목표일)는 Feature가 아니라 견적에 산다** — 승인 견적의 `EstimateItem.target_date`(+`feature_id` 링크)가 `deadline_overdue` 신호의 소스이며 피처가 done되면 자기해소한다. (구 Milestone 객체는 2026-08-19 은퇴 — [[changelog/supernova-platform/2026-08-19-retire-milestone-fold-commitment-into-estimate.md]].)
3. **(작업)** 빌드 함대 (frontend-dev / backend-dev / infra) 또는 메인 컨텍스트 직접 작업. git 이 코드 SoT.
   - **⚠️ 버그성 요청은 진단 확정 전 "실 I/O 재현 → 진입점 추적" 의무** (재발방지 — 실재 버그를 "문제없음"으로 오판·오배포한 이력, 2026-07-24 운영자 지시): ① **실제 요청/응답(에러 본문·로그·실 HTTP)을 먼저 확보**한 뒤 이론화·수정·배포한다(합성 재현으로 먼저 배포 금지). ② 진단은 **사용자의 정확한 진입점(URL·화면·액션)에서 시작해 그 화면이 부르는 실제 엔드포인트·함수를 끝까지 추적**한다 — 개념이 같아 보이는 인접 코드경로를 실제 경로의 증거로 대체 금지. ③ 트리거 상태가 DB에 없으면 = 무증거 아님 → 안전 환경(로컬·롤백 프로브·운영자 요청)에서 **직접 구성해 관측**. ④ **"버그 아님/사용 문제/정상 동작"은 긍정적 주장 → "버그 맞음"과 동일 이상의 증거(사용자 진입점 실재현 관측)를 요구**한다; 결론이 "코드 변경 불필요"인 **값싼 면죄 가설은 red flag → 확증 아닌 반증(버그 재현 시도)** 후에만 확정. 못 하면 판정은 "재현 불가 — 필요한 것 X"이지 "문제 없음"이 아니다. 정본: [[memory:not-a-bug-verdict-requires-reproduction]] + [`verify-locally-before-deploy`] 계열.
   - **화면-특정 레이아웃 요청**(재구성·개편·신규 화면)은 빌드 전 **티어 판정 후 라우팅**: 기본 **A**(frontend-dev 직행, `guidelines.md`·`design/screens.md` 봉투 소비) / 명백한 단일 레이아웃 신규화면 **B**(designer 1안·async) / IA가 복수로 유효한 큰 재설계 **C**(designer 2~3안·운영자 육안 픽). 동기 픽은 C만(100클라 병목 방지). 정본: [[docs/decisions/2026-07-08-designer-bespoke-screen-design.md]] §2. — **티어 C 는 dispatch 전 운영자 청취(성격·우선순위·loves/anti 레퍼런스)를 받고**(임의 판정 금지), 육안 픽은 **실캡처 병치(Artifact)** 로 제시하며, **픽 직후 디자인 델타 트리아지**(목업↔시스템 차이 3택: 반영/로컬/폐기)를 같은 동기 순간에 수행한다. 정본 [[docs/decisions/2026-07-08-designer-bespoke-delta-reconciliation-design.md]].
4. **(결과 기록)** 배포·작업 완료 후:
   - 먼저 `scripts/sum-tokens.py --from-time "<feature-request.created_at>"` 실행 → JSON 출력 보관.
   - `mcp__spnv-platform__create_document(kind="change-log", client=<slug>, body=<변경 요약 + 파일 + commit SHA + 배포 상태 + 비용 한 줄>, metadata={"date":"YYYY-MM-DD","topic":"<같은 slug>","usage":<sum-tokens.py JSON 통째>}, status="shipped")` — feature-request 의 topic 과 같은 slug 를 쓰면 검색이 자연스럽게 묶임.
   - **⚠️ roadmap Feature done 전이 (의무 — 작업 큐 SoT 동기화)**: 이 작업에 대응하는 roadmap Feature 가 있으면 `mcp__spnv-platform__update_feature(feature_id=<id>, status="done", source_document_id=<change-log id>)`. **작업 큐/"작업예정" 판정의 SoT 는 문서 status 가 아니라 roadmap Feature 의 `tracker_status`**(`get_roadmap` 반환, 견적-승인 게이트 반영) — 배포했는데 Feature 를 done 으로 안 넘기면 다음 세션이 재작업으로 오판한다. 착수 시점엔 대칭으로 `status="active"`. 정본: [[docs/decisions/2026-07-27-work-queue-sot-roadmap-tracker-status.md]].
   - **(마일스톤 write-back 폐지 — 2026-08-19)**: Milestone 객체가 은퇴돼 `deadline_overdue` 가 **승인 견적 항목 목표일(`EstimateItem.target_date`) + 링크 피처 상태**에서 파생되고 **피처 done 전이만으로 자기해소**한다 — 위 Feature done write-back이면 충분, 수동 마일스톤 done 전이 불요. 근거: [[changelog/supernova-platform/2026-08-19-retire-milestone-fold-commitment-into-estimate.md]].
   - **⚠️ 근거 자동 첨부 (의무 — 클라대면 작업 결과)**: change-log + roadmap Feature done 전이 **직후**, `/ship-evidence <client> <feature-id>` 로 결과 스크린샷·가이드를 그 Feature 에 클라대면 근거로 첨부(B1 표면 소비, platform 무변경). 클라대면 Feature 없음(reply-na·내부작업)이면 커맨드가 graceful skip. 안전요약은 denylist 게이트 통과가 의무. 정본: `.claude/commands/ship-evidence.md`.
5. **(요청 상태 갱신)** `mcp__spnv-platform__update_document(<feature-request id>, status="shipped")`.
6. **(회신 추적)** 클라이언트에 결과를 회신했으면: ① comms-thread 문서로 회신 내용 기록(`kind="comms-thread"`, 위키링크로 feature-request 참조) ② **`mcp__spnv-platform__record_comms_sent(client=<slug>, kind="reply", reply_thread=<comms-thread 문서 id 또는 path>, channel=<메일·카카오 등>)` 호출.** 회신 완료의 유일한 기록 지점이며, 주의 큐(`get_attention_queue`)의 `reply_owed` 판정이 이 원장에서 도출된다. **문서 태그를 손으로 `replied` 로 넘기지 말 것** — 태그는 접수 시점의 *분류*(회신 대상인가)이고 완료 표시가 아니다. 태그로 완료를 표시하던 구 방식은 요청·change-log·comms-thread 세 군데로 갈라져 큐를 못 쓰게 만들었다(2026-08-31 재판정). 회신은 *클라이언트가 보낸 원본 메일에 대한 답장*으로 (새 메일 작성 X — 받은 메일에 답장해야 스레드·인용 유지).
   - **⚠️ 호명 전 대상 검증 (cross-client 인물 혼동 방지 — 의무)** — 회신 초안(및 운영자 핸드오프 문장)에서 특정 인물을 호명하기 전, *그 클라이언트의 기존 comms-thread·기록·`runbook/<client>`에서 실제 호칭을 확인*한다. 한 클라이언트에 등장하는 인물명·호칭을 다른 클라이언트 작업에 **전이 금지**. 확정 호칭을 모르면 이름 대신 중립 호칭("대표님")을 쓰고 운영자에게 확인. (근거: 2026-07-07 cross-client 인물 오지칭 사고. "용어·약자 컨벤션"의 cross-system 금지와 같은 계열.)
   - **⚠️ 시크릿·PII 마스킹 (인라인 초안에도 의무 — 보안)** — main context 가 직접 회신 초안을 쓸 때도, 토큰·API key·비밀번호·미마스킹 에러로그·PII(결제정보 등)를 클라 대면 텍스트에 **절대 붙이지 않는다**. 보이면 즉시 mask + 운영자 알림. (comms 에이전트 dispatch 없이 인라인으로 답장해도 적용 — 상세: `comms.md §5.5`. 근거: guardrail 이 서브에이전트에만 있으면 인라인 경로로 누수 — 2026-07-28 감사.)
   - **회신 초안 핸드오프엔 원본 메일 직접 URL 필수** — 운영자가 클릭 한 번으로 원본을 열어 답장하도록 *반드시* 포함(새 메일 작성 X — 받은 메일에 답장). **클라이언트-특정 회신 파라미터**(메일 시스템·발신자 주소·회신 URL 포맷·담당자 호칭 등)는 fleet CLAUDE.md 에 인라인하지 말고 그 클라이언트의 `runbook/<client>/`(spnv-platform — step 0 에서 이미 조회) 정본을 따른다. 없으면 작업 후 그 runbook 에 남긴다(자가치유).
   - **새 세션의 "회신 필요한 개발 완료" 백로그**: `mcp__spnv-platform__get_attention_queue(client=<slug>)` 의 `reply_owed` 항목. 발송 원장 기준이라 이미 회신한 건은 자동으로 빠진다. `list_documents(tags=["reply-needed"])` 로 세지 말 것 — 그 태그는 분류이지 미완료 표시가 아니다.

**우회 금지** — 텍스트 메시지를 곧장 코드 작업으로 받지 말고, 위 0·1·2 단계를 먼저 거친다(특히 **0 — 절차 runbook 조회**: 같은 유형 요청을 매번 헤매는 걸 막는 핵심). 자주 잊는 단계이므로 *작업 시작 전* 의식적으로 체크.

**한 대화 = 한 요청** — 비용 추적 (`metadata.usage`) 이 정확하려면 한 conversation 안에서 동시에 여러 클라이언트 요청을 인터리브로 처리하지 말 것. 다른 요청은 새 conversation 으로. 자세한 추적 메커니즘: [`scripts/sum-tokens.py`](scripts/sum-tokens.py) docstring.

**spnv-platform 자기개발도 동일 라우팅 (라우팅 예외 아님)** — `supernova-platform` 은 *등록된 클라이언트*(`list_clients`). 따라서 플랫폼 자체 코드 변경(`clients/supernova-platform/`)도 — 비록 "클라이언트 메시지"로 들어온 게 아니어도 — *다른 클라이언트와 똑같이* client=`supernova-platform` 의 **feature-request → change-log** 로 **ship 시점에 능동 기록**한다(작업이 끝났는데 플랫폼 DB에 기록이 없으면 누락이다). git 의 설계 spec/plan 은 위키링크로 참조. 선례: `requests/supernova-platform/2026-06-13-cockpit-dashboard.md`, `…/2026-06-22-s3-client-drive.md`. *cross-client 함대 역량*(예: guide 생성기)만 `_system` decision 으로; spnv-platform 제품 기능은 supernova-platform 클라이언트 문서로. 다중주제 conversation 이면 `usage` 미첨부 + 본문에 비고.

**스키마 욕심 X** — body 는 마크다운 자유. metadata 는 `date`·`topic` + (change-log 한정) `usage` 면 충분. Librarian 이 횡단 패턴 추출하면서 진화시킴.

**위키링크 적극 사용** — body 작성 시 관련 다른 문서를 `[[<path>]]` 로 명시 link. 예: change-log body 안에 `[[requests/<client>/<date>-<topic>.md]]` 로 자기 feature-request 참조. cross-link 가 LLM-wiki 의 정수 — `list_backlinks` 가 자동 인덱싱.

**Concept page 참조** — feature-request·change-log body 안에서 *cross-client 패턴* 이 보이면 기존 `concepts/<topic>.md` 가 있는지 먼저 확인 (`list_documents(kind="concept")`), 있으면 `[[concepts/<topic>.md]]` 로 link, 없고 3회 이상 패턴이면 Librarian 의 promotion workflow (`librarian.md §4`) 에 후보로 들어감 (Librarian cron 이 자동 식별).

**Policy 상태 동기화** — change-log 작성 시 *영향 받는 policy* (회원가입 정책·요금표·API spec 등) 가 있으면 *같은 작업 단위 안에서* `mcp__spnv-platform__create_policy_revision(policy_id, new_body, summary, rationale, effective_from, triggered_by_id=<change-log id>)` 호출. 의무 단계 — drift 방지. `update_document(policy_id, body=...)` 는 서비스가 거부함 (revision history 보존 강제). 영향 받는 policy 가 *없거나 알 수 없으면* skip — Librarian 의 async fallback (P1+) 이 잡음.

**규범(norm) birth·동기화 (의무 — 위 policy 개정과 별개 단계)** — change-log 가 **내구성 비즈니스 규칙을 신설·변경**했으면(가격·할인·eligibility·컷오프·정산/환불·구독 상태전이 등 "무엇이 참이어야 하나" 명제), *같은 작업 단위 안에서* **규범 결정**(`kind=decision`, `decisions/<client>/`, 태그 `norm-warrant`·`active-norm-pilot`; 섹션 해석(should)/근거(warrant)·grade/불변식/**birth 대조 verdict**) + **클라 가독 정책**(`kind=policy`, `policies/<client>/`, 평문)을 birth/reconcile 한다. 판정 휴리스틱 = "이 change-log 가 *없던 규칙을 만들거나 있던 규칙을 바꿨나*?" → yes 면 규범. ⚠️ 위 `create_policy_revision` 은 *이미 있는 정책 개정*만 다루고 "없으면 skip" 이라 **새 규칙을 birth 하지 않는다** — 신설 규칙은 반드시 이 단계로 잡는다(이게 빠져 규칙이 change-log 본문에만 묻히는 게 대표 누락). grade 는 시스템 기록 존재 시 `evidenced`(birth 전 comms/change-log 코퍼스 검색 — 기억보다 기록 우선), 조회 불가 증언만이면 `attested`. **정본·트리거 전체(T1 이 라우팅·T2 훅·T3 Librarian 스윕): [[decisions/_system/2026-08-07-norm-warrant-trigger-framework.md]].** **전 클라이언트 의무** — change-log 가 규칙을 담았으면 *어느 클라든* 규범을 birth 한다(2026-08-07 dodam·ketovibe 파일럿 → 전 클라 확장). T3(Librarian)가 놓친 것을 잡는 async 백스톱.

## 함대 진화 패턴

- 진화 모양: **단일 `.md` → 평면적 다중 `.md`** (폴더화 X)
- 분화 시그널: 한 에이전트가 ~500줄 넘기 시작 / 본질적으로 다른 워크플로우가 한 파일에 섞임 / 도구 권한이 너무 광범위해짐
- orchestrator 패턴은 진짜 필요해질 때까지 미룸 — 지금은 메인 컨텍스트 + `/build-project` 가 그 역할
- 자세한 추론은 `docs/decisions/2026-05-28-fleet-design.md` 참조

## 메모리·컨텍스트 노트 (새 세션의 클로드에게)

- 이 파일(CLAUDE.md) 은 새 세션 시작 시 자동 로드된다. 디테일은 여기 두지 않고 **참조만** 둔다.
- 함대 에이전트들의 system prompt body 는 자동 로드되지 않는다 — Task tool 호출 시에만 로드된다.
- 사용자의 누적된 선호·결정은 `~/.claude/projects/-Users-juwon-projects-spnv/memory/` 에 별도 저장될 수 있다 (auto memory).
  - **이 메모리는 머신 종속이라 git 추적 대상 아님.** 다른 노트북에서 supernova clone 시 비어있는 게 정상. 핵심 정보는 모두 이 repo 자산 (CLAUDE.md + `.claude/` + `docs/decisions/`) 에 중복 보유되어 있으므로 시스템 동작에 문제 없음. 미세한 협업 스타일·운영 관행은 새 노트북에서 다시 누적됨.
- 진행 중 큰 결정을 내릴 때는 `docs/decisions/` 의 기존 파일을 먼저 읽어 일관성 유지.
- **auto-memory 규율 — 재발방지 (2026-07-24 운영자 지시)**: 특정 과제에만 필요한 재사용 지식·명령 레시피·과제-특정 배관을 auto-memory 에 **저장 금지**. MEMORY.md 는 매 세션 전부 로드되므로 좁은 과제 지식은 무관한 대화(다른 클라·다른 과제)까지 오염시킨다. auto-memory 엔 **세션·과제와 무관하게 항상 참인 것만**(사용자 선호·광범위 작업 관행·안정 레퍼런스). 과제로 넘길 재사용 컨텍스트는 그 과제의 **핸드오프 프롬프트에 인라인**한다. (메모리 dir Write 시 `PreToolUse` 훅이 이 기준을 리마인드 — `.claude/settings.local.json`, gitignored·머신 로컬.)
- **핸드오프 프롬프트 완결성 점검 — 재발방지 (동)**: 다음 세션/과제로 프롬프트를 넘길 때, **넘기기 전에 그 프롬프트만으로 컨텍스트가 완벽히 전달되는지 점검**한다. 이 대화에서만 얻은 재사용 노하우(검증 하네스·명령·함정·결정 근거)가 빠지지 않았는지 확인해 본문에 인라인. 내구 자산(CLAUDE.md·platform DB feature-request/change-log·git·로컬 spec)으로 커버되는 건 참조로 두되, 그 외 대화-종속 지식은 반드시 본문에.
