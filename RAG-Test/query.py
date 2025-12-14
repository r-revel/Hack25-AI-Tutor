import chromadb
from sentence_transformers import SentenceTransformer
import requests
import os


CHROMA_DIR = os.environ.get('CHROMA_DIR', './db')
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'mistral')


# init
client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_collection('cloud_docs')
emb_model = SentenceTransformer('intfloat/multilingual-e5-large')




def retrieve_docs(query: str, k: int = 4):
    emb = emb_model.encode(query).tolist()
    res = collection.query(query_embeddings=[emb], n_results=k)
    # res: dict with 'ids', 'documents', 'metadatas', 'distances'
    return res




def build_prompt(question: str, docs_res: dict) -> str:
    docs = docs_res.get('documents', [])
    metas = docs_res.get('metadatas', [])
    # собираем контекст (ограничиваем длину)
    ctx_parts = []
    src_parts = []
    for doc_list, meta_list in zip(docs, metas):
        for d, m in zip(doc_list, meta_list if isinstance(meta_list, list) else [meta_list]):
            ctx_parts.append(d)
            src_parts.append(f"- {m.get('title')} ({m.get('url')}), chunk {m.get('chunk_id')+1}/{m.get('total_chunks')}")


    context = '\n\n'.join(ctx_parts[:6]) # ограничение
    sources = '\n'.join(src_parts[:6])


    prompt = f"""
Ты — AI-репетитор по техническим дисциплинам. Отвечай подробно, шаг за шагом.
Используй ТОЛЬКО информацию из блока "Контекст". Ответ должен содержать все ключевые шаги.
Если информации недостаточно — честно скажи, что не уверен и предложи, где искать.
В конце обязательно добавь раздел "Источники" со ссылками.

---
Контекст:
{context}

Источники:
{sources}

Вопрос студента:
{question}
"""

    return prompt




def call_ollama(prompt: str, max_tokens: int = 1024):
    url = OLLAMA_HOST + '/api/generate'
    payload = {
        'model': OLLAMA_MODEL,
        'prompt': prompt,
        'max_tokens': max_tokens,
        'stream': False  # <<< КЛЮЧЕВО
    }

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()

    return data.get('response', '')





def answer_question(question: str):
    docs = retrieve_docs(question, k=4)
    prompt = build_prompt(question, docs)
    try:
        resp = call_ollama(prompt)
    except Exception as e:
        resp = f"LLM call failed: {e}. Prompt used:\n{prompt[:2000]}"
    return { 'answer': resp, 'sources': docs.get('metadatas', []) }