# ChannelTalk Review Labeler – Design Document

## 1. Mission & Scope
- Build an extensible pipeline that ingests ChannelTalk 상담 데이터를 (CSV 또는 Open API), 정규화된 `Conversation` 도메인 모델로 변환하고, LLM을 사용해 상담 단위 라벨링/요약/인사이트 추출을 수행한다.
- 최우선 목표는 **한 문의(채팅방)** 단위로 자동 라벨을 생성하고 결과를 CSV로 제공하는 것. 이후 벡터 검색, 고급 리포트, 추가 데이터 소스를 단계적으로 추가한다.
- 설계는 최소 코드로 MVP를 빠르게 만들되, 향후 반복 실행·확장·비동기화(스케줄러)·고객 요구 변경에 대응 가능하도록 모듈 경계를 명확히 한다.

## 2. Guiding Principles
- **Conversation-Centric**: 모든 파이프라인 단계는 `conversation_id`를 중심으로 동작.
- **Loose Coupling of Data & Models**: 원천별 변형은 어댑터 계층에, 코어 로직은 공통 스키마에 의존.
- **Traceable Processing**: 각 라벨 결과는 원본 대화와 버전을 추적 가능해야 한다.
- **Iterative Delivery**: CSV → API → 리포트 순으로 점진적 확장을 계획하고, 각 단계가 독립적으로 사용 가능하도록 구성.

## 3. Data Sources & Formats
- **CSV Export**: 여러 시트(UserChat, Message, User, Manager, Workflow, UserChatTag, Bot, SupportBot, UserChatMeet 등). 시트별 키 관계는 `UserChat` 중심. 초기 MVP는 UserChat + Message + User + Manager + Workflow + Tag를 우선 사용.
- **ChannelTalk Open API (User Chat API)**:
  - Pagination을 감싼 Adapter가 `Conversation` 리스트를 yield.
  - 필요 시 추가 엔드포인트(예: Manager detail)를 호출하거나 최초 실행 시 metadata cache 생성.
- **External Samples**: 기존 라벨 샘플 CSV(지정된 포맷)를 통해 라벨 스키마/프로토타입을 보강.

## 4. Core Domain Model
```python
class Conversation:
    id: str                  # UserChat.id
    channel_id: str | None
    created_at: datetime
    closed_at: datetime | None
    participants: Participants
    messages: list[Message]
    meta: dict[str, Any]      # workflow, tags, csat, priority, etc.

class Participants:
    user: UserProfile | None
    managers: list[ManagerProfile]
    bots: list[BotProfile]

class Message:
    id: str
    conversation_id: str
    sender_type: Literal["user", "manager", "bot", "system"]
    sender_id: str | None
    created_at: datetime
    text: str
    attachments: list[Attachment]
    meta: dict[str, Any]
```
- `meta`에는 확장 가능한 필드(예: CSAT, tags, workflow path) 저장.
- Embedding/Labelling 파이프라인은 `Message` 리스트를 시간순 정렬해 사용.
- 버전 관리: `ConversationVersion = f"{conversation_id}:{data_version}"` 형식으로 추적(예: CSV timestamp, API updated_at).

## 5. Architecture Overview

```
          ┌───────────────┐
          │ Source Adapter │  <─ CSV sheets / ChannelTalk API
          └───────┬───────┘
                  │ Raw events (dict)
         ┌────────▼────────┐
         │ ConversationFactory │  ← 데이터 정규화 & 조인
         └────────┬────────┘
                  │ Canonical Conversation
         ┌────────▼────────┐
         │ Preprocessing   │  ← 텍스트 정제/머지/Chunking
         └────────┬────────┘
                  │ Clean text per conversation/chunk
         ┌────────▼────────┐
         │ Embedding Store │  ← VectorStore 래퍼, versioned upsert
         └────────┬────────┘
                  │ Summaries / Embeddings
         ┌────────▼────────┐
         │ LLM Labeler     │  ← Prompt builder + LLMService
         └────────┬────────┘
                  │ LabelResult
        ┌─────────▼─────────┐
        │ Output Writers     │  ← CSV/Parquet/Report
        └────────────────────┘
```

## 6. Pipeline Stages
1. **Ingest** (`pipeline.ingest`):
   - Adapter를 통해 raw 자료를 로딩.
   - CSV: pandas dataframes, schema validation, 필요시 null 처리/타입 변환.
   - API: generator. pagination, rate limit handling, incremental support via `updated_since`.
2. **Normalize** (`pipeline.normalize`):
   - `ConversationFactory`가 raw dict을 받아 `Conversation` 객체 구성.
   - 메시지는 `created_at` 기준 정렬, 텍스트 없는 메시지는 필터링, attachments는 추후 확장 대비 meta로 보존.
   - 참여자/메타데이터 매핑: ids → profile dict (user, manager, bot).
3. **Preprocess** (`pipeline.preprocess`):
   - 텍스트 클렌징 (HTML 제거, 공백 정규화, 언어 감지 optional).
   - 대화 단위 long text 생성 (`conversation_text`).
   - 토큰 길이 초과 시 chunking 전략(시간 단위 또는 role turn 기반) 도입.
4. **Embedding** (`pipeline.embed`):
   - VectorStore 추상화 사용(현재: 로컬, 후속: Pinecone/Chroma).
   - Key: `(conversation_version, chunk_id)`; value: embedding, summary snippet, metadata.
   - 캐시 존재 시 재생성 생략.
5. **Labeling** (`pipeline.label`):
   - `prompt_builder`가 conversation summary/metadata를 포함한 prompt 생성.
   - `LLMService`가 호출 → `LabelResult(labels, confidence, reasoning, summary)`.
   - 레이블 스키마/규칙 config-driven(JSON/YAML).
   - 결과는 `LabelRecord` dataclass로 표현.
6. **Persist & Report** (`pipeline.output`):
   - 주 출력: `labels.csv` (`conversation_id`, `label_primary`, optional secondary labels, confidence, summary, manager, workflow, tags).
   - 추가 출력: JSONL (detail), parquet for analytics, aggregated insight (group by label/manager/CSAT).
   - Streamlit UI에는 라벨 테이블 및 다운로드 제공.

## 7. Module Responsibilities
- `adapters.channel_talk_csv.ChannelTalkCSVAdapter`
  - 입력: CSV 파일 경로들(혹은 폴더). pandas 기반 merge.
  - `load_conversations() -> Iterable[Conversation]`.
- `adapters.channel_talk_api.ChannelTalkAPIAdapter`
  - 입력: API credentials, since timestamp.
  - pagination, rate limit control, retry/backoff, incremental support.
- `models.conversation`, `models.label`
  - dataclass 정의와 validation 유틸.
- `pipeline.ingest`
  - Adapter registry, config 읽기, ingestion orchestration.
- `pipeline.preprocess`
  - 텍스트 정제, chunking, summary.
- `pipeline.embed`
  - `VectorStore` 인터페이스(현재 in-memory/FAISS + file persistence).
- `pipeline.label`
  - prompt 빌더, LLM 호출, 라벨 규칙 검증, 결과 postprocess.
- `pipeline.report`
  - pandas 집계, insight generation, Streamlit view helper.
- `store.vector_store`
  - embeddings CRUD, optional metadata persistence(JSON, sqlite 등).
- `services.llm_service`
  - OpenAI client wrapper. Rate limit, retry, logging.
- `config/` (추가 예정)
  - `settings.yaml` (엔드포인트, 모델명, 라벨 스키마, thresholds).

## 8. Data Handling Details
- **Key Joins (CSV)**:
  - `UserChat.id` ↔ `Message.chatId`.
  - `UserChat.userId` ↔ `User.id`.
  - `UserChat.managerIds` ↔ `Manager.id` (explode 후 join → group by).
  - `UserChat.workflowId` ↔ `Workflow.id`.
  - `UserChat.tags` ↔ `UserChatTag.name` (many-to-many: explode & map).
- **Timestamp Handling**:
  - 모든 시간은 UTC aware `datetime`. 입력에서 timezone 없으면 config에서 기본값 설정.
- **Missing Data**:
  - 필수 필드 비어있으면 warning 로깅 & skip/placeholder.
  - 메시지 없음 (`messages=[]`)인 conversation은 라벨링 대상 제외.
- **Normalization**:
  - 텍스트 전처리: HTML→plain, emoji optional 제거, URL placeholder.
  - 사용자/매니저 메타는 `Participants`에 dict로 보존.

## 9. LLM Prompt Structure (초안)
```
[System]
You are an assistant that classifies customer service chats.

[Context]
- Conversation ID: {conversation_id}
- Tags: {tags}
- Workflow: {workflow_path}
- CSAT: {csat_score}
- Manager: {manager_names}
- Conversation summary (if available): {summary}

[Messages]
{formatted transcript with role + timestamp}

[Task]
- Determine primary label among {label_schema}.
- Provide optional secondary labels if applicable.
- Return JSON with fields: label_primary, label_secondary, confidence, reasoning, summary.
```
- `prompt_builder`는 label schema/format을 config에서 받아 구성.
- 길이 제한 대비: `summary` → `messages` chunked. 필요 시 2단계 요약 (long → summary → label).

## 10. Storage Plan
- `data/`
  - `raw/` (optional cache of downloaded CSV/API dumps).
  - `normalized/` (`conversation_{date}.jsonl`).
  - `embeddings/` (vector store files, e.g., `faiss_index.bin`, `meta.json`).
  - `results/labels.csv`, `results/summary.jsonl`.
- `tmp/` 또는 `cache/`: 중간 산출물, chunked files.
- Versioning: output 파일명에 run timestamp 포함(`labels_YYYYMMDDHHMM.csv`) + latest symlink.

## 11. Observability & Logging
- 공통 로거(`logging`), 수준별(LogLevel INFO default).
- 각 단계에서 `conversation_id` 기반 context logging.
- Metrics placeholder (추후 Prometheus, or Streamlit dashboard).
- Error handling:
  - non-fatal 오류는 continue & record (e.g., 라벨 실패). `failed_conversations.csv`.
  - fatal errors raise & surfaced in UI.

## 12. Testing Strategy
- Unit tests: adapters (schema join), preprocess, prompt builder.
- Integration tests: pipeline end-to-end with fixture CSV.
- Mock OpenAI for deterministic label tests.
- Smoke test for Streamlit CLI (optional).

## 13. Implementation Roadmap
1. **Foundations**
   - [ ] 모델 정의(`models/conversation.py`, `models/label.py`).
   - [ ] config 구조 도입(`config/settings.yaml` + loader).
2. **CSV Pipeline**
   - [ ] CSV adapter + ConversationFactory.
   - [ ] Preprocess & Label skeleton (no embedding yet).
   - [ ] Streamlit UI와 연결.
3. **Embedding Layer**
   - [ ] `VectorStore` 리팩터, conversation version key 적용.
   - [ ] Embedding 기반 요약/검색.
4. **API Adapter**
   - [ ] ChannelTalk API client + pagination + auth.
   - [ ] Incremental fetching & caching.
5. **Reporting / Insights**
   - [ ] pandas 기반 요약 리포트.
   - [ ] Streamlit에서 label 분포, CSAT 등 시각화.
6. **Hardening**
   - [ ] Retry/Rate limit, error logging.
   - [ ] Integration tests & CI.
   - [ ] Prompt tuning & label schema iteration.

## 14. Open Questions & Future Enhancements
- 라벨 스키마 확정 및 변경 프로세스? (예: config에 정의, UI에서 편집?)
- 매우 긴 대화의 chunking 기준: 시간 기반 / role 기반 / message count?
- 다국어 처리 전략 (언어 감지 후 모델 선택, 번역 여부).
- Embedding store 교체 가능성 (Pinecone, Chroma) → 인터페이스 설계 유지.
- 팀/봇 메타 활용: 라벨링에 필요한가? 인사이트 용인가?
- Incremental run 시 기존 라벨과 diff 관리 방법? (e.g., conversation closed after update).
- 향후 실시간 처리(웹훅) 필요 여부.

---

이 문서를 기준으로 각 모듈/파이프라인을 순차적으로 구현하고, 변경 사항은 `docs/channel_talk_labeler_design.md` 업데이트를 통해 추적한다.
