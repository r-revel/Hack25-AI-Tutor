from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
import json
import uuid
from typing import Dict, Any, AsyncGenerator
from pydantic import BaseModel
import asyncio
from datetime import datetime

app = FastAPI(title="Ollama-compatible API")

# Модели данных
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: Dict[str, Any] = {}
    system: str = ""
    template: str = ""
    context: list = []

class ChatRequest(BaseModel):
    model: str
    messages: list
    stream: bool = False
    options: Dict[str, Any] = {}

# Хранилище для разных типов контента
RESPONSE_TEMPLATES = {
    "default": {
        "model": "my-custom-model",
        "created_at": "",
        "response": "Это стандартный ответ от модели",
        "done": True,
        "context": [],
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
        "prompt_eval_duration": 0,
        "eval_count": 0,
        "eval_duration": 0
    },
    "creative": {
        "model": "creative-model",
        "created_at": "",
        "response": "✨ Это креативный ответ с элементами творчества!",
        "done": True
    },
    "technical": {
        "model": "technical-model",
        "created_at": "",
        "response": "Технический ответ с точными данными и спецификациями.",
        "done": True
    },
    "simple": {
        "model": "simple-model",
        "response": "Простой и понятный ответ.",
        "done": True
    }
}

# Функция для определения типа запроса
def detect_request_type(request_data: Dict[str, Any]) -> str:
    """
    Определяет тип запроса на основе содержимого
    """
    prompt = request_data.get('prompt', '').lower()
    messages = request_data.get('messages', [])
    
    # Анализ промпта
    if any(word in prompt for word in ['креатив', 'творч', 'придумай', 'воображ']):
        return "creative"
    elif any(word in prompt for word in ['технич', 'код', 'алгоритм', 'архитектур']):
        return "technical"
    elif any(word in prompt for word in ['простой', 'объясни', 'понятно']):
        return "simple"
    
    # Анализ сообщений в чате
    for msg in messages:
        if isinstance(msg, dict) and 'content' in msg:
            content = msg['content'].lower()
            if any(word in content for word in ['креатив', 'творч']):
                return "creative"
            elif any(word in content for word in ['технич', 'код']):
                return "technical"
    
    return "default"

# Эндпоинт генерации (аналогичный Ollama /api/generate)
@app.post("/api/generate")
async def generate(request: GenerateRequest, http_request: Request):
    """
    Эндпоинт для генерации текста, совместимый с Ollama
    """
    request_type = detect_request_type(request.dict())
    template = RESPONSE_TEMPLATES.get(request_type, RESPONSE_TEMPLATES["default"])
    
    # Обновляем шаблон данными из запроса
    response_data = template.copy()
    response_data["model"] = request.model
    response_data["created_at"] = datetime.now().isoformat() + "Z"
    
    if request.stream:
        # Потоковый ответ
        async def stream_generator():
            full_response = response_data["response"]
            words = full_response.split()
            
            for i, word in enumerate(words):
                chunk = {
                    "model": request.model,
                    "created_at": datetime.now().isoformat() + "Z",
                    "response": word + " ",
                    "done": False
                }
                yield json.dumps(chunk) + "\n"
                await asyncio.sleep(0.1)  # Имитация задержки
            
            # Финальный чанк
            final_chunk = response_data.copy()
            final_chunk["done"] = True
            yield json.dumps(final_chunk) + "\n"
        
        return EventSourceResponse(stream_generator(), media_type="application/x-ndjson")
    else:
        # Непотоковый ответ
        return JSONResponse(content=response_data)

# Эндпоинт чата (аналогичный Ollama /api/chat)
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Эндпоинт для чата, совместимый с Ollama
    """
    request_data = request.dict()
    request_type = detect_request_type(request_data)
    template = RESPONSE_TEMPLATES.get(request_type, RESPONSE_TEMPLATES["default"])
    
    response_data = {
        "model": request.model,
        "created_at": datetime.now().isoformat() + "Z",
        "message": {
            "role": "assistant",
            "content": template["response"]
        },
        "done": True,
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
        "eval_count": 0
    }
    
    if request.stream:
        async def chat_stream_generator():
            content = template["response"]
            sentences = content.split('. ')
            
            for i, sentence in enumerate(sentences):
                if sentence:
                    chunk = {
                        "model": request.model,
                        "created_at": datetime.now().isoformat() + "Z",
                        "message": {
                            "role": "assistant",
                            "content": sentence + ('. ' if i < len(sentences)-1 else '.')
                        },
                        "done": False
                    }
                    yield json.dumps(chunk) + "\n"
                    await asyncio.sleep(0.15)
            
            final_chunk = {
                "model": request.model,
                "created_at": datetime.now().isoformat() + "Z",
                "message": {
                    "role": "assistant",
                    "content": ""
                },
                "done": True
            }
            yield json.dumps(final_chunk) + "\n"
        
        return EventSourceResponse(chat_stream_generator(), media_type="application/x-ndjson")
    else:
        return JSONResponse(content=response_data)

# Эндпоинт для списка моделей (Ollama /api/tags)
@app.get("/api/tags")
async def list_models():
    """
    Возвращает список доступных моделей
    """
    models = {
        "models": [
            {
                "name": "my-custom-model",
                "modified_at": datetime.now().isoformat() + "Z",
                "size": 1000000000,
                "digest": "sha256:abc123"
            },
            {
                "name": "creative-model",
                "modified_at": datetime.now().isoformat() + "Z",
                "size": 1200000000,
                "digest": "sha256:def456"
            },
            {
                "name": "technical-model",
                "modified_at": datetime.now().isoformat() + "Z",
                "size": 1500000000,
                "digest": "sha256:ghi789"
            }
        ]
    }
    return JSONResponse(content=models)

# Эндпоинт для проверки работы (Ollama /)
@app.get("/")
async def health_check():
    """
    Проверка здоровья сервера
    """
    return {
        "status": "ok",
        "message": "Ollama-compatible API is running",
        "version": "1.0.0"
    }

# Дополнительный эндпоинт для кастомной логики
@app.post("/api/custom")
async def custom_endpoint(request: Request):
    """
    Кастомный эндпоинт для дополнительной логики
    """
    data = await request.json()
    # Ваша кастомная логика здесь
    return JSONResponse(content={"custom": "response", "data": data})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)