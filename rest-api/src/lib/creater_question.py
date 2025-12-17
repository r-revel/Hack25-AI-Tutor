import json
from typing import List, Dict
from langchain_classic.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import re
from num2words import num2words

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
llm = Ollama(model="mistral")


def generate_questions_from_book(num_questions: int, book_json: Dict) -> List[Dict]:
    """
    Генерирует вопросы из книги в формате для записи в БД.
    """

    # Собираем весь текст книги
    all_content = []
    num_text = num2words(num_questions, lang='ru')

    for chapter in book_json.get("chapters", []):
        for subchapter in chapter.get("chapters", []):
            content = subchapter.get("content", "")
            clean_content = re.sub(
                r'--- Страница \d+.*?---', '', content, flags=re.DOTALL)
            if clean_content.strip():
                all_content.append(clean_content[:3000])

    context = "\n".join(all_content)

    # Усиленный промпт с требованием строгого формата
    prompt_template = PromptTemplate(
        template="""ТЫ ДОЛЖЕН ВЕРНУТЬ ТОЛЬКО JSON БЕЗ ЛЮБЫХ ДОПОЛНИТЕЛЬНЫХ ТЕКСТОВЫХ ПОЯСНЕНИЙ.

На основе следующего текста сгенерируй {num_text} не больше не меньше именно {num_text} тестовых вопросов на РУССКОМ ЯЗЫКЕ.
Тема книги: {topic}

Требования:
1. Все вопросы и варианты ответов должны быть на РУССКОМ ЯЗЫКЕ
2. Каждый вопрос имеет 4 варианта ответа (A, B, C, D)
3. Правильный ответ указывается одной буквой: A, B, C или D
4. Вопросы должны проверять понимание материала из текста

Текст для анализа:
{context}

ТЫ ДОЛЖЕН ВЕРНУТЬ ТОЛЬКО JSON В СЛЕДУЮЩЕМ ФОРМАТЕ:
[
  {{
    "question_text": "текст вопроса на русском",
    "option_a": "вариант A на русском",
    "option_b": "вариант B на русском", 
    "option_c": "вариант C на русском",
    "option_d": "вариант D на русском",
    "correct_answer": "A"
  }},
  ... еще вопросы ...
]

НЕ ДОБАВЛЯЙ НИКАКИХ ДОПОЛНИТЕЛЬНЫХ ТЕКСТОВ, КОММЕНТАРИЕВ ИЛИ РАЗМЕТКИ.""",
        input_variables=["num_text", "topic", "context"]
    )

    qa_chain = (
        {
            "num_text": RunnablePassthrough(),
            "topic": lambda _: book_json.get("title", ""),
            "context": lambda _: context
        }
        | prompt_template
        | llm
        | StrOutputParser()
    )

    # Генерируем вопросы
    response = qa_chain.invoke(num_text)

    # Усиленная очистка ответа
    try:
        # Удаляем все не-JSON части
        response = response.strip()

        # Ищем JSON массив
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # Если не нашли полный массив, ищем любые объекты
            json_match = re.findall(r'\{[^{}]*\}', response)
            if json_match:
                json_str = f"[{','.join(json_match)}]"
            else:
                return []

        # Парсим JSON
        questions = json.loads(json_str)

        # Проверяем и чистим каждый вопрос
        cleaned_questions = []
        for q in questions[:num_questions]:
            # Убеждаемся, что все поля строковые и на русском
            cleaned_q = {
                "question_text": str(q.get("question_text", "")).strip(),
                "option_a": str(q.get("option_a", "")).strip(),
                "option_b": str(q.get("option_b", "")).strip(),
                "option_c": str(q.get("option_c", "")).strip(),
                "option_d": str(q.get("option_d", "")).strip(),
                "correct_answer": str(q.get("correct_answer", "A")).strip().upper()
            }

            # Проверяем, что есть текст вопроса и варианты
            if cleaned_q["question_text"] and cleaned_q["option_a"]:
                cleaned_questions.append(cleaned_q)

        return cleaned_questions

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Ошибка парсинга JSON: {e}")
        print(f"Ответ модели: {response[:500]}")
        return []
