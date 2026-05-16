# Auto-Weekly Report Swarm
### 주간 보고서 자동 생성 AI 에이전트 시스템

**지원 포지션:** AI Agent Engineer  
**기술 스택:** Python · LangGraph · Gemini 3 Flash · Streamlit · Presidio · nh3  
**개발 기간:** 2026.05 (1인 개발)  
**배포:** [GitHub](https://github.com/uzzano-info/auto-weekly-report) · [Live Demo](https://auto-week-o4ffjlbsd7arcvstyqzpxh.streamlit.app/)

---

## 해결한 문제

매주 반복되는 주간 보고서 작성 업무를 자동화했습니다.  
로컬 메모, Git 커밋 로그, Notion 업무 일지를 AI가 수집하고, 카테고리별로 분류한 뒤, 보고용 마크다운 문서로 작성합니다.

---

## 시스템 구조

단일 LLM 호출의 불안정성을 해결하기 위해, **역할이 분리된 5개 노드가 순차 협업**하는 파이프라인을 설계했습니다.

```
[수집] → [보안 검증] → [분석·분류] → [보고서 작성] → [출력 정제] → 완료
```

| 노드 | 역할 | 사용 기술 |
|------|------|-----------|
| Collector | 로컬 메모 + Git + Notion에서 원시 데이터 수집 | LangChain Tools, Notion API |
| Guard | PII 마스킹 + 프롬프트 인젝션 탐지 | Presidio, spaCy(한국어) |
| Analyzer | 완료/진행 중/이슈로 카테고리 분류 | Gemini 3 Flash |
| Writer | 보고용 마크다운 문서 생성 | Gemini 3 Flash |
| Sanitizer | XSS 등 악성 코드 제거 후 안전한 출력 보장 | nh3 (Rust 기반) |

---

## 기술적 의사결정

**1. 결정론적 도구 호출**  
에이전트의 자율 탐색 대신, 지정된 경로와 API만 호출하도록 도구를 설계하여 환각(Hallucination)과 데이터 누락을 방지했습니다.

**2. OWASP ASI 기반 보안 아키텍처**  
수집 단계에서 주민번호·이메일·전화번호를 로컬에서 마스킹(Shift-Left DLP)하여, 민감 정보가 외부 LLM으로 전송되지 않도록 했습니다. Pydantic `field_validator`로 Path Traversal 공격도 차단합니다.

**3. 동적 Human-in-the-Loop**  
위험 패턴 감지 시 LangGraph `interrupt()` → `Command(resume=...)` 패턴으로 워크플로우를 중단하고, Streamlit UI에서 관리자 승인을 받은 후에만 재개되도록 구현했습니다.

---

## 해결한 기술 이슈

| 이슈 | 원인 | 해결 |
|------|------|------|
| Streamlit 새로고침 시 상태 유실 | 매 렌더링마다 MemorySaver 재생성 | `st.session_state`에 체크포인터 캐싱 |
| LLM 응답 파싱 에러 | Gemini SDK 업데이트로 응답 포맷 변경 | 타입 분기 처리하는 `get_text_content` 헬퍼 구현 |
| 환경 변수 로드 순서 충돌 | `import` 시점에 API Key 미로드 | `load_dotenv()` 선행 후 모듈 임포트 순서 제어 |

---

## 프로젝트 진행 현황

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | CLI + Streamlit 기본 파이프라인 | ✅ |
| 2 | MemorySaver 기반 대화형 피드백 루프 | ✅ |
| 3 | Notion API 연동 (외부 데이터 소스 확장) | ✅ |
| 4 | FastAPI 서버 + 스케줄러 자동 실행 | 🔜 |
| 5 | OWASP ASI 보안 레이어 (PII · XSS · HITL) | ✅ |
