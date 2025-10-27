# 리뷰 자동 라벨링 MVP

Streamlit 기반으로 샘플 라벨 데이터를 이용해 신규 리뷰를 자동 분류하는 프로토타입입니다.  
OpenAI 임베딩과 LLM을 활용해 카테고리, 요약, 의도 등의 라벨을 예측합니다.

## 주요 구성

- `app/streamlit_app.py` – Streamlit UI 엔트리 포인트
- `app/core/` – 설정, 스키마, 파이프라인 핵심 로직
- `app/ui/` – 세션/상태 관리 유틸
- `app/infra/` – 스토리지·로깅 등 인프라 계층 (추후 구현)

## 실행 전제

1. Python 3.10 이상
2. 의존성 설치

```bash
pip install -r requirements.txt
```

3. 필요한 환경변수 설정(예: `OPENAI_API_KEY`, `STORAGE`, `TMP_DIR`)

## 실행

```bash
streamlit run app/streamlit_app.py
```

## 개발 단계

1. 프로젝트 스캐폴딩 및 기본 UI 구성 ✅
2. CSV 검증/전처리 및 임베딩 파이프라인
3. 규칙 엔진, LLM 프롬프트, Chroma 연동
4. 결과 다운로드/통계, 예외 처리 강화
5. 테스트/배포 및 운영 가이드

