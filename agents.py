import os
from typing import TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
import nh3
import tools

# 1. 상태(State) 정의: 에이전트들이 서로 주고받을 데이터 구조
class ReportState(TypedDict):
    messages: Annotated[list, add_messages] # 대화 내역 누적용
    raw_data: str       # 수집된 원본 텍스트 (메모 + Git)
    analyzed_data: str  # 카테고리별로 분류/분석된 텍스트
    final_report: str   # 최종 완성된 마크다운 보고서
    risk_score: int     # [보안] 보안 위험도 점수 (0-100)

# 모델 초기화 (최신 Gemini 3 Flash 사용)
# 안정 버전 출시 후에는 model="gemini-3-flash"로 변경 가능
llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0.2)

def get_text_content(content) -> str:
    """LLM 응답에서 문자열을 안전하게 추출합니다 (최신 버전에 대비)"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])
    return str(content)

# 2. 노드 1: 수집가 (Collector) - 도구를 직접 호출하여 데이터 수집
def collector_node(state: ReportState) -> ReportState:
    print("🕵️ [Collector] 일일 메모, Git 로그, 그리고 노션 데이터를 수집합니다...")
    
    # 도구 호출
    notes = tools.read_daily_notes.invoke({"folder_path": "./daily_notes"})
    git_logs = tools.get_git_logs.invoke({"repo_path": "."})
    
    # 노션 데이터 수집
    notion_token = os.getenv("NOTION_API_KEY")
    notion_db_id = os.getenv("NOTION_DATABASE_ID")
    
    notion_data = "노션 설정이 되어 있지 않습니다."
    if notion_token and notion_db_id:
        notion_data = tools.read_notion_database.invoke({
            "integration_token": notion_token, 
            "database_id": notion_db_id
        })
    
    combined_data = f"### 일일 메모 ###\n{notes}\n\n### Git 커밋 로그 ###\n{git_logs}\n\n### 노션 업무 일지 ###\n{notion_data}"
    return {"raw_data": combined_data}

# [ASI01, ASI06, ASI09] 노드 1.5: 보안 가드 (Guardrail) - PII 마스킹 및 인젝션 탐지
def guard_node(state: ReportState) -> ReportState:
    print("🛡️ [Guardrail] 데이터 보안 스캔 및 PII 마스킹 중...")
    raw_data = state["raw_data"]
    
    # 1. PII 마스킹 (Shift-Left DLP)
    safe_data = tools.mask_sensitive_data(raw_data)
    
    # 2. 인젝션 탐지 (정규식 기반 1차 방어)
    risk_score = 0
    forbidden_words = ["ignore previous", "system prompt", "명령 무시", "지시 무시"]
    if any(word in safe_data.lower() for word in forbidden_words):
        risk_score += 50
        print("⚠️ [경고] 프롬프트 인젝션 의심 패턴 감지!")
    
    # 3. 동적 개입 (Dynamic HITL): 위험 점수 임계값 초과 시 일시 중단
    if risk_score >= 50:
        # interrupt()는 그래프를 멈추고, 사용자의 재개(resume) 입력을 기다림
        user_decision = interrupt(
            f"⚠️ 보안 경고: 프롬프트 인젝션 의심 (점수: {risk_score}). 승인하시겠습니까?"
        )
        if user_decision != "approve":
            print("🚫 [Guardrail] 사용자가 승인을 거절했습니다. 데이터를 비우고 진행합니다.")
            return {"raw_data": "[보안 정책에 의해 차단된 데이터]", "risk_score": risk_score}
        print("✅ [Guardrail] 사용자가 승인했습니다. 분석을 계속합니다.")
        
    return {"raw_data": safe_data, "risk_score": risk_score}

# 3. 노드 2: 분석가 (Analyzer) - 수집된 데이터를 카테고리화
def analyzer_node(state: ReportState) -> ReportState:
    print("🗂️ [Analyzer] 수집된 데이터를 분석하고 분류합니다...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "너는 꼼꼼한 데이터 분석가야. 제공된 메모와 커밋 로그를 읽고 [완료된 작업], [진행 중/예정 작업], [이슈 및 블로커] 3가지 카테고리로 명확하게 분류해줘. 전문적인 비즈니스 용어로 다듬어줘."),
        ("user", "{raw_data}")
    ])
    chain = prompt | llm
    result = chain.invoke({"raw_data": state["raw_data"]})
    return {"analyzed_data": get_text_content(result.content)}

# 4. 노드 3: 작성자 (Writer) - 최종 주간 보고서 마크다운 작성
def writer_node(state: ReportState) -> ReportState:
    print("✍️ [Writer] 최종 주간 보고서를 작성합니다...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "너는 대기업의 효율적인 기획자야. 제공된 분석 데이터를 바탕으로 상사에게 보고할 '주간 업무 보고서'를 마크다운 형식으로 작성해. 반드시 개조식(명사형 종결)으로 깔끔하게 정리해."),
        ("user", "{analyzed_data}")
    ])
    chain = prompt | llm
    result = chain.invoke({"analyzed_data": state["analyzed_data"]})
    return {"final_report": get_text_content(result.content)}

# [XSS 방어] 노드 4: 정제기 (Sanitizer) - 마크다운 출력물 정제
def sanitizer_node(state: ReportState) -> ReportState:
    print("🧹 [Sanitizer] 마크다운 출력 정제 중 (XSS 방어)...")
    final_report = state["final_report"]
    
    # 허용할 기본 태그 지정 (스크립트, 이프레임 등 위험 태그 제외)
    allowed_tags = {
        "b", "i", "strong", "em", "h1", "h2", "h3", "h4", "p", "br", 
        "ul", "ol", "li", "a", "code", "pre", "blockquote", "hr", "table", "thead", "tbody", "tr", "th", "td"
    }
    # nh3(Rust 기반) 라이브러리로 초고속 정제
    safe_report = nh3.clean(final_report, tags=allowed_tags)
    
    return {"final_report": safe_report}

# 5. 그래프(워크플로우) 조립
def build_graph(checkpointer=None):
    workflow = StateGraph(ReportState)
    
    # 노드 추가 (보안 노드 포함)
    workflow.add_node("collector", collector_node)
    workflow.add_node("guard", guard_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("sanitizer", sanitizer_node)
    
    # 엣지(흐름) 연결
    workflow.add_edge(START, "collector")
    workflow.add_edge("collector", "guard")
    workflow.add_edge("guard", "analyzer")
    workflow.add_edge("analyzer", "writer")
    workflow.add_edge("writer", "sanitizer")
    workflow.add_edge("sanitizer", END)
    
    # checkpointer가 없으면 기본 인메모리 세이버 사용 (CLI용)
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)
