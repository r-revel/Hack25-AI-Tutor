import os
import re
import json
import chromadb
import pandas as pd
from typing import List, Dict, Any
import torch
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings

device = 'cuda' if torch.cuda.is_available() else 'cpu'

# ---------- Настройка LLM ----------
llm = OllamaLLM(
    model="mistral",
    base_url="http://localhost:11434",
    temperature=0.1,
    top_p=0.95,
    num_predict=512,
)

# ---------- Модель эмбеддингов ----------
# Используем ту же модель, что использовалась при создании коллекции
embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",  # Размерность 1024
    model_kwargs={'device': device},
    encode_kwargs={'normalize_embeddings': False}
)

# ---------- Улучшенная очистка текста ----------


def clean_text_for_ragas(text: str) -> str:
    """Очистка текста для безопасного использования в JSON"""
    if not isinstance(text, str):
        return ""

    # Удаляем все управляющие символы
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', ' ', text)

    # Удаляем непечатаемые Unicode символы
    text = ''.join(char for char in text if char.isprintable()
                   or char in '\n\t\r')

    # Заменяем специфические пробелы
    text = text.replace('\xa0', ' ')
    text = text.replace('\u200b', '')
    text = text.replace('\ufeff', '')

    # Экранируем для JSON
    text = text.replace('\\', '\\\\')
    text = text.replace('"', "'")

    # Ограничиваем длину строк
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if len(line) > 1000:
            line = line[:1000] + "..."
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    return text.strip()

# ---------- Чтение документов из Chroma ----------


def load_and_clean_documents(limit: int = 30):
    """Загрузка и очистка документов из ChromaDB"""
    CHROMA_DIR = os.environ.get('CHROMA_DIR', './db')
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        collection = client.get_collection('cloud_docs')
    except chromadb.errors.NotFoundError:
        return None, None

    print("Loading documents from ChromaDB...")
    docs_res = collection.get(
        include=["documents", "metadatas"],
        limit=limit
    )

    documents = []
    for i, (text, meta) in enumerate(zip(docs_res.get("documents", []), docs_res.get("metadatas", []))):
        cleaned_text = clean_text_for_ragas(str(text))

        # Пропускаем слишком короткие документы
        if len(cleaned_text.split()) < 10:
            continue

        # Очищаем метаданные
        clean_meta = {}
        if isinstance(meta, dict):
            for key, value in meta.items():
                if isinstance(value, str):
                    clean_meta[key] = clean_text_for_ragas(value)
                else:
                    clean_meta[key] = value
        else:
            clean_meta = {"index": i}

        documents.append(Document(
            page_content=cleaned_text,
            metadata=clean_meta
        ))

    print(f"Loaded and cleaned {len(documents)} documents")
    return documents, client

# ---------- Кастомный генератор вопросов ----------


class CustomQuestionGenerator:
    """Кастомный генератор вопросов для обхода проблем RAGAS"""

    def __init__(self, llm, max_retries: int = 2):
        self.llm = llm
        self.max_retries = max_retries

    def generate_question_from_doc(self, doc_text: str, doc_id: int = 0) -> Dict[str, Any]:
        """Генерация одного вопроса из документа"""

        # Промпт с четкими инструкциями
        prompt = f"""На основе текста ниже создай один вопрос и ответ на него.

ТЕКСТ ДОКУМЕНТА:
{doc_text[:1500]}

ИНСТРУКЦИИ:
1. Вопрос должен проверять понимание ключевой информации из текста
2. Ответ должен быть точным и основанным только на тексте
3. Вопрос должен быть ясным и однозначным

ФОРМАТ ВЫВОДА (строго соблюдай этот JSON формат):
{{
    "question": "Твой вопрос здесь",
    "answer": "Точный ответ здесь"
}}

Сгенерируй только JSON, без дополнительного текста:"""

        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(prompt).strip()

                # Очистка ответа
                response = re.sub(r'```json\s*|\s*```', '', response)
                response = re.sub(r'^.*?\{', '{', response, flags=re.DOTALL)
                response = re.sub(r'\}.*?$', '}', response, flags=re.DOTALL)

                # Парсинг JSON
                data = json.loads(response)

                # Валидация полей
                required_fields = ["question", "answer"]
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing field: {field}")

                # Очистка значений
                data["question"] = clean_text_for_ragas(
                    data["question"]).strip()
                data["answer"] = clean_text_for_ragas(data["answer"]).strip()

                return {
                    "question": data["question"],
                    "ground_truth": data["answer"],
                    "context": doc_text[:1000],
                    "success": True
                }

            except json.JSONDecodeError as e:
                print(f"  Attempt {attempt + 1}: JSON decode error")
                if attempt == self.max_retries - 1:
                    return self.extract_qa_manually(response, doc_text)
            except Exception as e:
                print(f"  Attempt {attempt + 1}: Error - {str(e)[:50]}")
                if attempt == self.max_retries - 1:
                    return self.create_fallback_qa(doc_text)

        return self.create_fallback_qa(doc_text)

    def extract_qa_manually(self, response: str, doc_text: str) -> Dict[str, Any]:
        """Ручное извлечение вопроса и ответа из ответа LLM"""
        lines = [line.strip() for line in response.split('\n') if line.strip()]

        question = ""
        answer = ""

        # Ищем вопрос
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ["вопрос", "question", "?"]):
                question = line.replace("Вопрос:", "").replace(
                    "Question:", "").strip()
                # Берем следующие строки как ответ
                if i + 1 < len(lines):
                    answer = " ".join(lines[i+1:i+3])
                break

        if not question:
            question = lines[0] if lines else "Что описывает этот документ?"

        if not answer:
            answer = " ".join(lines[1:3]) if len(
                lines) > 1 else "Информация из документа"

        return {
            "question": clean_text_for_ragas(question),
            "ground_truth": clean_text_for_ragas(answer),
            "context": doc_text[:1000],
            "success": False,
            "note": "Manually extracted"
        }

    def create_fallback_qa(self, doc_text: str) -> Dict[str, Any]:
        """Создание резервного вопроса и ответа"""
        words = doc_text.split()[:20]
        topic = " ".join(words)

        return {
            "question": f"Что описывается в документе о '{topic}'?",
            "ground_truth": f"Документ содержит информацию о {topic}",
            "context": doc_text[:1000],
            "success": False,
            "note": "Fallback QA"
        }

    def generate_batch(self, documents: List[Document], num_questions: int = 10) -> List[Dict[str, Any]]:
        """Генерация батча вопросов"""
        questions = []

        print(f"Generating {num_questions} questions...")

        for i in range(min(num_questions, len(documents))):
            doc = documents[i]
            print(
                f"  Processing document {i+1}/{min(num_questions, len(documents))}")

            result = self.generate_question_from_doc(
                doc.page_content,
                doc_id=i
            )

            questions.append({
                "question": result["question"],
                "ground_truth": result["ground_truth"],
                "contexts": [doc.page_content[:2000]],
                "metadata": doc.metadata,
                "generation_success": result.get("success", False)
            })

        return questions


# ---------- Функции для RAG оценки ----------
def retrieve_docs_with_embeddings(question: str, collection, embeddings_model, k: int = 3) -> Dict[str, Any]:
    """Поиск релевантных документов с использованием эмбеддингов"""
    try:
        # Генерируем эмбеддинг для вопроса
        question_embedding = embeddings_model.embed_query(question)

        # Используем query с эмбеддингом
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else []
        }
    except Exception as e:
        print(f"  Error retrieving docs: {str(e)[:100]}")
        # Fallback: используем текстовый поиск
        try:
            results = collection.query(
                query_texts=[question],
                n_results=k,
                include=["documents", "metadatas", "distances"]
            )
            return {
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else []
            }
        except Exception as e2:
            print(f"  Text search also failed: {str(e2)[:100]}")
            return {"documents": [], "metadatas": [], "distances": []}


def answer_question(question: str, llm, context: str = "") -> Dict[str, Any]:
    """Генерация ответа на вопрос"""
    try:
        if context:
            prompt = f"""
Ты — AI-репетитор по техническим дисциплинам. Отвечай подробно, шаг за шагом.
Используй ТОЛЬКО информацию из блока "Контекст". Ответ должен содержать все ключевые шаги.
Если информации недостаточно — честно скажи.

---
Контекст:
{context}

Вопрос студента:
{question}
"""
        else:
            prompt = f"""Ответь на вопрос: {question}

Если не знаешь ответ, скажи "Не могу ответить на этот вопрос".

Ответ:"""

        response = llm.invoke(prompt)
        return {"answer": str(response).strip(), "success": True}
    except Exception as e:
        return {"answer": f"Ошибка генерации: {str(e)[:100]}", "success": False}


# ---------- Основная функция для RAG-ответов ----------
def get_rag_answer(question: str, collection, k=3) -> dict:
    """
    Полный цикл RAG: поиск + генерация ответа.
    """
    # 1. Поиск релевантных документов
    retrieved = retrieve_docs_with_embeddings(
        question,
        collection,
        embeddings,
        k=k
    )

    # 2. Подготовка контекста
    context = ""
    if retrieved["documents"]:
        context = " ".join(retrieved["documents"])

    # 3. Генерация ответа
    answer_result = answer_question(question, llm, context)

    # 4. Формирование полного ответа
    return {
        "answer": answer_result["answer"],
        "success": answer_result["success"],
        "contexts": retrieved["documents"],
        "sources": retrieved["metadatas"],
        "distances": retrieved["distances"]
    }
