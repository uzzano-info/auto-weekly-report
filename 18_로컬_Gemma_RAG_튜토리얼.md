# 🚀 로컬 환경에서 Gemma 설치 및 나만의 데이터로 RAG 구성하기 (초보자 가이드)

본 튜토리얼은 사용자님의 로컬 Mac 환경에 **Gemma** 모델을 설치하고, 사용자만의 개인 문서(텍스트, PDF 등)를 바탕으로 답변하는 **RAG(검색 증강 생성)** 시스템을 가장 쉽고 빠르게 구축하는 방법을 안내합니다.

---

## 🌟 개요: RAG란 무엇인가요?

**RAG(Retrieval-Augmented Generation)**는 쉽게 말해 AI에게 **"오픈북 시험"**을 보게 하는 기술입니다.
기본 모델(Gemma)은 학습된 과거 지식만 알고 있지만, RAG를 적용하면 여러분이 제공한 **사내 문서, 개인 메모, 특정 도서** 등을 실시간으로 읽고 참고하여 훨씬 정확하고 출처가 분명한 답변을 생성하게 됩니다.

---

## 🛠️ 1단계: 로컬 환경에 모델 설치하기 (Ollama 활용)

로컬에서 AI 모델을 구동하는 가장 쉽고 대중적인 도구는 **[Ollama](https://ollama.com/)** 입니다.

### 1. Ollama 설치
Mac 터미널을 열고 아래 명령어를 입력하거나, [공식 홈페이지](https://ollama.com)에서 다운로드하여 설치합니다.
```bash
# Homebrew를 사용한 설치
brew install ollama
```

### 2. Gemma 4 E2B 모델 다운로드 및 실행
Ollama를 통해 Gemma 4 E2B(Edge-to-Brain) 모델을 다운로드합니다.
```bash
# Gemma 4 E2B 모델 실행 (최초 실행 시 자동으로 다운로드 진행)
ollama run gemma4:e2b
```
> **Tip:** 다운로드가 완료되고 `>>>` 프롬프트가 뜨면 터미널에서 바로 대화를 나눌 수 있습니다. `/bye`를 입력하여 빠져나옵니다.

### 3. Ollama 서버 실행 확인
파이썬 코드에서 Ollama API를 호출하려면, Ollama가 **백그라운드 서버로 실행 중**이어야 합니다.
- Mac 앱으로 Ollama를 설치한 경우: **상단 메뉴바에 알파카 아이콘**이 보이면 이미 실행 중입니다.
- Homebrew로 설치한 경우: 별도 터미널 탭에서 아래 명령어를 실행해 두세요.
```bash
ollama serve
```

---

## 📚 2단계: 파이썬(Python) 환경 및 라이브러리 설정

RAG 파이프라인을 코드로 구성하기 위해 파이썬 환경을 설정합니다. (VS Code 터미널에서 진행)

### 1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate
```

### 2. 필수 라이브러리 설치
LangChain과 로컬 벡터 데이터베이스인 Chroma, 그리고 문서 처리에 필요한 라이브러리들을 설치합니다.
```bash
pip install langchain langchain-community langchain-ollama langchain-chroma chromadb langchain-text-splitters langchain-huggingface sentence-transformers pypdf
```

> **참고:** `langchain-chroma`는 LangChain↔Chroma 연결 인터페이스이고, `chromadb`가 실제 벡터 DB 엔진입니다. 둘 다 필요합니다.

---

## 🧠 3단계: 나만의 데이터 준비하기

프로젝트 폴더 안에 `data`라는 폴더를 만들고, AI가 읽었으면 하는 PDF 파일이나 텍스트(.txt) 파일을 넣습니다.
```bash
mkdir data
# 이후 data 폴더 안에 PDF 파일을 복사해 넣으세요
cp ~/Downloads/내문서.pdf ./data/
```
- 지원 형식 예시: `data/my_document.pdf`, `data/회의록.pdf`
- 여러 파일을 넣으면 한꺼번에 모두 로드됩니다.

---

## 📊 RAG 파이프라인 전체 흐름

아래는 이 튜토리얼에서 구축할 RAG 시스템의 전체 아키텍처입니다.

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  📄 내 문서  │───▶│  텍스트 분할  │───▶│ 임베딩 변환   │
│  (PDF/TXT)  │    │ (500자 단위)  │    │(ko-sroberta) │
└─────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  🤖 AI 답변  │◀───│ Gemma4:E2B   │◀───│  ChromaDB    │
│   (출력)     │    │ (LLM 생성)   │    │ (유사문서검색) │
└─────────────┘    └──────────────┘    └──────────────┘
```

**흐름 요약:** 내 문서 → 잘게 자르기 → 벡터로 변환 → DB 저장 → 질문 시 유사 문서 검색 → Gemma가 참고하여 답변 생성

---

## 💻 4단계: LangChain을 활용한 RAG 시스템 구축 (실전 코드)

프로젝트 폴더에 `local_rag.py` 파일을 생성하고 아래의 코드를 복사하여 붙여넣습니다.

```python
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

print("1. 문서를 로드하고 있습니다...")
# data 폴더 안의 PDF 파일들을 불러옵니다. (txt 파일인 경우 TextLoader 사용)
loader = DirectoryLoader('./data', glob="*.pdf", loader_cls=PyPDFLoader)
documents = loader.load()

print(f"로드된 문서 수: {len(documents)} 페이지")

print("2. 문서를 알맞은 크기로 자릅니다...")
# 모델이 한 번에 읽기 좋게 문서를 작은 조각(Chunk)으로 나눕니다.
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
splits = text_splitter.split_documents(documents)

print("3. 벡터 데이터베이스(Chroma)를 생성합니다...")
# 문서를 벡터(숫자)로 변환하는 임베딩 모델 (한국어 성능이 좋은 오픈소스 모델)
embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")

# 잘라낸 문서를 로컬 벡터 DB에 저장합니다.
vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)

# 검색기(Retriever) 설정: 질문과 가장 유사한 문서 3개를 찾도록 설정
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

print("4. 로컬 Gemma 모델과 프롬프트를 연결합니다...")
# Ollama에 설치된 Gemma 모델 호출
llm = ChatOllama(model="gemma4:e2b") 

# AI에게 지시할 프롬프트 템플릿 작성
template = """당신은 친절하고 정확한 AI 어시스턴트입니다.
반드시 아래 제공된 [Context] 정보만을 사용하여 사용자의 [Question]에 답변해주세요. 
만약 제공된 정보에 답이 없다면, "제공된 문서에서 해당 내용을 찾을 수 없습니다."라고 솔직하게 답변하세요.

[Context]: {context}

[Question]: {question}

답변:"""

prompt = ChatPromptTemplate.from_template(template)

# 문서의 내용을 하나로 합치는 헬퍼 함수
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# RAG 체인(Chain) 생성 (Retriever -> Prompt -> LLM -> Parser)
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

print("✅ RAG 시스템 준비 완료!\n")

# 5. 질문하기 (터미널 대화형)
while True:
    question = input("질문을 입력하세요 (종료하려면 'q' 입력): ")
    if question.lower() == 'q':
        break
    
    print("\n답변을 생성 중입니다...\n")
    # 체인 실행 및 답변 출력
    response = rag_chain.invoke(question)
    print("🤖 AI 답변:")
    print(response)
    print("-" * 50)
```

---

## 🎯 5단계: 실행 및 테스트

터미널에서 방금 만든 파이썬 코드를 실행합니다.

```bash
python local_rag.py
```

프로그램이 실행되면 콘솔에 **"질문을 입력하세요:"** 라는 문구가 뜹니다. `data` 폴더에 넣은 문서 내용과 관련된 질문을 던져보고, 로컬에서 구동되는 Gemma 모델이 내 데이터를 기반으로 똑똑하게 답변하는지 확인해 보세요!

---

## 💡 추가 팁: 코딩 없이 깔끔한 UI로 RAG 구축하고 싶다면?

파이썬 코드 작성 없이 ChatGPT와 같은 깔끔한 화면(Web UI)에서 내 문서를 업로드하고 대화하고 싶다면, 아래의 도구들을 강력하게 추천합니다.

1. **[AnythingLLM](https://useanything.com/)**: 가장 직관적이고 설정이 쉬운 데스크톱 앱입니다. Ollama와 클릭 몇 번으로 연동되며 자체적으로 문서 업로드 및 RAG 기능을 완벽하게 지원합니다.
2. **[Open WebUI](https://docs.openwebui.com/)**: Docker를 통해 설치하며, 실제 ChatGPT와 거의 동일한 UI를 제공합니다. 역시 Ollama와 완벽하게 연동되며, 파일 업로드 버튼 하나로 RAG가 작동합니다.

두 도구 모두 백엔드 언어모델로 **"Ollama (Gemma)"**를 연결하여 손쉽게 나만의 프라이빗한 로컬 AI 환경을 구축할 수 있습니다.
