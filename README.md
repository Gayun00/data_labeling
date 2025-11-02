# Review Labeling MVP

이 프로젝트는 `mvp.md` 설계를 바탕으로 고객 상담 대화를 요약하고 분류하는 최소 기능 제품(MVP)입니다. 전체 데이터 파이프라인은 다음과 같이 구성됩니다.

```
[원본 대화] ─┐
             │> 요약 → 임베딩 → 벡터 저장 → 유사도 검색 → Few-shot 분류 → 결과 저장
[샘플 데이터] ┘
```

## 디렉터리 구조

```
review-labeler-mvp/
├── data/
│   ├── conversations/   # 입력 대화 CSV/JSON
│   ├── results/         # 라벨링 결과
│   └── samples/         # 샘플 및 벡터 저장소
├── src/
│   ├── models.py        # 데이터 모델 정의
│   ├── llm_service.py   # LLM 호출 래퍼
│   ├── vector_store.py  # 벡터 저장/검색
│   ├── sample_manager.py# 샘플 관리 로직
│   ├── pipeline.py      # 메인 파이프라인 오케스트레이터
│   └── utils.py         # 공용 유틸리티
├── ui/
│   └── app.py           # Streamlit UI 진입점
├── tests/
│   └── test_pipeline.py # 파이프라인 단위 테스트
├── .env.example         # 환경 변수 템플릿
├── requirements.txt     # 의존성 목록
└── README.md            # 프로젝트 개요
```

## 빠른 시작

1. 가상환경을 구성하고 의존성을 설치합니다.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. `.env.example`을 참고해 `.env`를 생성하고 OpenAI 키 등 환경변수를 설정합니다.
3. Streamlit UI를 실행합니다.
   ```bash
   streamlit run ui/app.py
   ```

## 구현 우선순위

- [x] 디렉터리 및 파일 스캐폴딩
- [ ] 데이터 모델/서비스 레이어 구현
- [ ] 파이프라인 로직 작성
- [ ] Streamlit UI 연동
- [ ] 테스트 작성 및 자동화

향후에는 채널톡 API 연동, 일일 배치 스케줄러, 능동 학습 등 로드맵에 따라 확장할 수 있도록 구조화되어 있습니다.
