# tools.py
import os
import subprocess
from langchain_core.tools import tool

@tool
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
