# supernova-core — 중립 함대 코어

`kangju1/supernova` 에서 **클라이언트 인프라 좌표를 제외한** 함대 자산.
규칙(CLAUDE.md)·에이전트·커맨드·훅·보일러·템플릿·플레이북·결정 기록이 여기 산다.

## 왜 별도 repo 인가

담당 클라가 서로 다른 여러 PM 이 같은 함대 규칙 아래 일해야 한다. 그런데 원본 repo 는
커밋 559개의 history 에 좌표가 남아 있어(dodam 인스턴스 id 24커밋, gisa RDS 엔드포인트
12커밋) **파일을 옮기는 것만으로는 차단이 되지 않는다.** clean history 로 시작하는 것이
유일한 방법이었다.

## 좌표는 어디에 있나

**플랫폼이 준다.** 배포 정문이 배포 권한을 확인하는 그 호출에서 함께 받는다:

```
GET /api/authz/deploy-check/?client=<slug>
  → tunnel  : 그 클라가 **보이면** (DB 터널 파라미터)
  → deploy  : **배포할 수 있으면** (인스턴스·프로파일·프로젝트명)
```

권한이 없으면 빈 값이 아니라 **블록 자체가 없다**. 권한 확인과 좌표 차단이 같은
기제라서, 따로 지켜야 할 두 번째 관문이 생기지 않는다.

클라 인프라(OpenTofu)는 각 클라 repo 에 있다 — `clients/<client>/infra/`.

## 이 repo 에 좌표를 넣지 말 것

`.github/workflows/no-client-coordinates.yml` 가 push·PR 마다 스캔한다. 공개 상수
(Canonical AMI owner 등)는 `scripts/scan-client-coordinates.py` 의 ALLOWLIST 에 **이유와
함께** 추가한다.

## internal 전용으로 남은 것

`kangju1/supernova`(원본)에 남아 있고 여기 없는 것: `infra/`(registry + 잔여 클라
인프라) · `scripts/gating/onboard/`(가드 설치본) · `docs/gating/promotion-ledger.json`
(컷오버 스냅샷, 정본은 플랫폼 DB) · `ops/` 실기록.
