# Phase 5: OWASP ASI 기반 에이전트 보안 레이어 적용 튜토리얼

본 튜토리얼은 `Phase5_Security_Plan.md`에 명시된 3-Layer 보안 아키텍처를 로컬 및 Streamlit 환경에 단계별로 구현하기 위한 실무 가이드입니다.

---

## 🛠 준비 단계: 보안 패키지 설치

보안 검증 및 PII 마스킹에 필요한 라이브러리와 한국어 NLP 모델을 설치합니다.

```bash
# 1. 필요 패키지 설치
pip install presidio-analyzer presidio-anonymizer spacy nh3 pydantic

# 2. 한국어 자연어 처리 모델 다운로드 (Presidio용)
python -m spacy download ko_core_news_lg
```

---

## Step 1: PII 마스킹 및 Input Guardrail (`guard_node`) 구현

외부 데이터(Notion, Git)가 메인 LLM으로 넘어가기 **전(Shift-Left)**에 PII를 마스킹하고 악성 프롬프트를 차단합니다.

### 1-1. `tools.py` 업데이트 (마스킹 도구 추가)
Microsoft Presidio와 한국어 정규식 패턴을 결합하여 데이터를 정제하는 함수를 만듭니다.

```python
# tools.py (추가)
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# [중요] 한국어 NLP 엔진 명시적 연결 설정
configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "ko", "model_name": "ko_core_news_lg"}]
}
provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()

# Analyzer에 커스텀 NLP 엔진 탑재
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["ko"])
anonymizer = AnonymizerEngine()

# 한국어 주민번호 커스텀 패턴 추가 예시
rrn_pattern = Pattern(name="rrn_pattern", regex=r"\b\d{6}[- ]?\d{7}\b", score=1.0)
rrn_recognizer = PatternRecognizer(supported_entity="KR_RRN", patterns=[rrn_pattern], supported_language="ko")
analyzer.registry.add_recognizer(rrn_recognizer)

def mask_sensitive_data(text: str) -> str:
    """텍스트 내의 PII를 [REDACTED]로 마스킹합니다."""
    # 최대 10,000자 제한 (DoS 방어)
    text = text[:10000] 
    
    results = analyzer.analyze(text=text, entities=["KR_RRN", "EMAIL_ADDRESS", "PHONE_NUMBER"], language="ko")
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized_result.text
```

### 1-2. `agents.py` 업데이트 (`guard_node` 추가)
`ReportState`를 수정하고, `collector`와 `analyzer` 사이에 노드를 삽입합니다.

```python
# agents.py (수정 및 추가)
class ReportState(TypedDict):
    # 기존 속성 유지...
    risk_score: int     # 보안 위험도 점수

# [안내] 이 guard_node는 Step 3-2에서 interrupt() 로직이 추가됩니다.
# 우선 기본 보안 로직만 먼저 구현합니다.
def guard_node(state: ReportState) -> ReportState:
    print("🛡️ [Guardrail] 데이터 보안 스캔 및 PII 마스킹 중...")
    raw_data = state["raw_data"]
    
    # 1. PII 마스킹 (Shift-Left)
    safe_data = tools.mask_sensitive_data(raw_data)
    
    # 2. 인젝션 탐지 (정규식 기반 1차 방어)
    risk_score = 0
    forbidden_words = ["ignore previous", "system prompt", "명령 무시"]
    if any(word in safe_data.lower() for word in forbidden_words):
        risk_score += 50
        print("⚠️ [경고] 프롬프트 인젝션 의심 패턴 감지!")
        
    return {"raw_data": safe_data, "risk_score": risk_score}
```

---

## Step 2: Output Sanitization (`sanitizer_node`) 구현

메인 LLM이 작성한 보고서를 Streamlit에 띄우기 전, XSS 공격을 방지합니다.

### 2-1. `agents.py` 업데이트 (`sanitizer_node` 추가)

```python
# agents.py (추가)
import nh3

def sanitizer_node(state: ReportState) -> ReportState:
    print("🧹 [Sanitizer] 마크다운 출력 정제 중 (XSS 방어)...")
    final_report = state["final_report"]
    
    # 허용할 기본 태그 지정 (스크립트 제외)
    allowed_tags = {"b", "i", "strong", "em", "h1", "h2", "h3", "p", "br", "ul", "ol", "li", "a", "code", "pre", "blockquote"}
    safe_report = nh3.clean(final_report, tags=allowed_tags)
    
    return {"final_report": safe_report}
```

---

## Step 3: 도구 검증 및 Dynamic HITL (Streamlit 연동) 설정

### 3-1. `tools.py` 업데이트 (Pydantic 도구 검증)
에이전트가 로컬 경로를 마음대로 탐색하지 못하도록 입력값을 검증합니다.

```python
# tools.py (기존 도구 수정)
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool

class DailyNotesInput(BaseModel):
    folder_path: str = Field(default="./daily_notes")

    @field_validator("folder_path")
    def validate_path(cls, v):
        # ".." 등 경로 탐색 공격 차단
        if ".." in v or v.startswith("/"):
            raise ValueError("허용되지 않은 경로 접근입니다 (Path Traversal 탐지).")
        return v

@tool("read_daily_notes", args_schema=DailyNotesInput)
def read_daily_notes(folder_path: str = "./daily_notes") -> str:
    # 기존 로직 유지...
    pass
```

### 3-2. `agents.py` 업데이트 (최신 `interrupt()` 함수 적용)

> **⚠️ 주의:** `NodeInterrupt`(예외 발생 방식)는 **Deprecated**되었습니다.
> 최신 LangGraph 표준은 `from langgraph.types import interrupt`를 사용하는 것입니다.

```python
# agents.py (최종 guard_node — Step 1-2의 코드를 아래로 교체합니다)
from langgraph.types import interrupt

def guard_node(state: ReportState) -> ReportState:
    print("🛡️ [Guardrail] 데이터 보안 스캔 및 PII 마스킹 중...")
    raw_data = state["raw_data"]
    
    # 1. PII 마스킹 (Shift-Left)
    safe_data = tools.mask_sensitive_data(raw_data)
    
    # 2. 인젝션 탐지 (정규식 기반 1차 방어)
    risk_score = 0
    forbidden_words = ["ignore previous", "system prompt", "명령 무시"]
    if any(word in safe_data.lower() for word in forbidden_words):
        risk_score += 50
        print("⚠️ [경고] 프롬프트 인젝션 의심 패턴 감지!")
    
    # 3. 동적 개입 (Dynamic HITL): 점수가 50 이상이면 그래프 실행을 일시 중지
    if risk_score >= 50:
        user_decision = interrupt(
            f"⚠️ 보안 경고: 프롬프트 인젝션 의심 (점수: {risk_score}). 승인하시겠습니까?"
        )
        if user_decision != "approve":
            return {"raw_data": "", "risk_score": risk_score}
        
    return {"raw_data": safe_data, "risk_score": risk_score}

# build_graph에 checkpointer 파라미터 추가 (app.py에서 주입받음)
def build_graph(checkpointer=None):
    workflow = StateGraph(ReportState)
    
    workflow.add_node("collector", collector_node)
    workflow.add_node("guard", guard_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("sanitizer", sanitizer_node)
    
    workflow.add_edge(START, "collector")
    workflow.add_edge("collector", "guard")
    workflow.add_edge("guard", "analyzer")
    workflow.add_edge("analyzer", "writer")
    workflow.add_edge("writer", "sanitizer")
    workflow.add_edge("sanitizer", END)
    
    # checkpointer가 없으면 기본 MemorySaver 사용
    if checkpointer is None:
        checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
```

### 3-3. `app.py` 업데이트 (Streamlit 메모리 유지 + 재개 로직)
`st.session_state`를 활용하여 LangGraph 체크포인터가 날아가지 않도록 보호하고, `interrupt` 후 사용자가 승인하면 `Command(resume=...)`로 재개합니다.

```python
# app.py (수정)
from langgraph.types import Command

# 체크포인터 캐싱 (화면 새로고침에도 상태 유지)
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()

graph = build_graph(checkpointer=st.session_state.memory)

# 보안 경고가 떴을 때 Streamlit UI에서 승인 버튼 표시
if st.session_state.get("needs_approval"):
    st.warning("⚠️ 보안 검토가 필요한 데이터가 감지되었습니다.")
    if st.button("✅ 승인 후 계속 진행"):
        # Command(resume=...)로 그래프를 재개
        result = graph.invoke(
            Command(resume="approve"),
            config={"configurable": {"thread_id": "user_123"}}
        )
        st.session_state.needs_approval = False
```

---

## 🎉 다음 단계
위 코드를 차례대로 적용하면 Phase 5의 엔터프라이즈급 보안 레이어 구축이 완료됩니다. 준비가 되셨다면 **"Step 1부터 적용해 줘"**라고 말씀해 주세요!
