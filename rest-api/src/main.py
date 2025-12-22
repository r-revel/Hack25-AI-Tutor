from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List
import crud
import lib.schemas as schemas
from lib.install import InstallSystem
from lib.swear_detector import RussianSwearDetector
from lib.seed_topics import seed_topics_from_jsonl
import auth
import models
from database import engine, get_db, create_db_and_tables
from auth import authenticate_user, create_access_token, get_current_active_user
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
import json
from typing import Dict, Any, AsyncGenerator
from pydantic import BaseModel
import asyncio
from datetime import datetime
from fastapi import BackgroundTasks


# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Tutor API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    from database import SessionLocal

    db = SessionLocal()
    try:
        seed_topics_from_jsonl(
            db,
            "/app/Notebooks/cloud_ru_docs.jsonl"
        )
    finally:
        db.close()


@app.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400, detail="Username already registered")
    db_email = crud.get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.post("/login", response_model=schemas.Token)
def login(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/install", response_model=str)
def install_model(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Создаем систему установки с списком моделей
    models_to_install = ["mistral", "intfloat/multilingual-e5-large"]
    installer = InstallSystem(models_to_install)

    # Устанавливаем модели
    results = installer.install()
    return f"Результаты установки: {results}"


@app.get("/topics", response_model=List[schemas.TopicResponse])
def get_topics(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    topics = crud.get_topics(db, skip=skip, limit=limit)
    return topics


@app.get("/topics/{topic_id}", response_model=schemas.TopicResponse)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = crud.get_topic(db, topic_id=topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@app.get("/topics/{topic_id}/progress", response_model=List[schemas.UserProgressResponse])
def get_progress(
    topic_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    progress = crud.get_user_progress(
        db, user_id=current_user.id, topic_id=topic_id)
    return progress


@app.post("/topics/{topic_id}/progress", response_model=List[schemas.UserProgressResponse])
def add_progress_message(
    topic_id: int,
    progress: schemas.UserProgressCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify topic exists
    topic = crud.get_topic(db, topic_id=topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    detector = RussianSwearDetector(model_name='mistral')

    result = detector.check(progress.message)

    if result['has_swear'] == True:
        progress.message = '************'
        crud.create_user_progress(
            db=db,
            progress=progress,
            user_id=current_user.id
        )
        crud.create_user_progress(
            db=db,
            progress=schemas.UserProgressCreate(
                topic_id=topic_id,
                is_user=False,
                message='Недопустимо использования ненормативной лексики'
            ),
            user_id=current_user.id
        )
    else:
        crud.create_user_progress(
            db=db,
            progress=progress,
            user_id=current_user.id
        )
        crud.create_user_progress(
            db=db,
            progress=schemas.UserProgressCreate(
                topic_id=topic_id,
                is_user=False,
                message='Системное сообщения'
            ),
            user_id=current_user.id
        )

    progress_list = crud.get_user_progress(
        db, user_id=current_user.id, topic_id=topic_id)
    return progress_list


@app.post("/topics/{topic_id}/start-test", response_model=schemas.TestSessionResponse)
def start_test(topic_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from lib.creater_question import generate_questions_from_book

    topic = crud.get_topic(db, topic_id=topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    questions = crud.get_questions_by_topic(db, topic_id=topic_id)
    missing = 4 - len(questions)

    def generate_missing_questions(topic_json, topic_id, missing):
        try:
            generated = generate_questions_from_book(missing, json.loads(topic_json))
            for q in generated:
                crud.create_question(db, schemas.QuestionCreate(
                    topic_id=topic_id,
                    question_text=q["question_text"],
                    option_a=q["option_a"],
                    option_b=q["option_b"],
                    option_c=q["option_c"],
                    option_d=q["option_d"],
                    correct_answer=q["correct_answer"]
                ))
            print(f"✅ Сгенерированы {missing} вопросов для топика {topic_id}")
        except Exception as e:
            print(f"⚠️ Ошибка генерации вопросов для топика {topic_id}: {e}")

    if missing > 0:
        # Генерация в фоне
        background_tasks.add_task(generate_missing_questions, topic.json, topic.id, missing)

    # Создаём тестовую сессию сразу, даже если вопросов пока <4
    test_session = crud.create_test_session(db, topic_id=topic_id, user_id=0)
    return test_session




@app.get("/test/{session_id}/questions", response_model=List[schemas.QuestionResponse])
def get_test_questions(
    session_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify session belongs to user
    test_session = crud.get_test_session(
        db, session_id=session_id, user_id=current_user.id)
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    if test_session.completed_at:
        raise HTTPException(status_code=400, detail="Test already completed")

    # Get 4 random questions for the topic
    questions = crud.get_questions_by_topic(
        db, topic_id=test_session.topic_id, limit=4)
    return questions


@app.post("/test/{session_id}/submit", response_model=schemas.TestResultResponse)
def submit_test(
    session_id: int,
    test_submit: schemas.TestSubmit,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify session belongs to user
    test_session = crud.get_test_session(
        db, session_id=session_id, user_id=current_user.id)
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    if test_session.completed_at:
        raise HTTPException(status_code=400, detail="Test already completed")

    # Get questions for this topic
    questions = crud.get_questions_by_topic(
        db, topic_id=test_session.topic_id, limit=4)
    question_dict = {q.id: q for q in questions}

    # Check answers and calculate score
    correct_count = 0
    test_answers = []

    for answer in test_submit.answers:
        question = question_dict.get(answer.question_id)
        if not question:
            continue

        is_correct = (answer.user_answer.upper() ==
                      question.correct_answer.upper())
        if is_correct:
            correct_count += 1

        test_answer = schemas.TestAnswerBase(
            question_id=answer.question_id,
            user_answer=answer.user_answer,
            is_correct=is_correct
        )
        test_answers.append(test_answer)

    # Update test session
    test_session = crud.complete_test_session(
        db, session_id=session_id, score=correct_count)

    # Create test answers records
    for answer in test_answers:
        db_answer = models.TestAnswer(
            test_session_id=session_id,
            question_id=answer.question_id,
            user_answer=answer.user_answer,
            is_correct=answer.is_correct
        )
        db.add(db_answer)

    db.commit()

    # Prepare response
    percentage = (correct_count / 4) * 100 if questions else 0

    return schemas.TestResultResponse(
        session=test_session,
        correct_answers=correct_count,
        total_questions=4,
        percentage=percentage
    )


@app.get("/test/history", response_model=List[schemas.TestSessionResponse])
def get_test_history(
    skip: int = 0,
    limit: int = 20,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    tests = db.query(models.TestSession).filter(
        models.TestSession.user_id == current_user.id
    ).order_by(models.TestSession.started_at.desc()).offset(skip).limit(limit).all()
    return tests


@app.get("/admin/generated/questions", response_model=str)
def get_generated_questions(
    topic_id: int,
    db: Session = Depends(get_db)
):
    topic = crud.get_topic(db, topic_id=topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Пытаемся импортировать генератор только когда реально нужен
    try:
        from lib.creater_question import generate_questions_from_book
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Генерация вопросов сейчас недоступна: {e}"
        )

    generated_data = generate_questions_from_book(4, json.loads(topic.json))

    for question_item in generated_data:
        question_create = schemas.QuestionCreate(
            question_text=question_item["question_text"],
            option_a=question_item["option_a"],
            option_b=question_item["option_b"],
            option_c=question_item["option_c"],
            option_d=question_item["option_d"],
            correct_answer=question_item["correct_answer"],
            topic_id=topic_id
        )
        crud.create_question(db=db, question=question_create)

    return "success"


@app.post("/admin/topics", response_model=schemas.TopicResponse)
def create_topic_admin(
    topic: schemas.TopicCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # In production, add admin check here
    return crud.create_topic(db=db, topic=topic)


@app.post("/admin/questions", response_model=schemas.QuestionResponse)
def create_question_admin(
    question: schemas.QuestionCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify topic exists
    topic = crud.get_topic(db, topic_id=question.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return crud.create_question(db=db, question=question)


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Tutor API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


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
    template = RESPONSE_TEMPLATES.get(
        request_type, RESPONSE_TEMPLATES["default"])

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
    template = RESPONSE_TEMPLATES.get(
        request_type, RESPONSE_TEMPLATES["default"])

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


@app.get("/api/db")
async def cteated_db(request: Request):
    create_db_and_tables()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
