# 개발 진행 방식 메모

이 문서는 기능 설계 외에 **구현과 검증을 어떻게 진행할지**에 대한 가이드라인을 정리한다. MVP를 빠르게 만들면서도 구조를 이해하고 재미를 느낄 수 있도록, 작은 단위 설계→구현→확인의 사이클을 반복한다.

## 1. 기본 철학
- **작은 반복**: 큰 기능을 바로 만들기보다, ConversationFactory → LabelerService → Export 등 각 컴포넌트를 작은 입력/출력 예제로 먼저 구현하고 확인한다.
- **가시성 확보**: 각 단계의 결과를 바로 확인할 수 있는 CLI/Notebook/간단한 리포트를 만들어두고, 동작을 눈으로 보면서 구조를 이해한다.
- **도메인 스키마 고정**: `domain.inquiries` / `labels` 등의 공통 스키마를 기준으로 모든 컴포넌트를 연결한다. 다른 소스를 붙이거나 확장할 때는 Adapter만 바뀌어야 한다.

## 2. 단계별 진행 예시
1. **샘플 데이터 준비**  
   - 실제 API 대신 로컬 JSON/CSV로 `userChats + messages` 예시를 만들고, ConversationFactory가 어떻게 하나의 문의 객체를 만드는지 확인한다.
2. **ConversationFactory 구현**  
   - 입력→출력 예제를 테스트하는 간단한 CLI/노트북을 만들어 결과를 print/log로 확인.  
   - 문제 없이 정제되면 `domain.inquiries` 저장 형식을 확정한다.
3. **LabelerService 프로토타입**  
   - 라벨러는 `inquiry_id` 하나를 받아 샘플 검색→프롬프트→LLM 호출→검증까지 실행하는 함수를 우선 만든다.  
   - 테스트에서는 모의 LLM 응답을 사용하거나 짧은 대화로 직접 호출해 본다.
4. **Export/리포트 확인**  
   - `inquiries + labels`를 join해서 CSV/간단한 DataFrame으로 출력해 보고, 포함해야 할 컬럼/요약을 실제로 눈으로 확인한다.
5. **샘플/벡터 스토어**  
   - 샘플 JSON을 적고, 저장 버튼을 누르면 벡터가 재생성되는지 테스트.  
   - 라벨링 전 샘플 검색 결과를 log로 출력해 샘플이 기대대로 오는지 확인한다.

## 3. 테스트 & 데모 방식
- **Notebook/CLI**: `scripts/demo_conversation_factory.py`, `notebooks/labeler_demo.ipynb` 같은 도구로 빠르게 실행해 본다.
- **로그/리포트**: 각 단계에서 핵심 정보(예: 라벨 결과, 샘플 유사도, 실패 이유)를 로그에 남겨, 로컬에서 바로 확인할 수 있게 한다.
- **점진적 구현**: 한 컴포넌트를 구현하면 바로 작은 테스트로 검증하고, 그 결과를 토대로 다음 컴포넌트 설계를 정리한다.

## 4. 향후 확장 시 유의점
- 다른 데이터 소스/리포트/모니터링을 추가할 때도 이 방식대로 “작게 설계→직접 실행→확인” 사이클을 반복한다.
- 세부 기능 논의는 각 컴포넌트를 구현하기 직전에 짧게 설계하고, 결과를 문서에 업데이트한다.

## 5. 핵심 로직 설계 (실행 가이드)
아래 설계는 위 반복 철학을 그대로 적용해 **ConversationFactory → Labeling Service → Export** 흐름을 순서대로 구현하기 위한 체크리스트다.

### 5.1 ConversationFactory
- **입력 소스**: `data/raw/user_chats/*.jsonl`, `data/raw/messages/*.jsonl` (임시로 샘플 CSV/JSON을 사용해도 됨).
- **출력 스키마**: `data/domain/inquiries.jsonl`, `data/domain/inquiry_messages.jsonl` 혹은 SQLite 테이블. `Conversation` dataclass와 동일한 필드 유지.
- **단계**
  1. `scripts/demo_conversation_factory.py`에서 최소 2건의 raw 데이터를 읽어 factory를 호출.
  2. 메시지 병합/정렬 → Participants 구성 → meta 채우기 과정을 함수로 분리(`build_messages`, `build_participants`).
  3. 성공/실패 케이스를 로그로 출력하고, 실패 건은 `data/domain/_failed_inquiries.jsonl`에 저장해 재현 가능하도록 한다.
- **검증 포인트**
  - 메시지 개수와 시간 정렬이 raw와 일치하는지.
  - `new_inquiry_ids` 리스트가 생성되는지 (직전 빌드 시각을 state 파일로 저장).
  - CLI 실행 결과를 README에 캡처해두고, 실패 시 바로 raw 데이터를 열어 비교한다.

### 5.2 샘플/벡터 준비
- **목표**: 사람이 입력한 샘플 CSV를 로딩→검증→임베딩→벡터 스토어 업데이트까지 한 번의 명령으로 실행.
- **샘플 포맷**: `sample_id(optional), label_primary, label_secondary(optional, comma), summary, raw_text(optional)`.
- **워크플로우**
  1. `SampleManager.ingest_from_csv()` 호출을 위한 CLI(`scripts/ingest_samples.py`) 작성.
  2. `auto_embed=True`일 때 `embeddings/tfidf.py` 또는 OpenAI 임베딩을 사용하여 `VectorStore.upsert_samples` 호출.
  3. 결과는 `data/samples/library.json` + `data/samples/vectors.pkl`(임시)로 직렬화.
- **검증 포인트**
  - CSV 내 필수 컬럼 누락 시 오류 메시지가 사람이 읽기 쉬운지.
  - 벡터 수와 레코드 수가 일치하는지 테스트 (`pytest tests/test_samples.py`).
  - 재실행 시 같은 sample_id가 덮어쓰이고, vector_id는 유지되는지 확인.

### 5.3 LabelerService
- **입력**: `new_inquiry_ids` JSON 리스트 + `SampleLibrary` + 라벨 스키마 정의(`config/labels.yaml`).
- **주요 컴포넌트**
  1. `SimilarityRetriever.retrieve(conversation, library)`로 상위 K개 샘플 확보.
  2. `PromptBuilder` (신규 모듈)에서 context/task/instruction 섹션을 조합.
  3. `LLMService.label()` 실행 후 JSON 파싱, 스키마 검증(`pydantic` 또는 수동 체크).
  4. 실패 시 `RetryPolicy` (예: 2회) → 지속 실패면 `LabelRunManager`에 `status=failed`로 기록.
- **실행 플로우**
  - `scripts/run_labeler.py --ids data/domain/new_ids.json` 형태로 CLI 작성.
  - LLM 없이도 동작 확인을 위해 `MockLLMService`를 추가하여 deterministic JSON을 반환하게 하고 단위 테스트에 사용.
- **검증 포인트**
  - 각 문의마다 한번씩 LLM이 호출되는지 로깅.
  - 프롬프트 길이가 임계값(예: 6k tokens)을 넘으면 요약 단계를 거쳤는지.
  - 라벨 스키마에 없는 값이 나오면 실패로 처리되고 재시도 큐에 들어가는지.

### 5.4 Export & 리뷰 루프
- **출력**: `data/results/labels.csv`, `data/results/report_{date}.xlsx`.
- **단계**
  1. `labels.status='completed'`인 건만 조인하여 기본 리포트 (문의 ID, 채널, 태그, 라벨, confidence) 생성.
  2. `needs_review/failed` 목록을 별도 CSV로 만들어 수동 검토 UI 또는 Google Sheet로 업로드.
  3. 사람이 수정한 결과를 다시 `labels` 테이블에 upsert 할 수 있는 `scripts/apply_manual_labels.py` 마련.
- **검증 포인트**
  - Export 스크립트 실행으로 생성된 파일을 바로 열어볼 수 있는지.
  - 수동 수정 후 재업로드 시 기존 자동 라벨을 덮어쓰되 `source=human`, `updated_at`을 기록하는지.

### 5.5 실행 순서 요약
1. `demo_conversation_factory.py`로 raw→domain 변환 확인.
2. `ingest_samples.py`로 샘플 라이브러리/벡터 생성.
3. `run_labeler.py` (mock LLM)로 end-to-end 건 1~2개 처리.
4. OpenAI 키 설정 후 실제 LLM 호출 및 결과 검증.
5. `export_reports.py`로 CSV/엑셀 생성, `needs_review` 리스트 공유.

각 단계가 독립 실행 가능하도록 CLI/노트북을 유지하면, 새 기능을 추가할 때도 동일한 실험 구조를 재사용할 수 있다.

이 문서는 구현 방법을 구체화할 때 참고용으로 유지하며, 필요 시 각 단계에서 얻은 인사이트나 개선점을 추가 기록한다.
