# main.py
from dotenv import load_dotenv

# 환경 변수 로드 (.env)
load_dotenv()

from agents import build_graph
from datetime import datetime

def main():
    print("🚀 Auto-Weekly Report Swarm 시작!\n")
    
    # 1. 그래프 빌드
    graph = build_graph()
    
    # 오늘 날짜 추출
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 2. 초기 상태 및 설정
    initial_state = {"raw_data": "", "analyzed_data": "", "final_report": "", "messages": [], "risk_score": 0}
    config = {"configurable": {"thread_id": "cli_user_1"}}
    
    # 그래프 실행
    result = graph.invoke(initial_state, config=config)
    
    # 3. 결과물 저장
    report_content = result["final_report"]
    output_filename = f"Weekly_Report_{today_str}.md"
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n✅ 완료! 최종 보고서가 '{output_filename}' 파일로 저장되었습니다.")

if __name__ == "__main__":
    main()
