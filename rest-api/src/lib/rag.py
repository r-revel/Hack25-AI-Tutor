from langchain_community.llms import Ollama
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. Инициализация эмбеддингов через LangChain
embeddings = SentenceTransformerEmbeddings(
    model_name="intfloat/multilingual-e5-small"
)

# 2. Инициализация векторной базы через LangChain
vectorstore = Chroma(
    collection_name="docs",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

# 3. Инициализация LLM
llm = Ollama(model="llama3")

# 4. Создание ретривера (гибридный поиск можно добавить позже)
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# 5. Создание промпта как в вашем примере
prompt_template = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Ты репетитор. Отвечай на русском языке, используя предоставленный контекст.

Контекст:
{context}

Строгие правила:
1. Отвечай только на основе контекста
2. Будь педагогичным и развернутым
3. Если в контексте нет ответа - скажи об этом
4. Форматируй ответ с примерами<|eot_id|>

<|start_header_id|>user<|end_header_id|>
{question}<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["context", "question"]
)

# 6. Создание RAG цепи через LCEL (LangChain Expression Language)
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 7. Альтернативный вариант через RetrievalQA (более классический)
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    chain_type_kwargs={
        "prompt": prompt,
    },
    return_source_documents=True
)

# 8. Функция для ответа (вариант 1 - через LCEL)


def rag_answer(query: str) -> str:
    """Ответ на вопрос с использованием RAG"""
    try:
        response = rag_chain.invoke(query)
        return response
    except Exception as e:
        return f"Ошибка: {str(e)}"

# 9. Функция для ответа (вариант 2 - через RetrievalQA)


def rag_answer_with_sources(query: str):
    """Ответ на вопрос с источниками"""
    try:
        result = qa_chain.invoke({"query": query})
        return {
            "answer": result["result"],
            "sources": [doc.page_content for doc in result["source_documents"]]
        }
    except Exception as e:
        return {"error": str(e)}


# 10. Тестирование
if __name__ == "__main__":
    # Вариант 1
    print("=== Вариант 1 (LCEL) ===")
    answer = rag_answer("Что такое теорема Пифагора?")
    print(answer)

    print("\n=== Вариант 2 (с источниками) ===")
    result = rag_answer_with_sources("Что такое теорема Пифагора?")
    if "answer" in result:
        print("Ответ:", result["answer"])
        print("\nИсточники:")
        for i, source in enumerate(result["sources"], 1):
            print(f"{i}. {source[:100]}...")
    else:
        print("Ошибка:", result["error"])


# Установка зависимостей
# pip install langchain langchain-community chromadb sentence-transformers ollama
