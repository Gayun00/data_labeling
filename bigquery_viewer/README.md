# BigQuery 메시지 뷰어

Channel.io 메시지 데이터를 BigQuery에서 가져와서 Streamlit으로 시각화하는 앱입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 설정

### 1. 인증 파일

프로젝트 루트에 `accountkey.json` 파일이 있어야 합니다.
BigQuery 서비스 계정 키 파일입니다.

### 2. 환경변수 설정

`bigquery_viewer` 폴더에 `.env` 파일을 생성하고 다음 중 하나의 방법으로 설정하세요:

**방법 1: 전체 테이블명 한 번에 지정**

```bash
BQ_TABLE_FULL=your-project-id.your-dataset.your-table
```

**방법 2: 분리해서 지정**

```bash
BQ_PROJECT_ID=your-project-id
BQ_DATASET=your-dataset
BQ_TABLE=your-table
```

참고: `BQ_TABLE_FULL`이 설정되어 있으면 우선 사용됩니다.
없으면 `BQ_PROJECT_ID`, `BQ_DATASET`, `BQ_TABLE`을 조합해서 사용합니다.

`.env.example` 파일을 참고하세요.

## 실행

```bash
streamlit run app.py
```

## 기능

- **오늘 메시지**: 오늘 하루의 모든 메시지 조회
- **날짜 선택**: 특정 날짜의 메시지 조회
- **키워드 검색**: 키워드가 언급된 대화방의 전체 대화 조회
