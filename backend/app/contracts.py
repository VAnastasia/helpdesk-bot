from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class Source(BaseModel):
    document: str
    section: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    fallback: bool
