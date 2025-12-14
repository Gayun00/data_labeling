"""시스템 메시지 포맷팅 테스트"""
import os
import sys
import json
import pandas as pd
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "bigquery_viewer"))

from bq_client import BigQueryClient

def main():
    """시스템 메시지 포맷팅 테스트"""
    client = BigQueryClient()
    
    # 11월 데이터 가져오기
    print("11월 데이터 가져오는 중...")
    df = client.get_messages_by_month(2025, 11, limit_chats=5)
    
    # 시스템 메시지 필터링
    system_messages = df[df['plainText'].str.contains('시스템 메시지', na=False)]
    
    print(f"\n총 {len(df)}개 메시지 중 시스템 메시지: {len(system_messages)}개")
    
    if len(system_messages) > 0:
        print("\n시스템 메시지 샘플:")
        print("=" * 80)
        for idx, (_, row) in enumerate(system_messages.head(3).iterrows(), 1):
            print(f"\n샘플 #{idx}")
            print(f"PersonType: {row['personType']}")
            print(f"CreatedAt: {row['created_at']}")
            print(f"plainText:")
            print(row['plainText'])
            print("=" * 80)
    else:
        print("\n시스템 메시지를 찾을 수 없습니다.")
        print("\nplainText가 NULL인 메시지 확인...")
        null_messages = df[df['plainText'].isna() | (df['plainText'] == '')]
        print(f"plainText가 NULL이거나 빈 메시지: {len(null_messages)}개")
        
        if len(null_messages) > 0:
            print("\n샘플:")
            sample = null_messages.iloc[0]
            print(f"PersonType: {sample['personType']}")
            print(f"CreatedAt: {sample['created_at']}")
            print(f"plainText: {sample['plainText']}")
            print(f"workflow_info: {sample.get('workflow_info', 'N/A')}")


if __name__ == "__main__":
    main()

