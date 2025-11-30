# Architecture Review Checklist

리뷰 세션에서 확인했던 핵심 질문/답변을 모아서 빠르게 복습할 수 있도록 정리했다.

## 1. 데이터 계층 이해
- **Raw Layer를 보존하는 이유**  
  ChannelTalk API 응답을 변형 없이 저장해 두면 스키마 변경이나 추가 분석이 필요할 때 재수집 없이 재가공만으로 대응 가능하다.
- **Domain Layer와 Label Layer 분리**  
  `inquiries`, `inquiry_messages`는 정규화된 대화 본문, `labels`, `label_audit`는 라벨 결과와 이력. 같은 DB에 두더라도 테이블로 구분해 책임을 나눈다.
- **조인 방식**  
  `labels.inquiry_id` = `inquiries.id`(=userChatId). 라벨 결과에서 원본 메타/전문이 필요할 때는 이 키로 조인해 가져온다.

## 2. 배치 & Push 트리거
- Airflow/cron 등이 매일 배치를 돌려 Cursor 기반으로 원본 데이터를 저장하고 도메인 계층을 업데이트한다.
- ConversationFactory가 새 `userChatId` 목록(`new_inquiry_ids`)을 반환하면, 배치가 **push 방식**으로 라벨러에 ID 리스트를 전달한다.
- 라벨러는 전달받은 ID로 도메인 테이블을 직접 조회해 라벨링하므로 결합도가 낮고 재시도도 간단해진다.

## 3. 라벨러 & 에러 처리
- LLM 호출/JSON 파싱 실패 시 `LabelerService`가 정해진 횟수만큼 자동 재시도, 여전히 실패하면 `labels`에 `status=failed`로 저장하고 `LabelRunManager`에 기록.
- Confidence 임계치 미달 등 애매한 결과는 `status=needs_review`로 기록해 Manual Review 큐에 넣는다.
- 수동 수정이 이뤄지면 `label_audit`에 history를 남겨 품질 추적이 가능하다.

## 4. 샘플 데이터 & 벡터 스토어
- 샘플 입력 필드는 최소 `text`, `labels`(다중 라벨 지원). Summary/근거가 있으면 프롬프트 품질이 향상된다.
- 샘플 라벨이 곧 라벨 스키마이므로, CSV/JSON ingest 시 필수 필드 검증과 중복 처리 필요.
- 현재 전략은 버전 관리 대신 “샘플이 수정/추가되면 벡터와 라벨 스키마를 즉시 갱신한다”는 방식으로 단순화했다. 즉, 최신 샘플 상태가 곧 라벨 기준이 된다.

## 5. 전반 플로우 요약
1. 배치가 Cursor 기반으로 ChannelTalk API → Raw 레이어 적재.
2. ConversationFactory가 Raw→Domain 변환 + `new_inquiry_ids` 생성.
3. 배치가 새 ID 리스트를 라벨러에 push.
4. 라벨러는 ID로 도메인 조회 → 샘플 검색 → 프롬프트 → LLM → `labels` 저장.
5. 실패/리뷰 필요 건은 상태값으로 구분하고 Manual Review/재시도 대상에 포함.

이 체크리스트로 설계 리뷰 전에 핵심 질문을 빠르게 복습하거나, 팀과의 Q&A 내용을 문서로 남길 수 있다.
