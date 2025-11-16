🎯 목표

ChannelTalk API에서 기간별 상담 데이터를 가져와 요약 및 다중 라벨을 부여하고, 구조화된 데이터로 저장한다.

OpenAI Agents SDK를 사용하여 에이전트를 만들고, 필요한 작업을 Function Tool로 분리한다.

민감 정보(휴대폰번호, 계좌번호, 주소 등)를 필터링하고, 안전하게 데이터를 처리한다.

라벨링 결과를 추후 리포트/시각화에 활용할 수 있도록 정규화된 형태로 저장한다.

📦 1. 환경 준비
1.1 Python 패키지 설치
python -m venv venv
source venv/bin/activate
pip install openai==1.\* requests pandas python-dotenv

1.2 환경 변수 설정 (.env)
OPENAI_API_KEY=sk-...
CHANNELTALK_ACCESS_KEY=your_access_key
CHANNELTALK_ACCESS_SECRET=your_access_secret

🛠 2. ChannelTalk API 도구 정의

Agents SDK에서 사용할 함수들은 다음과 같이 Python으로 정의한다:

import os
import requests

ACCESS_KEY = os.getenv("CHANNELTALK_ACCESS_KEY")
ACCESS_SECRET = os.getenv("CHANNELTALK_ACCESS_SECRET")
BASE_URL = "https://open.channel.io"

def fetch_user_chat_list(createdFrom: str, createdTo: str) -> dict:
url = f"{BASE_URL}/open/v5/user-chats"
headers = {
"X-Access-Key": ACCESS_KEY,
"X-Access-Secret": ACCESS_SECRET
}
params = {"createdFrom": createdFrom, "createdTo": createdTo}
res = requests.get(url, headers=headers, params=params)
res.raise_for_status()
return res.json()

def fetch_chat_metadata(userChatId: str) -> dict:
url = f"{BASE_URL}/open/v5/user-chats/{userChatId}"
headers = {
"X-Access-Key": ACCESS_KEY,
"X-Access-Secret": ACCESS_SECRET
}
res = requests.get(url, headers=headers)
res.raise_for_status()
return res.json()

def fetch_chat_messages(userChatId: str, limit: int = 100, cursor: str = None) -> dict:
url = f"{BASE_URL}/open/v5/user-chats/{userChatId}/messages"
headers = {
"X-Access-Key": ACCESS_KEY,
"X-Access-Secret": ACCESS_SECRET
}
params = {"limit": limit}
if cursor:
params["cursor"] = cursor
res = requests.get(url, headers=headers, params=params)
res.raise_for_status()
return res.json()

🧠 3. 민감 정보(PII) 필터링 함수
import re

def mask*pii(text: str) -> str: # 휴대폰 번호 마스킹 (예: 010-1234-5678 → **\*-\*\***-\*\*\**)
phone*pattern = re.compile(r'\b(01[0-9])[ -]?(\d{3,4})[ -]?(\d{4})\b')
text = phone_pattern.sub('***-\***\*-\*\*\*\*', text)

    # 계좌번호 마스킹 (8~14자리 숫자 → ************)
    account_pattern = re.compile(r'\b\d{8,14}\b')
    text = account_pattern.sub('************', text)

    # 주소 간단 마스킹 (한국 주요 지역 키워드)
    for kw in ['서울', '경기', '부산', '대구', '인천',
               '광주', '대전', '울산', '세종', '제주']:
        text = re.sub(rf'{kw}[^\s,\.]*', '***', text)
    return text

상담 메시지 배열을 정제할 때 각 메시지의 plainText에 이 함수를 적용한다.

샘플 데이터도 동일한 방식으로 정제하여 임베딩 생성 시 민감 정보가 포함되지 않도록 한다.

🧱 4. OpenAI Agent 설정
4.1 에이전트 생성
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

agent = client.beta.v2.agents.create(
name="ChannelTalkLabeler",
description="채널톡 상담 데이터를 요약하고 라벨링합니다.",
model="gpt-4-1106-preview",
instructions=(
"주어진 상담 대화 메시지를 분석하여 핵심 요약과 라벨을 반환하세요. "
"휴대폰번호, 계좌번호, 주소 등 개인정보는 '\*\*\*'로 마스킹하세요. "
"결과는 summary, labels 배열, emotion 세 가지 속성으로 구성된 JSON 객체여야 합니다."
),
tools=[ # 위에서 정의한 세 함수 등록
{
"type": "function",
"function": {
"name": "fetch_user_chat_list",
"description": "기간 내 상담 ID 목록을 가져옵니다",
"parameters": {
"type": "object",
"properties": {
"createdFrom": {"type": "string", "format": "date-time"},
"createdTo": {"type": "string", "format": "date-time"}
},
"required": ["createdFrom", "createdTo"]
}
}
},
{
"type": "function",
"function": {
"name": "fetch_chat_metadata",
"description": "특정 상담의 메타 정보를 가져옵니다",
"parameters": {
"type": "object",
"properties": {
"userChatId": {"type": "string"}
},
"required": ["userChatId"]
}
}
},
{
"type": "function",
"function": {
"name": "fetch_chat_messages",
"description": "특정 상담의 메시지 목록을 가져옵니다",
"parameters": {
"type": "object",
"properties": {
"userChatId": {"type": "string"},
"limit": {"type": "integer"},
"cursor": {"type": "string"}
},
"required": ["userChatId"]
}
}
}
],
guardrails=[{
"type": "json",
"name": "safe_output",
"parameters": {
"return_schema": {
"type": "object",
"properties": {
"summary": {"type": "string"},
"labels": {"type": "array", "items": {"type": "string"}},
"emotion": {"type": "string"}
},
"required": ["summary", "labels"]
}
}
}]
)

instructions에서 개인정보 마스킹 지시를 명시함.

guardrails를 통해 JSON 형태를 강제하여 안정적인 응답을 얻는다
galileo.ai
.

4.2 상담 대화 요약/라벨링 호출
import json

def summarize_and_label_dialog(dialog_text: str) -> dict:
user_message = f"{dialog_text}"
response = client.beta.v2.chat.completions.create(
agent_id=agent.id,
messages=[{"role": "user", "content": user_message}]
)
content = response.choices[0].message.content
return json.loads(content)

dialog_text는 mask_pii()를 적용한 뒤 시간순으로 병합한 상담 메시지.

결과는 {"summary": ..., "labels": [...], "emotion": ...} 구조.

🔁 5. 전체 파이프라인 플로우

기간 선택: createdFrom, createdTo 설정.

상담 목록 수집: fetch_user_chat_list() 호출 → 상담 ID 배열 반환.

상담별 메타‧메시지 수집:

fetch_chat_metadata()로 메타데이터.

fetch_chat_messages()로 페이지네이션하여 모든 메시지 수집.

민감 정보 마스킹 및 병합:

각 메시지의 plainText에 mask_pii() 적용.

[sender] text 형식으로 시간순 병합해 하나의 문자열 생성.

에이전트 호출:

summarize_and_label_dialog()에 병합된 문자열 전달.

결과 저장:

원하는 형태(예: CSV/엑셀/DB)로 userChatId, 요약, 라벨, 기타 메타데이터를 저장.

원본 메시지는 별도 테이블이나 시트에 보관하여 JOIN 가능하게 함.

(선택) 리포트 생성 및 시각화:

기간별 통계 요약(라벨별 건수, 감정 분포)을 자동 생성.

추후 Looker Studio 등과 연결 가능.

📂 6. 샘플 데이터 관리

샘플 구조: text와 labels 필드를 가진 여러 행으로 구성 (CSV/JSON).

벡터화: 업로드 시 임베딩을 생성하고 로컬 DB나 파일로 저장. 이 임베딩을 사용해 새 문의와 유사도 비교를 하거나 LLM 프롬프트에 few-shot 예제로 포함할 수 있음.

업로드/다운로드: CSV/JSON 파일을 업로드해 저장하고, 필요시 다운로드 기능도 제공.

✅ 마무리

이 설계는 ChannelTalk API와 Agents SDK를 활용하여 상담 데이터를 자동으로 수집하고, 개인 정보 마스킹과 요약‧라벨링을 수행한 후, 구조화된 출력으로 저장·관리하는 완전한 파이프라인입니다. Codex는 이 문서를 기반으로 설치, 함수 정의, 에이전트 설정, PII 필터링, 데이터 저장까지 일련의 작업을 자동으로 구현할 수 있을 것입니다.
