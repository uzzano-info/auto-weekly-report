import os
import subprocess
from langchain_core.tools import tool
from langchain_community.document_loaders import NotionDBLoader
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# [보안] 한국어 NLP 엔진 명시적 연결 설정 (Shift-Left DLP 용)
configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "ko", "model_name": "ko_core_news_lg"}]
}
provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()

# Analyzer 및 Anonymizer 초기화
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["ko"])
anonymizer = AnonymizerEngine()

# 한국어 주민번호(RRN) 커스텀 패턴 추가
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

@tool
def read_notion_database(integration_token: str, database_id: str) -> str:
    """Notion API를 통해 최근 7일간 수정된 업무 일지를 가져옵니다."""
    try:
        # 7일 전 날짜 계산
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Notion 필터 설정 (최근 7일 이내 수정된 항목)
        filter_obj = {
            "timestamp": "last_edited_time",
            "last_edited_time": {
                "on_or_after": seven_days_ago
            }
        }
        
        loader = NotionDBLoader(
            integration_token=integration_token,
            database_id=database_id,
            filter_object=filter_obj
        )
        
        docs = loader.load()
        return "\n\n".join([doc.page_content for doc in docs]) if docs else "최근 7일간 노션에 기록된 업무 일지가 없습니다."
    except Exception as e:
        return f"노션 데이터 가져오기 실패: {str(e)}"

class DailyNotesInput(BaseModel):
    folder_path: str = Field(default="./daily_notes", description="메모 파일이 저장된 폴더 경로")

    @field_validator("folder_path")
    def validate_path(cls, v):
        # [ASI02] 경로 탐색 공격(Path Traversal) 차단
        if ".." in v or v.startswith("/"):
            raise ValueError("허용되지 않은 경로 접근입니다 (보안 정책 위반).")
        return v

@tool("read_daily_notes", args_schema=DailyNotesInput)
def read_daily_notes(folder_path: str = "./daily_notes") -> str:
    """지정된 폴더에 있는 모든 일일 메모(.txt, .md) 파일의 내용을 읽어옵니다."""
    if not os.path.exists(folder_path):
        return "폴더가 존재하지 않습니다."
    
    all_notes = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt") or filename.endswith(".md"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                all_notes.append(f"--- {filename} ---\n{f.read()}")
    
    return "\n\n".join(all_notes) if all_notes else "이번 주 작성된 메모가 없습니다."

@tool
def get_git_logs(repo_path: str = ".") -> str:
    """지정된 로컬 Git 저장소에서 최근 7일간의 커밋 로그를 가져옵니다."""
    try:
        result = subprocess.run(
            ["git", "log", "--since=7.days", "--pretty=format:%s"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return "Git 저장소에 아직 커밋이 없거나 접근할 수 없습니다."
        return result.stdout if result.stdout else "최근 7일간 커밋 내역이 없습니다."
    except Exception as e:
        return f"Git 로그 추출 실패: {str(e)}"
