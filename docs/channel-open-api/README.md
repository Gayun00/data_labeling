# ChannelTalk Open API 설계

## 1. 목적 & 범위
- ChannelTalk Open API를 통해 **문의(=UserChat)** 단위 데이터를 일 배치로 적재하고, 메시지 본문을 분석해 자동 라벨링 및 보고서/엑셀 생성을 지원한다.
- 설계 목표는 (1) 필요한 엔드포인트 정의, (2) 요청 파라미터 및 커서 운용 방법, (3) 원본 JSON을 보존하는 데이터 계층 구조를 명시하는 것이다.

## 2. API 사용 전략

### 2.1 `GET /open/v5/user-chats`
- **목적**: 문의방 목록 + 메타데이터 수집.
- **요청 파라미터**
  - `state`: `opened|closed|snoozed`; 배치 정책에 맞춰 선택. 예) `state=opened`.
  - `sortOrder`: `desc`(추천, 최신순) 또는 `asc`.
  - `limit`: 1~500; 기본 25. 초기 배치에서는 500으로 설정해 호출 수를 줄인다.
  - `since`: 페이징 커서. 직전 응답의 `next` 값을 저장해 두었다가 다음 호출에 그대로 전달한다. 최초 실행 시 생략.
- **주요 응답 필드(샘플 인터페이스)**
  ```jsonc
  {
    "next": "eyJjaGF0S2V5IjoiZ3Jvn0=",
    "userChats": [
      {
        "id": "uc_123",          // userChatId
        "channelId": "ch_45",
        "state": "closed",
        "managed": true,
        "userId": "user_1",
        "managerIds": ["mgr_1"],
        "assigneeId": "mgr_1",
        "teamId": "team_2",
        "tags": ["refund", "priority"],
        "handling": { "type": "auto" },
        "source": { "page": "...", "supportBot": {...} },
        "goalState": "achieved",
        "contactKey": "ckey",
        "contactOrder": 1656032152515,
        "openedAt": 1656032152526,
        "closedAt": 1656032152526,
        "createdAt": 1656032152527,
        "sessions": [...],
        "users": [...],
        "managers": [...],
        "chatTags": [...]
      }
    ]
  }
  ```
- **사용 방식**
  1. `next` 커서를 받아 저장 → 다음 배치의 `since` 값으로 재사용.
  2. 각 항목의 `id`를 `userChatId`로 기록해 메시지 API 호출에 사용.
  3. 메타 필드(state, tags, assignee, timestamps, sessions/users/managers 등)는 원본 보존 후 도메인 모델에 필요한 값만 추출한다.

### 2.2 `GET /open/v5/user-chats/{userChatId}/messages`
- **목적**: 특정 문의방의 메시지/봇 정보를 수집.
- **요청 파라미터**
  - `userChatId`: 부모 문의 ID (`/user-chats` 응답의 `id`).
  - `sortOrder`: `desc`(최신 우선) 또는 `asc`.
  - `limit`: 기본 25, 필요 시 조정.
  - `since`: 메시지 페이징 커서 (`next`를 저장했다가 이어받을 때만 사용).
- **주요 응답 필드**
  ```jsonc
  {
    "next": "eyJtZXNzYWdlS2V5IjoiZ3Iv...==",
    "messages": [
      {
        "id": "msg_1",
        "chatId": "uc_123",
        "personType": "user|manager|bot|system",
        "personId": "user_1",
        "plainText": "문의 내용...",
        "blocks": [...],
        "files": [...],
        "buttons": [...],
        "webPage": {...},
        "log": {...},
        "form": {...},
        "state": "sent",
        "createdAt": 1656032152433,
        "updatedAt": 1656032152427,
        "threadMsg": false
      }
    ],
    "bots": [
      { "id": "bot_1", "channelId": "ch_45", "name": "FAQ Bot", ... }
    ]
  }
  ```
- **사용 방식**
  1. `/user-chats`에서 받은 모든 `userChatId`에 대해 메시지 API 호출.
  2. 메시지를 시간순으로 정렬(`createdAt asc`)해 Conversation 분석에 사용.
  3. 첨부파일/액션/폼 등 추가 필드를 보존하면 이후 라벨 규칙 확장 시 재활용 가능.

## 3. 일간 배치 흐름
1. **커서 로드**: 저장소(예: DB, S3, local json)에서 `user_chats_cursor` 값을 조회. 없으면 `null`.
2. **User Chat 수집**:
   - `GET /user-chats?since=<cursor>&state=opened&sortOrder=desc&limit=500`.
   - 응답의 `userChats`를 `raw_user_chats` 저장(append)하고, `next`를 최신 커서로 갱신.
   - `next`가 없으면 더 이상 신규 데이터 없음 → 루프 종료.
3. **메시지 수집**:
   - 새로 적재한 각 `userChatId`별로 `GET /user-chats/{id}/messages`.
   - 메시지 `next` 커서가 있으면 `raw_messages`에 저장 후 `message_cursor[id]`로 갱신(필요 시 이어받기).
4. **도메인 변환 & 라벨링 큐**:
   - `ConversationFactory`가 raw 데이터를 읽어 `domain.inquiries` 객체를 생성.
   - 새 객체를 라벨링 워커 큐에 enqueue → LLM/룰 기반 분류 수행.
5. **커서 보존**: 배치 마지막에 `user_chats_cursor = next`를 durable storage에 기록. 실패 시 재시작 가능.

## 4. 데이터 계층 모델

| 계층 | 설명 | 저장 예시 |
| --- | --- | --- |
| `raw.user_chats` | `/user-chats` 응답을 변형 없이 저장. pagination cursor, sessions/users/managers 포함. | S3 JSON, Postgres JSONB, Parquet 등 |
| `raw.messages` | `userChatId`별 `/messages` 응답 저장. 메시지/봇/커서 유지. | `raw_messages/<userChatId>.json` |
| `domain.inquiries` | 한 문의 단위로 메타 + 메시지를 묶은 객체. 라벨링 대상. | DB table / parquet |
| `label.results` | `domain.inquiries.id` 기준 라벨링 결과(`category`, `confidence`, `explanation`). | Postgres table, CSV export |

도메인 객체 예시:
```jsonc
{
  "id": "uc_123",
  "meta": {
    "channelId": "ch_45",
    "state": "closed",
    "tags": ["refund"],
    "assigneeId": "mgr_1",
    "managerIds": ["mgr_1"],
    "timestamps": {
      "createdAt": 1656032152527,
      "openedAt": 1656032152526,
      "closedAt": 1656032152526
    },
    "users": [...],
    "managers": [...],
    "sessions": [...]
  },
  "messages": [
    { "id": "msg_1", "sender": "user", "text": "...", "createdAt": 1656032152433 },
    { "id": "msg_2", "sender": "manager", "text": "...", "createdAt": 1656032152520 }
  ],
  "label": null
}
```
- `label` 필드는 자동 라벨링 후 `{ "category": "환불요청", "confidence": 0.83, "source": "gpt-4o-mini" }` 등으로 채운다.
- 원본과 도메인을 분리하면 재처리/엑셀 Export 시 원본 손실 없이 가공 로직만 교체 가능.

## 5. 확장 포인트
- **엑셀/CSV Export**: `domain.inquiries` + `label.results`를 조인해 채널/태그/라벨별 리포트를 생성. 원본 필드를 그대로 남겨두면 추가 컬럼을 쉽게 노출 가능.
- **재수집/리플레이**: `raw.*` 계층이 그대로 남아 있으므로 커서 초기화 후에도 과거 데이터를 재사용하거나, 새로운 라벨러 버전을 적용해 재처리할 수 있다.
- **필터/리포트 강화**: `state`, `tags`, `goalState`, `managerIds` 등 메타 필드를 기준으로 특정 구간만 추출해 별도 라벨링/모델 실험에 활용 가능.

이 문서를 기준으로 개발 시 `raw → domain → label` 순으로 책임을 분리하고, 커서값을 안정적으로 보존하는 배치 파이프라인을 구현한다.

## 6. 파이프라인 개요
1. **Ingest**: ChannelTalk Open API 호출로 user chat 메타와 메시지를 수집해 `raw` 계층에 저장하고 커서를 갱신.
2. **Normalize**: `ConversationFactory`가 raw 데이터를 결합·정제하여 `domain.inquiries` 객체를 생성.
3. **Label**: 라벨링 큐/서비스가 `domain.inquiries`를 입력으로 LLM/룰 기반 분류를 실행하고 `label.results`에 저장.
4. **Report**: `domain + label` 데이터를 조합해 CSV/엑셀/대시보드를 생성.
5. **Monitor**: 배치 러너가 단계 실행/에러/커서 상태를 추적하여 재시작 가능성을 확보.

## 7. 컴포넌트 설계

| 계층 | 주요 컴포넌트 | 역할 |
| --- | --- | --- |
| Ingest | `ChannelTalkClient`, `UserChatFetcher`, `MessageFetcher`, `RawStore` | API 호출/재시도, 커서 관리, raw 데이터 저장 |
| Normalize | `ConversationFactory`, `SchemaValidators` | raw 데이터를 도메인 `Inquiry` 객체로 변환 |
| Labeling | `LabelingQueue`, `LabelerService`, `LabelStore` | 라벨링 요청 큐 관리, LLM 호출 및 결과 저장 |
| Report | `ReportBuilder`, `DashboardAPI(선택)` | `Inquiry+Label`을 조합해 CSV/리포트 생성 |
| Orchestration | `BatchRunner`, `MetricsLogger`, `Config` | 일 배치 스케줄, 상태 로깅, 설정 관리 |

각 컴포넌트는 패키지/폴더 단위로 구현할 수 있으며, 예: `src/ingest`, `src/domain`, `src/labeling`, `src/report`, `src/orchestrator`, `src/store`.

## 8. 데이터 저장 상세

### 8.1 Raw Layer
- **원칙**: API 응답을 변형 없이 저장하며, 커서와 수집 시각을 함께 기록해 재처리/감사를 지원.
- **테이블/컬렉션 예시**
  - `raw_user_chats`
    - `user_chat_id` (PK), `channel_id`, `state`, `payload`(JSONB), `cursor_next`, `fetched_at`.
    - `payload`에 `/user-chats` 응답 전체를 보존. `cursor_next`는 호출 직후 받은 `next` 값.
  - `raw_messages`
    - `user_chat_id`, `message_id`(PK), `payload`(JSONB), `cursor_next`, `fetched_at`.
    - 메시지 페이지마다 append하며, 동일 메시지 ID는 upsert.
- **저장소 선택**: 초기엔 Postgres JSONB 또는 Parquet 파일(S3/local). 대량 데이터 시 Data Lake + Glue Athena 패턴으로 확장 가능.

### 8.2 Domain Layer
- **목적**: 라벨링과 리포트가 바로 소비할 수 있는 정규화된 스키마 제공.
- **테이블 예시**
  - `inquiries`
    - `id`(=user_chat_id, PK), `channel_id`, `state`, `opened_at`, `closed_at`, `tags`(JSONB), `assignee_id`, `manager_ids`(JSONB), `meta`(JSONB), `message_count`, `built_at`.
  - `inquiry_messages`
    - `id`(=message_id, PK), `inquiry_id`, `sender_type`, `sender_id`, `created_at`, `text`, `attachments`(JSONB), `meta`(JSONB).
- `meta`에는 추가 필드(세션, goalState, source, supportBot 등)를 그대로 담아 향후 규칙에 활용.

### 8.3 Label Layer
- `labels`
  - `inquiry_id`(FK), `category`, `sub_category`, `confidence`, `model_version`, `prompt_version`, `explanation`, `labeled_at`.
  - 동일 문의를 여러 라벨러가 처리할 수 있도록 `version` 또는 `run_id` 필드 추가.
- `label_audit`
  - 수동 수정 내역, 검수 기록, human override를 저장해 품질 관리.

## 9. 배치/스케줄링 설계
- **잡 구분**
  1. `fetch_user_chats`: `user_chats_cursor`를 사용해 `/user-chats` 호출, `raw_user_chats` 적재.
  2. `fetch_messages`: 새 `user_chat_id` 목록으로 `/messages` 호출, `raw_messages` 적재.
  3. `build_inquiries`: raw 데이터를 조합해 `inquiries` + `inquiry_messages` upsert.
  4. `run_labeling`: 신규/미라벨 문의를 큐에 넣고 라벨링 처리, `labels` 저장.
  5. `export_reports`: `inquiries + labels` 조인해 CSV/리포트를 생성하고 공유 위치에 저장.
- **오케스트레이션**
  - 단순 MVP: Cron + Python 스크립트 체이닝, 커서는 로컬/DB에 저장.
  - 확장 시: Airflow/Prefect 등으로 DAG 구성, 태스크 간 의존성 관리, 재시작 지원.
  - 각 태스크는 idempotent하게 작성해 재시도 시 중복 저장을 피함(upsert).
- **모니터링**
  - 처리 건수, 실패 건수, 마지막 커서, 라벨링 응답 시간 등을 metric/log로 기록.
  - 경고 조건: 커서 정지(신규 데이터 없음), API 실패 반복, 라벨링 에러율 상승.
