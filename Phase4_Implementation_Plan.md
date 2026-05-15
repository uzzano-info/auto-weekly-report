# Phase 4: FastAPI 서버 배포 및 자동화 스케줄링 구현 계획

본 문서는 **Auto-Weekly Report Swarm** 프로젝트의 마지막 단계인 **Phase 4(자동화 및 배포)**를 위한 상세 구현 계획서입니다. 2026년 최신 개발 표준(Serverless Cron + FastAPI Lifespan)을 반영하여 설계되었습니다.

---

## 1. 개요
*   **목표:** 매주 정해진 시간에 에이전트가 스스로 보고서를 생성하고, 이를 외부(Slack 등)로 공유하며 API를 통해 온디맨드(On-demand) 호출이 가능하도록 구축함.
*   **핵심 가치:** "보고를 위한 보고" 시간을 0으로 단축.

---

## 2. 아키텍처 (Hybrid Automation)

2026년 표준에 따라 두 가지 경로로 자동화를 실현합니다:

1.  **정기 실행 (Cron):** **GitHub Actions**를 활용하여 매주 금요일 오후 5시 자동 실행 (서버 비용 무료).
2.  **수시 실행 (API):** **FastAPI** 서버를 통해 필요할 때 언제든 API 호출로 보고서 생성.

---

## 3. 상세 단계별 계획

### **Step 1: LangServe 기반 API 서버 구축 (`api.py`)**
*   **기능:** 보고서 생성 로직을 외부에서 호출 가능한 엔드포인트로 노출.
*   **기술:** **LangServe** (FastAPI 기반), `APIKeyHeader` (보안).
*   **보안 (중요):** 엔드포인트가 외부에 노출되므로 과금 폭탄을 막기 위해 반드시 **API 인증(Auth) 미들웨어**를 적용해야 합니다.
*   **장점:** 직접 코딩할 필요 없이 스트리밍(Streaming), 상태 조회, 테스트용 웹 Playground UI가 자동 생성됨.

### **Step 1.5: 에이전트 영구 기억 장치 도입 (Checkpointer)**
*   **문제 해결:** 현재의 `MemorySaver()`는 서버 재시작 시 기억이 증발함.
*   **기술:** `SqliteSaver` (로컬/단순 배포용) 또는 `PostgresSaver` (프로덕션용) 도입.
*   **효과:** 매주 에이전트가 이전 주차의 보고서를 기억하고 맥락을 이어갈 수 있음.

### **Step 2: 정기 실행 자동화 (GitHub Actions)**
*   **설정:** `.github/workflows/weekly_report.yml` 작성.
*   **트리거:** `schedule: - cron: '0 8 * * 5'` (UTC 기준 금요일 17:00 KST).
*   **Git 로그 버그 방지 (중요):** GitHub Actions의 기본 체크아웃은 'Shallow Clone(최신 커밋 1개만 가져옴)' 방식입니다. 이를 그대로 쓰면 에이전트가 이번 주 Git 로그를 읽지 못하므로 반드시 `fetch-depth: 0` 옵션을 명시해야 합니다.
*   **결과물 보존 로직:** Actions 가상 환경에서 생성된 보고서(.md)가 증발하지 않도록, 완료 즉시 저장소의 `reports/` 폴더에 자동 Commit & Push 하는 단계 추가.

### **Step 3: 외부 채널 공유 (Slack/Email 연동)**
*   **도구 개발:** `tools.py` 내 `send_to_slack` 함수 추가.
*   **데이터:** 마크다운 보고서 요약본을 슬랙 채널에 업로드.
*   **효과:** 보고서 생성을 기다리지 않고 실시간 알림으로 결과 확인.

### **Step 4: 배포 및 운영 환경 설정**
*   **플랫폼:** Railway 또는 Render (상시 API 서버용).
*   **환경 변수:** 로컬 `.env` 설정값을 클라우드 환경 변수로 전이.

---

## 4. 기술 스택 (2026 Edition)
*   **Backend & API:** LangServe, FastAPI (Python 3.10+)
*   **Agentic Persistence:** LangGraph `SqliteSaver` 또는 `PostgresSaver` (상태 영구 보존)
*   **Scheduling:** GitHub Actions (Primary, Serverless)
*   **Notification:** Slack Webhook / MCP (Model Context Protocol)

---

## 5. 기대 효과
*   **완전 무인화:** 한 번 설정으로 매주 금요일 퇴근 전 보고서가 슬랙에 도착함.
*   **접근성 향상:** API를 통해 팀 내 다른 시스템과 연동 가능.
*   **비용 최적화:** GitHub Actions를 활용한 효율적인 리소스 관리.

---
**다음 단계:** "작업 시작해줘"라고 말씀하시면 **Step 1: FastAPI 서버 구축**부터 착수합니다.
