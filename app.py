# app.py
import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from agents import build_graph, ReportState
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

st.set_page_config(page_title="주간 보고서 자동화", page_icon="🛡️")

# 1. [보안] 세션 상태를 활용한 체크포인터 유지 (새로고침 방어)
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()
if "result" not in st.session_state:
    st.session_state.result = None
if "needs_approval" not in st.session_state:
    st.session_state.needs_approval = False

# 그래프 빌드 (세션 세이버 주입)
graph = build_graph(checkpointer=st.session_state.memory)
config = {"configurable": {"thread_id": "user_123"}}

st.title("🛡️ 보안 강화 위클리 리포트 스웜")
st.write("Notion, Git, 로컬 메모를 안전하게 분석하여 보고서를 생성합니다. (OWASP ASI 적용)")

# 2. [보안] 동적 개입 (HITL) 처리: 승인 대기 중인 경우
if st.session_state.needs_approval:
    st.warning("⚠️ 보안 경고: 데이터 내에서 민감 정보 패턴이나 프롬프트 인젝션 의심 텍스트가 발견되었습니다.")
    st.info("관리자의 승인이 있어야 분석을 계속 진행합니다.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 승인 (계속 진행)", type="primary"):
            with st.spinner("분석을 재개합니다..."):
                # Command(resume="approve")를 통해 interrupt 지점부터 다시 실행
                st.session_state.result = graph.invoke(Command(resume="approve"), config=config)
                st.session_state.needs_approval = False
                st.rerun()
    with col2:
        if st.button("🚫 거절 (중단)"):
            st.session_state.result = graph.invoke(Command(resume="reject"), config=config)
            st.session_state.needs_approval = False
            st.rerun()

# 3. 메인 실행 버튼
if not st.session_state.needs_approval and st.button("🚀 보고서 생성 시작", type="primary"):
    with st.spinner("🕵️ 데이터 수집 및 보안 스캐닝 중..."):
        # 초기 상태 전송
        initial_state = {"raw_data": "", "analyzed_data": "", "final_report": "", "messages": [], "risk_score": 0}
        
        # 그래프 실행
        st.session_state.result = graph.invoke(initial_state, config=config)
        
        # interrupt 발생 여부 확인
        snapshot = graph.get_state(config)
        if snapshot.next: # 다음 노드가 있다는 것은 interrupt로 멈췄음을 의미
            st.session_state.needs_approval = True
            st.rerun()

# 4. 결과 출력
if st.session_state.result and "final_report" in st.session_state.result and st.session_state.result["final_report"]:
    report = st.session_state.result["final_report"]
    
    st.success("✅ 보고서 생성 완료!")
    st.markdown("### 📊 생성된 보고서 (Sanitized)")
    st.info(report)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    st.download_button(
        label="📥 마크다운 파일 다운로드",
        data=report,
        file_name=f"Weekly_Report_{today_str}.md",
        mime="text/markdown"
    )
