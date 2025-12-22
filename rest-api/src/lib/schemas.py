from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List

# User schemas


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Topic schemas


class TopicBase(BaseModel):
    title: str
    image: str
    json_: str = Field(..., alias="json")


class TopicCreate(TopicBase):
    pass


class TopicResponse(TopicBase):
    id: int
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Question schemas


class QuestionBase(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str


class QuestionCreate(QuestionBase):
    topic_id: int


class QuestionResponse(QuestionBase):
    id: int
    topic_id: int

    class Config:
        from_attributes = True

# UserProgress schemas


class UserProgressBase(BaseModel):
    message: str
    is_user: bool


class UserProgressCreate(UserProgressBase):
    topic_id: int


class UserProgressResponse(UserProgressBase):
    id: int
    user_id: int
    topic_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Test schemas


class TestAnswerBase(BaseModel):
    question_id: int
    user_answer: str
    is_correct: Optional[bool] = None


class TestSessionCreate(BaseModel):
    topic_id: int


class TestSessionResponse(BaseModel):
    id: int
    user_id: int
    topic_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    total_score: int

    class Config:
        from_attributes = True


class TestSubmit(BaseModel):
    answers: List[TestAnswerBase]

# Auth schemas


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None

# Response schemas


class TestResultResponse(BaseModel):
    session: TestSessionResponse
    correct_answers: int
    total_questions: int
    percentage: float
