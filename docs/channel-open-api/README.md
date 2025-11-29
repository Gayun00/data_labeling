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
