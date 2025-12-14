"""BigQuery 클라이언트 모듈"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from dotenv import load_dotenv

# 환경변수 로드: bigquery_viewer 폴더의 .env 파일 찾기
current_dir = Path(__file__).resolve().parent
env_path = current_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 없으면 프로젝트 루트의 .env도 시도
    project_root = current_dir.parent
    root_env = project_root / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    else:
        # 둘 다 없으면 기본 동작 (현재 디렉토리에서 찾기)
        load_dotenv()


class BigQueryClient:
    """BigQuery 클라이언트"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """초기화"""
        if credentials_path is None:
            # 프로젝트 루트의 accountkey.json 찾기
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            credentials_path = os.path.join(project_root, "accountkey.json")
        
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"인증 파일을 찾을 수 없습니다: {credentials_path}")
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        
        # 프로젝트 ID는 환경변수 우선, 없으면 credentials에서 가져옴
        project_id = os.getenv("BQ_PROJECT_ID") or credentials.project_id
        self.client = bigquery.Client(project=project_id, credentials=credentials)
        self.project_id = project_id
        
        # 테이블 정보 환경변수에서 가져오기
        self.table_full_name = os.getenv("BQ_TABLE_FULL")
        if not self.table_full_name:
            # 분리된 환경변수로 구성
            bq_project = os.getenv("BQ_PROJECT_ID") or project_id
            bq_dataset = os.getenv("BQ_DATASET", "channel_io")
            bq_table = os.getenv("BQ_TABLE", "messages")
            self.table_full_name = f"{bq_project}.{bq_dataset}.{bq_table}"
        
        # 디버깅용: 사용 중인 테이블명 출력
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"BigQuery 테이블 사용: {self.table_full_name}")
    
    def _extract_text_from_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """blocks 필드에서 텍스트 추출 및 워크플로우 정보 처리"""
        def extract_text(row):
            # plainText가 있으면 그대로 사용
            if pd.notna(row['plainText']) and row['plainText'] != '':
                return row['plainText']
            
            # blocks에서 텍스트 추출
            if pd.notna(row.get('blocks')):
                try:
                    blocks = row['blocks']
                    # JSON 문자열인 경우 파싱
                    if isinstance(blocks, str):
                        blocks = json.loads(blocks)
                    
                    if isinstance(blocks, list):
                        texts = []
                        for block in blocks:
                            if isinstance(block, dict):
                                # blocks 구조: [{"type": "text", "value": "..."}]
                                if 'value' in block:
                                    texts.append(str(block['value']))
                                elif 'text' in block:
                                    texts.append(str(block['text']))
                                elif 'content' in block:
                                    texts.append(str(block['content']))
                        if texts:
                            return '\n'.join(texts)
                except Exception as e:
                    # 파싱 실패 시 로그 (선택사항)
                    pass
            
            # plainText와 blocks가 모두 없으면 시스템 메시지 내용 생성
            system_msg = self._format_system_message(row)
            return system_msg
        
        def format_workflow_info(row):
            """워크플로우 정보 포맷팅"""
            info_parts = []
            
            # workflow 정보
            if pd.notna(row.get('workflow')):
                try:
                    workflow = row['workflow']
                    if isinstance(workflow, str):
                        workflow = json.loads(workflow)
                    if isinstance(workflow, dict):
                        workflow_str = f"워크플로우: {workflow.get('id', 'N/A')} (섹션: {workflow.get('sectionId', 'N/A')})"
                        info_parts.append(workflow_str)
                except:
                    pass
            
            # log 정보
            if pd.notna(row.get('log')):
                try:
                    log = row['log']
                    if isinstance(log, str):
                        log = json.loads(log)
                    if isinstance(log, dict):
                        log_str = f"액션: {log.get('action', 'N/A')}"
                        if log.get('triggerType'):
                            log_str += f" (트리거: {log.get('triggerType')})"
                        info_parts.append(log_str)
                except:
                    pass
            
            # options 정보
            if pd.notna(row.get('options')):
                try:
                    options = row['options']
                    if isinstance(options, str):
                        options = json.loads(options)
                    if isinstance(options, list) and options:
                        info_parts.append(f"옵션: {', '.join(options)}")
                except:
                    pass
            
            return ' | '.join(info_parts) if info_parts else None
        
        if 'blocks' in df.columns:
            # extract_text 내부에서 _format_system_message를 호출하므로 여기서는 그대로 사용
            df['plainText'] = df.apply(extract_text, axis=1)
        else:
            # blocks 컬럼이 없는 경우 (get_today_messages 등)
            df['plainText'] = df.apply(
                lambda row: self._format_system_message(row) if (pd.isna(row['plainText']) or row['plainText'] == '') else row['plainText'], 
                axis=1
            )
        
        # 워크플로우 정보 추가
        df['workflow_info'] = df.apply(format_workflow_info, axis=1)
        
        return df
    
    def _format_system_message(self, row) -> str:
        """시스템 메시지 내용 포맷팅"""
        parts = []
        
        # log 정보
        if pd.notna(row.get('log')):
            try:
                log = row['log']
                # BigQuery에서 가져올 때 이미 문자열일 수 있음
                if isinstance(log, str):
                    # JSON 문자열인 경우 파싱
                    if log.startswith('{') or log.startswith('['):
                        log = json.loads(log)
                    else:
                        # 일반 문자열인 경우 그대로 사용
                        parts.append(f"로그: {log}")
                        log = None
                
                if isinstance(log, dict):
                    action = log.get('action', '')
                    trigger_type = log.get('triggerType', '')
                    trigger_id = log.get('triggerId', '')
                    values = log.get('values', [])
                    
                    if action:
                        log_str = f"액션: {action}"
                        if values:
                            log_str += f" (값: {', '.join(map(str, values))})"
                        if trigger_type:
                            log_str += f" | 트리거 타입: {trigger_type}"
                            if trigger_id:
                                log_str += f" (ID: {trigger_id})"
                        parts.append(log_str)
            except Exception as e:
                # 파싱 실패 시 원본 문자열 표시
                if pd.notna(row.get('log')):
                    parts.append(f"로그: {str(row['log'])}")
        
        # workflow 정보
        if pd.notna(row.get('workflow')):
            try:
                workflow = row['workflow']
                if isinstance(workflow, str):
                    workflow = json.loads(workflow)
                if isinstance(workflow, dict):
                    workflow_id = workflow.get('id', '')
                    section_id = workflow.get('sectionId', '')
                    action_index = workflow.get('actionIndex', '')
                    if workflow_id:
                        workflow_str = f"워크플로우 ID: {workflow_id}"
                        if section_id:
                            workflow_str += f", 섹션: {section_id}"
                        if action_index is not None:
                            workflow_str += f", 액션 인덱스: {action_index}"
                        parts.append(workflow_str)
            except:
                pass
        
        # options 정보
        if pd.notna(row.get('options')):
            try:
                options = row['options']
                # BigQuery에서 가져올 때 이미 리스트일 수도 있음
                if isinstance(options, str):
                    # JSON 배열 문자열인 경우 파싱
                    if options.startswith('['):
                        options = json.loads(options)
                    else:
                        options = [options]
                
                if isinstance(options, list) and options:
                    parts.append(f"옵션: {', '.join(map(str, options))}")
            except Exception as e:
                # 파싱 실패 시 원본 표시
                if pd.notna(row.get('options')):
                    parts.append(f"옵션: {str(row['options'])}")
        
        if parts:
            return "[시스템 메시지]\n" + "\n".join(parts)
        else:
            return "[시스템 메시지]"
    
    def get_today_messages(self) -> pd.DataFrame:
        """오늘 하루의 모든 메시지 가져오기"""
        query = f"""
        SELECT
            m.id,
            m.chatId,
            TIMESTAMP_MILLIS(m.createdAt) AS created_at,
            m.personType,
            m.plainText,
            m.blocks
        FROM `{self.table_full_name}` m
        WHERE DATE(TIMESTAMP_MILLIS(m.createdAt)) = CURRENT_DATE()
        ORDER BY m.chatId, m.createdAt ASC
        """
        
        query_job = self.client.query(query)
        results = query_job.result()
        df = results.to_dataframe()
        
        return self._extract_text_from_blocks(df)
    
    def get_messages_by_date(self, target_date: str) -> pd.DataFrame:
        """특정 날짜의 모든 메시지 가져오기"""
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
            m.options
        FROM `{self.table_full_name}` m
        WHERE DATE(TIMESTAMP_MILLIS(m.createdAt)) = @target_date
        ORDER BY m.chatId, m.createdAt ASC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        df = results.to_dataframe()
        
        return self._extract_text_from_blocks(df)
    
    def get_messages_by_month(self, year: int, month: int, limit_chats: int = 50) -> pd.DataFrame:
        """특정 월에 메시지가 있는 대화방의 전체 메시지 가져오기"""
        start_date = f"{year}-{month:02d}-01"
        # 월의 마지막 날 계산
        if month == 12:
            end_date = f"{year}-12-31"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        query = f"""
        WITH chats_in_month AS (
          SELECT DISTINCT chatId
          FROM `{self.table_full_name}`
          WHERE DATE(TIMESTAMP_MILLIS(createdAt)) >= @start_date
            AND DATE(TIMESTAMP_MILLIS(createdAt)) < @end_date
          LIMIT @limit_chats
        )
        SELECT
            m.id,
            m.chatId,
            TIMESTAMP_MILLIS(m.createdAt) AS created_at,
            m.personType,
            m.plainText,
            m.blocks,
            m.workflow,
            m.log,
            m.options
        FROM `{self.table_full_name}` m
        INNER JOIN chats_in_month cim ON m.chatId = cim.chatId
        ORDER BY m.chatId, m.createdAt ASC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
                bigquery.ScalarQueryParameter("limit_chats", "INT64", limit_chats)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        df = results.to_dataframe()
        
        return self._extract_text_from_blocks(df)
    
    def get_messages_by_keyword(self, keyword: str, limit_chats: int = 10) -> pd.DataFrame:
        """키워드가 언급된 대화방의 전체 메시지 가져오기"""
        query = f"""
        WITH matching_chats AS (
          SELECT DISTINCT chatId
          FROM `{self.table_full_name}`
          WHERE LOWER(COALESCE(plainText, TO_JSON_STRING(blocks), '')) LIKE LOWER(@keyword)
          LIMIT @limit_chats
        )
        SELECT
            m.id,
            m.chatId,
            TIMESTAMP_MILLIS(m.createdAt) AS created_at,
            m.personType,
            m.plainText,
            m.blocks,
            m.workflow,
            m.log,
            m.options
        FROM `{self.table_full_name}` m
        INNER JOIN matching_chats mc ON m.chatId = mc.chatId
        ORDER BY m.chatId, m.createdAt ASC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("keyword", "STRING", f"%{keyword}%"),
                bigquery.ScalarQueryParameter("limit_chats", "INT64", limit_chats)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        df = results.to_dataframe()
        
        return self._extract_text_from_blocks(df)

