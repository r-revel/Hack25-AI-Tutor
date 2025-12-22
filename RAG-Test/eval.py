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
from datasets import Dataset

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
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t\r')
    
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
    collection = client.get_collection('cloud_docs')
    
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
                data["question"] = clean_text_for_ragas(data["question"]).strip()
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
                question = line.replace("Вопрос:", "").replace("Question:", "").strip()
                # Берем следующие строки как ответ
                if i + 1 < len(lines):
                    answer = " ".join(lines[i+1:i+3])
                break
        
        if not question:
            question = lines[0] if lines else "Что описывает этот документ?"
        
        if not answer:
            answer = " ".join(lines[1:3]) if len(lines) > 1 else "Информация из документа"
        
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
            print(f"  Processing document {i+1}/{min(num_questions, len(documents))}")
            
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

# ---------- Основной процесс ----------
def main():
    print("=" * 60)
    print("RAG TEST SET GENERATION AND EVALUATION")
    print("=" * 60)
    
    # 1. Загрузка документов
    documents, chroma_client = load_and_clean_documents(limit=20)
    
    if not documents:
        print("ERROR: No documents loaded!")
        return
    
    print(f"\n✓ Loaded {len(documents)} clean documents")
    
    # 2. Генерация вопросов
    print("\n" + "=" * 60)
    print("GENERATING QUESTIONS")
    print("=" * 60)
    
    generator = CustomQuestionGenerator(llm, max_retries=2)
    questions_data = generator.generate_batch(documents, num_questions=10)
    
    print(f"\n✓ Generated {len(questions_data)} questions")
    
    # 3. Сохранение тестсета
    print("\n" + "=" * 60)
    print("SAVING TESTSET")
    print("=" * 60)
    
    df_questions = pd.DataFrame(questions_data)
    
    # Сохраняем подробную информацию
    df_questions.to_csv("generated_questions_detailed.csv", index=False, encoding='utf-8')
    
    # Сохраняем упрощенную версию для RAGAS
    df_simple = df_questions[["question", "ground_truth", "contexts"]].copy()
    df_simple.to_csv("generated_testset.csv", index=False, encoding='utf-8')
    
    print(f"✓ Saved detailed questions to: generated_questions_detailed.csv")
    print(f"✓ Saved testset to: generated_testset.csv")
    
    # 4. Подготовка для оценки RAGAS
    print("\n" + "=" * 60)
    print("PREPARING FOR RAGAS EVALUATION")
    print("=" * 60)
    
    # Получаем коллекцию Chroma
    collection = chroma_client.get_collection('cloud_docs')
    
    # Подготавливаем данные для оценки
    evaluation_data = []
    
    print("Generating answers for evaluation...")
    for i, row in df_simple.iterrows():
        print(f"  Processing question {i+1}/{len(df_simple)}")
        
        question = row["question"]
        
        # Получаем релевантные документы с правильным эмбеддингом
        retrieved = retrieve_docs_with_embeddings(
            question, 
            collection, 
            embeddings, 
            k=3
        )
        
        # Генерируем ответ на основе полученных документов
        context_for_answer = " ".join(retrieved["documents"]) if retrieved["documents"] else ""
        answer_result = answer_question(question, llm, context_for_answer)
        
        # Подготавливаем контексты
        contexts = retrieved["documents"] if retrieved["documents"] else row["contexts"]
        
        evaluation_data.append({
            "question": question,
            "answer": answer_result["answer"],
            "contexts": contexts[:3],
            "ground_truth": row["ground_truth"],
            "retrieval_success": len(retrieved["documents"]) > 0
        })
    
    # Создаем Dataset для RAGAS
    dataset = Dataset.from_list(evaluation_data)
    
    # Сохраняем dataset
    dataset.save_to_disk("ragas_evaluation_dataset")
    print(f"✓ Saved evaluation dataset")
    
    # 5. Оценка с помощью RAGAS
    print("\n" + "=" * 60)
    print("RUNNING RAGAS EVALUATION")
    print("=" * 60)
    
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            answer_correctness,
        )
        
        print("Starting evaluation...")
        
        result = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
                answer_correctness,
            ],
            llm=llm,
            embeddings=embeddings
        )
        
        # Сохраняем результаты
        result_df = result.to_pandas()
        result_df.to_csv("evaluation_results.csv", index=False, encoding='utf-8')
        
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        
        # Выводим сводку
        print(f"\nTotal questions evaluated: {len(result_df)}")
        
        # Средние значения метрик
        metrics_summary = {}
        for metric in ["faithfulness", "answer_relevancy", "context_precision", 
                      "context_recall", "answer_correctness"]:
            if metric in result_df.columns:
                avg_score = result_df[metric].mean()
                metrics_summary[metric] = avg_score
                print(f"{metric:20s}: {avg_score:.3f}")
        
        # Сохраняем сводку
        with open("evaluation_summary.txt", "w", encoding="utf-8") as f:
            f.write("RAGAS EVALUATION SUMMARY\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Total questions: {len(result_df)}\n\n")
            for metric, score in metrics_summary.items():
                f.write(f"{metric:20s}: {score:.3f}\n")
        
        print(f"\n✓ Results saved to: evaluation_results.csv")
        print(f"✓ Summary saved to: evaluation_summary.txt")
        
    except ImportError as e:
        print(f"RAGAS not available: {e}")
        print("Skipping evaluation...")
    except Exception as e:
        print(f"Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Вывод статистики
    print("\n" + "=" * 60)
    print("GENERATION STATISTICS")
    print("=" * 60)
    
    # Статистика по успешности генерации
    if "generation_success" in df_questions.columns:
        success_count = df_questions["generation_success"].sum()
        success_rate = (success_count / len(df_questions)) * 100
        print(f"\nGeneration success: {success_count}/{len(df_questions)} ({success_rate:.1f}%)")
    
    # Статистика по успешности поиска
    if evaluation_data:
        retrieval_success = sum(1 for item in evaluation_data if item.get("retrieval_success", False))
        print(f"Retrieval success: {retrieval_success}/{len(evaluation_data)} ({(retrieval_success/len(evaluation_data))*100:.1f}%)")
    
    # Длина вопросов
    avg_question_len = df_questions["question"].apply(len).mean()
    avg_answer_len = df_questions["ground_truth"].apply(len).mean()
    print(f"\nAverage question length: {avg_question_len:.0f} chars")
    print(f"Average answer length: {avg_answer_len:.0f} chars")
    
    # Примеры вопросов
    print("\nSample questions:")
    for i in range(min(3, len(df_questions))):
        question = df_questions.iloc[i]["question"]
        answer = df_questions.iloc[i]["ground_truth"]
        print(f"\n{i+1}. Q: {question[:80]}...")
        print(f"   A: {answer[:80]}...")
    
    print("\n" + "=" * 60)
    print("PROCESS COMPLETED!")
    print("=" * 60)

# ---------- Запуск ----------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()