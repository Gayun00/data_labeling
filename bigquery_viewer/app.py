"""BigQuery 메시지 뷰어 Streamlit 앱"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from bq_client import BigQueryClient

# 페이지 설정
st.set_page_config(
    page_title="Channel.io 메시지 뷰어",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid;
        color: #000000;
    }
    .chat-message.user {
        background-color: #e3f2fd;
        border-color: #2196f3;
        color: #000000;
    }
    .chat-message.manager {
        background-color: #f3e5f5;
        border-color: #9c27b0;
        color: #000000;
    }
    .chat-message.bot {
        background-color: #fff3e0;
        border-color: #ff9800;
        color: #000000;
    }
    .chat-header {
        font-weight: bold;
        margin-bottom: 0.5rem;
        color: #000000;
    }
    .chat-time {
        font-size: 0.85rem;
        color: #666;
    }
    .chat-message div {
        color: #000000;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)  # 1분 캐시 (디버깅용으로 짧게)
def load_messages(mode: str, date_str: str = None, keyword: str = None, limit_chats: int = 10, cache_key: str = None):
    """메시지 로드 (캐싱)"""
    try:
        client = BigQueryClient()
        
        if mode == "november":
            df = client.get_messages_by_month(2025, 11, limit_chats)
        elif mode == "today":
            df = client.get_today_messages()
        elif mode == "date":
            df = client.get_messages_by_date(date_str)
        elif mode == "keyword":
            df = client.get_messages_by_keyword(keyword, limit_chats)
        else:
            return pd.DataFrame()
        
        # 디버깅: 시스템 메시지 확인
        system_msgs = df[df['plainText'].str.contains('시스템 메시지', na=False)]
        if len(system_msgs) > 0:
            st.sidebar.info(f"시스템 메시지 {len(system_msgs)}개 발견")
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()


def format_message_html(person_type: str, created_at: datetime, plain_text: str, workflow_info: str = None) -> str:
    """메시지를 HTML로 포맷팅"""
    type_class = {
        'user': ('user', '👤 사용자'),
        'manager': ('manager', '💼 상담원'),
        'bot': ('bot', '🤖 봇')
    }.get(person_type, ('user', f'❓ {person_type}'))
    
    class_name, label = type_class
    time_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
    
    # 텍스트를 줄바꿈 처리
    text_html = plain_text.replace('\n', '<br>')
    
    # 워크플로우 정보 추가
    workflow_html = ""
    if workflow_info and pd.notna(workflow_info):
        workflow_html = f'<div style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; font-style: italic;">{workflow_info}</div>'
    
    return f"""
    <div class="chat-message {class_name}">
        <div class="chat-header">{label}</div>
        <div class="chat-time">{time_str}</div>
        <div>{text_html}</div>
        {workflow_html}
    </div>
    """


def main():
    """메인 앱"""
    st.title("💬 Channel.io 메시지 뷰어")
    
    # 사이드바
    with st.sidebar:
        st.header("필터 설정")
        
        mode = st.radio(
            "데이터 모드",
            ["11월 전체", "오늘", "날짜 선택", "키워드 검색"],
            index=0
        )
        
        date_str = None
        keyword = None
        limit_chats = 10
        
        if mode == "11월 전체":
            limit_chats = st.slider("최대 대화방 수", 1, 100, 50)
        elif mode == "날짜 선택":
            selected_date = st.date_input(
                "날짜 선택",
                value=date.today()
            )
            date_str = selected_date.strftime('%Y-%m-%d')
        elif mode == "키워드 검색":
            keyword = st.text_input("검색 키워드", placeholder="예: 김영익")
            limit_chats = st.slider("최대 대화방 수", 1, 50, 10)
        
        st.divider()
        
        # 통계 표시
        if st.button("🔄 데이터 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # 메인 영역
    if mode == "키워드 검색" and not keyword:
        st.info("키워드를 입력해주세요.")
        return
    
    # 모드에 따라 쿼리 파라미터 설정
    query_mode = {
        "11월 전체": "november",
        "오늘": "today",
        "날짜 선택": "date",
        "키워드 검색": "keyword"
    }[mode]
    
    # 데이터 로드
    with st.spinner("데이터를 불러오는 중..."):
        # 캐시 키에 현재 시간 추가하여 강제 새로고침 가능하게
        cache_key = f"{query_mode}_{date_str}_{keyword}_{limit_chats}"
        df = load_messages(query_mode, date_str, keyword, limit_chats, cache_key)
    
    if df.empty:
        st.warning("데이터가 없습니다.")
        return
    
    # 통계 정보
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 메시지", len(df))
    with col2:
        st.metric("총 대화방", df['chatId'].nunique())
    with col3:
        st.metric("사용자 메시지", len(df[df['personType'] == 'user']))
    with col4:
        st.metric("상담원 메시지", len(df[df['personType'] == 'manager']))
    
    st.divider()
    
    # 대화방별로 그룹화
    grouped = df.groupby('chatId')
    chat_ids = list(grouped.groups.keys())
    
    # 대화방 선택
    if len(chat_ids) > 0:
        selected_chat_idx = st.selectbox(
            f"대화방 선택 (총 {len(chat_ids)}개)",
            range(len(chat_ids)),
            format_func=lambda x: f"대화방 {x+1} ({len(grouped.get_group(chat_ids[x]))}개 메시지)"
        )
        
        selected_chat_id = chat_ids[selected_chat_idx]
        chat_df = grouped.get_group(selected_chat_id).sort_values('created_at')
        
        # 대화방 정보
        with st.expander("📋 대화방 정보", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Chat ID:** `{selected_chat_id}`")
                st.write(f"**메시지 수:** {len(chat_df)}개")
            with col2:
                person_types = chat_df['personType'].value_counts()
                st.write("**참여자:**")
                for pt, cnt in person_types.items():
                    st.write(f"- {pt}: {cnt}개")
            
            first_msg = chat_df['created_at'].min()
            last_msg = chat_df['created_at'].max()
            st.write(f"**기간:** {first_msg.strftime('%Y-%m-%d %H:%M:%S')} ~ {last_msg.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.divider()
        
        # 대화 내용 표시
        st.subheader("💬 대화 내용")
        
        # 각 메시지 표시
        for _, msg in chat_df.iterrows():
            workflow_info = msg.get('workflow_info') if 'workflow_info' in chat_df.columns else None
            html = format_message_html(
                msg['personType'],
                msg['created_at'],
                msg['plainText'],
                workflow_info
            )
            st.markdown(html, unsafe_allow_html=True)
        
        # 원본 데이터 테이블 (접을 수 있게)
        with st.expander("📊 원본 데이터 테이블"):
            st.dataframe(
                chat_df[['created_at', 'personType', 'plainText']],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("표시할 대화방이 없습니다.")


if __name__ == "__main__":
    main()

