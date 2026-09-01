# gisa — Operations Runbook

> Responder가 매칭하는 1차 시드. 새 패턴 확정 시 `P-NNN` 항목 추가.
> 마지막 갱신: 2026-06-02 (초안)

## 시스템 개요

- **백엔드**: TODO (Django 5.x, EC2 + RDS, supervisor 경로, 로그 위치)
- **프론트엔드**: TODO (Next.js, Amplify 또는 별도 호스팅)
- **DB**: TODO (PostgreSQL 버전, RDS 인스턴스명)
- **외부 의존**: TODO (결제 PG, SMS, 메일 등)
- **도메인**: TODO

## 시드 패턴 (사용자 인터뷰로 채움)

### P-001 <장애 패턴 1>
TODO: 증상 / 1차 확인 / 옵션 3개 / 추천 분기 / 사후 액션

### P-002 <장애 패턴 2>
TODO

## 공통 절차

### 알람 → 결정 흐름
1. `#ops-alarms` 채널에서 `[gisa] ...` prefix 의 Watcher 메시지 확인
2. 메시지의 Responder 호출 prompt (별도 메시지) 복사 → 메인 Claude Code 붙여넣기
3. Responder 가 분석을 spnv-platform 에 기록 (`create_document` kind=response) 후 thread reply — "전체 분석" 링크는 spnv-platform 문서 URL (`ops/responses/*.md` 파일 경로 노출 금지, responder.md §99)
4. 추천 옵션 직접 실행 → spnv-platform response 문서 `status` 를 `applied` 로 갱신 (`update_document`)
5. 사용자 영향 있으면 `@comms gisa` 으로 안내문 초안

### CloudWatch Logs Insights 쿼리
```
fields @timestamp, level, name, message, request_id
| filter level in ["ERROR", "CRITICAL"]
| stats count() as cnt by name, message
| sort cnt desc
| limit 20
```

## 진화 메모
새 패턴 발견 시 P-NNN 추가. Librarian 이 3회 이상 반복 발견한 패턴은 자동 후보 → 사용자 검토 후 정식 등재.
