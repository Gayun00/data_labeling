## ChannelTalk Auto Labeler

`channel.md` 사양에 맞춘 신규 파이프라인입니다. 기존 엑셀 업로드 흐름과 분리되어 `channel_agent/` 폴더에서 동작합니다.

### 준비
1. 의존성 추가 설치  
   ```bash
   pip install -r requirements.txt
   ```
2. 환경 변수 (`.env`)  
   ```
   OPENAI_API_KEY=sk-...
   CHANNELTALK_ACCESS_KEY=your_access_key
   CHANNELTALK_ACCESS_SECRET=your_access_secret
   # 옵션
   CHANNELTALK_BASE_URL=https://open.channel.io
   CHANNEL_OUTPUT_DIR=data/channel/results
   OPENAI_MODEL=gpt-4-1106-preview
   ```

### 빠른 실행 (샘플 스크립트)
`python -m channel_agent.runner --from 2024-08-01T00:00:00Z --to 2024-08-07T23:59:59Z`

### 구성 요소
- `channel_api.py` : ChannelTalk API 호출 도구들
- `pii.py` : 휴대폰/계좌/주소 마스킹
- `agent.py` : OpenAI Agents SDK 기반 에이전트 정의
- `pipeline.py` : 날짜 범위별 수집→마스킹→요약/라벨링→CSV 저장
- `storage.py` : 결과 저장 유틸
- `ui_app.py` : Streamlit 기반 샘플(text, labels) 관리 UI, 날짜 범위 선택 후 라벨링 실행(목/실제 모드)
- `sample_vectors.py` : 샘플 데이터를 임베딩해 간단한 유사도 검색용 로컬 인덱스(JSON) 생성/조회
  - 라벨링 결과: `labeled_chats.csv`(대화별) + `chat_labels.csv`(라벨 explode) + `skipped_chats.csv`(off-topic/abuse 스킵 로그)

### 출력
`data/channel/results/labeled_chats.csv` 에 `user_chat_id, summary, labels, emotion, created_at, custom_fields` 컬럼이 저장됩니다. labels는 `|` 로 join 되어 있습니다.

### 주의
- 네트워크 호출이 필요한 코드이므로 실제 실행 시 올바른 API 키 세팅이 필요합니다.
- 에이전트는 실행 시점에 생성되며, 동일 세션에서 재사용됩니다. 기존 에이전트 ID를 재사용하려면 `ChannelAgent.summarize_and_label_dialog(..., agent_id=<id>)` 로 전달할 수 있습니다.
- 현재 `channel_api.py`는 호출이 어려운 환경을 고려해 목 데이터를 반환하도록 되어 있습니다. 실제 연동 시 주석 처리된 요청 코드를 되살리고 목 데이터를 제거하세요.

### 샘플/라벨링 UI
- 실행: `streamlit run channel_agent/ui_app.py`
- 탭 1: 샘플 관리 — CSV/엑셀 업로드 또는 직접 입력(editable grid)으로 `text`, `labels` 필드 관리 → `data/channel/samples/samples.csv` 저장. 라벨은 콤마(,)나 파이프(|) 구분을 허용, 저장 시 `|` 정규화(다중 라벨 지원).
- 탭 2: 라벨링 실행 — 날짜 범위 선택 후 파이프라인 실행 결과를 UI에서 미리보고 CSV 다운로드. 기본은 목(Mock) 모드(키/네트워크 없이), 실사용 시 체크 해제 후 키/네트워크 필요. 로컬 PII 마스킹을 끌 수 있는 옵션으로 에이전트/가드레일이 직접 마스킹하는지 테스트할 수 있습니다.
- 샘플 벡터 인덱스: 샘플 탭에서 “인덱스 생성/갱신”으로 `data/channel/samples/sample_vectors.json` 생성. 모의 임베딩(키/네트워크 없이) 또는 OpenAI 임베딩 선택 가능. 질의 입력 후 유사도 검색 결과를 바로 표로 확인할 수 있습니다.
