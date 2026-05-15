from typing import TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
import tools

# 1. 상태(State) 정의: 에이전트들이 서로 주고받을 데이터 구조
class ReportState(TypedDict):
    messages: Annotated[list, add_messages] # 대화 내역 누적용
    raw_data: str       # 수집된 원본 텍스트 (메모 + Git)
    analyzed_data: str  # 카테고리별로 분류/분석된 텍스트
    final_report: str   # 최종 완성된 마크다운 보고서

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
    print("🕵️ [Collector] 일일 메모와 Git 로그를 수집합니다...")
    notes = tools.read_daily_notes.invoke({"folder_path": "./daily_notes"})
    git_logs = tools.get_git_logs.invoke({"repo_path": "."})
    
    combined_data = f"### 일일 메모 ###\n{notes}\n\n### Git 커밋 로그 ###\n{git_logs}"
    return {"raw_data": combined_data}

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

# 5. 그래프(워크플로우) 조립
def build_graph():
    workflow = StateGraph(ReportState)
    
    # 노드 추가
    workflow.add_node("collector", collector_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("writer", writer_node)
    
    # 엣지(흐름) 연결
    workflow.add_edge(START, "collector")
    workflow.add_edge("collector", "analyzer")
    workflow.add_edge("analyzer", "writer")
    workflow.add_edge("writer", END)
    
    # 메모리 객체 생성
    memory = MemorySaver()
    
    # 컴파일 시 checkpointer 전달
    return workflow.compile(checkpointer=memory)
