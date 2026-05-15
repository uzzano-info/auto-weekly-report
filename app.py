# app.py
import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from agents import build_graph

st.set_page_config(page_title="주간 보고서 자동화", page_icon="📝")

st.title("📝 오토 위클리 리포트 생성기")
st.write("버튼을 누르면 로컬 폴더의 메모와 Git 로그를 취합하여 주간 보고서를 작성합니다.")

if st.button("보고서 생성 시작", type="primary"):
    with st.spinner("AI가 데이터를 수집하고 분석 중입니다... 잠시만 기다려주세요."):
        # LangGraph 실행 (실무에서는 @st.cache_resource 로 build_graph를 캐싱하는 것을 권장합니다)
        graph = build_graph()
        
        # 메모리 체크포인터용 thread_id 설정
        config = {"configurable": {"thread_id": "user_123"}}
        
        # 초기 상태 전송
        initial_state = {"raw_data": "", "analyzed_data": "", "final_report": "", "messages": []}
        result = graph.invoke(initial_state, config=config)
        
        report = result["final_report"]
        
    st.success("✅ 보고서 생성 완료!")
    
    # 결과 화면 출력
    st.markdown("### 📊 생성된 보고서")
    st.info(report)
    
    # 오늘 날짜 추출
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 다운로드 버튼
    st.download_button(
        label="📥 마크다운 파일 다운로드",
        data=report,
        file_name=f"Weekly_Report_{today_str}.md",
        mime="text/markdown"
    )
