from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from datetime import datetime
from database import Base


class User(Base):
    """Таблица для авторизации пользователей"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    progress = relationship(
        "UserProgress", back_populates="user", cascade="all, delete-orphan")
    test_sessions = relationship(
        "TestSession", back_populates="user", cascade="all, delete-orphan")


class Topic(Base):
    """Таблица доступных тем для обучения"""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    image: Mapped[str] = mapped_column(String(100), nullable=False)
    json: Mapped[str] = mapped_column(Text)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Relationships
    questions = relationship(
        "Question", back_populates="topic", cascade="all, delete-orphan")
    progress = relationship(
        "UserProgress", back_populates="topic", cascade="all, delete-orphan")
    test_sessions = relationship(
        "TestSession", back_populates="topic", cascade="all, delete-orphan")


class Question(Base):
    """Таблица вопросов для тестов"""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(255))
    option_b: Mapped[str] = mapped_column(String(255))
    option_c: Mapped[str] = mapped_column(String(255))
    option_d: Mapped[str] = mapped_column(String(255))
    correct_answer: Mapped[str] = mapped_column(String(1), nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="questions")
    test_answers = relationship(
        "TestAnswer", back_populates="question", cascade="all, delete-orphan")


class UserProgress(Base):
    """Таблица истории обучения пользователя по темам"""
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text)
    is_user: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="progress")
    topic = relationship("Topic", back_populates="progress")


class TestSession(Base):
    """Таблица сессий тестирования (4 вопроса по теме)"""
    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    total_score: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="test_sessions")
    topic = relationship("Topic", back_populates="test_sessions")
    answers = relationship(
        "TestAnswer", back_populates="test_session", cascade="all, delete-orphan")


class TestAnswer(Base):
    """Таблица ответов пользователя на вопросы теста"""
    __tablename__ = "test_answers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    test_session_id: Mapped[int] = mapped_column(
        ForeignKey("test_sessions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"), nullable=False)
    user_answer: Mapped[str] = mapped_column(String(1))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Relationships
    test_session = relationship("TestSession", back_populates="answers")
    question = relationship("Question", back_populates="test_answers")
