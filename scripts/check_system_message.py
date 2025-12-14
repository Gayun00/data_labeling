"""특정 시스템 메시지 확인"""
import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
import json

# 환경변수 로드
project_root = Path(__file__).parent.parent
env_path = project_root / "bigquery_viewer" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    root_env = project_root / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    else:
        load_dotenv()

def get_table_name():
    """환경변수에서 테이블명 가져오기"""
    table_full = os.getenv("BQ_TABLE_FULL")
    if table_full:
        return table_full
    
    project_id = os.getenv("BQ_PROJECT_ID")
    dataset = os.getenv("BQ_DATASET", "channel_io")
    table = os.getenv("BQ_TABLE", "messages")
    
    if project_id:
        return f"{project_id}.{dataset}.{table}"
    else:
        # credentials에서 프로젝트 ID 가져오기
        script_dir = Path(__file__).parent
        accountkey_path = script_dir.parent / "accountkey.json"
        if accountkey_path.exists():
            credentials = service_account.Credentials.from_service_account_file(str(accountkey_path))
            project_id = credentials.project_id
            return f"{project_id}.{dataset}.{table}"
    
    raise ValueError("테이블명을 확인할 수 없습니다. 환경변수를 설정해주세요.")

def main():
    """특정 시스템 메시지 확인"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    accountkey_path = project_root / "accountkey.json"
    
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or str(accountkey_path)
    
    if not os.path.exists(credentials_path):
        print(f"인증 파일을 찾을 수 없습니다: {credentials_path}")
        return
    
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    project_id = credentials.project_id
    client = bigquery.Client(project=project_id, credentials=credentials)
    
    # 테이블명 가져오기
    table_name = get_table_name()
    
    # 특정 시간의 시스템 메시지 확인
    query = f"""
    SELECT
        m.id,
        m.chatId,
        TIMESTAMP_MILLIS(m.createdAt) AS created_at,
        m.personType,
        m.plainText,
        m.blocks,
        m.workflow,
        m.log,
        m.options,
        TO_JSON_STRING(m) AS full_json
    FROM `{table_name}` m
    WHERE TIMESTAMP_MILLIS(m.createdAt) BETWEEN TIMESTAMP('2025-10-21 07:07:00')
      AND TIMESTAMP('2025-10-21 07:07:10')
      AND m.personType = 'bot'
      AND m.plainText IS NULL
    LIMIT 5
    """
    
    print("쿼리 실행 중...")
    print("=" * 80)
    
    query_job = client.query(query)
    results = query_job.result()
    df = results.to_dataframe()
    
    if len(df) > 0:
        for idx, row in df.iterrows():
            print(f"\n샘플 #{idx + 1}")
            print(f"ID: {row['id']}")
            print(f"ChatId: {row['chatId']}")
            print(f"CreatedAt: {row['created_at']}")
            print(f"plainText: {row['plainText']}")
            print(f"\nworkflow:")
            print(json.dumps(row['workflow'], indent=2, ensure_ascii=False) if pd.notna(row['workflow']) else "NULL")
            print(f"\nlog:")
            print(json.dumps(row['log'], indent=2, ensure_ascii=False) if pd.notna(row['log']) else "NULL")
            print(f"\noptions:")
            print(row['options'])
            print(f"\nblocks:")
            print(json.dumps(row['blocks'], indent=2, ensure_ascii=False) if pd.notna(row['blocks']) else "NULL")
            print("\n" + "=" * 80)
    else:
        print("해당 시간의 메시지를 찾을 수 없습니다.")


if __name__ == "__main__":
    main()

