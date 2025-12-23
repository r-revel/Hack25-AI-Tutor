# rest-api\src\crud.py
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
import random
from models import User, Topic, Question, UserProgress, TestSession, TestAnswer
from lib.schemas import UserCreate, TopicCreate, QuestionCreate, UserProgressCreate
from auth import get_password_hash

# User CRUD


def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

# Topic CRUD


def get_topics(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Topic).filter(Topic.is_available == True).offset(skip).limit(limit).all()


def get_topic(db: Session, topic_id: int):
    return db.query(Topic).filter(Topic.id == topic_id).first()


def get_topic_title(db: Session, title: str):
    return db.query(Topic).filter(Topic.title == title).first()


def create_topic(db: Session, topic: TopicCreate):
    db_topic = Topic(**topic.dict())
    db.add(db_topic)
    db.commit()
    db.refresh(db_topic)
    return db_topic

# Question CRUD


def get_questions_by_topic(db: Session, topic_id: int, limit: int = 4):
    questions = db.query(Question).filter(Question.topic_id == topic_id).all()
    if len(questions) > limit:
        return random.sample(questions, limit)
    return questions


def create_question(db: Session, question: QuestionCreate):
    db_question = Question(**question.dict())
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

# UserProgress CRUD


def get_user_progress(db: Session, user_id: int, topic_id: int):
    return db.query(UserProgress).filter(
        and_(UserProgress.user_id == user_id,
             UserProgress.topic_id == topic_id)
    ).order_by(UserProgress.created_at).all()


def create_user_progress(db: Session, progress: UserProgressCreate, user_id: int):
    db_progress = UserProgress(**progress.dict(), user_id=user_id)
    db.add(db_progress)
    db.commit()
    db.refresh(db_progress)
    return db_progress

# TestSession CRUD


def create_test_session(db: Session, topic_id: int, user_id: Optional[int] = None):
    """
    Создает тестовую сессию. Если user_id не указан, ставим 0.
    """
    if user_id is None:
        user_id = 0  # Заглушка для неавторизованного пользователя

    db_session = TestSession(topic_id=topic_id, user_id=user_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def get_test_session(db: Session, session_id: int, user_id: Optional[int] = None):
    """
    Получает тестовую сессию. Если user_id не указан, ищем по session_id только.
    """
    query = db.query(TestSession).filter(TestSession.id == session_id)
    if user_id is not None:
        query = query.filter(TestSession.user_id == user_id)
    return query.first()


def complete_test_session(db: Session, session_id: int, score: int):
    db_session = db.query(TestSession).filter(
        TestSession.id == session_id).first()
    if db_session:
        db_session.total_score = score
        db_session.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(db_session)
    return db_session
